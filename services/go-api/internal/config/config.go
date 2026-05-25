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
	defaultDBAddr            = ""
	defaultMetricsEnabled    = true
	defaultPprofEnabled      = true
	defaultRateLimitEnabled  = true
	defaultRateLimitRequests = 120
	defaultRateLimitWindow   = 60
	defaultRateLimitPaths    = "/health,/metrics,/debug/pprof"
	envGoAPIAddr             = "GO_API_ADDR"
	envPythonRuntimeBaseURL  = "PYTHON_RUNTIME_BASE_URL"
	envRequestTimeoutMillis  = "REQUEST_TIMEOUT_MS"
	envRedisAddr             = "REDIS_ADDR"
	envDBAddr                = "DB_ADDR"
	envMetricsEnabled        = "METRICS_ENABLED"
	envPprofEnabled          = "PPROF_ENABLED"
	envRateLimitEnabled      = "RATE_LIMIT_ENABLED"
	envRateLimitRequests     = "RATE_LIMIT_REQUESTS"
	envRateLimitWindow       = "RATE_LIMIT_WINDOW_SECONDS"
	envRateLimitExcluded     = "RATE_LIMIT_EXCLUDED_PATHS"
)

type Config struct {
	GoAPIAddr            string
	PythonRuntimeBaseURL string
	RequestTimeout       time.Duration
	RedisAddr            string
	DBAddr               string
	MetricsEnabled       bool
	PprofEnabled         bool
	RateLimitEnabled     bool
	RateLimitRequests    int
	RateLimitWindow      time.Duration
	RateLimitExcluded    []string
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
		DBAddr:               getEnv(envDBAddr, defaultDBAddr),
		MetricsEnabled:       getEnvBool(envMetricsEnabled, defaultMetricsEnabled),
		PprofEnabled:         getEnvBool(envPprofEnabled, defaultPprofEnabled),
		RateLimitEnabled:     getEnvBool(envRateLimitEnabled, defaultRateLimitEnabled),
		RateLimitRequests:    positiveEnvInt(envRateLimitRequests, defaultRateLimitRequests),
		RateLimitWindow:      time.Duration(positiveEnvInt(envRateLimitWindow, defaultRateLimitWindow)) * time.Second,
		RateLimitExcluded:    splitCSV(getEnv(envRateLimitExcluded, defaultRateLimitPaths)),
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

func positiveEnvInt(key string, fallback int) int {
	value := getEnvInt(key, fallback)
	if value <= 0 {
		return fallback
	}
	return value
}

func getEnvBool(key string, fallback bool) bool {
	raw, ok := os.LookupEnv(key)
	if !ok {
		return fallback
	}
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}

func splitCSV(raw string) []string {
	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		value := strings.TrimSpace(part)
		if value != "" {
			values = append(values, value)
		}
	}
	return values
}
