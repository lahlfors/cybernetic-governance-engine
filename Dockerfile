# Dockerfile
# Unified Dockerfile for Backend and Agent
# Installs all dependencies from pyproject.toml

FROM python:3.11-slim

# 1. Install System Dependencies
# nemoguardrails often needs build-essential, and potentially others.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy Project Files
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
# Copy any other needed files (e.g. README if pyproject checks it)
COPY README.md . 

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. Install Python Dependencies
# Use uv for faster resolution
RUN uv pip install --system . openai nemoguardrails presidio-analyzer presidio-anonymizer spacy

# Download Spacy Model for Presidio
RUN python -m spacy download en_core_web_sm

# 4. Environment
ENV PORT=8080
ENV PYTHONPATH=/app

# 5. Default Entrypoint (Can be overridden by Cloud Run command)
# Default to running the server (Backend)
CMD ["python", "-m", "src.governed_financial_advisor.server"]
