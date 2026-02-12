#!/bin/bash
# Proxy script for Financial Advisor UI

echo "🔍 Finding UI Service in namespace 'governance-stack'..."
POD=$(kubectl get pod -n governance-stack -l app=financial-advisor-ui -o jsonpath="{.items[0].metadata.name}")

if [ -z "$POD" ]; then
    echo "❌ UI Pod not found! Is it deployed?"
    exit 1
fi

echo "✅ Found UI Pod: $POD"
echo "🚀 Port-forwarding to http://localhost:8080..."
echo "Press Ctrl+C to stop."

kubectl port-forward -n governance-stack pod/$POD 8080:8501
