apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-reasoning
  namespace: governance-stack
  labels:
    app: vllm-reasoning
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-reasoning
  template:
    metadata:
      labels:
        app: vllm-reasoning
    spec:
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: "32Gi"
        - name: model-cache
          emptyDir: {}
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          imagePullPolicy: IfNotPresent
          resources:
            limits:
              nvidia.com/gpu: "${TP_SIZE_REASONING}"
              memory: "64Gi"
              cpu: "16"
            requests:
              nvidia.com/gpu: "${TP_SIZE_REASONING}"
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
            - name: PORT
              value: "8000"

          ports:
            - containerPort: 8000
              name: http
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 120
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 300
            periodSeconds: 15
          command:
            - "python3"
            - "-m"
            - "vllm.entrypoints.openai.api_server"
            - "--model"
            - "${MODEL_REASONING}"
            - "--served-model-name"
            - "${MODEL_REASONING}"
            - "--dtype"
            - "auto"
            - "--enable-prefix-caching"
            - "--max-model-len"
            - "8192"
            - "--enforce-eager"
            - "--tensor-parallel-size"
            - "${TP_SIZE_REASONING}"
            - "--gpu-memory-utilization"
            - "0.90"
            - "--disable-log-stats"
      nodeSelector:
        cloud.google.com/gke-accelerator: "nvidia-l4"
      tolerations:
      - key: "cloud.google.com/gke-spot"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
      - key: "nvidia.com/gpu"
        operator: "Equal"
        value: "present"
        effect: "NoSchedule"
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-reasoning-service
  namespace: governance-stack
spec:
  selector:
    app: vllm-reasoning
  ports:
  - port: 8000
    targetPort: 8000
    protocol: TCP
    name: http
  type: ClusterIP
