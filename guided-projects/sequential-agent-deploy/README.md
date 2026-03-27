Here's the full journey from start to finish:

---

**Project Goal**
Deploy a Zoo Tour Guide AI agent to Google Cloud Run using ADK (Agent Development Kit).

---

** Problems & Fixes**

**1. Empty `$SERVICE_ACCOUNT` variable**
- `.env` file was never loaded → `source .env` needed every session

**2. `.env` file deleted**
- Had to recreate it using `gcloud` commands to fetch project values automatically

**3. Not logged into gcloud**
- Fixed with `gcloud auth login` + `gcloud auth application-default login`

**4. IAM permissions missing (main blocker)**
- Cloud Build SA needed `roles/run.admin` + `roles/iam.serviceAccountUser`(final fix that made deploy work)
- Compute SA needed `roles/logging.logWriter`
- Compute SA needed `roles/artifactregistry.writer` 

**5. `get_animal_info` function error**
- Old Cloud Run container had a different `agent.py`
- The program lab default instruction mentioned a zoo tool that didn't exist - LLM halucinate and looked for random get_animal_info function which doesn't exist in (code) tool box.
- Fixed by updating the instruction without using the zool tool and animal info.

---

** Key Lessons Learned**

| Lesson | Detail |
|---|---|
| `source .env` | place to store deployment configurations outside the code |
| Local Run | `adk web` to test agent before deploying |
| Cloud Build logs | Always check browser URL for real errors |
| IAM roles | Need to be set up manually in lab environments |

---

**✅ Final State**
- Agent deployed to Cloud Run ✅
- Local `adk web` working ✅
- Wikipedia tool working ✅