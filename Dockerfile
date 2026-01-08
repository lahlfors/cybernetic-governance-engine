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
RUN pip install --no-cache-dir . uvicorn fastapi google-auth google-cloud-aiplatform google-adk opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests

# Expose the port
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN cat financial_advisor/server.py

# Run the server
CMD ["python", "financial_advisor/server.py"]
