---
description: Deploy the Cybernetic Governance Engine to Google Cloud Run
---

# Deployment Workflow

This workflow deploys the backend and UI services to Google Cloud Run.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Project ID: `laah-cybernetics` (configured in `.env`)
- Required permissions for Cloud Run, Secret Manager, and Redis

## Steps

### 1. Sync dependencies (optional, if virtual environment needs updating)

This project is configured to use public PyPI exclusively. All dependencies including `google-adk` are available on public PyPI.

// turbo
```bash
uv sync --group deployment
```

**Note**: The project now uses only public PyPI, eliminating all authentication issues with private Google registries.

### 2. Run the deployment script

```bash
source .venv/bin/activate && python deployment/deploy_all.py --project-id laah-cybernetics
```

**Available options**:
- `--project-id`: GCP project ID (required)
- `--region`: GCP region (default: us-central1)
- `--service-name`: Backend service name (default: governed-financial-advisor)
- `--ui-service-name`: UI service name (default: governed-financial-advisor-ui)
- `--skip-build`: Skip container image building
- `--skip-redis`: Skip Redis provisioning
- `--skip-ui`: Skip UI deployment
- `--redis-host`: Redis host (if using existing instance)
- `--redis-port`: Redis port (if using existing instance)
- `--redis-instance-name`: Redis instance name

### 3. Verify deployment

The script will output the URLs for both the backend and UI services. Check the deployment status:

```bash
gcloud run services describe governed-financial-advisor --region us-central1 --project laah-cybernetics
gcloud run services describe governed-financial-advisor-ui --region us-central1 --project laah-cybernetics
```

## What the deployment script does

1. **Provisions Redis**: Creates a Memorystore Redis instance if not skipped
2. **Manages Secrets**: Stores configuration in Secret Manager
3. **Builds Container Images**: Builds and pushes Docker images for backend and UI
4. **Deploys to Cloud Run**: Deploys both services with appropriate configuration

## Troubleshooting

### Missing module errors
If you encounter `ModuleNotFoundError` for deployment dependencies, run:
```bash
uv sync --group deployment
```

### Authentication issues
If deployment commands fail with authentication errors, run:
```bash
gcloud auth login
gcloud auth application-default login
```

### Dependency resolution issues
The project is configured to use public PyPI exclusively. If you encounter dependency resolution errors, ensure:
1. `pip.conf` exists in the project root and points to `https://pypi.org/simple`
2. `[tool.uv]` section in `pyproject.toml` has `index-url = "https://pypi.org/simple"`

