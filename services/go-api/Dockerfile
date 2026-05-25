FROM golang:1.23-alpine AS build

WORKDIR /src

COPY services/go-api ./
RUN CGO_ENABLED=0 GOOS=linux go build -mod=vendor -o /out/go-api ./cmd/api

FROM alpine:3.20

RUN apk add --no-cache ca-certificates

COPY --from=build /out/go-api /usr/local/bin/go-api

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/go-api"]
