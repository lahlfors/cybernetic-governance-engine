# Deploying Langfuse on Google Cloud Run

This guide explains how to deploy a self-hosted Langfuse instance on Google Cloud Run using `gcloud`.

## Prerequisites

1.  **Google Cloud SDK**: Ensure `gcloud` is installed and authenticated.
2.  **PostgreSQL Database**: You need a PostgreSQL database (e.g., Cloud SQL). Note the connection string (`postgresql://user:password@host:5432/dbname`).
3.  **Secrets**: You need to create secrets in Secret Manager for sensitive configuration.

## Setup Steps

### 1. Create Secrets

Run the following commands to create the necessary secrets in Google Secret Manager. Replace the values with your actual secrets.

```bash
# Database Connection String
echo -n "postgresql://user:password@host:5432/langfuse" | gcloud secrets create langfuse-database-url --data-file=-
# Or if you already have it:
# gcloud secrets versions add langfuse-database-url --data-file=-

# Generate Random Secrets
openssl rand -base64 32 | gcloud secrets create langfuse-nextauth-secret --data-file=-
openssl rand -base64 32 | gcloud secrets create langfuse-salt --data-file=-
openssl rand -base64 32 | gcloud secrets create langfuse-encryption-key --data-file=-
```

### 2. Grant Access to Secrets

The Cloud Run service account needs permission to access these secrets.

```bash
SERVICE_ACCOUNT=$(gcloud run services describe langfuse-server --format 'value(spec.template.spec.serviceAccountName)' || echo "default-compute@developer.gserviceaccount.com")
# Note: For initial deployment, use the default compute service account or create one first.

# Grant Secret Accessor role to the service account for all secrets created above.
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"
```

### 3. Deploy Langfuse Service

Apply the `service.yaml` configuration:

```bash
gcloud run services replace service.yaml
```

Alternatively, deploy using `gcloud run deploy`:

```bash
gcloud run deploy langfuse-server \
    --image langfuse/langfuse:latest \
    --region us-central1 \
    --set-secrets="DATABASE_URL=langfuse-database-url:latest,NEXTAUTH_SECRET=langfuse-nextauth-secret:latest,SALT=langfuse-salt:latest,ENCRYPTION_KEY=langfuse-encryption-key:latest" \
    --set-env-vars="NEXTAUTH_URL=https://langfuse-server-uc.a.run.app,TELEMETRY_ENABLED=false,LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=true"
```

### 4. Post-Deployment Configuration

1.  **Update NEXTAUTH_URL**: After deployment, get the actual service URL and update the `NEXTAUTH_URL` environment variable if it differs from the placeholder.
    ```bash
    SERVICE_URL=$(gcloud run services describe langfuse-server --format 'value(status.url)')
    gcloud run services update langfuse-server --update-env-vars NEXTAUTH_URL=$SERVICE_URL
    ```

2.  **Create API Keys**:
    - Access the Langfuse dashboard at the service URL.
    - Create a new project.
    - Generate public/secret API keys.
    - Update your application configuration (e.g., `deployment/k8s/current_deployment.yaml`) with these keys.

## Database Note

Ensure your Cloud Run service can connect to your Cloud SQL instance. You may need to enable the Cloud SQL Admin API and use the Cloud SQL Auth Proxy or Private IP connection.
If using Cloud SQL, add the instance connection name:

```yaml
      annotations:
        run.googleapis.com/cloudsql-instances: PROJECT_ID:REGION:INSTANCE_NAME
```

And update the `DATABASE_URL` format appropriately.
