# managed-mcp-bigquery-maps-agent

This project builds an LLM Agent using ADK and configure MCP clients as tools using MCPToolset. The MCP servers used are BigQuery and Gmaps which are fully managed and hosted by Google.

Cloned and extended from [google/mcp — launchmybakery](https://github.com/google/mcp/tree/main/examples/launchmybakery),
following the [Google Codelabs tutorial](https://codelabs.developers.google.com/adk-mcp-bigquery-maps).

An AI agent empowered by Gemini 3.1 Pro that orchestrates enterprise data (BigQuery) and 
geospatial context (Google Maps) via remote MCP servers to solve a real business problem:

    Example question: How would you help a friend launch a new high-end sourdough bakery in Los Angeles?

## Changes from original

- Extracted MCP toolset configs into a dedicated `/tools` directory (`gmap_bigquery.py`)
- Renamed agent folder to `gmap_location_analyzer`
- Enabled APIs and created Maps API key manually via GCP Console instead of bash scripts

## Structure
```text
├── gmap_location_analyzer/   # Agent (agent.py)
├── tools/                    # MCP toolset configs
├── setup/                    # Setup scripts
├── data/                     # Synthetic bakery dataset — demographics, foot traffic, competitor pricing, weekly sales
└── .env                      # GCP project metadata & API keys (ignored in git)
```

![Architecture Diagram](../../images/architecture_diagram.png)