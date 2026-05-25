package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	"npc-agent-backend/services/go-api/internal/agentclient"
	"npc-agent-backend/services/go-api/internal/config"
	httpserver "npc-agent-backend/services/go-api/internal/http"
	"npc-agent-backend/services/go-api/internal/logger"
)

func main() {
	cfg := config.Load()
	log := logger.New()

	agent := agentclient.New(cfg.PythonRuntimeBaseURL, cfg.RequestTimeout)

	var redisClient *redis.Client
	if cfg.RedisAddr != "" {
		redisClient = redis.NewClient(&redis.Options{Addr: cfg.RedisAddr})
		defer redisClient.Close()
	}

	router := httpserver.NewRouter(cfg, log, agent, redisClient)
	server := &http.Server{
		Addr:              cfg.GoAPIAddr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       cfg.RequestTimeout + 5*time.Second,
		WriteTimeout:      cfg.RequestTimeout + 5*time.Second,
		IdleTimeout:       60 * time.Second,
	}

	errCh := make(chan error, 1)
	go func() {
		log.Info("go_api.starting",
			slog.String("addr", cfg.GoAPIAddr),
			slog.String("python_runtime_base_url", cfg.PythonRuntimeBaseURL),
			slog.String("redis_addr", cfg.RedisAddr),
			slog.String("db_addr", cfg.DBAddr),
			slog.Bool("rate_limit_enabled", cfg.RateLimitEnabled),
			slog.Int("rate_limit_requests", cfg.RateLimitRequests),
			slog.Int64("rate_limit_window_seconds", int64(cfg.RateLimitWindow.Seconds())),
		)
		errCh <- server.ListenAndServe()
	}()

	stopCh := make(chan os.Signal, 1)
	signal.Notify(stopCh, os.Interrupt, syscall.SIGTERM)

	select {
	case sig := <-stopCh:
		log.Info("go_api.shutdown_signal", slog.String("signal", sig.String()))
	case err := <-errCh:
		if !errors.Is(err, http.ErrServerClosed) {
			log.Error("go_api.listen_failed", slog.String("error", err.Error()))
			os.Exit(1)
		}
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Error("go_api.shutdown_failed", slog.String("error", err.Error()))
		os.Exit(1)
	}
	log.Info("go_api.stopped")
}
