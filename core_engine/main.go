package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/proxy"
)

type TestConfig struct {
	Tag            string          `json:"tag"`
	Protocol       string          `json:"protocol"`
	Config         json.RawMessage `json:"config"`
	ListenIP       string          `json:"listen_ip"`
	TestPort       int             `json:"test_port"`
	ClientPath     string          `json:"client_path"`
	FragmentConfig json.RawMessage `json:"fragment_config,omitempty"`
}

type TestResult struct {
	Tag    string `json:"tag"`
	Ping   int64  `json:"ping_ms"`
	Status string `json:"status"`
}

func main() {
	inputData, err := io.ReadAll(os.Stdin)
	if err != nil { os.Exit(1) }
	var configs []TestConfig
	if err := json.Unmarshal(inputData, &configs); err != nil { os.Exit(1) }

	results := make(chan TestResult, len(configs))
	var wg sync.WaitGroup

	for _, conf := range configs {
		wg.Add(1)
		go func(c TestConfig) {
			defer wg.Done()

			var cmd *exec.Cmd
			var configFile *os.File

			ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()

			if c.Protocol == "hysteria" || c.Protocol == "hysteria2" {
				configFile, err = os.CreateTemp("", "hysteria-*.json")
				if err != nil { results <- TestResult{Tag: c.Tag, Ping: -1, Status: "tempfile_error"}; return }
				defer os.Remove(configFile.Name())
				configFile.Write(c.Config)
				configFile.Close()
				cmd = exec.CommandContext(ctx, c.ClientPath, "client", "-c", configFile.Name())

			} else {
				configFile, err = os.CreateTemp("", "xray-*.json")
				if err != nil { results <- TestResult{Tag: c.Tag, Ping: -1, Status: "tempfile_error"}; return }
				defer os.Remove(configFile.Name())

				outbounds := []json.RawMessage{c.Config}
				if len(c.FragmentConfig) > 0 && string(c.FragmentConfig) != "null" {
					fragmentOutbound := map[string]interface{}{ "protocol": "freedom", "tag": "fragment", "settings": map[string]json.RawMessage{"fragment": c.FragmentConfig}}
					fragmentBytes, _ := json.Marshal(fragmentOutbound)
					outbounds = append(outbounds, json.RawMessage(fragmentBytes))
				}

				fullConfig := map[string]interface{}{
					"log":       map[string]string{"loglevel": "warning"},
					"inbounds":  []map[string]interface{}{{"protocol": "socks", "port": c.TestPort, "listen": c.ListenIP, "settings": map[string]interface{}{"auth": "noauth", "udp": true}}},
					"outbounds": outbounds,
				}
				configBytes, _ := json.Marshal(fullConfig)
				configFile.Write(configBytes)
				configFile.Close()

				cmd = exec.CommandContext(ctx, c.ClientPath, "-c", configFile.Name())
			}


			if runtime.GOOS == "windows" {
				setHideWindow(cmd)
			}

			var clientOutput bytes.Buffer
			cmd.Stdout = &clientOutput
			cmd.Stderr = &clientOutput

			if err := cmd.Start(); err != nil {
				results <- TestResult{Tag: c.Tag, Ping: -1, Status: "client_start_failed"}; return
			}

			time.Sleep(900 * time.Millisecond)
			ping, status := testProxy(c.TestPort)

			if status != "success" {
				logStr := strings.ReplaceAll(string(clientOutput.Bytes()), "\n", " ")
				if len(logStr) > 200 { logStr = logStr[:200] }
				status = fmt.Sprintf("%s | log: %s", status, logStr)
			}

			cmd.Process.Kill()
			cmd.Wait()

			results <- TestResult{Tag: c.Tag, Ping: ping, Status: status}
		}(conf)
	}

	wg.Wait()
	close(results)

	finalResults := make([]TestResult, 0, len(configs))
	for res := range results { finalResults = append(finalResults, res) }
	outputData, _ := json.Marshal(finalResults)
	fmt.Println(string(outputData))
}

func testProxy(port int) (int64, string) {
	targetURL := "http://www.google.com/generate_204"
	timeout := 8 * time.Second
	dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("%s:%d", listenIP, port), nil, proxy.Direct)
	if err != nil { return -1, fmt.Sprintf("failed_dialer: %v", err) }
	httpClient := &http.Client{ Transport: &http.Transport{DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) { return dialer.Dial(network, addr) }}, Timeout: timeout}
	start := time.Now()
	resp, err := httpClient.Get(targetURL)
	if err != nil { return -1, fmt.Sprintf("failed_http: %v", err) }
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNoContent { return -1, fmt.Sprintf("bad_status_%d", resp.StatusCode) }
	return time.Since(start).Milliseconds(), "success"
}