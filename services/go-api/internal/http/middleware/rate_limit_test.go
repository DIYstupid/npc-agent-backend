package middleware

import (
	"context"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"npc-agent-backend/services/go-api/internal/metrics"
)

type fakeLimiter struct {
	allowed bool
	err     error
	calls   int
}

func (l *fakeLimiter) Allow(_ context.Context, _ string) (bool, error) {
	l.calls++
	return l.allowed, l.err
}

func TestRateLimitRejectsWhenLimitExceeded(t *testing.T) {
	limiter := &fakeLimiter{allowed: false}
	router := rateLimitTestRouter(limiter, []string{"/health"})

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/chat/blacksmith_001", nil)
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("status = %d, body = %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"code":"rate_limited"`) {
		t.Fatalf("body = %s", rec.Body.String())
	}
	if limiter.calls != 1 {
		t.Fatalf("calls = %d", limiter.calls)
	}
}

func TestRateLimitSkipsExcludedPath(t *testing.T) {
	limiter := &fakeLimiter{allowed: false}
	router := rateLimitTestRouter(limiter, []string{"/health"})

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", rec.Code, rec.Body.String())
	}
	if limiter.calls != 0 {
		t.Fatalf("calls = %d", limiter.calls)
	}
}

func rateLimitTestRouter(limiter Limiter, excluded []string) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(RequestID())
	router.Use(RateLimit(
		RateLimitConfig{
			Enabled:       true,
			ExcludedPaths: excluded,
		},
		limiter,
		slog.New(slog.NewTextHandler(io.Discard, nil)),
		metrics.NewRecorder(),
	))
	router.GET("/health", func(c *gin.Context) {
		c.String(http.StatusOK, "ok")
	})
	router.POST("/chat/:npc_id", func(c *gin.Context) {
		c.String(http.StatusOK, "ok")
	})
	return router
}
