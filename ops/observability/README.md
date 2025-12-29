# Observability (Prometheus + Grafana)

This folder is optional and intended for local/dev environments.

## Metrics endpoint

- Endpoint: `GET /api/metrics`
- Development: open by default
- Production: set `METRICS_TOKEN` and send `Authorization: Bearer <token>` (or `X-Metrics-Token`)

## Run locally

```bash
docker compose -f docker-compose.yml -f ops/observability/docker-compose.observability.yml up -d
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (default login `admin` / `admin`)

## Notes

- If you enable `METRICS_TOKEN` in production, update Prometheus config to send a bearer token (e.g., `bearer_token_file`).
- Slow query logging is disabled by default. Set `SLOW_QUERY_MS` to enable it.

