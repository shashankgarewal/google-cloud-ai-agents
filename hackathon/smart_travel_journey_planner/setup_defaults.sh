#!/bin/bash
# Setup Default Service Accounts for Deployment

# Configuration
PROJECT_ID="smart-train-recommender"

echo "Fetching Project Number for $PROJECT_ID..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "Project Number: $PROJECT_NUMBER"

COMPUTE_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

# 1. Enable Deployment APIs
echo "Enabling Deployment APIs..."
APIS=(
    "cloudbuild.googleapis.com"
    "run.googleapis.com"
    "artifactregistry.googleapis.com"
    "secretmanager.googleapis.com"
)

for API in "${APIS[@]}"; do
    echo "Enabling $API..."
    gcloud services enable "$API"
done

# 2. Setup Compute Engine Default SA (Runtime Identity)
echo -e "\nConfiguring Compute Engine Default SA ($COMPUTE_SA)..."
COMPUTE_ROLES=(
    "roles/aiplatform.user"
    "roles/logging.logWriter"
    "roles/secretmanager.secretAccessor"
)

for ROLE in "${COMPUTE_ROLES[@]}"; do
    echo "Assigning $ROLE..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$COMPUTE_SA" \
        --role="$ROLE" \
        --no-user-output-enabled
done

# 3. Setup Cloud Build SA (Deployment Identity)
echo -e "\nConfiguring Cloud Build SA ($CLOUDBUILD_SA)..."
CLOUDBUILD_ROLES=(
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/artifactregistry.admin"
)

for ROLE in "${CLOUDBUILD_ROLES[@]}"; do
    echo "Assigning $ROLE..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$CLOUDBUILD_SA" \
        --role="$ROLE" \
        --no-user-output-enabled
done

echo -e "\nDefault Service Accounts Configured!"
