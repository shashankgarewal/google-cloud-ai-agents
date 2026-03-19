<!-- ----------------------------- Setup Steps ----------------------------- -->

# 1. Set the variables in your terminal first
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA_NAME=lab2-cr-service

# 2. Create the .env file using those variables
cat <<EOF > .env
PROJECT_ID=$PROJECT_ID
PROJECT_NUMBER=$PROJECT_NUMBER
SA_NAME=$SA_NAME
SERVICE_ACCOUNT=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
MODEL="gemini-2.5-flash"
EOF


<!-- ---------------------------- Isolate Agent ---------------------------- -->
dedication service account for isolated iam role
`gcloud iam service-accounts create ${SA_NAME} --display-name="Service Account for C1T1L1"`

# Grant the "Vertex AI User" (roles/aiplatform.user) role to your service account
`gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT" --role="roles/aiplatform.user"`

<!-- ------------------------------- Deploy -------------------------------- -->
Single command that build container image, push to artifact registry, and launch service on cloud run.

```bash
uvx --from google-adk==1.14.0 \
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=europe-west1 \
  --service_name=zoo-tour-guide \
  --with_ui \
  . \
  -- \
  --labels=dev-tutorial=codelab-adk \
  --service-account=$SERVICE_ACCOUNT
```