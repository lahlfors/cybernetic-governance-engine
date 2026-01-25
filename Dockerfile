# Use python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies using uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt uvicorn fastapi google-auth google-cloud-aiplatform google-adk opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests

# Copy project files
COPY . .

# Expose the port
ENV PYTHONPATH="/app:/app/src"
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN ls -R src

# Run the server
CMD ["python", "src/server.py"]
