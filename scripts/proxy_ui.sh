#!/bin/bash
# Proxy localhost:8080 to the GKE UI service
# Useful for local testing of the deployed UI.

PORT=${PORT:-8080}
NAMESPACE="governance-stack"
SERVICE="service/financial-advisor-ui"

# Ensure kubectl is in path
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl could not be found. Please install it."
    exit 1
fi

echo "🚀 Starting Proxy to Financial Advisor UI on GKE..."
echo "🔗 Local URL: http://localhost:$PORT"
echo "ℹ️  Press Ctrl+C to stop."

# Port forward to service port 80
kubectl port-forward -n $NAMESPACE $SERVICE $PORT:80
