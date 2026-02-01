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
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/src"
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/src"
# Install specific packages first if needed for caching, or just install everything from pyproject.toml
# Installing kfp and other deps
RUN pip install --no-cache-dir kfp uvicorn fastapi google-auth google-cloud-aiplatform google-adk opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests && \
    pip install --no-cache-dir .

# Expose the port
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN ls -R src

# Run the server
CMD ["python", "-m", "src.governed_financial_advisor.server"]
