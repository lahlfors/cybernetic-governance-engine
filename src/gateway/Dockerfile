FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definition
COPY pyproject.toml .

# Create virtual env and install dependencies
RUN uv venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies from pyproject.toml
RUN uv export --no-emit-project --no-dev --no-hashes --format requirements-txt > requirements.txt && \
    uv pip install -r requirements.txt

# Copy Source Code
COPY src/gateway /app/src/gateway
COPY src/governed_financial_advisor /app/src/governed_financial_advisor
COPY config /app/config

# Environment Variables
ENV PYTHONUNBUFFERED=1
ENV PORT=50051
# Fix for imports: Ensure /app is in PYTHONPATH so absolute imports from 'src' work
ENV PYTHONPATH=/app

# Expose port (gRPC standard)
EXPOSE 50051

# Run the gRPC Gateway server
CMD ["python", "src/gateway/server/main.py"]
