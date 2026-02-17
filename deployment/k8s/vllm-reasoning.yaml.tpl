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
  strategy:
    type: Recreate
  template:
    metadata:
      labels:
        app: vllm-reasoning
    spec:
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Equal"
        value: "present"
        effect: "NoSchedule"
      nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-l4
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - vllm-inference
            topologyKey: "kubernetes.io/hostname"
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        command: ["python3", "-m", "vllm.entrypoints.openai.api_server"]
        args:
        - "--model"
        - "casperhansen/deepseek-r1-distill-llama-8b-awq"
        - "--served-model-name"
        - "casperhansen/deepseek-r1-distill-llama-8b-awq"
        - "--max-model-len"
        - "8192"
        - "--dtype"
        - "half"
        - "--quantization"
        - "awq"
        - "--enforce-eager"

        - "--trust-remote-code"
        - "--enable-auto-tool-choice"
        - "--tool-call-parser"
        - "hermes"
        - "--port"
        - "8000"
        - "--gpu-memory-utilization"
        - "0.9"
        env:
        - name: HUGGING_FACE_HUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token-secret
              key: token
        readinessProbe:
          httpGet:
            path: /v1/models
            port: 8000
          initialDelaySeconds: 120
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /v1/models
            port: 8000
          initialDelaySeconds: 600
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 5
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
          requests:
            nvidia.com/gpu: 1
            memory: "16Gi"
            cpu: "2"
        volumeMounts:
        - name: dshm
          mountPath: /dev/shm
        - name: model-cache
          mountPath: /root/.cache/huggingface
      volumes:
      - name: dshm
        emptyDir:
          medium: Memory
          sizeLimit: "4Gi"
      - name: model-cache
        persistentVolumeClaim:
          claimName: model-cache-reasoning-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-reasoning
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
