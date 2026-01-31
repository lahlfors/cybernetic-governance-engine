#!/bin/bash
# Proxy localhost:8080 to the private Cloud Run UI service
# Useful if the public URL returns 403 Forbidden due to IAM policy failures.

# PID File to track the running proxy
PID_FILE=".proxy_ui.pid"

cleanup() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
      echo "🛑 Stopping existing proxy (PID: $PID)..."
      kill $PID
    else
      echo "🧹 Removing stale PID file..."
    fi
    rm "$PID_FILE"
  fi
}

# Handle 'stop' command
if [ "$1" == "stop" ]; then
  cleanup
  echo "✅ Proxy stopped."
  exit 0
fi

# Auto-cleanup before starting new instance
cleanup

PORT=${PORT:-8080}
echo "🚀 Starting Proxy to Financial Advisor UI..."
echo "🔗 Local URL: http://localhost:$PORT"

# Start in background to capture PID, but wait for it so script stays alive
gcloud run services proxy financial-advisor-ui \
  --project laah-cybernetics \
  --region us-central1 \
  --port $PORT &

PROXY_PID=$!
echo $PROXY_PID > "$PID_FILE"

# Trap interrupt to cleanup
trap "cleanup; exit" INT TERM EXIT

wait $PROXY_PID
