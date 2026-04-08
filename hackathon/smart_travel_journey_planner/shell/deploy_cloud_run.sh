#!/bin/bash
# Deploy Smart Travel Journey Planner to Cloud Run

# Configuration
PROJECT_ID="smart-train-recommender"
REGION="us-central1"
APP_NAME="smart-travel-planner"
REPO_NAME="run-repo"
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${APP_NAME}"

echo "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# 1. Enable Required APIs (Cloud Build, Artifact Registry, Cloud Run)
echo "Enabling necessary APIs for deployment..."
gcloud services enable \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    run.googleapis.com

# 2. Create Artifact Registry Repository (if it doesn't exist)
echo "Checking for Artifact Registry repository '$REPO_NAME'..."
if ! gcloud artifacts repositories describe $REPO_NAME --location=$REGION >/dev/null 2>&1; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker repository for Cloud Run images"
else
    echo "Repository '$REPO_NAME' already exists."
fi

# 3. Build and push image using Cloud Build
echo "Building the Docker image and pushing to Artifact Registry..."
gcloud builds submit --tag $IMAGE_URL .

# 4. Deploy to Cloud Run
echo "Deploying application to Cloud Run..."
# Note: You can add --set-env-vars to inject variables from your .env file
# For example: --set-env-vars="WORKSPACE_MCP_URL=your_url,WORKSPACE_MCP_COMMAND=your_command"
gcloud run deploy $APP_NAME \
    --image $IMAGE_URL \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --service-account="deployed-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "=========================================================="
echo "Deployment initiated!"
echo "Check the Cloud Run console for the live Service URL."
echo "=========================================================="
