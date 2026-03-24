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

## General
1. Not all AI services are available in every region — `us-central1` has the broadest coverage.


# Projects 
| Project | Concepts Learned | Codelab |
|---|---|---|
| [`hello_agent`](./hello_agent) | ADK basics, project setup, venv | [↗](https://codelabs.developers.google.com/devsite/codelabs/build-agents-with-adk-foundation) |
| [`sequential_agent_deployed`](./sequential_agent_deployed) | Sequential agents, state sharing, Cloud Run | [↗](https://codelabs.developers.google.com/codelabs/production-ready-ai-with-gc/5-deploying-agents/deploy-an-adk-agent-to-cloud-run) |