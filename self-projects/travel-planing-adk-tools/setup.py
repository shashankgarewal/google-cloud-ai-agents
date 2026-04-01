import os
from dotenv import load_dotenv

# Load the variables from the .env file
load_dotenv("trip_planner/.env")

# Retrieve the specific value
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
billing_id = os.getenv("BILLING_ACCOUNT_ID")

sa_id = project_id.replace("adk", "")
sa_name = sa_id.rsplit("-").capitalize() + " Service Account"
print(f"Project ID: {project_id}")

# gcloud billing projects link project_id --billing-account=billing_id

# gcloud iam service-accounts create $sa_id --display-name=$sa_name \
#    --project=$GOOGLE_CLOUD_PROJECT