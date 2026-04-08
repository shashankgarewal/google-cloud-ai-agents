#!/bin/bash
# Setup Infrastructure for Smart Travel Journey Planner

# Configuration
PROJECT_ID="smart-train-recommender"
SERVICE_ACCOUNT_ID="deployed-sa"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_ID@$PROJECT_ID.iam.gserviceaccount.com"

echo "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# 1. Enable APIs
echo "Enabling Google Cloud APIs..."
APIS=(
    "aiplatform.googleapis.com"
    "calendar.googleapis.com"
    "gmail.googleapis.com"
    "tasks.googleapis.com"
    "iam.googleapis.com"
    "cloudresourcemanager.googleapis.com"
    "serviceusage.googleapis.com"
    "secretmanager.googleapis.com"
)

for API in "${APIS[@]}"; do
    echo "Enabling $API..."
    gcloud services enable "$API"
done

# 2. Create Service Account if it doesn't exist
echo "Checking for Service Account $SERVICE_ACCOUNT_ID..."
if ! gcloud iam service-accounts list --filter="email:$SERVICE_ACCOUNT_EMAIL" --format="value(email)" | grep -q "$SERVICE_ACCOUNT_EMAIL"; then
    echo "Creating Service Account $SERVICE_ACCOUNT_ID..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_ID" --display-name="Deployed Service Account for Journey Planner"
else
    echo "Service Account $SERVICE_ACCOUNT_ID already exists."
fi

# 3. Assign Roles
echo "Assigning IAM Roles..."
ROLES=(
    "roles/aiplatform.user"
    "roles/logging.logWriter"
    "roles/serviceusage.serviceUsageConsumer"
    "roles/secretmanager.secretAccessor"
)

for ROLE in "${ROLES[@]}"; do
    echo "Assigning $ROLE to $SERVICE_ACCOUNT_EMAIL..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$ROLE" \
        --no-user-output-enabled
done

echo -e "\nSetup Complete!"
echo "Important Note: For Workspace MCP to work, ensures you have configured the OAuth 2.0 Client ID in your .env file."
