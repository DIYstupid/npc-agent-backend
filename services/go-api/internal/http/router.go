package httpserver

import (
	"log/slog"
	"net/http"
	_ "net/http/pprof"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"npc-agent-backend/services/go-api/internal/agentclient"
	"npc-agent-backend/services/go-api/internal/config"
	"npc-agent-backend/services/go-api/internal/http/handler"
	"npc-agent-backend/services/go-api/internal/http/middleware"
	"npc-agent-backend/services/go-api/internal/http/proxy"
	"npc-agent-backend/services/go-api/internal/metrics"
	"npc-agent-backend/services/go-api/internal/ratelimit"
)

func NewRouter(cfg config.Config, log *slog.Logger, agent *agentclient.Client, redisClient *redis.Client) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)

	metricsRecorder := metrics.NewRecorder()

	router := gin.New()
	router.Use(
		middleware.RequestID(),
		middleware.Recovery(log),
		middleware.Timeout(cfg.RequestTimeout),
		middleware.Metrics(metricsRecorder),
		middleware.AccessLog(log),
	)

	healthHandler := handler.NewHealthHandler(cfg, agent, redisClient)
	router.GET("/health", healthHandler.Get)
	if cfg.MetricsEnabled {
		router.GET("/metrics", gin.WrapH(metricsRecorder.Handler()))
	}
	if cfg.PprofEnabled {
		router.Any("/debug/pprof/*any", gin.WrapH(http.DefaultServeMux))
	}

	var limiter middleware.Limiter
	if redisClient != nil {
		limiter = ratelimit.NewRedisLimiter(redisClient, cfg.RateLimitRequests, cfg.RateLimitWindow)
	}
	router.Use(middleware.RateLimit(
		middleware.RateLimitConfig{
			Enabled:       cfg.RateLimitEnabled,
			ExcludedPaths: cfg.RateLimitExcluded,
		},
		limiter,
		log,
		metricsRecorder,
	))

	proxyHandler := proxy.New(agent, log)
	router.POST("/chat/:npc_id", proxyHandler.Chat)
	router.POST("/chat/:npc_id/stream", proxyHandler.ChatStream)

	return router
}
