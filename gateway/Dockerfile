FROM golang:1.27 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /gateway ./cmd/agenmini-gateway
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /gateway /usr/local/bin/agenmini-gateway
ENV PORT=20128 DATA_DIR=/app/data HOST=0.0.0.0
ENTRYPOINT ["agenmini-gateway"]
