# Dockerfile for NeMo Guardrails Service
FROM python:3.11-slim

# Install System Deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python Deps
ENV PIP_DEFAULT_TIMEOUT=100
# Explicitly install nemoguardrails and dependencies
RUN uv pip install --system \
    "nemoguardrails>=0.17.0" \
    "google-adk>=1.0.0" \
    "openai>=1.0.0" \
    "fastapi>=0.110.0" \
    "uvicorn>=0.29.0" \
    "pydantic>=2.0.0" \
    "google-cloud-aiplatform" \
    "langchain-google-vertexai"

# Copy Service Code
# We expect the context to be the root of the repo, so we copy src/nemo_service
COPY src/nemo_service/ /app/src/nemo_service/
COPY config/ /app/config/

# Copy Rails Config (Assumes it's in src/governed_financial_advisor/governance/rails or we will copy it to src/nemo_service/rails)
# We will ensure rails are copied to /app/src/nemo_service/rails
# For now, let's assume we copy the 'config' directory from the repo if needed,
# but the plan is to have rails inside src/nemo_service/rails.
# We will rely on the user copying rails to src/nemo_service/rails OR mapping it.

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Entrypoint
CMD ["python", "-m", "src.nemo_service.main"]
