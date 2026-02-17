apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}
  namespace: governance-stack
  labels:
    app: ${APP_NAME}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${APP_NAME}
  template:
    metadata:
      labels:
        app: ${APP_NAME}
    spec:
      serviceAccountName: financial-advisor-sa
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: "16Gi"  # vLLM requires large shared memory
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
          env:

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
            - "--host"
            - "0.0.0.0"
            - "--port"
            - "8000"
${ARGS}
      nodeSelector:
${NODE_SELECTOR}
      tolerations:
${TOLERATIONS}
