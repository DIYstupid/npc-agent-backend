package middleware

import (
	"context"
	"log/slog"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"

	"npc-agent-backend/services/go-api/internal/metrics"
)

type Limiter interface {
	Allow(ctx context.Context, key string) (bool, error)
}

type RateLimitConfig struct {
	Enabled       bool
	ExcludedPaths []string
}

func RateLimit(cfg RateLimitConfig, limiter Limiter, log *slog.Logger, recorder *metrics.Recorder) gin.HandlerFunc {
	if log == nil {
		log = slog.Default()
	}

	return func(c *gin.Context) {
		if !cfg.Enabled || limiter == nil || isRateLimitExcluded(c.Request.URL.Path, cfg.ExcludedPaths) {
			c.Next()
			return
		}

		key := "ip:" + c.ClientIP()
		allowed, err := limiter.Allow(c.Request.Context(), key)
		if err != nil {
			if recorder != nil {
				recorder.IncRateLimitError()
			}
			log.Error("rate_limit.redis_failed",
				slog.String("request_id", RequestIDValue(c)),
				slog.String("key", key),
				slog.String("error", err.Error()),
			)
			c.Next()
			return
		}
		if allowed {
			c.Next()
			return
		}

		c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
			"error": gin.H{
				"code":       "rate_limited",
				"message":    "too many requests",
				"request_id": RequestIDValue(c),
			},
		})
	}
}

func isRateLimitExcluded(path string, excludedPaths []string) bool {
	for _, excluded := range excludedPaths {
		if excluded == "" {
			continue
		}
		if path == excluded || strings.HasPrefix(path, strings.TrimRight(excluded, "/")+"/") {
			return true
		}
	}
	return false
}
