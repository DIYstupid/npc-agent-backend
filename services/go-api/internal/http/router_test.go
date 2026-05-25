package httpserver

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"npc-agent-backend/services/go-api/internal/agentclient"
	"npc-agent-backend/services/go-api/internal/config"
	"npc-agent-backend/services/go-api/internal/http/middleware"
)

func TestHealthIncludesPythonRuntime(t *testing.T) {
	runtime := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok","service":"npc-agent-backend","version":"0.5.0"}`))
	}))
	defer runtime.Close()

	router := NewRouter(testConfig(runtime.URL), testLogger(), agentclient.New(runtime.URL, time.Second), nil)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"service":"go-api"`) {
		t.Fatalf("body missing go service: %s", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"python_runtime"`) {
		t.Fatalf("body missing python runtime: %s", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"reachable":true`) {
		t.Fatalf("body missing reachable runtime: %s", rec.Body.String())
	}
}

func TestChatProxyForwardsJSON(t *testing.T) {
	runtime := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/blacksmith_001" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		if r.Header.Get(middleware.RequestIDHeader) != "req-123" {
			t.Fatalf("X-Request-ID = %q", r.Header.Get(middleware.RequestIDHeader))
		}
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("ReadAll: %v", err)
		}
		if string(body) != `{"player_id":"player_001","message":"hello"}` {
			t.Fatalf("body = %s", string(body))
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"reply":"hello"}`))
	}))
	defer runtime.Close()

	router := NewRouter(testConfig(runtime.URL), testLogger(), agentclient.New(runtime.URL, time.Second), nil)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/chat/blacksmith_001", strings.NewReader(`{"player_id":"player_001","message":"hello"}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set(middleware.RequestIDHeader, "req-123")
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", rec.Code, rec.Body.String())
	}
	if rec.Body.String() != `{"reply":"hello"}` {
		t.Fatalf("body = %s", rec.Body.String())
	}
	if rec.Header().Get(middleware.RequestIDHeader) != "req-123" {
		t.Fatalf("response X-Request-ID = %q", rec.Header().Get(middleware.RequestIDHeader))
	}
}

func TestChatStreamProxyPassesThroughSSE(t *testing.T) {
	runtime := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/blacksmith_001/stream" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		_, _ = w.Write([]byte("event: start\ndata: {\"request_id\":\"req-123\"}\n\n"))
		_, _ = w.Write([]byte("event: final\ndata: {\"reply\":\"done\"}\n\n"))
	}))
	defer runtime.Close()

	router := NewRouter(testConfig(runtime.URL), testLogger(), agentclient.New(runtime.URL, time.Second), nil)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/chat/blacksmith_001/stream", strings.NewReader(`{"player_id":"player_001","message":"hello"}`))
	req.Header.Set("Content-Type", "application/json")
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", rec.Code, rec.Body.String())
	}
	if !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/event-stream") {
		t.Fatalf("Content-Type = %q", rec.Header().Get("Content-Type"))
	}
	body := rec.Body.String()
	if !strings.Contains(body, "event: start") || !strings.Contains(body, "event: final") {
		t.Fatalf("body = %s", body)
	}
}

func testConfig(runtimeURL string) config.Config {
	return config.Config{
		GoAPIAddr:            ":0",
		PythonRuntimeBaseURL: runtimeURL,
		RequestTimeout:       time.Second,
		RedisAddr:            "",
	}
}

func testLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}
