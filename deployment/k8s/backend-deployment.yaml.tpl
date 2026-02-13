apiVersion: apps/v1
kind: Deployment
metadata:
  name: governed-financial-advisor
  namespace: governance-stack
  labels:
    app: governed-financial-advisor
spec:
  replicas: 1
  selector:
    matchLabels:
      app: governed-financial-advisor
  template:
    metadata:
      labels:
        app: governed-financial-advisor
    spec:
      serviceAccountName: financial-advisor-sa
      volumes:
        - name: policy-volume
          secret:
            secretName: finance-policy-rego
        - name: opa-config-volume
          secret:
            secretName: opa-configuration
      containers:
        # Main Agent Container
        - name: ingress-agent
          image: ${IMAGE_URI}
          imagePullPolicy: Always
          ports:
            - containerPort: 8080
          env:
            # --- Service Configuration ---
            - name: PORT
              value: "${PORT}"
            - name: DEPLOY_TIMESTAMP
              value: "${DEPLOY_TIMESTAMP}"

            # --- Infrastructure ---
            - name: GOOGLE_CLOUD_PROJECT
              value: "${GOOGLE_CLOUD_PROJECT}"
            - name: GOOGLE_CLOUD_LOCATION
              value: "${GOOGLE_CLOUD_LOCATION}"

            # --- Redis Session Management ---
            - name: REDIS_HOST
              value: "${REDIS_HOST}"
            - name: REDIS_PORT
              value: "${REDIS_PORT}"
            - name: REDIS_URL
              value: "redis://${REDIS_HOST}:${REDIS_PORT}"

            # --- Model Configuration (Tiered) ---
            - name: MODEL_FAST
              value: "${MODEL_FAST}"
            - name: MODEL_REASONING
              value: "${MODEL_REASONING}"
            - name: MODEL_CONSENSUS
              value: "${MODEL_CONSENSUS}"

            # --- vLLM Inference Endpoints ---
            - name: VLLM_BASE_URL
              value: "${VLLM_BASE_URL}"
            - name: VLLM_API_KEY
              value: "${VLLM_API_KEY}"
            - name: OPENAI_API_BASE
              value: "${VLLM_BASE_URL}"
            - name: OPENAI_API_KEY
              value: "${VLLM_API_KEY}"
            - name: VLLM_FAST_API_BASE
              value: "${VLLM_FAST_API_BASE}"
            - name: VLLM_REASONING_API_BASE
              value: "${VLLM_REASONING_API_BASE}"
            - name: VLLM_GATEWAY_URL
              value: "${VLLM_GATEWAY_URL}"

            # --- Policy Engine ---
            - name: OPA_URL
              value: "${OPA_URL}"

            # --- Langfuse (Hot Tier Observability) ---
            - name: LANGFUSE_PUBLIC_KEY
              value: "${LANGFUSE_PUBLIC_KEY}"
            - name: LANGFUSE_SECRET_KEY
              value: "${LANGFUSE_SECRET_KEY}"
            - name: LANGFUSE_HOST
              value: "${LANGFUSE_HOST}"

            # --- OpenTelemetry (Cold Tier) ---
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "${OTEL_EXPORTER_OTLP_ENDPOINT}"
            - name: OTEL_EXPORTER_OTLP_HEADERS
              value: "${OTEL_EXPORTER_OTLP_HEADERS}"
            - name: TRACE_SAMPLING_RATE
              value: "${TRACE_SAMPLING_RATE}"

            # --- Cold Tier Storage ---
            - name: COLD_TIER_GCS_BUCKET
              value: "${COLD_TIER_GCS_BUCKET}"
            - name: COLD_TIER_GCS_PREFIX
              value: "${COLD_TIER_GCS_PREFIX}"

            # --- Gateway Configuration ---
            - name: GATEWAY_HOST
              value: "${GATEWAY_HOST}"
            - name: GATEWAY_GRPC_PORT
              value: "${GATEWAY_GRPC_PORT}"

            # --- MCP Configuration ---
            - name: MCP_MODE
              value: "${MCP_MODE}"
            - name: ALPHAVANTAGE_API_KEY
              value: "${ALPHAVANTAGE_API_KEY}"

            # --- Secrets (from K8s Secrets) ---
            - name: HUGGING_FACE_HUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: hf-token-secret
                  key: token

          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "1000m"
              memory: "2Gi"

        # OPA Sidecar
        - name: opa
          image: openpolicyagent/opa:latest-static
          ports:
            - containerPort: 8181
          args:
            - "run"
            - "--server"
            - "--addr=localhost:8181"
            - "--config-file=/config/opa_config.yaml"
            - "/policies/finance_policy.rego"
          volumeMounts:
            - name: policy-volume
              mountPath: /policies/finance_policy.rego
              subPath: finance_policy.rego
              readOnly: true
            - name: opa-config-volume
              mountPath: /config
              readOnly: true
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "250m"
              memory: "256Mi"

---
apiVersion: v1
kind: Service
metadata:
  name: governed-financial-advisor
  namespace: governance-stack
spec:
  type: LoadBalancer
  selector:
    app: governed-financial-advisor
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080
