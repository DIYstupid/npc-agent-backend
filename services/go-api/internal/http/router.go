package httpserver

import (
	"log/slog"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"npc-agent-backend/services/go-api/internal/agentclient"
	"npc-agent-backend/services/go-api/internal/config"
	"npc-agent-backend/services/go-api/internal/http/handler"
	"npc-agent-backend/services/go-api/internal/http/middleware"
	"npc-agent-backend/services/go-api/internal/http/proxy"
)

func NewRouter(cfg config.Config, log *slog.Logger, agent *agentclient.Client, redisClient *redis.Client) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)

	router := gin.New()
	router.Use(
		middleware.RequestID(),
		middleware.Recovery(log),
		middleware.Timeout(cfg.RequestTimeout),
		middleware.AccessLog(log),
	)

	healthHandler := handler.NewHealthHandler(cfg, agent, redisClient)
	router.GET("/health", healthHandler.Get)

	proxyHandler := proxy.New(agent, log)
	router.POST("/chat/:npc_id", proxyHandler.Chat)
	router.POST("/chat/:npc_id/stream", proxyHandler.ChatStream)

	return router
}
