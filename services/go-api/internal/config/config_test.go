package config

import (
	"os"
	"testing"
	"time"
)

func TestLoadUsesDefaults(t *testing.T) {
	unsetEnv(t, envGoAPIAddr, envPythonRuntimeBaseURL, envRequestTimeoutMillis, envRedisAddr)

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
	if cfg.RequestTimeout != 30*time.Second {
		t.Fatalf("RequestTimeout = %s, want 30s", cfg.RequestTimeout)
	}
}

func TestLoadReadsEnvironment(t *testing.T) {
	t.Setenv(envGoAPIAddr, ":9090")
	t.Setenv(envPythonRuntimeBaseURL, "http://runtime.local/")
	t.Setenv(envRequestTimeoutMillis, "1234")
	t.Setenv(envRedisAddr, "redis.local:6379")

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
