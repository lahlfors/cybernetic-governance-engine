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
            - name: REDIS_PORT
              value: "${REDIS_PORT}"
            - name: REDIS_HOST
              value: "${REDIS_HOST}"
            - name: REDIS_URL
              value: "redis://${REDIS_HOST}:${REDIS_PORT}"
            - name: VLLM_GATEWAY_URL
              value: "${VLLM_GATEWAY_URL}"
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "500m"
              memory: "1Gi"
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
