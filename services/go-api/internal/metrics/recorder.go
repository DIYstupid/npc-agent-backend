package metrics

import (
	"fmt"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

type Recorder struct {
	mu             sync.Mutex
	startedAt      time.Time
	requests       map[requestKey]int64
	durationMillis map[requestKey]int64
	inFlight       int64
	rateLimitErrs  int64
}

type requestKey struct {
	Method string
	Path   string
	Status int
}

func NewRecorder() *Recorder {
	return &Recorder{
		startedAt:      time.Now(),
		requests:       make(map[requestKey]int64),
		durationMillis: make(map[requestKey]int64),
	}
}

func (r *Recorder) IncInFlight() {
	if r == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.inFlight++
}

func (r *Recorder) DecInFlight() {
	if r == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.inFlight > 0 {
		r.inFlight--
	}
}

func (r *Recorder) ObserveRequest(method string, path string, status int, elapsed time.Duration) {
	if r == nil {
		return
	}
	if path == "" {
		path = "unknown"
	}
	key := requestKey{
		Method: method,
		Path:   path,
		Status: status,
	}

	r.mu.Lock()
	defer r.mu.Unlock()
	r.requests[key]++
	r.durationMillis[key] += elapsed.Milliseconds()
}

func (r *Recorder) IncRateLimitError() {
	if r == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.rateLimitErrs++
}

func (r *Recorder) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		_, _ = w.Write([]byte(r.Render()))
	})
}

func (r *Recorder) Render() string {
	if r == nil {
		return ""
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	var builder strings.Builder
	builder.WriteString("# HELP go_api_uptime_seconds Process uptime in seconds.\n")
	builder.WriteString("# TYPE go_api_uptime_seconds gauge\n")
	builder.WriteString(fmt.Sprintf("go_api_uptime_seconds %.0f\n", time.Since(r.startedAt).Seconds()))
	builder.WriteString("# HELP go_api_in_flight_requests Current in-flight HTTP requests.\n")
	builder.WriteString("# TYPE go_api_in_flight_requests gauge\n")
	builder.WriteString(fmt.Sprintf("go_api_in_flight_requests %d\n", r.inFlight))
	builder.WriteString("# HELP go_api_requests_total Total HTTP requests by method, route, and status.\n")
	builder.WriteString("# TYPE go_api_requests_total counter\n")

	keys := make([]requestKey, 0, len(r.requests))
	for key := range r.requests {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].Path != keys[j].Path {
			return keys[i].Path < keys[j].Path
		}
		if keys[i].Method != keys[j].Method {
			return keys[i].Method < keys[j].Method
		}
		return keys[i].Status < keys[j].Status
	})
	for _, key := range keys {
		labels := metricLabels(key)
		builder.WriteString(fmt.Sprintf("go_api_requests_total{%s} %d\n", labels, r.requests[key]))
	}

	builder.WriteString("# HELP go_api_request_duration_ms_total Total HTTP request duration in milliseconds.\n")
	builder.WriteString("# TYPE go_api_request_duration_ms_total counter\n")
	for _, key := range keys {
		labels := metricLabels(key)
		builder.WriteString(fmt.Sprintf("go_api_request_duration_ms_total{%s} %d\n", labels, r.durationMillis[key]))
	}

	builder.WriteString("# HELP go_api_rate_limit_errors_total Redis rate limiter errors that were allowed open.\n")
	builder.WriteString("# TYPE go_api_rate_limit_errors_total counter\n")
	builder.WriteString(fmt.Sprintf("go_api_rate_limit_errors_total %d\n", r.rateLimitErrs))

	return builder.String()
}

func metricLabels(key requestKey) string {
	return fmt.Sprintf(
		`method="%s",path="%s",status="%d"`,
		escapeLabel(key.Method),
		escapeLabel(key.Path),
		key.Status,
	)
}

func escapeLabel(value string) string {
	value = strings.ReplaceAll(value, `\`, `\\`)
	value = strings.ReplaceAll(value, `"`, `\"`)
	value = strings.ReplaceAll(value, "\n", `\n`)
	return value
}
