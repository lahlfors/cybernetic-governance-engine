# Use python 3.12 slim image
FROM python:3.12-slim

# Set working directory
# Set working directory
WORKDIR /app
ENV PYTHONPATH=/app

# Install system dependencies
# git is often needed for installing dependencies from git
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definition to cache dependency layer
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (much faster than pip)
# --system installs into the system python, avoiding venv complexity in container
RUN uv pip install --system --no-cache -r pyproject.toml && \
    uv pip install --system --no-cache \
    uvicorn fastapi "google-adk[extensions]" \
    opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace \
    opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests \
    spacy presidio-analyzer presidio-anonymizer && \
    python -m spacy download en_core_web_lg

# Copy project files
COPY . .

# Install project
RUN uv pip install --system -e .

# Expose the port
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN ls -R src && ls -R config

# Run the server
CMD ["python", "-m", "src.governed_financial_advisor.server"]
