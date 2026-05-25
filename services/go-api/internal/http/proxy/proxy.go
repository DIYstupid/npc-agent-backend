package proxy

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"

	"github.com/gin-gonic/gin"

	"npc-agent-backend/services/go-api/internal/http/middleware"
)

type AgentClient interface {
	Do(ctx context.Context, method string, path string, query url.Values, body io.Reader, headers http.Header) (*http.Response, error)
}

type Handler struct {
	client AgentClient
	log    *slog.Logger
}

func New(client AgentClient, log *slog.Logger) *Handler {
	if log == nil {
		log = slog.Default()
	}
	return &Handler{
		client: client,
		log:    log,
	}
}

func (h *Handler) Chat(c *gin.Context) {
	npcID := c.Param("npc_id")
	h.forward(c, "/chat/"+url.PathEscape(npcID), false)
}

func (h *Handler) ChatStream(c *gin.Context) {
	npcID := c.Param("npc_id")
	h.forward(c, "/chat/"+url.PathEscape(npcID)+"/stream", true)
}

func (h *Handler) forward(c *gin.Context, path string, stream bool) {
	if h.client == nil {
		writeProxyError(c, http.StatusBadGateway, "python_runtime_not_configured", "python runtime client is not configured")
		return
	}

	headers := forwardedHeaders(c.Request.Header)
	headers.Set(middleware.RequestIDHeader, middleware.RequestIDValue(c))

	resp, err := h.client.Do(c.Request.Context(), c.Request.Method, path, c.Request.URL.Query(), c.Request.Body, headers)
	if err != nil {
		h.writeClientError(c, err)
		return
	}
	defer resp.Body.Close()

	copyResponseHeaders(c.Writer.Header(), resp.Header)

	contentType := resp.Header.Get("Content-Type")
	if stream && resp.StatusCode >= 200 && resp.StatusCode < 300 && strings.HasPrefix(contentType, "text/event-stream") {
		h.copyStream(c, resp)
		return
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.writeClientError(c, err)
		return
	}
	c.Data(resp.StatusCode, contentType, body)
}

func (h *Handler) copyStream(c *gin.Context, resp *http.Response) {
	c.Status(resp.StatusCode)
	c.Writer.WriteHeaderNow()

	flusher, _ := c.Writer.(http.Flusher)
	buf := make([]byte, 32*1024)

	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, err := c.Writer.Write(buf[:n]); err != nil {
				h.log.Info("proxy.stream_client_disconnected",
					slog.String("request_id", middleware.RequestIDValue(c)),
					slog.String("error", err.Error()),
				)
				return
			}
			if flusher != nil {
				flusher.Flush()
			}
		}
		if readErr != nil {
			if !errors.Is(readErr, io.EOF) {
				h.log.Error("proxy.stream_read_failed",
					slog.String("request_id", middleware.RequestIDValue(c)),
					slog.String("error", readErr.Error()),
				)
			}
			return
		}
	}
}

func (h *Handler) writeClientError(c *gin.Context, err error) {
	if errors.Is(err, context.DeadlineExceeded) || errors.Is(c.Request.Context().Err(), context.DeadlineExceeded) {
		writeProxyError(c, http.StatusGatewayTimeout, "python_runtime_timeout", "python runtime timed out")
		return
	}

	h.log.Error("proxy.python_runtime_failed",
		slog.String("request_id", middleware.RequestIDValue(c)),
		slog.String("error", err.Error()),
	)
	writeProxyError(c, http.StatusBadGateway, "python_runtime_error", err.Error())
}

func writeProxyError(c *gin.Context, status int, code string, message string) {
	c.AbortWithStatusJSON(status, gin.H{
		"error": gin.H{
			"code":       code,
			"message":    message,
			"request_id": middleware.RequestIDValue(c),
		},
	})
}

func forwardedHeaders(src http.Header) http.Header {
	dst := make(http.Header, len(src)+1)
	for key, values := range src {
		if skipForwardHeader(key) {
			continue
		}
		for _, value := range values {
			dst.Add(key, value)
		}
	}
	return dst
}

func copyResponseHeaders(dst http.Header, src http.Header) {
	for key, values := range src {
		if skipForwardHeader(key) {
			continue
		}
		for _, value := range values {
			dst.Add(key, value)
		}
	}
}

func skipForwardHeader(key string) bool {
	switch strings.ToLower(key) {
	case "connection", "content-length", "host", "transfer-encoding":
		return true
	default:
		return false
	}
}
