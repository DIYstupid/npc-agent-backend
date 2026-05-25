package middleware

import (
	"time"

	"github.com/gin-gonic/gin"

	"npc-agent-backend/services/go-api/internal/metrics"
)

func Metrics(recorder *metrics.Recorder) gin.HandlerFunc {
	return func(c *gin.Context) {
		if recorder == nil {
			c.Next()
			return
		}

		startedAt := time.Now()
		recorder.IncInFlight()
		defer recorder.DecInFlight()
		defer func() {
			path := c.FullPath()
			if path == "" {
				path = c.Request.URL.Path
			}
			recorder.ObserveRequest(
				c.Request.Method,
				path,
				c.Writer.Status(),
				time.Since(startedAt),
			)
		}()

		c.Next()
	}
}
