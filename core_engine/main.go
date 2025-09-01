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

	"golang.org/x/net/proxy"
)

// note: This struct defines the input format we expect from Python.
type TestConfig struct {
	Tag      string          `json:"tag"`
	Config   json.RawMessage `json:"config"` // * We use RawMessage to keep the outbound config as-is.
	TestPort int             `json:"test_port"`
}

// note: This struct defines the output format we send back to Python.
type TestResult struct {
	Tag    string `json:"tag"`
	Ping   int64  `json:"ping_ms"` // * Ping in milliseconds
	Status string `json:"status"`
}

func main() {
	// ! Read the list of configs from Standard Input (stdin).
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

	results := make([]TestResult, 0)
	var wg sync.WaitGroup // ? A WaitGroup waits for a collection of goroutines to finish.
	var mu sync.Mutex     // ? A Mutex prevents race conditions when writing to the results slice.

	// * All tests will run concurrently!
	for _, conf := range configs {
		wg.Add(1)
		go func(c TestConfig) {
			defer wg.Done()

			// * Create a temporary config file for the Xray core to use.
			tmpFile, err := os.CreateTemp("", "xray-test-*.json")
			if err != nil {
				return
			}
			defer os.Remove(tmpFile.Name())

			fullConfig := map[string]interface{}{
				"inbounds": []map[string]interface{}{
					{
						"protocol": "socks",
						"port":     c.TestPort,
						"listen":   "127.0.0.1",
						"settings": map[string]interface{}{"udp": true},
					},
				},
				"outbounds": []json.RawMessage{c.Config},
			}

			configBytes, _ := json.Marshal(fullConfig)
			tmpFile.Write(configBytes)
			tmpFile.Close()

			// todo: We need a way to run the xray executable here.
			// For now, let's assume it's running and we can test the SOCKS port.
			// This part will be completed in the next steps.

			ping, status := testProxy(c.TestPort)

			mu.Lock()
			results = append(results, TestResult{Tag: c.Tag, Ping: ping, Status: status})
			mu.Unlock()
		}(conf)
	}

	wg.Wait() // * Wait for all tests to complete.

	// ! Print the final results as a JSON array to Standard Output (stdout).
	outputData, _ := json.Marshal(results)
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
