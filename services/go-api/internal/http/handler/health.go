package handler

import (
	"context"
	"net"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"npc-agent-backend/services/go-api/internal/agentclient"
	"npc-agent-backend/services/go-api/internal/config"
)

const serviceVersion = "0.1.0"

type HealthHandler struct {
	cfg         config.Config
	agent       *agentclient.Client
	redisClient *redis.Client
}

type dependencyHealth struct {
	Addr       string `json:"addr,omitempty"`
	Configured bool   `json:"configured"`
	Reachable  bool   `json:"reachable"`
	Error      string `json:"error,omitempty"`
}

type healthResponse struct {
	Status           string                    `json:"status"`
	Service          string                    `json:"service"`
	Version          string                    `json:"version"`
	RequestTimeoutMS int64                     `json:"request_timeout_ms"`
	PythonRuntime    agentclient.RuntimeHealth `json:"python_runtime"`
	Redis            dependencyHealth          `json:"redis"`
	DB               dependencyHealth          `json:"db"`
}

func NewHealthHandler(cfg config.Config, agent *agentclient.Client, redisClient *redis.Client) *HealthHandler {
	return &HealthHandler{
		cfg:         cfg,
		agent:       agent,
		redisClient: redisClient,
	}
}

func (h *HealthHandler) Get(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), dependencyTimeout(h.cfg.RequestTimeout))
	defer cancel()

	pythonRuntime := agentclient.RuntimeHealth{Configured: false}
	if h.agent != nil {
		pythonRuntime = h.agent.CheckHealth(ctx)
	}
	redisStatus := h.checkRedis(ctx)
	dbStatus := h.checkDB(ctx)

	overallStatus := "ok"
	if !runtimeHealthy(pythonRuntime) ||
		(redisStatus.Configured && !redisStatus.Reachable) ||
		(dbStatus.Configured && !dbStatus.Reachable) {
		overallStatus = "degraded"
	}

	c.JSON(http.StatusOK, healthResponse{
		Status:           overallStatus,
		Service:          "go-api",
		Version:          serviceVersion,
		RequestTimeoutMS: h.cfg.RequestTimeoutMillis(),
		PythonRuntime:    pythonRuntime,
		Redis:            redisStatus,
		DB:               dbStatus,
	})
}

func runtimeHealthy(status agentclient.RuntimeHealth) bool {
	if !status.Configured || !status.Reachable {
		return false
	}
	if status.StatusCode < http.StatusOK || status.StatusCode >= http.StatusMultipleChoices {
		return false
	}
	return status.Status == "" || status.Status == "ok"
}

func (h *HealthHandler) checkRedis(ctx context.Context) dependencyHealth {
	status := dependencyHealth{
		Addr:       h.cfg.RedisAddr,
		Configured: h.cfg.RedisAddr != "",
	}
	if !status.Configured {
		return status
	}
	if h.redisClient == nil {
		status.Error = "redis client is not configured"
		return status
	}

	if err := h.redisClient.Ping(ctx).Err(); err != nil {
		status.Error = err.Error()
		return status
	}
	status.Reachable = true
	return status
}

func (h *HealthHandler) checkDB(ctx context.Context) dependencyHealth {
	status := dependencyHealth{
		Addr:       h.cfg.DBAddr,
		Configured: h.cfg.DBAddr != "",
	}
	if !status.Configured {
		return status
	}

	dialer := net.Dialer{}
	conn, err := dialer.DialContext(ctx, "tcp", h.cfg.DBAddr)
	if err != nil {
		status.Error = err.Error()
		return status
	}
	_ = conn.Close()
	status.Reachable = true
	return status
}

func dependencyTimeout(requestTimeout time.Duration) time.Duration {
	if requestTimeout <= 0 || requestTimeout > 2*time.Second {
		return 2 * time.Second
	}
	return requestTimeout
}
