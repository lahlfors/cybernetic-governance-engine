apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: governance-stack
data:
  relay.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      batch:
        send_batch_size: 1000
        timeout: 1s

    exporters:
      otlphttp/langfuse:
        endpoint: "http://langfuse-web.governance-stack.svc.cluster.local:80/api/public/otel"
        headers:
          # Note: In a production environment, use Kubernetes Secrets.
          # For this configuration, we assume these environment variables are injected.
          Authorization: "Basic ${env:LANGFUSE_BASIC_AUTH}"

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlphttp/langfuse]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: governance-stack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
        - name: otel-collector
          image: otel/opentelemetry-collector-contrib:0.100.0
          args:
            - "--config=/conf/relay.yaml"
          env:
            - name: LANGFUSE_BASIC_AUTH
              valueFrom:
                secretKeyRef:
                  name: langfuse-secrets # Assuming a secret exists or will be created
                  key: basic-auth
                  optional: true 
          # We need to compute the basic auth if we have separate keys.
          # Alternatively, we can construct the auth header in the exporter if the collector supports it,
          # or use an init container/script to base64 encode them.
          # Assuming the environment has LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.
          volumeMounts:
            - name: otel-collector-config-vol
              mountPath: /conf
      volumes:
        - name: otel-collector-config-vol
          configMap:
            name: otel-collector-config
            items:
              - key: relay.yaml
                path: relay.yaml
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
  namespace: governance-stack
spec:
  selector:
    app: otel-collector
  ports:
    - name: grpc
      port: 4317
      targetPort: 4317
      protocol: TCP
    - name: http
      port: 4318
      targetPort: 4318
      protocol: TCP
  type: ClusterIP
