# Setup Infrastructure for Smart Travel Journey Planner

# Configuration
$PROJECT_ID = "smart-train-recommender"
$SERVICE_ACCOUNT_ID = "deployed-sa"
$SERVICE_ACCOUNT_EMAIL = "$SERVICE_ACCOUNT_ID@$PROJECT_ID.iam.gserviceaccount.com"

Write-Host "Setting project to $PROJECT_ID..." -ForegroundColor Cyan
gcloud config set project $PROJECT_ID

# 1. Enable APIs
Write-Host "Enabling Google Cloud APIs..." -ForegroundColor Cyan
$APIS = @(
    "aiplatform.googleapis.com",
    "calendar.googleapis.com",
    "gmail.googleapis.com",
    "tasks.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "secretmanager.googleapis.com"
)

foreach ($API in $APIS) {
    Write-Host "Enabling $API..."
    gcloud services enable $API
}

# 2. Create Service Account if it doesn't exist
Write-Host "Checking for Service Account $SERVICE_ACCOUNT_ID..." -ForegroundColor Cyan
$SA_EXISTS = gcloud iam service-accounts list --filter="email:$SERVICE_ACCOUNT_EMAIL" --format="value(email)"

if (-not $SA_EXISTS) {
    Write-Host "Creating Service Account $SERVICE_ACCOUNT_ID..."
    gcloud iam service-accounts create $SERVICE_ACCOUNT_ID --display-name="Deployed Service Account for Journey Planner"
} else {
    Write-Host "Service Account $SERVICE_ACCOUNT_ID already exists."
}

# 3. Assign Roles
Write-Host "Assigning IAM Roles..." -ForegroundColor Cyan
$ROLES = @(
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/secretmanager.secretAccessor"
)

foreach ($ROLE in $ROLES) {
    Write-Host "Assigning $ROLE to $SERVICE_ACCOUNT_EMAIL..."
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" `
        --role="$ROLE" `
        --no-user-output-enabled
}

Write-Host "`nSetup Complete!" -ForegroundColor Green
Write-Host "Important Note: For Workspace MCP to work, ensures you have configured the OAuth 2.0 Client ID in your .env file."
Write-Host "If running in a production environment (like Cloud Run), ensure the Service Account is attached to the instance."
