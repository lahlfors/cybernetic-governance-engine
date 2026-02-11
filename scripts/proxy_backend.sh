#!/bin/bash
# Proxy localhost:8081 to the Backend service
# Useful for running API tests against the deployed agent.

PORT=${PORT:-8081}
NAMESPACE="governance-stack"

SERVICE="service/governed-financial-advisor"

# Ensure kubectl is in path
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl could not be found. Please install it."
    exit 1
fi

echo "🚀 Starting Proxy to Backend Service on GKE..."
echo "🔗 Local URL: http://localhost:$PORT"
echo "ℹ️  Press Ctrl+C to stop."

# Port forward to service port 80 relative to the service 
# (The service maps 80 -> 8080 on container, so we forward to service port 80)
kubectl port-forward -n $NAMESPACE $SERVICE $PORT:80
