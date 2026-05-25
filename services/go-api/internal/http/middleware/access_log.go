package middleware

import (
	"log/slog"
	"time"

	"github.com/gin-gonic/gin"
)

func AccessLog(log *slog.Logger) gin.HandlerFunc {
	if log == nil {
		log = slog.Default()
	}

	return func(c *gin.Context) {
		startedAt := time.Now()
		c.Next()

		log.Info("http.access",
			slog.String("request_id", RequestIDValue(c)),
			slog.String("method", c.Request.Method),
			slog.String("path", c.Request.URL.Path),
			slog.Int("status", c.Writer.Status()),
			slog.Int("bytes", c.Writer.Size()),
			slog.Int64("elapsed_ms", time.Since(startedAt).Milliseconds()),
			slog.String("client_ip", c.ClientIP()),
		)
	}
}
