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
      gcloud organizations add-iam-policy-binding [ORG_ID] \
         --member="user:YOUR_EMAIL" \
         --role="roles/resourcemanager.folderCreator"

      # Create folder
      gcloud resource-manager folders create \
         --display-name="GenAI-Academy-2026" \
         --organization=[ORG_ID]

      # Create project inside folder
      gcloud projects create [PROJECT_ID] \
         --name="[PROJECT_DISPLAY_NAME]" \
         --folder=[FOLDER_ID]
   ```


# Layout 
| Project | Concepts Learned | Codelab |
|---|---|---|
| [`hello_agent`](./hello_agent) | ADK basics, project setup, venv | [↗](https://codelabs.developers.google.com/devsite/codelabs/build-agents-with-adk-foundation) |
| [`sequential_agent_deployed`](./sequential_agent_deployed) | Sequential agents, state sharing, Cloud Run | [↗](https://codelabs.developers.google.com/codelabs/production-ready-ai-with-gc/5-deploying-agents/deploy-an-adk-agent-to-cloud-run) |