#!/bin/bash
# Proxy localhost:8080 to the private Cloud Run UI service
# Useful if the public URL returns 403 Forbidden due to IAM policy failures.

echo "🚀 Starting Proxy to Financial Advisor UI..."
echo "🔗 Local URL: http://localhost:8080"

gcloud run services proxy financial-advisor-ui \
  --project laah-cybernetics \
  --region northamerica-northeast2 \
  --port 8080
