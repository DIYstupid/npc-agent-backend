package agentclient

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
}

type RuntimeHealth struct {
	BaseURL    string `json:"base_url"`
	Configured bool   `json:"configured"`
	Reachable  bool   `json:"reachable"`
	StatusCode int    `json:"status_code,omitempty"`
	Status     string `json:"status,omitempty"`
	Service    string `json:"service,omitempty"`
	Version    string `json:"version,omitempty"`
	Error      string `json:"error,omitempty"`
}

func New(baseURL string, timeout time.Duration) *Client {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}

	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

func (c *Client) CheckHealth(ctx context.Context) RuntimeHealth {
	status := RuntimeHealth{
		BaseURL:    c.baseURL,
		Configured: c.baseURL != "",
	}
	if !status.Configured {
		status.Error = "PYTHON_RUNTIME_BASE_URL is empty"
		return status
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/health", nil)
	if err != nil {
		status.Error = err.Error()
		return status
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		status.Error = err.Error()
		return status
	}
	defer resp.Body.Close()

	status.Reachable = true
	status.StatusCode = resp.StatusCode

	var payload struct {
		Status  string `json:"status"`
		Service string `json:"service"`
		Version string `json:"version"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&payload); err != nil {
		status.Error = fmt.Sprintf("decode health response: %v", err)
		return status
	}
	status.Status = payload.Status
	status.Service = payload.Service
	status.Version = payload.Version
	return status
}

func (c *Client) Do(ctx context.Context, method string, path string, query url.Values, body io.Reader, headers http.Header) (*http.Response, error) {
	if c.baseURL == "" {
		return nil, fmt.Errorf("PYTHON_RUNTIME_BASE_URL is empty")
	}

	target := c.baseURL + path
	if encodedQuery := query.Encode(); encodedQuery != "" {
		target += "?" + encodedQuery
	}

	req, err := http.NewRequestWithContext(ctx, method, target, body)
	if err != nil {
		return nil, err
	}
	copyHeaders(req.Header, headers)
	return c.httpClient.Do(req)
}

func copyHeaders(dst http.Header, src http.Header) {
	for key, values := range src {
		if shouldSkipHeader(key) {
			continue
		}
		for _, value := range values {
			dst.Add(key, value)
		}
	}
}

func shouldSkipHeader(key string) bool {
	switch strings.ToLower(key) {
	case "connection", "content-length", "host", "transfer-encoding":
		return true
	default:
		return false
	}
}
