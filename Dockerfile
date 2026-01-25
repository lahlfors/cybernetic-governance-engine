# Use python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install dependencies
# Set PYTHONPATH to include src
# Set PYTHONPATH to include /app so 'from src...' imports work
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/src"

RUN pip install uv && \
    uv export --no-emit-project --no-dev --no-hashes --format requirements-txt > requirements.txt && \
    pip install kfp && \
    pip install --no-cache-dir -r requirements.txt uvicorn fastapi google-auth google-cloud-aiplatform google-adk opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests

# Expose the port
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN ls -R src

# Run the server
CMD ["python", "src/server.py"]
