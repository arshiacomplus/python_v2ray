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
	PingURL    string `json:"ping_url,omitempty"`
}
type TestResult struct {
	Tag    string `json:"tag"`
	Ping   int64  `json:"ping_ms"`
	Status string `json:"status"`
}
type SpeedTestJob struct {
	Tag           string `json:"tag"`
	ListenIP      string `json:"listen_ip"`
	TestPort      int    `json:"test_port"`
	DownloadURL   string `json:"download_url"`
	DownloadBytes int    `json:"download_bytes"`
}
type SpeedTestResult struct {
	Tag             string  `json:"tag"`
	Status          string  `json:"status"`
	DownloadMbps    float64 `json:"download_mbps"`
	BytesDownloaded int64   `json:"bytes_downloaded"`
}
type UploadTestJob struct {
	Tag         string `json:"tag"`
	ListenIP    string `json:"listen_ip"`
	TestPort    int    `json:"test_port"`
	UploadURL   string `json:"upload_url"`
	UploadBytes int    `json:"upload_bytes"`
}
type UploadTestResult struct {
	Tag           string  `json:"tag"`
	Status        string  `json:"status"`
	UploadMbps    float64 `json:"upload_mbps"`
	BytesUploaded int64   `json:"bytes_uploaded"`
}
type zeroReader struct{}
func (z zeroReader) Read(p []byte) (n int, err error) {
	for i := range p {
		p[i] = 0
	}
	return len(p), nil
}
func main() {
	inputData, err := io.ReadAll(os.Stdin)
	if err != nil { os.Exit(1) }
	var rawJobs []json.RawMessage
	if err := json.Unmarshal(inputData, &rawJobs); err != nil { os.Exit(1) }
	var finalResults []interface{}
	var mu sync.Mutex
	var wg sync.WaitGroup
	for _, rawJob := range rawJobs {
		var temp map[string]interface{}
		json.Unmarshal(rawJob, &temp)
		wg.Add(1)
		if _, isUploadTest := temp["upload_url"]; isUploadTest {
			var job UploadTestJob
			json.Unmarshal(rawJob, &job)
			go func(j UploadTestJob) {
				defer wg.Done()
				resultsChan := make(chan UploadTestResult, 1)
				runUploadTest(j, resultsChan)
				result := <-resultsChan
				mu.Lock()
				finalResults = append(finalResults, result)
				mu.Unlock()
			}(job)
		} else if _, isSpeedTest := temp["download_url"]; isSpeedTest {
			var job SpeedTestJob
			json.Unmarshal(rawJob, &job)
			go func(j SpeedTestJob) {
				defer wg.Done()
				resultsChan := make(chan SpeedTestResult, 1)
				runSpeedTest(j, resultsChan)
				result := <-resultsChan
				mu.Lock()
				finalResults = append(finalResults, result)
				mu.Unlock()
			}(job)
		} else {
			var job TestJob
			json.Unmarshal(rawJob, &job)
			go func(j TestJob) {
				defer wg.Done()
				resultsChan := make(chan TestResult, 1)
				runTest(j, resultsChan)
				result := <-resultsChan
				mu.Lock()
				finalResults = append(finalResults, result)
				mu.Unlock()
			}(job)
		}
	}
	wg.Wait()
	outputData, _ := json.Marshal(finalResults)
	fmt.Println(string(outputData))
}
func runUploadTest(j UploadTestJob, results chan<- UploadTestResult) {
	payloadReader := io.LimitReader(zeroReader{}, int64(j.UploadBytes))
	dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("%s:%d", j.ListenIP, j.TestPort), nil, proxy.Direct)
	if err != nil {
		results <- UploadTestResult{Tag: j.Tag, Status: "error: dialer creation failed"}
		return
	}
	transport := &http.Transport{
		DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return dialer.Dial(network, addr)
		},
	}
	httpClient := &http.Client{Transport: transport, Timeout: 45 * time.Second}
	req, err := http.NewRequest("POST", j.UploadURL, payloadReader)
	if err != nil {
		results <- UploadTestResult{Tag: j.Tag, Status: fmt.Sprintf("error: request creation failed: %v", err)}
		return
	}
	req.Header.Set("Content-Type", "application/octet-stream")
	req.ContentLength = int64(j.UploadBytes)
	start := time.Now()
	resp, err := httpClient.Do(req)
	if err != nil {
		results <- UploadTestResult{Tag: j.Tag, Status: fmt.Sprintf("error: http post failed: %v", err)}
		return
	}
	defer resp.Body.Close()
	duration := time.Since(start).Seconds()
	if resp.StatusCode != http.StatusOK {
		results <- UploadTestResult{Tag: j.Tag, Status: fmt.Sprintf("error: bad status %d", resp.StatusCode)}
		return
	}
	if duration == 0 {
		results <- UploadTestResult{Tag: j.Tag, Status: "error: division by zero"}
		return
	}
	uploadMbps := (float64(j.UploadBytes) * 8) / (duration * 1024 * 1024)
	results <- UploadTestResult{
		Tag:           j.Tag,
		Status:        "success",
		UploadMbps:    uploadMbps,
		BytesUploaded: int64(j.UploadBytes),
	}
}
func runSpeedTest(j SpeedTestJob, results chan<- SpeedTestResult) {
	fullURL := fmt.Sprintf("%s?bytes=%d", j.DownloadURL, j.DownloadBytes)
	dialer, err := proxy.SOCKS5("tcp", fmt.Sprintf("%s:%d", j.ListenIP, j.TestPort), nil, proxy.Direct)
	if err != nil {
		results <- SpeedTestResult{Tag: j.Tag, Status: "error: dialer creation failed"}
		return
	}
	transport := &http.Transport{
		DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return dialer.Dial(network, addr)
		},
	}
	httpClient := &http.Client{Transport: transport, Timeout: 45 * time.Second}
	start := time.Now()
	resp, err := httpClient.Get(fullURL)
	if err != nil {
		results <- SpeedTestResult{Tag: j.Tag, Status: fmt.Sprintf("error: http get failed: %v", err)}
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		results <- SpeedTestResult{Tag: j.Tag, Status: fmt.Sprintf("error: bad status %d", resp.StatusCode)}
		return
	}
	bytesDownloaded, err := io.Copy(io.Discard, resp.Body)
	if err != nil {
		results <- SpeedTestResult{Tag: j.Tag, Status: fmt.Sprintf("error: download failed: %v", err), BytesDownloaded: bytesDownloaded}
		return
	}
	duration := time.Since(start).Seconds()
	if duration == 0 {
		results <- SpeedTestResult{Tag: j.Tag, Status: "error: division by zero"}
		return
	}
	speedMbps := (float64(bytesDownloaded) * 8) / (duration * 1024 * 1024)
	results <- SpeedTestResult{
		Tag:             j.Tag,
		Status:          "success",
		DownloadMbps:    speedMbps,
		BytesDownloaded: bytesDownloaded,
	}
}
func runTest(j TestJob, results chan<- TestResult) {
	urlToTest := j.PingURL
	if urlToTest == "" {
		urlToTest = "http://www.google.com/generate_204"
	}
	if j.ClientPath == "" {
		ping, status := testProxy(j.ListenIP, j.TestPort, urlToTest)
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
		if err != nil { results <- TestResult{Tag: j.Tag, Ping: -1, Status: "tempfile_error"}; return }
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
	ping, status := testProxy(j.ListenIP, j.TestPort, urlToTest)
	if status != "success" {
		logStr := strings.ReplaceAll(string(clientOutput.Bytes()), "\n", " ")
		if len(logStr) > 200 { logStr = logStr[:200] }
		status = fmt.Sprintf("%s | log: %s", status, logStr)
	}
	cmd.Process.Kill()
	cmd.Wait()
	results <- TestResult{Tag: j.Tag, Ping: ping, Status: status}
}
func testProxy(listenIP string, port int, targetURL string) (int64, string) {
	const maxRetries = 3
	const retryDelay = 200 * time.Millisecond

	var lastError string
	bestPing := int64(-1)
	for attempt := 1; attempt <= maxRetries; attempt++ {
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

		if resp.StatusCode != http.StatusNoContent && resp.StatusCode != http.StatusOK {
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