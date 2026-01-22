# Use python 3.12 slim image
# Note: User recommended python:3.10-bookworm for broad compatibility, but 3.12-slim is often fine for wasmtime wheels.
# Sticking to slim but keeping build-essential which is already there.
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including OPA for policy compilation
# build-essential is critical for compiling C-extensions if wheels are missing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install OPA CLI for compiling Rego to WASM
RUN curl -L -o /usr/local/bin/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static && \
    chmod +x /usr/local/bin/opa

# Copy project files
COPY . .

# Compile Rego policy to WASM
RUN opa build -t wasm -e finance/allow src/governance/policy/finance_policy.rego && \
    tar -xzf bundle.tar.gz && \
    mv /policy.wasm /app/policy.wasm && \
    rm -f bundle.tar.gz

# Install dependencies
# Set PYTHONPATH to include src
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/src"

# Add wasmtime to requirements
RUN pip install uv && \
    uv export --no-emit-project --no-dev --no-hashes --format requirements-txt > requirements.txt && \
    # Explicitly add wasmtime as a production dependency
    echo "wasmtime>=18.0.0" >> requirements.txt && \
    pip install --no-cache-dir -r requirements.txt uvicorn fastapi google-auth google-cloud-aiplatform google-adk opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests

# Expose the port
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN ls -R src

# Run the server
CMD ["python", "src/server.py"]
