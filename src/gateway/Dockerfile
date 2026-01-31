FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# gcc and python3-dev might be needed for some grpc extensions or other libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management (keeping consistent with repo)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definition
COPY pyproject.toml .
# Copy lock file if it exists, otherwise we generate
# COPY uv.lock .

# Create virtual env and install dependencies
# We need grpcio, grpcio-tools, google-genai, openai, httpx, pydantic, opentelemetry-api, python-json-logger, google-auth
# We can use `uv sync` if we have the full project structure or just install specifically.
# Since this is a dedicated container, installing specifically is cleaner/smaller.
RUN uv venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

RUN uv pip install \
    grpcio \
    grpcio-tools \
    google-genai \
    openai \
    httpx \
    pydantic \
    opentelemetry-api \
    python-json-logger \
    google-auth \
    google-cloud-run-v2 \
    python-dotenv

# Copy Source Code
# We need src/gateway and src/governed_financial_advisor (for shared governance logic imports)
COPY src/gateway /app/src/gateway
COPY src/governed_financial_advisor /app/src/governed_financial_advisor
COPY config /app/config

# Environment Variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port (Cloud Run uses 8080 by default)
EXPOSE 8080

# Run the server
CMD ["python", "src/gateway/server/main.py"]
