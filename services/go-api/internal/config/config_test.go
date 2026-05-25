package config

import (
	"os"
	"strings"
	"testing"
	"time"
)

func TestLoadUsesDefaults(t *testing.T) {
	unsetEnv(
		t,
		envGoAPIAddr,
		envPythonRuntimeBaseURL,
		envRequestTimeoutMillis,
		envRedisAddr,
		envDBAddr,
		envMetricsEnabled,
		envPprofEnabled,
		envRateLimitEnabled,
		envRateLimitRequests,
		envRateLimitWindow,
		envRateLimitExcluded,
	)

	cfg := Load()

	if cfg.GoAPIAddr != defaultGoAPIAddr {
		t.Fatalf("GoAPIAddr = %q, want %q", cfg.GoAPIAddr, defaultGoAPIAddr)
	}
	if cfg.PythonRuntimeBaseURL != defaultPythonRuntimeBase {
		t.Fatalf("PythonRuntimeBaseURL = %q, want %q", cfg.PythonRuntimeBaseURL, defaultPythonRuntimeBase)
	}
	if cfg.RedisAddr != defaultRedisAddr {
		t.Fatalf("RedisAddr = %q, want %q", cfg.RedisAddr, defaultRedisAddr)
	}
	if cfg.DBAddr != defaultDBAddr {
		t.Fatalf("DBAddr = %q, want %q", cfg.DBAddr, defaultDBAddr)
	}
	if cfg.RequestTimeout != 30*time.Second {
		t.Fatalf("RequestTimeout = %s, want 30s", cfg.RequestTimeout)
	}
	if !cfg.MetricsEnabled {
		t.Fatalf("MetricsEnabled = false, want true")
	}
	if !cfg.PprofEnabled {
		t.Fatalf("PprofEnabled = false, want true")
	}
	if !cfg.RateLimitEnabled {
		t.Fatalf("RateLimitEnabled = false, want true")
	}
	if cfg.RateLimitRequests != defaultRateLimitRequests {
		t.Fatalf("RateLimitRequests = %d, want %d", cfg.RateLimitRequests, defaultRateLimitRequests)
	}
	if cfg.RateLimitWindow != defaultRateLimitWindow*time.Second {
		t.Fatalf("RateLimitWindow = %s", cfg.RateLimitWindow)
	}
	if len(cfg.RateLimitExcluded) == 0 {
		t.Fatalf("RateLimitExcluded is empty")
	}
}

func TestLoadReadsEnvironment(t *testing.T) {
	t.Setenv(envGoAPIAddr, ":9090")
	t.Setenv(envPythonRuntimeBaseURL, "http://runtime.local/")
	t.Setenv(envRequestTimeoutMillis, "1234")
	t.Setenv(envRedisAddr, "redis.local:6379")
	t.Setenv(envDBAddr, "postgres.local:5432")
	t.Setenv(envMetricsEnabled, "false")
	t.Setenv(envPprofEnabled, "false")
	t.Setenv(envRateLimitEnabled, "true")
	t.Setenv(envRateLimitRequests, "7")
	t.Setenv(envRateLimitWindow, "9")
	t.Setenv(envRateLimitExcluded, "/health, /metrics")

	cfg := Load()

	if cfg.GoAPIAddr != ":9090" {
		t.Fatalf("GoAPIAddr = %q", cfg.GoAPIAddr)
	}
	if cfg.PythonRuntimeBaseURL != "http://runtime.local" {
		t.Fatalf("PythonRuntimeBaseURL = %q", cfg.PythonRuntimeBaseURL)
	}
	if cfg.RequestTimeout != 1234*time.Millisecond {
		t.Fatalf("RequestTimeout = %s", cfg.RequestTimeout)
	}
	if cfg.RedisAddr != "redis.local:6379" {
		t.Fatalf("RedisAddr = %q", cfg.RedisAddr)
	}
	if cfg.DBAddr != "postgres.local:5432" {
		t.Fatalf("DBAddr = %q", cfg.DBAddr)
	}
	if cfg.MetricsEnabled {
		t.Fatalf("MetricsEnabled = true")
	}
	if cfg.PprofEnabled {
		t.Fatalf("PprofEnabled = true")
	}
	if !cfg.RateLimitEnabled {
		t.Fatalf("RateLimitEnabled = false")
	}
	if cfg.RateLimitRequests != 7 {
		t.Fatalf("RateLimitRequests = %d", cfg.RateLimitRequests)
	}
	if cfg.RateLimitWindow != 9*time.Second {
		t.Fatalf("RateLimitWindow = %s", cfg.RateLimitWindow)
	}
	if got := strings.Join(cfg.RateLimitExcluded, ","); got != "/health,/metrics" {
		t.Fatalf("RateLimitExcluded = %q", got)
	}
}

func unsetEnv(t *testing.T, keys ...string) {
	t.Helper()

	type oldValue struct {
		key   string
		value string
		ok    bool
	}
	oldValues := make([]oldValue, 0, len(keys))
	for _, key := range keys {
		value, ok := os.LookupEnv(key)
		oldValues = append(oldValues, oldValue{key: key, value: value, ok: ok})
		if err := os.Unsetenv(key); err != nil {
			t.Fatalf("Unsetenv(%s): %v", key, err)
		}
	}

	t.Cleanup(func() {
		for _, old := range oldValues {
			if old.ok {
				_ = os.Setenv(old.key, old.value)
			} else {
				_ = os.Unsetenv(old.key)
			}
		}
	})
}
