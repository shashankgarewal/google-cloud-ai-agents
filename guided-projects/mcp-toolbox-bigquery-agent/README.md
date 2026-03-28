# Description  
An ADK agent connected to **MCP Toolbox for Databases**, exposing the **Google Cloud Release Notes** BigQuery public dataset as a queryable MCP interface.

---

## What this does  
- Configures **MCP Toolbox for Databases** to use the `google_cloud_release_notes` BigQuery public dataset  
- Provides a tool (`search_release_notes_bq`) that returns release notes from the past 7 days  
- Runs a **single-node ADK agent** that uses the toolbox to answer natural‑language questions over the dataset  

The agent relies on the MCP Toolbox for tool execution; the “agentic” behavior comes from the MCP integration rather than multi‑agent orchestration.

---
