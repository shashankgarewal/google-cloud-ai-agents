# Learnings

## Agents (ADK/MCP/tools)
1. `adk create $agent` prompts to choose a backend — went with **Vertex AI** over 
   Google AI Studio because:
   - Fully managed — Google handles servers, scaling, maintenance
   - Unified — single platform for deployment, monitoring, evaluation
   - Built for apps — you build the layer, users interact with your agent
   - Scales from 1 to millions of users

2. While the `instructions` is context/prompt for the agent functionality, the `description` is intended for other agents. A bad description means fuzzy orchestration.

3. `from . import agent` inside __init__.py makes python execute agent.py as the package gets imported. If __init__.py left empty, and folder name has dash `-`, python won't be able to import agent. 
It's best to name agents folder with underscore `_`, given google adk [faced issue deploying agent named with dashes](https://github.com/google/adk-python/issues/2902)

4. The `adk create` prompt offers 2 backends for Gemini: 
   - **Google AI** — just plug in an API key and go. 
   - **Vertex AI** — the production-ready option on GCP, with proper auth, security, and scaling.

   Both use the same `google-genai` SDK under the hood; differs in inital client setup (`vertexai=True` + project/location vs. just an API key).[1](https://google.github.io/adk-docs/agents/models/google-gemini/#google-ai-studio) and [2](https://ai.google.dev/gemini-api/docs/migrate-to-cloud)


## GCP
1. Project ID must be set even for locally running agents — turns out the Vertex AI API
   (`aiplatform.googleapis.com`) is what connects local `agent.py` to Gemini, which 
   actually runs on Google Cloud, not your machine.

2. GCP Organization is a separate entity — a new domain is required to create one.
   As a workaround to manage projects in this repo, basic **folders** were used instead.
   GCP gives an org placeholder for every Google account, so folders can live inside that.

3. To create a folder, the `resourcemanager.folders.create` permission is needed on the org.
   Simpler to do via CLI than the console:
   ```bash
      # Get ORG_ID
      gcloud organizations list

      # Set permission
      gcloud organizations add-iam-policy-binding [ORG_ID] --member="user:YOUR_EMAIL" --role="roles/resourcemanager.folderCreator"

      # Create folder
      gcloud resource-manager folders create --display-name="[FOLDER_NAME]" --organization=[ORG_ID]

      # Get FOLDER_ID
      gcloud resource-manager folders list --organization=[ORG_ID]

      # Create project inside folder
      gcloud projects create [PROJECT_ID] --name="[PROJECT_DISPLAY_NAME]" --folder=[FOLDER_ID]
   ```
4. `gcloud config set project [PROJECT_ID]` sets the **default CLI project** — it does not associate the current working directory with that project.

5. Even if the agent is running locally, all execution to any google model (e.g., Vertex AI service) is performed by gcloud, therefore setting billing is mandatory.
   ```bash
      # find billing ID
      gcloud billing accounts list 

      # set billing ID in your project ID
      gcloud billing projects link [PROJECT_ID] --billing-account=[BILLING_ACCOUNT_ID]

      # to check if already assigned
      gcloud billing projects describe [PROJECT_ID]
   ```

6. The Project IDs are globally unique across **all GCP users and organizations**, similar to how domain names work on the internet or username in linkedin.

7. The service account automatically binds with active/default project configured at the momemnt of creating service account. 
      
      ![service account creation failed when no project is set](sa_fail_no_projectID.png)


## General
1. Not all AI services are available in every region — `us-central1` has the broadest coverage.

2. APIs are enabled at the project level, while roles and permissions to use those APIs are granted at the service account level.

3. The app (the deployd code) is different from the project. The project is the infrastructure wrapper — the app is the code running inside it.
   
   **Cloud Hierarchy**
   ```bash
      Organization (optional, company level)
      └── Folder (optional, team/env grouping)
            └── Cloud Project
                  └── Billing Account
                        └── Link a billing account to project
                  └── APIs enabled (e.g. aiplatform.googleapis.com)
                  └── Service Account 
                        └── Roles granted by project (e.g. aiplatform.user)
                  └── Cloud Run / Compute Engine
                        └── Your App (code) deployed here
                        └── Service Account attached at deployment
   ```
   **App Workflow**
   ```bash
      The App makes an API call
         → Cloud Run uses the attached service account
            → service account has roles granted by the project
               → project has the API enabled
                  → call succeeds ✅
   ```

4. In ADK deploy,  the (.) identifies the folder containing your agent (agent.yaml, tools, MCP configs); all flags before the path (.) configure ADK itself,and everything after the -- is passed directly and untouched to gcloud run deploy as Cloud Run flags.
The `.` in ADK DEPLOY COMMAND specify agent source directory, while the `--` seperates ADK arguments from gcloud arguments. The deployment with the adk command over traditional `gcloud run deploy` does 2 major things: 
- Creates the Agent UI + registers metadata for the ADK console
- Create docker image, builds & packages the ADK agent (tools, manifest, MCP config), no manual tasks.

   ```bash
      source .env 
      adk deploy cloud_run \
      --project=$GOOGLE_CLOUD_PROJECT \
      --region=$GOOGLE_CLOUD_LOCATION \
      --service_name=$GOOGLE_CLOUD_PROJECT \
      --with_ui \
      . \
      -- \
      --service-account=$SERVICE_ACCOUNT
   ```

# Projects 
| Project | Concepts Learned | Codelab |
|---|---|---|
| [`hello_agent`](./hello_agent) | ADK basics, project setup, venv | [Live](https://codelabs.developers.google.com/devsite/codelabs/build-agents-with-adk-foundation) / [archive](https://web.archive.org/web/20260324113305/https://codelabs.developers.google.com/devsite/codelabs/build-agents-with-adk-empowering-with-tools) |
| [`sequential_agent_deployed`](./sequential_agent_deployed) | Sequential agents, state sharing, Cloud Run | [Live](https://codelabs.developers.google.com/codelabs/production-ready-ai-with-gc/5-deploying-agents/deploy-an-adk-agent-to-cloud-run) / [archive](https://web.archive.org/web/20260324113659/https://codelabs.developers.google.com/codelabs/production-ready-ai-with-gc/5-deploying-agents/deploy-an-adk-agent-to-cloud-run)|