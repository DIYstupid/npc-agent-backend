FROM golang:1.23-alpine AS build

WORKDIR /src

ARG GOPROXY=https://goproxy.cn,direct
ENV GOPROXY=${GOPROXY}

COPY services/go-api/go.mod services/go-api/go.sum ./
RUN go mod download

COPY services/go-api ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/go-api ./cmd/api

FROM alpine:3.20

RUN apk add --no-cache ca-certificates

COPY --from=build /out/go-api /usr/local/bin/go-api

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/go-api"]
