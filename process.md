While the gcloud academy program is designed and recommended to use gcloud shell, this repository is developement on windows 10 local machine with vscode ide.

# Steps used google cloud in local machine (Windows 10):
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