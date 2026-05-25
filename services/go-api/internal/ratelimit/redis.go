package ratelimit

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

const defaultPrefix = "go-api:rate_limit"

type RedisLimiter struct {
	client *redis.Client
	limit  int
	window time.Duration
	prefix string
}

func NewRedisLimiter(client *redis.Client, limit int, window time.Duration) *RedisLimiter {
	return &RedisLimiter{
		client: client,
		limit:  limit,
		window: window,
		prefix: defaultPrefix,
	}
}

func (l *RedisLimiter) Allow(ctx context.Context, key string) (bool, error) {
	if l == nil || l.client == nil || l.limit <= 0 || l.window <= 0 {
		return true, nil
	}

	windowID := time.Now().UnixNano() / l.window.Nanoseconds()
	redisKey := fmt.Sprintf("%s:%s:%d", l.prefix, key, windowID)

	pipe := l.client.TxPipeline()
	count := pipe.Incr(ctx, redisKey)
	pipe.Expire(ctx, redisKey, l.window)
	if _, err := pipe.Exec(ctx); err != nil {
		return true, err
	}

	return count.Val() <= int64(l.limit), nil
}
