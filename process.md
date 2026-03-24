While the genai academy program is designed and recommended to use gcloud shell, this repository is developement on windows 10 local machine with vscode ide.

# Steps to setup gcloud cli in local machine (Windows 10):
1. Install gcloud cli installer exe from [here](https://docs.cloud.google.com/sdk/docs/install-sdk) and select beta components
2. Connect google account on cli using `gcloud init` 
3. Install google cloud code extension in vscode: gives UI to view logs, check cloud runs easily, and more.
4. For extension, cloud signin is visible at in vscode sidebar 
5. Set dependency paths ![gcloud, and other components (if installed) paths set to google-cloud-sdk bin folder](assets/images/dependency_path.png)
6. Add following script to .bashrc to view the default project_id in gitbash terminal
```
get_gcloud_project() {
  gcloud config get-value project 2>/dev/null
}

PROMPT_COMMAND='GCP_PROJECT=$(get_gcloud_project)'
PS1='\[\033[32m\]\u@\h\[\033[00m\] \[\033[33m\]${GCP_PROJECT}\[\033[00m\] \[\033[36m\]\w\[\033[00m\]\n$ '
```


* Now CLI and Extension work together as a unified tool instead of two separate programs — both using the same SDK installation, ensuring consistent behavior across terminal commands and VS Code UI actions.

Note: Extension and SDK are still seperate, you need to manually set project id for both. 

# Steps to spin up any project:
 
## 1. Python environment
   ```bash
   # Python 3.10+ required (ADK constraint)
   python -m venv venv
   source venv/Scripts/activate  # Git Bash on Windows
   # source venv/bin/activate     # macOS / Linux
   
   # If local Python < 3.10, use conda instead:
   conda create -p venv python=3.12 -y && conda activate venv
   
   pip install -r requirements.txt
   ```
 
## 2. GCP project for AI agents
   ```bash
   gcloud projects create [PROJECT_ID] --name="[PROJECT_NAME]" --folder=[FOLDER_ID]        # omit if not using folders
   
   gcloud config set project [PROJECT_ID]
   
   # Enable Vertex AI 
   gcloud services enable aiplatform.googleapis.com

   # Set Billing ID in your project ID
   gcloud billing projects link [PROJECT_ID] --billing-account=[BILLING_ACCOUNT_ID]
   ```

## 3. Create and run an agent
   ```bash
   adk create [AGENT_NAME]
   # Prompts:
   #   Model:      1 → gemini-2.5-flash
   #   Backend:    2 → Vertex AI
   #   Project ID: your project id
   #   Region:     us-central1
   
   adk run [AGENT_NAME]   # CLI
   adk web                # Local web UI
   ```