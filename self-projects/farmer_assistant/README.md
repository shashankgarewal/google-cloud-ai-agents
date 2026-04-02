
## services enabled
  - run.googleapis.com 
  - artifactregistry.googleapis.com
  - cloudbuild.googleapis.com
  - aiplatform.googleapis.com
  - compute.googleapis.com
  - routes.googleapis.com
  - mapstools.googleapis.com

## IAM roles
- roles/aiplatform.user
- roles/run.invoker
- roles/cloudbuild.builds.editor
- roles/mcp.toolUser

```bash
    gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT  --member="serviceAccount:$SERVICE_ACCOUNT" --role="$SERVICE"
```