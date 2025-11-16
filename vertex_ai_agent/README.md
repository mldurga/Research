# Vertex AI Agent for PI System

This directory contains a Google Vertex AI Agent that integrates with your AVEVA PI System MCP server running in Google Cloud Run.

## Overview

The agent provides:
- **Semantic Search**: Natural language search across AF elements
- **Data Analytics**: Historical and real-time data retrieval
- **Forecasting**: Time-series predictions using Prophet
- **System Monitoring**: PI System health checks
- **Batch Operations**: Efficient multi-element data retrieval

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface                            │
│              (Vertex AI Console / API)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            Vertex AI Agent Engine                            │
│  ┌──────────────────────────────────────────────────┐        │
│  │  PI System Assistant Agent                       │        │
│  │  (agent.py - Gemini 2.0 Flash)                   │        │
│  │  ┌──────────────────────────────────────┐        │        │
│  │  │  MCPToolset (SSE Connection)         │        │        │
│  │  └──────────────┬───────────────────────┘        │        │
│  └─────────────────┼──────────────────────────────┘│        │
└──────────────────────┼──────────────────────────────────────┘
                       │ HTTPS
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               Google Cloud Run                               │
│  ┌──────────────────────────────────────────────────┐        │
│  │  PI System MCP Server                             │        │
│  │  (FastMCP - pi_mcp_server.py)                     │        │
│  │  ┌────────────────────────────────────┐           │        │
│  │  │  PI WebAPI Client                  │           │        │
│  │  │  Vector DB (ChromaDB)              │           │        │
│  │  │  Forecasting (Prophet)             │           │        │
│  │  └───────────┬────────────────────────┘           │        │
│  └──────────────┼───────────────────────────────────┘        │
└──────────────────┼──────────────────────────────────────────┘
                   │ HTTPS
                   ▼
┌─────────────────────────────────────────────────────────────┐
│            AVEVA PI System                                   │
│  - PI Data Archive                                           │
│  - PI Asset Framework (AF)                                   │
│  - PI WebAPI                                                 │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Vertex AI API** enabled
3. **MCP Server** deployed to Cloud Run (already done)
4. **Python 3.10+** installed
5. **uv** (ADK CLI tool) installed

## Setup

### 1. Configure Environment Variables

Copy the example environment file and fill in your details:

```bash
cp .env.example .env
```

Edit `.env` and set:
- `MCP_SERVER_URL`: Your Cloud Run URL (e.g., `https://your-service-xxxxx.run.app`)
- `GCP_PROJECT_ID`: Your Google Cloud project ID
- `GCP_REGION`: Deployment region (e.g., `us-central1`)
- `STAGING_BUCKET`: GCS bucket for staging (e.g., `gs://your-bucket`)

### 2. Install Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python dependencies
uv pip install -r requirements.txt
```

### 3. Test Configuration

Run the test script to verify everything is set up correctly:

```bash
python test_agent.py
```

This will check:
- MCP server connectivity
- Agent configuration
- Tool availability

## Deployment

### Option 1: Using the Deployment Script (Recommended)

```bash
./deploy.sh
```

This script will:
1. Validate your environment configuration
2. Validate the agent definition
3. Deploy to Vertex AI Agent Engine
4. Provide next steps

### Option 2: Manual Deployment

```bash
# Validate agent
uv run adk validate .

# Deploy to Vertex AI
uv run adk deploy agent_engine \
    --project=YOUR_PROJECT_ID \
    --region=us-central1 \
    --staging_bucket=gs://your-staging-bucket \
    --agent_name=pi-system-assistant \
    .
```

## Using the Agent

### Via Vertex AI Console

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **Vertex AI** > **Agent Builder**
3. Find your agent: `pi-system-assistant`
4. Click **Open** to start chatting
5. Enable **Tools** in the interface

### Via API

```python
from google.cloud import aiplatform

aiplatform.init(
    project="YOUR_PROJECT_ID",
    location="us-central1"
)

# Get the agent
agent = aiplatform.Agent("pi-system-assistant")

# Send a query
response = agent.predict(
    instances=[{
        "query": "Find all temperature sensors in Unit 100"
    }]
)

print(response)
```

### Example Queries

Try these queries with your agent:

1. **Semantic Search**:
   - "Find all temperature sensors in the plant"
   - "Show me pumps in Unit 100"
   - "List all equipment with the Tank template"

2. **Data Retrieval**:
   - "Get the last 24 hours of data for sensor XYZ"
   - "Show me current values for all attributes of element ABC"
   - "Retrieve interpolated hourly data for the past week"

3. **Forecasting**:
   - "Forecast the next 7 days for this temperature sensor"
   - "Predict future values based on 30 days of historical data"

4. **System Health**:
   - "Check PI System health status"
   - "Show me vector database statistics"

## Configuration

### Agent Configuration (`agent.py`)

The agent is configured with:
- **Model**: Gemini 2.0 Flash (optimized for speed and cost)
- **Tools**: All MCP server tools via `MCPToolset`
- **Preamble**: Expert instructions for PI System interactions
- **Function Calling**: AUTO mode (agent decides when to use tools)

### MCP Connection

The agent connects to your Cloud Run MCP server using:
- **Connection Type**: SSE (Server-Sent Events)
- **Authentication**: Optional Bearer token
- **Timeout**: Configurable in `config.yaml`

### Tool Filtering

To expose only specific tools, edit `agent.py`:

```python
mcp_toolset = adk.mcp.MCPToolset(
    connection_params=create_mcp_connection(),
    tool_filter=[
        "search_af_elements_semantic",
        "get_recorded_values",
        "forecast_pi_attribute"
    ]
)
```

## Monitoring

### View Logs

```bash
gcloud logging read "resource.type=vertex_ai_agent" \
    --project=YOUR_PROJECT_ID \
    --limit=50
```

### Monitor Usage

1. Go to **Vertex AI** > **Agent Builder** > **Your Agent**
2. Click **Monitoring** tab
3. View metrics:
   - Request count
   - Latency
   - Error rate
   - Tool usage

## Troubleshooting

### Agent Can't Connect to MCP Server

1. Verify Cloud Run URL is correct in `.env`
2. Check Cloud Run service is running:
   ```bash
   gcloud run services describe YOUR_SERVICE_NAME
   ```
3. Verify authentication (if using bearer token)

### Tools Not Available

1. Check MCP server health:
   ```bash
   curl https://YOUR_CLOUD_RUN_URL/health
   ```
2. Verify MCP server is returning tools list
3. Check agent logs for connection errors

### Deployment Fails

1. Verify all required environment variables are set
2. Check GCP permissions:
   - Vertex AI Editor
   - Storage Admin (for staging bucket)
3. Ensure staging bucket exists and is accessible

### High Latency

1. Check MCP server performance
2. Consider increasing Cloud Run instances
3. Optimize tool filter to reduce overhead
4. Use caching in MCP server (if applicable)

## Security Best Practices

1. **Authentication**:
   - Use bearer tokens for MCP server authentication
   - Enable Cloud Run authentication

2. **Tool Access**:
   - Use `tool_filter` to limit exposed tools
   - Restrict write operations if not needed

3. **Network Security**:
   - Use VPC connectors for private access
   - Enable Cloud Armor for DDoS protection

4. **Monitoring**:
   - Enable audit logging
   - Set up alerts for anomalous usage
   - Monitor tool invocation patterns

## Cost Optimization

1. **Model Selection**: Gemini 2.0 Flash is cost-effective
2. **Tool Filtering**: Reduce unnecessary tool calls
3. **Caching**: Enable response caching where applicable
4. **Scaling**: Configure appropriate min/max replicas
5. **Batch Operations**: Use batch tools to reduce API calls

## Development

### Local Testing

```bash
# Set environment variables
export MCP_SERVER_URL="https://your-cloud-run-url.run.app"

# Run tests
python test_agent.py

# Test agent locally (requires ADK dev server)
uv run adk web
```

### Update Agent

After making changes to `agent.py`:

```bash
# Validate changes
uv run adk validate .

# Redeploy
./deploy.sh
```

## Support

- **Vertex AI Documentation**: https://cloud.google.com/vertex-ai/docs
- **ADK Documentation**: https://google.github.io/adk-docs/
- **MCP Protocol**: https://modelcontextprotocol.io/

## License

Copyright 2024. All rights reserved.
