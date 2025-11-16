# Quick Start Guide: Deploy Your PI System Assistant to Vertex AI

**Estimated time:** 15-30 minutes

## Prerequisites Checklist

- [ ] Google Cloud project with billing enabled
- [ ] Your MCP server URL from Cloud Run
- [ ] Python 3.10+ installed on your machine
- [ ] Basic familiarity with command line

## 3-Step Deployment

### Step 1: Setup (5 minutes)

```bash
cd vertex_ai_agent
./setup.sh
```

The setup script will:
- Install required tools (uv, gcloud SDK)
- Enable Google Cloud APIs
- Create environment configuration
- Verify MCP server connectivity

**Important:** Have your MCP Server URL ready!

### Step 2: Configure (2 minutes)

The setup script creates a `.env` file. Verify it contains:

```bash
cat .env
```

Should show:
```
MCP_SERVER_URL=https://your-actual-cloud-run-url.run.app
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
STAGING_BUCKET=gs://your-bucket
```

**Get your MCP Server URL:**
```bash
gcloud run services list --format='value(status.url)'
```

### Step 3: Deploy (5-10 minutes)

```bash
./deploy.sh
```

This automatically:
1. ✅ Validates configuration
2. ✅ Tests MCP connection
3. ✅ Deploys to Vertex AI
4. ✅ Provides access URL

## Using Your Agent

### Option 1: Vertex AI Console (Easiest)

1. Go to: https://console.cloud.google.com/vertex-ai/agents
2. Find agent: `pi-system-assistant`
3. Click **Open** to start chatting

### Option 2: Try These Queries

**Basic test:**
```
"Hello! What PI System tools do you have?"
```

**Search test:**
```
"Find all temperature sensors in the plant"
```

**Data retrieval:**
```
"Get the last 24 hours of data for sensor TS-101"
```

**Health check:**
```
"Check PI System health status"
```

**Forecasting:**
```
"Forecast the next 7 days for temperature sensor TS-101"
```

## Troubleshooting

### Issue: MCP Server Connection Failed

```bash
# Test your MCP server manually
curl https://YOUR_MCP_URL/health

# If it fails, check Cloud Run status
gcloud run services describe YOUR_SERVICE_NAME
```

### Issue: Deployment Failed

```bash
# Check environment variables
cat .env

# Verify APIs are enabled
gcloud services list --enabled | grep aiplatform

# Check permissions
gcloud projects get-iam-policy $GCP_PROJECT_ID
```

### Issue: Tools Not Working

1. Verify MCP server is running
2. Check agent logs:
   ```bash
   gcloud logging read "resource.type=vertex_ai_agent" --limit=20
   ```
3. Re-deploy: `./deploy.sh`

## What's Next?

1. ✅ Test with your actual PI System data
2. ✅ Review example queries in `examples/example_queries.md`
3. ✅ Set up monitoring and alerts
4. ✅ Share with your team
5. ✅ Customize for your specific use cases

## Getting Help

- **Detailed Guide**: See `DEPLOYMENT_GUIDE.md`
- **Full Documentation**: See `README.md`
- **Example Queries**: See `examples/example_queries.md`
- **API Usage**: See `examples/api_usage.py`

## Key Files

```
vertex_ai_agent/
├── agent.py              ← Main agent definition
├── requirements.txt      ← Dependencies
├── config.yaml          ← Configuration
├── deploy.sh            ← Deployment script
├── setup.sh             ← Setup script
├── .env                 ← Your settings (created by setup)
├── README.md            ← Full documentation
├── DEPLOYMENT_GUIDE.md  ← Detailed deployment guide
└── examples/            ← Examples and patterns
    ├── example_queries.md
    └── api_usage.py
```

## Support Commands

```bash
# View agent in console
gcloud ai agents list --region=us-central1

# Check logs
gcloud logging tail "resource.type=vertex_ai_agent"

# Update agent
./deploy.sh

# Test locally
python test_agent.py
```

---

**You're all set!** 🚀 Your PI System Assistant is now live in Vertex AI!
