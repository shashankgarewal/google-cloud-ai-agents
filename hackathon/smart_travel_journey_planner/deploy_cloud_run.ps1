# Deploy Smart Travel Journey Planner to Cloud Run

# Configuration
$PROJECT_ID = "smart-train-recommender"
$REGION = "us-central1"
$APP_NAME = "smart-travel-planner"
$REPO_NAME = "run-repo"
$IMAGE_URL = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${APP_NAME}"
$SERVICE_ACCOUNT = "deployed-sa@${PROJECT_ID}.iam.gserviceaccount.com"

Write-Host "Setting project to $PROJECT_ID..." -ForegroundColor Cyan
gcloud config set project $PROJECT_ID

# 1. Enable Required APIs (Cloud Build, Artifact Registry, Cloud Run)
Write-Host "Enabling necessary APIs for deployment..." -ForegroundColor Cyan
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com run.googleapis.com

# 2. Create Artifact Registry Repository (if it doesn't exist)
Write-Host "Checking for Artifact Registry repository '$REPO_NAME'..." -ForegroundColor Cyan
$repoExists = gcloud artifacts repositories describe $REPO_NAME --location=$REGION 2>$null

if (-not $repoExists) {
    Write-Host "Creating Artifact Registry repository..." -ForegroundColor Yellow
    gcloud artifacts repositories create $REPO_NAME `
        --repository-format=docker `
        --location=$REGION `
        --description="Docker repository for Cloud Run images"
} else {
    Write-Host "Repository '$REPO_NAME' already exists." -ForegroundColor Green
}

# 3. Build and push image using Cloud Build
Write-Host "Building the Docker image and pushing to Artifact Registry..." -ForegroundColor Cyan
gcloud builds submit --tag $IMAGE_URL .

# 4. Deploy to Cloud Run
Write-Host "Deploying application to Cloud Run..." -ForegroundColor Cyan
# Note: You can add --set-env-vars to inject variables from your .env file
# For example: --set-env-vars="WORKSPACE_MCP_URL=your_url,WORKSPACE_MCP_COMMAND=your_command"
gcloud run deploy $APP_NAME `
    --image $IMAGE_URL `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --service-account=$SERVICE_ACCOUNT

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "Deployment initiated!" -ForegroundColor Green
Write-Host "Check the Cloud Run console for the live Service URL." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
