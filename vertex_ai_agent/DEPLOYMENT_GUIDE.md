# Complete Deployment Guide: Vertex AI Agent for PI System

This comprehensive guide walks you through deploying your PI System Assistant agent to Google Vertex AI.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Deployment Process](#deployment-process)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Testing & Verification](#testing--verification)
7. [Troubleshooting](#troubleshooting)
8. [Production Considerations](#production-considerations)

---

## Prerequisites

### 1. Google Cloud Platform

- [ ] Active GCP project with billing enabled
- [ ] Owner or Editor role on the project
- [ ] Vertex AI API enabled
- [ ] Cloud Storage API enabled
- [ ] MCP server deployed to Cloud Run (already completed)

### 2. Local Environment

- [ ] Python 3.10 or later
- [ ] Git installed
- [ ] Google Cloud SDK (`gcloud`) installed
- [ ] Sufficient disk space (500MB minimum)

### 3. MCP Server Information

- [ ] Cloud Run URL of your MCP server
- [ ] Bearer token (if authentication is enabled)
- [ ] Verification that MCP server is running and accessible

---

## Quick Start

For experienced users, here's the fastest path to deployment:

```bash
# 1. Navigate to the agent directory
cd vertex_ai_agent

# 2. Run the automated setup
./setup.sh

# 3. Deploy to Vertex AI
./deploy.sh
```

That's it! Skip to [Post-Deployment Configuration](#post-deployment-configuration).

---

## Detailed Setup

### Step 1: Clone and Prepare

```bash
# You're already in the Research directory with the vertex_ai_agent folder
cd vertex_ai_agent

# Verify all files are present
ls -la
```

Expected files:
- `agent.py` - Agent definition with MCP integration
- `requirements.txt` - Python dependencies
- `config.yaml` - Configuration file
- `deploy.sh` - Deployment script
- `setup.sh` - Setup script
- `test_agent.py` - Test suite
- `README.md` - Documentation
- `.env.example` - Environment template

### Step 2: Install Google Cloud SDK

If not already installed:

**Linux/Mac:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

**Windows:**
Download from: https://cloud.google.com/sdk/docs/install

### Step 3: Authenticate with Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Verify authentication
gcloud auth list
```

### Step 4: Enable Required APIs

```bash
# Enable Vertex AI
gcloud services enable aiplatform.googleapis.com

# Enable Cloud Storage
gcloud services enable storage.googleapis.com

# Enable Cloud Run (if not already enabled)
gcloud services enable run.googleapis.com

# Verify enabled services
gcloud services list --enabled
```

### Step 5: Create Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your preferred editor
nano .env
# or
vim .env
# or
code .env
```

**Required Configuration:**

```bash
# Your Cloud Run MCP server URL
MCP_SERVER_URL=https://your-mcp-server-xxxxx.run.app

# Optional: Bearer token if your MCP server requires authentication
MCP_SERVER_BEARER_TOKEN=

# Your Google Cloud project ID
GCP_PROJECT_ID=your-project-id

# Deployment region
GCP_REGION=us-central1

# Staging bucket (will be created if it doesn't exist)
STAGING_BUCKET=gs://your-project-id-vertex-ai-staging

# Agent configuration
AGENT_ENGINE_LOCATION=us-central1
AGENT_ENGINE_APP_NAME=pi-system-assistant
```

**How to get your MCP Server URL:**

```bash
# List your Cloud Run services
gcloud run services list

# Get the URL of your MCP service
gcloud run services describe YOUR_MCP_SERVICE_NAME --format='value(status.url)'
```

### Step 6: Create Staging Bucket

```bash
# Set your project and region
PROJECT_ID="your-project-id"
REGION="us-central1"

# Create the bucket
gsutil mb -p $PROJECT_ID -l $REGION gs://${PROJECT_ID}-vertex-ai-staging

# Verify bucket creation
gsutil ls | grep vertex-ai-staging
```

### Step 7: Install Python Dependencies

**Option A: Using uv (Recommended)**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Install dependencies
uv pip install -r requirements.txt
```

**Option B: Using pip**

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Deployment Process

### Automated Deployment (Recommended)

```bash
# Run the deployment script
./deploy.sh
```

The script will:
1. ✅ Validate environment variables
2. ✅ Check MCP server connectivity
3. ✅ Validate agent configuration
4. ✅ Deploy to Vertex AI Agent Engine
5. ✅ Provide access URLs and next steps

### Manual Deployment

If you prefer manual control:

```bash
# Load environment variables
source .env

# Validate agent configuration
uv run adk validate .

# Deploy to Vertex AI
uv run adk deploy agent_engine \
    --project="$GCP_PROJECT_ID" \
    --region="$GCP_REGION" \
    --staging_bucket="$STAGING_BUCKET" \
    --agent_name="$AGENT_ENGINE_APP_NAME" \
    .
```

### Deployment Output

Successful deployment will show:

```
✅ Agent validation successful
✅ Uploading agent to staging bucket
✅ Creating Vertex AI agent engine deployment
✅ Deployment complete!

Agent URL: https://console.cloud.google.com/vertex-ai/agents/...
```

---

## Post-Deployment Configuration

### Step 1: Access Vertex AI Console

1. Navigate to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project
3. Go to **Vertex AI** > **Agent Builder**
4. Find your agent: `pi-system-assistant`

### Step 2: Enable Tools

In the agent configuration:

1. Click on your agent
2. Go to **Settings** or **Configuration**
3. Enable **Function Calling** (should be enabled by default)
4. Enable **Tools** in the chat interface
5. Save configuration

### Step 3: Configure Permissions

```bash
# Grant necessary permissions to the agent service account
# (Replace SERVICE_ACCOUNT with your agent's service account)

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:SERVICE_ACCOUNT@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Allow agent to access Cloud Run MCP server
gcloud run services add-iam-policy-binding YOUR_MCP_SERVICE \
    --region=$GCP_REGION \
    --member="serviceAccount:SERVICE_ACCOUNT@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
```

### Step 4: Configure Search Capability (Optional)

For enhanced search features:

1. In Vertex AI Agent Builder, go to **Data Stores**
2. Create a new data store if needed
3. Link it to your agent
4. Configure search settings

---

## Testing & Verification

### Step 1: Run Pre-Deployment Tests

```bash
# Run test suite
python test_agent.py
```

Expected output:
```
✅ MCP server is accessible
✅ Agent imported successfully
✅ Agent has 1 toolset(s)
🎉 All tests passed!
```

### Step 2: Test in Vertex AI Console

Access your agent in the console and try these queries:

**Basic Test:**
```
"Hello! What can you help me with?"
```

**Tool Test:**
```
"Check PI System health status"
```

**Search Test:**
```
"Find all temperature sensors"
```

**Data Retrieval Test:**
```
"Get current values for element ABC"
```

### Step 3: Verify Tool Execution

Check that tools are being called:

1. In the Vertex AI console, send a query
2. Look for **Tool Calls** section in the response
3. Verify tool names and parameters
4. Check results are returned correctly

### Step 4: Monitor Logs

```bash
# View agent logs
gcloud logging read "resource.type=vertex_ai_agent AND resource.labels.agent_id=YOUR_AGENT_ID" \
    --limit=50 \
    --format=json

# View MCP server logs
gcloud run logs read YOUR_MCP_SERVICE --region=$GCP_REGION --limit=50
```

---

## Troubleshooting

### Issue: Agent Can't Connect to MCP Server

**Symptoms:**
- Tool calls fail
- Connection timeout errors
- "MCP server unreachable" messages

**Solutions:**

1. Verify MCP server is running:
   ```bash
   curl https://YOUR_MCP_URL/health
   ```

2. Check Cloud Run service status:
   ```bash
   gcloud run services describe YOUR_MCP_SERVICE --region=$GCP_REGION
   ```

3. Verify authentication:
   ```bash
   # Test with bearer token
   curl -H "Authorization: Bearer YOUR_TOKEN" https://YOUR_MCP_URL/health
   ```

4. Check service account permissions:
   ```bash
   gcloud run services get-iam-policy YOUR_MCP_SERVICE --region=$GCP_REGION
   ```

### Issue: Tools Not Available

**Symptoms:**
- Agent responds but doesn't use tools
- "No tools available" message
- Function calling disabled

**Solutions:**

1. Check agent.py has MCPToolset:
   ```python
   tools=[mcp_toolset]  # Should be present
   ```

2. Verify tool config:
   ```python
   tool_config=types.ToolConfig(
       function_calling_config=types.FunctionCallingConfig(
           mode='AUTO'  # Should be AUTO or ANY
       )
   )
   ```

3. Re-deploy agent:
   ```bash
   ./deploy.sh
   ```

### Issue: Deployment Fails

**Symptoms:**
- "Deployment failed" error
- Permission denied
- Bucket not found

**Solutions:**

1. Check environment variables:
   ```bash
   cat .env
   ```

2. Verify APIs are enabled:
   ```bash
   gcloud services list --enabled | grep aiplatform
   ```

3. Check IAM permissions:
   ```bash
   gcloud projects get-iam-policy $GCP_PROJECT_ID \
       --flatten="bindings[].members" \
       --filter="bindings.members:user:YOUR_EMAIL"
   ```

4. Verify staging bucket exists:
   ```bash
   gsutil ls $STAGING_BUCKET
   ```

### Issue: High Latency

**Symptoms:**
- Slow responses
- Timeout errors
- Poor user experience

**Solutions:**

1. Check MCP server performance:
   ```bash
   gcloud run services describe YOUR_MCP_SERVICE \
       --region=$GCP_REGION \
       --format='value(status.traffic)'
   ```

2. Increase Cloud Run resources:
   ```bash
   gcloud run services update YOUR_MCP_SERVICE \
       --region=$GCP_REGION \
       --memory=2Gi \
       --cpu=2
   ```

3. Enable caching in MCP server

4. Optimize tool filter in agent.py

### Issue: Cost Concerns

**Symptoms:**
- Higher than expected bills
- Too many API calls

**Solutions:**

1. Monitor usage:
   ```bash
   gcloud logging read "resource.type=vertex_ai_agent" \
       --format="table(timestamp, jsonPayload.request)"
   ```

2. Set budget alerts in GCP Console

3. Optimize queries and caching

4. Use tool filtering to reduce overhead

---

## Production Considerations

### Security

1. **Authentication:**
   ```bash
   # Enable IAM authentication on Cloud Run
   gcloud run services update YOUR_MCP_SERVICE \
       --region=$GCP_REGION \
       --no-allow-unauthenticated
   ```

2. **Network Security:**
   - Use VPC connectors for private communication
   - Enable Cloud Armor for DDoS protection
   - Implement rate limiting

3. **Secrets Management:**
   ```bash
   # Store bearer tokens in Secret Manager
   echo -n "YOUR_TOKEN" | gcloud secrets create mcp-bearer-token --data-file=-

   # Grant access to service account
   gcloud secrets add-iam-policy-binding mcp-bearer-token \
       --member="serviceAccount:SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor"
   ```

### Monitoring

1. **Set Up Alerts:**
   ```bash
   # Create alert for high error rate
   gcloud alpha monitoring policies create \
       --notification-channels=CHANNEL_ID \
       --display-name="Agent High Error Rate" \
       --condition-display-name="Error rate > 5%" \
       --condition-threshold-value=5 \
       --condition-threshold-duration=300s
   ```

2. **Dashboard:**
   - Create custom dashboard in Cloud Monitoring
   - Track: Request count, latency, error rate, tool usage

3. **Logging:**
   ```bash
   # Export logs to BigQuery for analysis
   gcloud logging sinks create agent-logs-export \
       bigquery.googleapis.com/projects/PROJECT/datasets/agent_logs \
       --log-filter='resource.type="vertex_ai_agent"'
   ```

### Scaling

1. **Auto-scaling Configuration:**
   ```bash
   # Update Cloud Run scaling
   gcloud run services update YOUR_MCP_SERVICE \
       --region=$GCP_REGION \
       --min-instances=1 \
       --max-instances=10 \
       --cpu=2 \
       --memory=4Gi
   ```

2. **Connection Pooling:**
   - Configure MCP server for connection pooling
   - Use persistent connections

3. **Caching Strategy:**
   - Implement Redis for frequently accessed data
   - Cache AF element metadata
   - Cache recent query results

### Maintenance

1. **Regular Updates:**
   ```bash
   # Update dependencies
   uv pip install --upgrade google-genai[adk]

   # Re-validate and deploy
   uv run adk validate .
   ./deploy.sh
   ```

2. **Backup Configuration:**
   ```bash
   # Backup agent configuration
   cp agent.py agent.py.backup
   cp .env .env.backup

   # Version control
   git add .
   git commit -m "Backup agent configuration"
   git push
   ```

3. **Health Checks:**
   ```bash
   # Automated health check script
   #!/bin/bash
   # Check MCP server
   curl -f https://YOUR_MCP_URL/health || echo "MCP server down!"

   # Check agent availability
   # Add agent health check logic
   ```

---

## Next Steps

After successful deployment:

1. ✅ Test thoroughly with real queries
2. ✅ Set up monitoring and alerts
3. ✅ Document your specific use cases
4. ✅ Train users on query patterns
5. ✅ Implement feedback loop for improvements
6. ✅ Plan for scaling and optimization

---

## Support Resources

- **Vertex AI Documentation**: https://cloud.google.com/vertex-ai/docs
- **ADK Documentation**: https://google.github.io/adk-docs/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **PI System Resources**: https://docs.osisoft.com/

---

## Appendix: Common Commands

### Agent Management

```bash
# List agents
gcloud ai agents list --region=$GCP_REGION

# Describe agent
gcloud ai agents describe AGENT_ID --region=$GCP_REGION

# Delete agent
gcloud ai agents delete AGENT_ID --region=$GCP_REGION
```

### Logs and Monitoring

```bash
# Tail logs
gcloud logging tail "resource.type=vertex_ai_agent"

# Export logs
gcloud logging read "resource.type=vertex_ai_agent" \
    --format=json > agent_logs.json

# View metrics
gcloud monitoring time-series list \
    --filter='resource.type="vertex_ai_agent"'
```

### Troubleshooting Commands

```bash
# Test MCP connectivity
curl -v https://YOUR_MCP_URL

# Check service account
gcloud iam service-accounts describe SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com

# View quota usage
gcloud compute project-info describe --project=$GCP_PROJECT_ID
```

---

**Congratulations!** 🎉 Your Vertex AI Agent for PI System is now deployed and ready to use!
