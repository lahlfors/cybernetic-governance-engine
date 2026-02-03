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
RUN pip install uv keyring keyrings.google-artifactregistry-auth && \
    uv export --no-emit-project --no-dev --no-hashes --format requirements-txt > requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install -e .

# Expose the port
ENV PORT=8080
EXPOSE 8080

# DEBUG: Check file content
RUN ls -R src

# Run the server
CMD ["python", "-m", "src.governed_financial_advisor.server"]
