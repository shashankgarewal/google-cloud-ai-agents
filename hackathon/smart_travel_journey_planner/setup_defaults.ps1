# Setup Default Service Accounts for Deployment

# Configuration
$PROJECT_ID = "smart-train-recommender"

Write-Host "Fetching Project Number for $PROJECT_ID..." -ForegroundColor Cyan
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
Write-Host "Project Number: $PROJECT_NUMBER"

$COMPUTE_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
$CLOUDBUILD_SA = "$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

# 1. Enable Deployment APIs
Write-Host "Enabling Deployment APIs..." -ForegroundColor Cyan
$APIS = @(
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com"
)

foreach ($API in $APIS) {
    Write-Host "Enabling $API..."
    gcloud services enable $API
}

# 2. Setup Compute Engine Default SA (Runtime Identity)
# This is often used by Cloud Run/Functions by default
Write-Host "`nConfiguring Compute Engine Default SA ($COMPUTE_SA)..." -ForegroundColor Cyan
$COMPUTE_ROLES = @(
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor"
)

foreach ($ROLE in $COMPUTE_ROLES) {
    Write-Host "Assigning $ROLE..."
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$COMPUTE_SA" `
        --role="$ROLE" `
        --no-user-output-enabled
}

# 3. Setup Cloud Build SA (Deployment Identity)
Write-Host "`nConfiguring Cloud Build SA ($CLOUDBUILD_SA)..." -ForegroundColor Cyan
# Cloud Build needs to be able to deploy to Cloud Run and act as the runtime SA
$CLOUDBUILD_ROLES = @(
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/artifactregistry.admin"
)

foreach ($ROLE in $CLOUDBUILD_ROLES) {
    Write-Host "Assigning $ROLE..."
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$CLOUDBUILD_SA" `
        --role="$ROLE" `
        --no-user-output-enabled
}

Write-Host "`nDefault Service Accounts Configured!" -ForegroundColor Green
Write-Host "Note: If you are using a custom SA for Cloud Run (like deployed-sa), ensure Cloud Build has 'iam.serviceAccountUser' on THAT specific SA."
