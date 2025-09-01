// core_engine/main.go

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"sync"
	"time"
	"os/exec"
	"golang.org/x/net/proxy"
)

// note: This struct defines the input format we expect from Python.
type TestConfig struct {
	Tag      string          `json:"tag"`
	Config   json.RawMessage `json:"config"` // * We use RawMessage to keep the outbound config as-is.
	TestPort int             `json:"test_port"`
	XrayPath   string          `json:"xray_path"`
}

// note: This struct defines the output format we send back to Python.
type TestResult struct {
	Tag    string `json:"tag"`
	Ping   int64  `json:"ping_ms"` // * Ping in milliseconds
	Status string `json:"status"`
}

func main() {
	inputData, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading stdin: %v\n", err)
		os.Exit(1)
	}

	var configs []TestConfig
	if err := json.Unmarshal(inputData, &configs); err != nil {
		fmt.Fprintf(os.Stderr, "Error unmarshaling json: %v\n", err)
		os.Exit(1)
	}

	results := make(chan TestResult, len(configs)) // * Use a buffered channel for collecting results.
	var wg sync.WaitGroup

	// * All tests will run concurrently!
	for _, conf := range configs {
		wg.Add(1)
		go func(c Test-Config) {
			defer wg.Done()

			tmpFile, err := os.CreateTemp("", "xray-test-*.json")
			if err != nil {
				results <- TestResult{Tag: c.Tag, Ping: -1, Status: "tempfile_error"}
				return
			}
			// * Ensure the temp file is cleaned up even if something panics.
			defer os.Remove(tmpFile.Name())

			fullConfig := map[string]interface{}{
				"inbounds": []map[string]interface{}{
					{
						"protocol": "socks",
						"port":     c.TestPort,
						"listen":   "127.0.0.1",
						"settings": map[string]interface{}{
							"auth": "noauth",
							"udp":  true,
						},
					},
				},
				"outbounds": []json.RawMessage{c.Config},
			}

			configBytes, _ := json.Marshal(fullConfig)
			if _, err := tmpFile.Write(configBytes); err != nil {
				results <- TestResult{Tag: c.Tag, Ping: -1, Status: "tempfile_write_error"}
				tmpFile.Close()
				return
			}
			tmpFile.Close()

			// * We set a context with a timeout for the entire Xray process.
			ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()

			cmd := exec.CommandContext(ctx, c.XrayPath, "-c", tmpFile.Name())

			if err := cmd.Start(); err != nil {
				results <- TestResult{Tag: c.Tag, Ping: -1, Status: "xray_start_failed"}
				return
			}

			time.Sleep(700 * time.Millisecond)

			ping, status := testProxy(c.TestPort)

			// * Killing the process is more reliable than waiting for it to exit.
			cmd.Process.Kill()
			cmd.Wait() /

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
	// * This function tests the SOCKS5 proxy that the Xray core creates.
	targetURL := "https://www.gstatic.com/generate_204"
	timeout := 8 * time.Second

	dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("127.0.0.1:%d", port), nil, proxy.Direct)
	if err != nil {
		return -1, "failed_dialer"
	}

	httpTransport := &http.Transport{}
	httpClient := &http.Client{Transport: httpTransport, Timeout: timeout}
	httpTransport.DialContext = func(ctx context.Context, network, addr string) (net.Conn, error) {
		return dialer.Dial(network, addr)
	}

	start := time.Now()
	resp, err := httpClient.Get(targetURL)
	if err != nil {
		return -1, "failed_http"
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return -1, fmt.Sprintf("bad_status_%d", resp.StatusCode)
	}

	latency := time.Since(start).Milliseconds()
	return latency, "success"
}
