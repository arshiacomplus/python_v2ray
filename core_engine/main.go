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

type TestJob struct {
	Tag        string `json:"tag"`
	Protocol   string `json:"protocol"`
	ConfigURI  string `json:"config_uri,omitempty"`
	ListenIP   string `json:"listen_ip"`
	TestPort   int    `json:"test_port"`
	ClientPath string `json:"client_path,omitempty"`
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
	var jobs []TestJob
	if err := json.Unmarshal(inputData, &jobs); err != nil {
		os.Exit(1)
	}

	results := make(chan TestResult, len(jobs))
	var wg sync.WaitGroup

	for _, job := range jobs {
		wg.Add(1)
		go func(j TestJob) {
			defer wg.Done()
			runTest(j, results)
		}(job)
	}

	wg.Wait()
	close(results)

	finalResults := make([]TestResult, 0, len(jobs))
	for res := range results {
		finalResults = append(finalResults, res)
	}
	outputData, _ := json.Marshal(finalResults)
	fmt.Println(string(outputData))
}

func runTest(j TestJob, results chan<- TestResult) {
	if j.ClientPath == "" {
		ping, status := testProxy(j.ListenIP, j.TestPort)
		results <- TestResult{Tag: j.Tag, Ping: ping, Status: status}
		return
	}

	var cmd *exec.Cmd
	var configFile *os.File
	var err error

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if j.Protocol == "hysteria2" {
		configFile, err = os.CreateTemp("", "hysteria-*.json")
		if err != nil {
			results <- TestResult{Tag: j.Tag, Ping: -1, Status: "tempfile_error"}
			return
		}
		defer os.Remove(configFile.Name())

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
		cmd = exec.CommandContext(ctx, j.ClientPath, "client", "-c", configFile.Name())
	} else {
		results <- TestResult{Tag: j.Tag, Ping: -1, Status: "unsupported_client_protocol"}
		return
	}

	setHideWindow(cmd)

	var clientOutput bytes.Buffer
	cmd.Stdout, cmd.Stderr = &clientOutput, &clientOutput

	if err := cmd.Start(); err != nil {
		results <- TestResult{Tag: j.Tag, Ping: -1, Status: "client_start_failed"}
		return
	}

	proxyReady := false
	for i := 0; i < 20; i++ {
		conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", j.ListenIP, j.TestPort), 200*time.Millisecond)
		if err == nil {
			conn.Close()
			proxyReady = true
			break
		}
		time.Sleep(200 * time.Millisecond)
	}

	if !proxyReady {
		cmd.Process.Kill()
		cmd.Wait()
		results <- TestResult{Tag: j.Tag, Ping: -1, Status: "proxy_startup_timeout"}
		return
	}

	ping, status := testProxy(j.ListenIP, j.TestPort)

	if status != "success" {
		logStr := strings.ReplaceAll(string(clientOutput.Bytes()), "\n", " ")
		if len(logStr) > 200 {
			logStr = logStr[:200]
		}
		status = fmt.Sprintf("%s | log: %s", status, logStr)
	}

	cmd.Process.Kill()
	cmd.Wait()

	results <- TestResult{Tag: j.Tag, Ping: ping, Status: status}
}

func testProxy(listenIP string, port int) (int64, string) {
	const maxRetries = 3
	const retryDelay = 200 * time.Millisecond

	var lastError string
	bestPing := int64(-1)
	for attempt := 1; attempt <= maxRetries; attempt++ {
		targetURL := "http://www.google.com/generate_204"
		timeout := 8 * time.Second

		dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("%s:%d", listenIP, port), nil, proxy.Direct)
		if err != nil {
			return -1, fmt.Sprintf("failed_dialer: %v", err)
		}

		transport := &http.Transport{
			DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
				return dialer.Dial(network, addr)
			},
		}
		httpClient := &http.Client{Transport: transport, Timeout: timeout}

		start := time.Now()
		resp, err := httpClient.Get(targetURL)

		if err != nil {
			lastError = fmt.Sprintf("failed_http: %v (attempt %d/%d)", err, attempt, maxRetries)
			time.Sleep(retryDelay)
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusNoContent {
			lastError = fmt.Sprintf("bad_status_%d (attempt %d/%d)", resp.StatusCode, attempt, maxRetries)
			time.Sleep(retryDelay)
			continue
		}


		currentPing := time.Since(start).Milliseconds()
		if bestPing == -1 || currentPing < bestPing {

			bestPing = currentPing
		}
	}

	if bestPing != -1 {
		return bestPing, "success"
	}

	return -1, lastError
}