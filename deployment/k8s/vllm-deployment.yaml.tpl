apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-inference
  namespace: governance-stack
  labels:
    app: vllm-inference
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-inference
  template:
    metadata:
      labels:
        app: vllm-inference
    spec:
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: "16Gi"  # vLLM requires large shared memory
        - name: model-cache
          hostPath:
            path: /mnt/models
            type: DirectoryOrCreate
      containers:
        - name: vllm
          image: ${IMAGE_NAME}
          imagePullPolicy: IfNotPresent
          resources:
            limits:
${RESOURCE_LIMITS}
              memory: "64Gi"
              cpu: "16"
            requests:
${RESOURCE_REQUESTS}
              memory: "32Gi"
              cpu: "12"
          volumeMounts:
            - mountPath: /dev/shm
              name: dshm
            - mountPath: /root/.cache/huggingface
              name: model-cache
          env:
            - name: HUGGING_FACE_HUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: hf-token-secret
                  key: token
${ENV_VARS}
          ports:
            - containerPort: 8000
              name: http
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 120
            periodSeconds: 15
          command:
            - "python3"
            - "-m"
            - "vllm.entrypoints.openai.api_server"
            - "--model"
            - "google/gemma-3-27b-it"
${ARGS}
            - "--gpu-memory-utilization"
            - "0.90"
            - "--max-model-len"
            - "8192"
            - "--enable-chunked-prefill"
            - "--disable-log-stats"
