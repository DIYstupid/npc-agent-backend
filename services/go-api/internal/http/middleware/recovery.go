package middleware

import (
	"fmt"
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"
)

func Recovery(log *slog.Logger) gin.HandlerFunc {
	if log == nil {
		log = slog.Default()
	}

	return gin.CustomRecovery(func(c *gin.Context, recovered any) {
		message := fmt.Sprintf("%v", recovered)
		log.Error("http.panic_recovered",
			slog.String("request_id", RequestIDValue(c)),
			slog.String("method", c.Request.Method),
			slog.String("path", c.Request.URL.Path),
			slog.String("error", message),
		)

		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
			"error": gin.H{
				"code":       "internal_error",
				"message":    "internal server error",
				"request_id": RequestIDValue(c),
			},
		})
	})
}
