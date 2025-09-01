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

type TestJob struct {
	Tag            string          `json:"tag"`
	Protocol       string          `json:"protocol"`
	Config         json.RawMessage `json:"config,omitempty"`
	ConfigURI      string          `json:"config_uri,omitempty"`
	ListenIP       string          `json:"listen_ip"`
	TestPort       int             `json:"test_port"`
	ClientPath     string          `json:"client_path,omitempty"`
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
	var jobs []TestJob
	if err := json.Unmarshal(inputData, &jobs); err != nil { os.Exit(1) }

	results := make(chan TestResult, len(jobs))
	var wg sync.WaitGroup

	for _, job := range jobs {
		wg.Add(1)
		go func(j TestJob) {
			defer wg.Done()

			if j.ClientPath != "" {
				runIndividualTest(j, results)
			} else {
				ping, status := testProxy(j.ListenIP, j.TestPort)
				results <- TestResult{Tag: j.Tag, Ping: ping, Status: status}
			}
		}(job)
	}

	wg.Wait()
	close(results)

	finalResults := make([]TestResult, 0, len(jobs))
	for res := range results { finalResults = append(finalResults, res) }
	outputData, _ := json.Marshal(finalResults)
	fmt.Println(string(outputData))
}

func runIndividualTest(j TestJob, results chan<- TestResult) {
	var cmd *exec.Cmd
	configFile, err := os.CreateTemp("", "client-test-*.json")
	if err != nil { results <- TestResult{Tag: j.Tag, Ping: -1, Status: "tempfile_error"}; return }
	defer os.Remove(configFile.Name())

	if j.Protocol == "hysteria2" {
		// Simplified Hysteria config creation
		uriParts := strings.Split(strings.Split(j.ConfigURI, "://")[1], "@")
		serverParts := strings.Split(uriParts[1], "?")[0]
		sni := strings.Split(strings.Split(j.ConfigURI, "sni=")[1], "#")[0]
		config := map[string]interface{}{
			"server":   serverParts, "auth": uriParts[0],
			"socks5":   map[string]string{"listen": fmt.Sprintf("%s:%d", j.ListenIP, j.TestPort)},
			"tls":      map[string]interface{}{"sni": sni, "insecure": true},
		}
		configBytes, _ := json.Marshal(config)
		configFile.Write(configBytes)
		configFile.Close()
		cmd = exec.Command(j.ClientPath, "client", "-c", configFile.Name())
	} else {
		// Logic for other individual clients can be added here
		results <- TestResult{Tag: j.Tag, Ping: -1, Status: "unsupported_individual_client"}; return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if runtime.GOOS == "windows" { setHideWindow(cmd) }

	var clientOutput bytes.Buffer
	cmd.Stdout, cmd.Stderr = &clientOutput, &clientOutput

	if err := cmd.Start(); err != nil { results <- TestResult{Tag: j.Tag, Ping: -1, Status: "client_start_failed"}; return }
	time.Sleep(1200 * time.Millisecond) // Hysteria might take longer to start

	ping, status := testProxy(j.ListenIP, j.TestPort)
	if status != "success" {
		logStr := strings.ReplaceAll(string(clientOutput.Bytes()), "\n", " ")
		status = fmt.Sprintf("%s | log: %s", status, logStr[:200])
	}

	cmd.Process.Kill()
	cmd.Wait()
	results <- TestResult{Tag: j.Tag, Ping: ping, Status: status}
}

func testProxy(listenIP string, port int) (int64, string) {
	targetURL := "http://www.google.com/generate_204"
	timeout := 8 * time.Second
	dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("%s:%d", listenIP, port), nil, proxy.Direct)
	if err != nil { return -1, fmt.Sprintf("failed_dialer: %v", err) }

	httpClient := &http.Client{
		Transport: &http.Transport{
			DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
				return dialer.Dial(network, addr)
			},
		},
		Timeout: timeout,
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

	return time.Since(start).Milliseconds(), "success"
}