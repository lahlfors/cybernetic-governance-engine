apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway
  namespace: governance-stack
  labels:
    app: gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gateway
  template:
    metadata:
      labels:
        app: gateway
    spec:
      serviceAccountName: financial-advisor-sa # Needs access to Firestore/etc if applicable, or same SA
      volumes:
        - name: policy-volume
          secret:
            secretName: finance-policy-rego
        - name: opa-config-volume
          secret:
            secretName: opa-configuration
      containers:
        - name: gateway
          image: ${GATEWAY_IMAGE_URI}
          imagePullPolicy: Always
          ports:
            - containerPort: 8080
              name: http
            - containerPort: 50051
              name: grpc
          env:
            - name: PORT
              value: "8080"
            - name: GATEWAY_GRPC_PORT
              value: "50051"
            - name: GOOGLE_CLOUD_PROJECT
              value: "${GOOGLE_CLOUD_PROJECT}"
            - name: GOOGLE_CLOUD_LOCATION
              value: "${GOOGLE_CLOUD_LOCATION}"
            - name: ENABLE_LOGGING
              value: "${ENABLE_LOGGING}"
            - name: OTEL_TRACES_EXPORTER
              value: "none"
            - name: REDIS_PORT
              value: "${REDIS_PORT}"
            - name: REDIS_HOST
              value: "${REDIS_HOST}"
            - name: REDIS_URL
              value: "redis://${REDIS_HOST}:${REDIS_PORT}"
            - name: VLLM_BASE_URL
              value: "${VLLM_BASE_URL}"
            - name: VLLM_GATEWAY_URL
              value: "${VLLM_GATEWAY_URL}"
            - name: VLLM_REASONING_API_BASE
              value: "${VLLM_REASONING_API_BASE}"
            - name: VLLM_FAST_API_BASE
              value: "${VLLM_FAST_API_BASE}"
            - name: GUARDRAILS_MODEL_NAME
              value: "${GUARDRAILS_MODEL_NAME}"
            # --- LangSmith ---
            - name: LANGSMITH_TRACING
              value: "${LANGSMITH_TRACING}"
            - name: LANGSMITH_ENDPOINT
              value: "${LANGSMITH_ENDPOINT}"
            - name: LANGSMITH_API_KEY
              value: "${LANGSMITH_API_KEY}"
            - name: LANGSMITH_PROJECT
              value: "${LANGSMITH_PROJECT}"
            - name: LANGCHAIN_TRACING_V2
              value: "${LANGCHAIN_TRACING_V2}"
            - name: LANGCHAIN_ENDPOINT
              value: "${LANGSMITH_ENDPOINT}"
            - name: LANGCHAIN_API_KEY
              value: "${LANGSMITH_API_KEY}"
            - name: LANGCHAIN_PROJECT
              value: "${LANGCHAIN_PROJECT}"
            # OPA Configuration
            - name: OPA_URL
              value: "http://localhost:8181/v1/data/finance/allow"
          resources:
            requests:
              cpu: "1000m"
              memory: "2Gi"
            limits:
              cpu: "2000m"
              memory: "4Gi"

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
  name: gateway
  namespace: governance-stack
spec:
  selector:
    app: gateway
  ports:
    - name: http
      protocol: TCP
      port: 8080
      targetPort: 8080
    - name: grpc
      protocol: TCP
      port: 50051
      targetPort: 50051
  type: ClusterIP
