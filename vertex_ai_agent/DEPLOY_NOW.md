# 🚀 Deploy Your Vertex AI Agent - Complete Guide

Your Vertex AI agent is ready to deploy! Due to environment limitations in this Claude session, please follow these steps to complete the deployment.

## ✅ What's Already Done

- ✅ Agent code created (`agent.py`)
- ✅ Configuration file ready (`.env`)
- ✅ MCP server URL configured: `https://pi-mcp-488440068832.asia-south1.run.app/`
- ✅ Project set up: `abiding-circle-478407-i8`
- ✅ Region configured: `asia-south1`
- ✅ Service account credentials ready (`gcp-credentials.json`)

## 🎯 Quick Deployment Options

### **Option 1: Google Cloud Shell (RECOMMENDED - Easiest)**

This is the fastest way to deploy since Cloud Shell has all tools pre-installed.

1. **Upload Files to Cloud Shell:**
   ```bash
   # In your local terminal, compress the folder
   cd /path/to/Research
   tar -czf vertex_ai_agent.tar.gz vertex_ai_agent/
   ```

2. **Open Cloud Shell:**
   - Go to: https://console.cloud.google.com/?project=abiding-circle-478407-i8
   - Click the **Cloud Shell** icon (>_) in the top right

3. **Upload the tar file** using the three-dot menu → Upload file

4. **Extract and deploy:**
   ```bash
   # Extract files
   tar -xzf vertex_ai_agent.tar.gz
   cd vertex_ai_agent

   # Authenticate with service account
   gcloud auth activate-service-account --key-file=gcp-credentials.json
   gcloud config set project abiding-circle-478407-i8

   # Enable required APIs
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable run.googleapis.com

   # Create staging bucket
   gsutil mb -l asia-south1 gs://abiding-circle-478407-i8-vertex-ai-staging

   # Install uv (ADK CLI)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.cargo/env

   # Install dependencies
   uv pip install -r requirements.txt

   # Deploy to Vertex AI
   uv run adk deploy agent_engine \
       --project=abiding-circle-478407-i8 \
       --region=asia-south1 \
       --staging_bucket=gs://abiding-circle-478407-i8-vertex-ai-staging \
       --agent_name=pi-system-assistant \
       .
   ```

### **Option 2: Your Local Machine**

If you prefer to deploy from your computer:

1. **Prerequisites:**
   ```bash
   # Install Google Cloud SDK if not already installed
   # Visit: https://cloud.google.com/sdk/docs/install

   # Install Python 3.10+
   python3 --version

   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Navigate to the agent directory:**
   ```bash
   cd /path/to/Research/vertex_ai_agent
   ```

3. **Authenticate:**
   ```bash
   gcloud auth activate-service-account --key-file=gcp-credentials.json
   gcloud config set project abiding-circle-478407-i8
   ```

4. **Enable APIs:**
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable run.googleapis.com
   ```

5. **Create staging bucket:**
   ```bash
   gsutil mb -l asia-south1 gs://abiding-circle-478407-i8-vertex-ai-staging
   ```

6. **Install dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

7. **Deploy:**
   ```bash
   uv run adk deploy agent_engine \
       --project=abiding-circle-478407-i8 \
       --region=asia-south1 \
       --staging_bucket=gs://abiding-circle-478407-i8-vertex-ai-staging \
       --agent_name=pi-system-assistant \
       .
   ```

### **Option 3: Manual Deployment via Console**

If you prefer a UI-based approach:

1. **Enable APIs manually:**
   - Go to: https://console.cloud.google.com/apis/library?project=abiding-circle-478407-i8
   - Search and enable:
     - Vertex AI API
     - Cloud Storage API
     - Cloud Run API

2. **Create staging bucket:**
   - Go to: https://console.cloud.google.com/storage/browser?project=abiding-circle-478407-i8
   - Click "CREATE BUCKET"
   - Name: `abiding-circle-478407-i8-vertex-ai-staging`
   - Location: asia-south1
   - Click "CREATE"

3. **Use Cloud Shell for deployment** (see Option 1)

## 📋 Verification Steps

After deployment completes, verify everything is working:

```bash
# Check if agent is deployed
gcloud ai agents list --region=asia-south1

# Test MCP server connectivity
curl https://pi-mcp-488440068832.asia-south1.run.app/

# View agent in console
```

## 🎉 Access Your Agent

Once deployed, access your agent at:

1. **Vertex AI Console:**
   - https://console.cloud.google.com/vertex-ai/agents?project=abiding-circle-478407-i8
   - Look for: `pi-system-assistant`

2. **Test queries:**
   - "Check PI System health"
   - "Find all temperature sensors"
   - "Get current values for element XYZ"

## 🔧 Troubleshooting

### Issue: "APIs not enabled"
```bash
# Enable manually
gcloud services enable aiplatform.googleapis.com storage.googleapis.com
```

### Issue: "Permission denied"
```bash
# Verify service account has permissions
gcloud projects get-iam-policy abiding-circle-478407-i8 \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:vertex-ai-deployer@*"
```

### Issue: "Bucket already exists (owned by another project)"
```bash
# Use a different bucket name in .env
STAGING_BUCKET=gs://abiding-circle-478407-i8-vertexai-staging-v2
```

### Issue: "MCP server not reachable"
```bash
# Test MCP server
curl -v https://pi-mcp-488440068832.asia-south1.run.app/

# Check Cloud Run service
gcloud run services describe pi-mcp --region=asia-south1
```

## 📊 Deployment Output

Successful deployment will show:

```
✅ Agent validation successful
✅ Uploading agent to staging bucket
✅ Creating Vertex AI agent
✅ Deployment complete!

Agent deployed: projects/abiding-circle-478407-i8/locations/asia-south1/agents/pi-system-assistant
```

## 📞 Next Steps

After successful deployment:

1. ✅ Test agent in Vertex AI console
2. ✅ Try example queries from `examples/example_queries.md`
3. ✅ Set up monitoring and alerts
4. ✅ Share with your team
5. ✅ Integrate into applications via API

## 📚 Additional Resources

- **Full Documentation:** See `README.md`
- **Deployment Guide:** See `DEPLOYMENT_GUIDE.md`
- **Example Queries:** See `examples/example_queries.md`
- **API Usage:** See `examples/api_usage.py`

---

**Your agent is ready to deploy!** Choose your preferred method above and follow the steps. 🚀

If you encounter any issues, check the troubleshooting section or refer to the detailed deployment guide.
