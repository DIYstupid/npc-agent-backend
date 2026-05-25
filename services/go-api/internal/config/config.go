package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultGoAPIAddr         = ":8080"
	defaultPythonRuntimeBase = "http://127.0.0.1:8000"
	defaultRequestTimeoutMS  = 30000
	defaultRedisAddr         = "127.0.0.1:6379"
	envGoAPIAddr             = "GO_API_ADDR"
	envPythonRuntimeBaseURL  = "PYTHON_RUNTIME_BASE_URL"
	envRequestTimeoutMillis  = "REQUEST_TIMEOUT_MS"
	envRedisAddr             = "REDIS_ADDR"
)

type Config struct {
	GoAPIAddr            string
	PythonRuntimeBaseURL string
	RequestTimeout       time.Duration
	RedisAddr            string
}

func Load() Config {
	timeoutMS := getEnvInt(envRequestTimeoutMillis, defaultRequestTimeoutMS)
	if timeoutMS <= 0 {
		timeoutMS = defaultRequestTimeoutMS
	}

	return Config{
		GoAPIAddr:            getEnv(envGoAPIAddr, defaultGoAPIAddr),
		PythonRuntimeBaseURL: strings.TrimRight(getEnv(envPythonRuntimeBaseURL, defaultPythonRuntimeBase), "/"),
		RequestTimeout:       time.Duration(timeoutMS) * time.Millisecond,
		RedisAddr:            getEnv(envRedisAddr, defaultRedisAddr),
	}
}

func (c Config) RequestTimeoutMillis() int64 {
	return c.RequestTimeout.Milliseconds()
}

func getEnv(key string, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	raw, ok := os.LookupEnv(key)
	if !ok {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return value
}
