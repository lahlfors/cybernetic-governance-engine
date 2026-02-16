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
      serviceAccountName: financial-advisor-sa
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: "16Gi"  # vLLM requires large shared memory
        # - name: model-cache
        #   persistentVolumeClaim:
        #     claimName: model-cache-fast-pvc
      containers:
        - name: vllm
          # Ensure image has runai extensions: pip install vllm[runai]
          image: ${IMAGE_NAME}
          imagePullPolicy: IfNotPresent
          resources:
            limits:
${RESOURCE_LIMITS}
              memory: "64Gi"
              cpu: "16"
            requests:
${RESOURCE_REQUESTS}
              memory: "10Gi"
              cpu: "3"
          volumeMounts:
            - mountPath: /dev/shm
              name: dshm
            # - mountPath: /root/.cache/huggingface
            #   name: model-cache
          env:
            - name: HUGGING_FACE_HUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: hf-token-secret
                  key: token
            # Run:ai Streamer Configuration for GCS
            - name: RUNAI_STREAMER_S3_USE_VIRTUAL_ADDRESSING
              value: "0"
            - name: AWS_ENDPOINT_URL
              value: "https://storage.googleapis.com"
            - name: AWS_EC2_METADATA_DISABLED
              value: "true"
${ENV_VARS}
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
            initialDelaySeconds: 600
            periodSeconds: 15
          command:
            - "vllm"
            - "serve"
            - "${MODEL_PATH}" # e.g. gs://bucket/model
            - "--load-format"
            - "runai_streamer"
            - "--port"
            - "8000"
${ARGS}
      nodeSelector:
${NODE_SELECTOR}
      tolerations:
${TOLERATIONS}
