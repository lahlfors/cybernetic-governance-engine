# Deploying Langfuse v3 on GKE

This directory contains the configuration for deploying a self-hosted Langfuse v3 stack on Google Kubernetes Engine (GKE).

## Architecture

The Langfuse v3 deployment on GKE consists of:

*   **Langfuse Web**: Next.js frontend and API server (`langfuse-web`).
*   **Langfuse Worker**: Asynchronous event processor (`langfuse-worker`).
*   **OpenTelemetry Collector**: Receives traces from the Gateway and exports to Langfuse via OTLP (`otel-collector`).
*   **ClickHouse**: OLAP database for high-volume trace data (Single-node statefulset).
*   **MinIO**: S3-compatible object storage for raw event ingestion (Required for v3).
*   **Redis**: Queue and caching (shared with other services).
*   **PostgreSQL**: Metadata storage (Cloud SQL via `advisor-secrets`).

## Prerequisites

1.  **GKE Cluster**: A running GKE cluster.
2.  **Secret Manager**: Secrets must be populated in `advisor-secrets`.
3.  **kubectl**: Configured to point to your cluster.

## Deployment

The deployment is managed via the main `deployment/deploy_sw.py` script, but can be applied manually:

```bash
kubectl apply -f deployment/k8s/minio.yaml
kubectl apply -f deployment/k8s/langfuse-db.yaml
kubectl apply -f deployment/k8s/langfuse-web.yaml
kubectl apply -f deployment/k8s/langfuse-worker.yaml
```

## MinIO Configuration

Langfuse v3 **requires** S3-compatible storage. We use a self-hosted MinIO instance for this purpose to keep costs low and avoid external dependencies for development environments.

*   **Bucket**: `langfuse-events` (Automatically created by `mc-setup` job or manual setup).
*   **Access**: Internal only via `http://minio.governance-stack.svc.cluster.local:9000`.

## Accessing Langfuse

Port-forward the web service to access the UI:

```bash
kubectl port-forward svc/langfuse-web 3000:80 -n governance-stack
```

Visit `http://localhost:3000`.

## Troubleshooting

*   **500 Errors on Startup**: Check `REDIS_HOST` and `REDIS_PORT` env vars.
*   **Ingestion Hangs**: Verify MinIO connectivity and that the `langfuse-events` bucket exists.
*   **ClickHouse Connection**: Ensure `advisor-secrets` has the correct `CLICKHOUSE_PASSWORD`.
