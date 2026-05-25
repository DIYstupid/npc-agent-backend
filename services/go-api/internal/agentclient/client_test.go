package agentclient

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestCheckHealth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok","service":"npc-agent-backend","version":"0.5.0"}`))
	}))
	defer server.Close()

	client := New(server.URL, time.Second)
	status := client.CheckHealth(context.Background())

	if !status.Configured || !status.Reachable {
		t.Fatalf("status = %+v, want configured and reachable", status)
	}
	if status.Status != "ok" || status.Service != "npc-agent-backend" || status.Version != "0.5.0" {
		t.Fatalf("unexpected status: %+v", status)
	}
}

func TestDoForwardsRequest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/blacksmith_001" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		if r.URL.Query().Get("debug") != "1" {
			t.Fatalf("query = %q", r.URL.RawQuery)
		}
		if r.Header.Get("X-Request-ID") != "req-1" {
			t.Fatalf("X-Request-ID = %q", r.Header.Get("X-Request-ID"))
		}
		w.WriteHeader(http.StatusCreated)
	}))
	defer server.Close()

	client := New(server.URL, time.Second)
	headers := http.Header{"X-Request-ID": []string{"req-1"}}
	query := map[string][]string{"debug": {"1"}}

	resp, err := client.Do(context.Background(), http.MethodPost, "/chat/blacksmith_001", query, nil, headers)
	if err != nil {
		t.Fatalf("Do returned error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("StatusCode = %d", resp.StatusCode)
	}
}
