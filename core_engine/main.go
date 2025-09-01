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
	"strings"
	"sync"
	"time"

	"golang.org/x/net/proxy"
)

type TestConfig struct {
	Tag      string          `json:"tag"`
	Config   json.RawMessage `json:"config"`
	TestPort int             `json:"test_port"`
	XrayPath string          `json:"xray_path"`
	FragmentConfig json.RawMessage `json:"fragment_config,omitempty"`
}

type TestResult struct {
	Tag    string `json:"tag"`
	Ping   int64  `json:"ping_ms"`
	Status string `json:"status"`
}

func main() {
	inputData, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}

	var configs []TestConfig
	if err := json.Unmarshal(inputData, &configs); err != nil {
		os.Exit(1)
	}

	results := make(chan TestResult, len(configs))
	var wg sync.WaitGroup

	for _, conf := range configs {
		wg.Add(1)
		go func(c TestConfig) {
			defer wg.Done()

			tmpFile, err := os.CreateTemp("", "xray-test-*.json")
			if err != nil {
				results <- TestResult{Tag: c.Tag, Ping: -1, Status: "tempfile_error"}
				return
			}
			defer os.Remove(tmpFile.Name())


			outbounds := []json.RawMessage{c.Config}

			if len(c.FragmentConfig) > 0 && string(c.FragmentConfig) != "null" {
				fragmentOutbound := map[string]interface{}{
					"protocol": "freedom",
					"tag":      "fragment",
					"settings": map[string]json.RawMessage{
						"fragment": c.FragmentConfig,
					},
				}
				fragmentBytes, _ := json.Marshal(fragmentOutbound)
				outbounds = append(outbounds, json.RawMessage(fragmentBytes))
			}

			fullConfig := map[string]interface{}{
				"log":       map[string]string{"loglevel": "warning"}, // Use "warning" to reduce noise
				"inbounds":  []map[string]interface{}{{"protocol": "socks", "port": c.TestPort, "listen": "127.0.0.1", "settings": map[string]interface{}{"auth": "noauth", "udp": true}}},
				"outbounds": outbounds,
			}

			configBytes, _ := json.Marshal(fullConfig)
			tmpFile.Write(configBytes)
			tmpFile.Close()

			ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()

			cmd := exec.CommandContext(ctx, c.XrayPath, "-c", tmpFile.Name())

			var xrayOutput bytes.Buffer
			cmd.Stdout = &xrayOutput
			cmd.Stderr = &xrayOutput

			if err := cmd.Start(); err != nil {
				results <- TestResult{Tag: c.Tag, Ping: -1, Status: "xray_start_failed"}
				return
			}

			time.Sleep(800 * time.Millisecond)

			ping, status := testProxy(c.TestPort)

			if status != "success" {
				logStr := string(xrayOutput.Bytes())
				logStr = strings.ReplaceAll(logStr, "\n", " ")
				logStr = strings.ReplaceAll(logStr, "\r", "")
				if len(logStr) > 250 {
					logStr = logStr[:250]
				}
				status = fmt.Sprintf("%s | xray_log: %s", status, logStr)
			}

			cmd.Process.Kill()
			cmd.Wait()

			results <- TestResult{Tag: c.Tag, Ping: ping, Status: status}
		}(conf)
	}

	wg.Wait()
	close(results)

	finalResults := make([]TestResult, 0, len(configs))
	for res := range results {
		finalResults = append(finalResults, res)
	}

	outputData, _ := json.Marshal(finalResults)
	fmt.Println(string(outputData))
}

func testProxy(port int) (int64, string) {
	targetURL := "http://www.google.com/generate_204"
	timeout := 8 * time.Second

	dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("127.0.0.1:%d", port), nil, proxy.Direct)
	if err != nil {
		return -1, fmt.Sprintf("failed_dialer: %v", err)
	}

	httpTransport := &http.Transport{}
	httpClient := &http.Client{Transport: httpTransport, Timeout: timeout}
	httpTransport.DialContext = func(ctx context.Context, network, addr string) (net.Conn, error) {
		return dialer.Dial(network, addr)
	}

	start := time.Now()
	resp, err := httpClient.Get(targetURL)
	if err != nil {
		return -1, fmt.Sprintf("failed_http: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNoContent {
		return -1, fmt.Sprintf("bad_status_%d", resp.StatusCode)
	}

	latency := time.Since(start).Milliseconds()
	return latency, "success"
}