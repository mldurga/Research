#!/bin/bash

# Deployment script for Vertex AI Agent Engine
# This script deploys the PI System Assistant agent to Google Vertex AI

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment variables from .env file${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check required environment variables
REQUIRED_VARS=("GCP_PROJECT_ID" "GCP_REGION" "STAGING_BUCKET" "MCP_SERVER_URL")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: Required environment variable $var is not set${NC}"
        echo "Please set it in your .env file or export it in your shell"
        exit 1
    fi
done

echo -e "${GREEN}=== Vertex AI Agent Deployment ===${NC}"
echo "Project: $GCP_PROJECT_ID"
echo "Region: $GCP_REGION"
echo "Staging Bucket: $STAGING_BUCKET"
echo "MCP Server URL: $MCP_SERVER_URL"
echo ""

# Check if uv is installed (ADK CLI tool)
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}Installing uv (ADK CLI tool)...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Check if ADK is installed
if ! uv run adk --version &> /dev/null; then
    echo -e "${YELLOW}Installing Google GenAI ADK...${NC}"
    uv pip install google-genai[adk]
fi

# Validate agent configuration
echo -e "${GREEN}Validating agent configuration...${NC}"
if ! uv run adk validate .; then
    echo -e "${RED}Agent validation failed! Please check your agent.py${NC}"
    exit 1
fi

echo -e "${GREEN}Agent validation successful!${NC}"
echo ""

# Deploy to Vertex AI Agent Engine
echo -e "${GREEN}Deploying to Vertex AI Agent Engine...${NC}"
echo "This may take a few minutes..."
echo ""

uv run adk deploy agent_engine \
    --project="$GCP_PROJECT_ID" \
    --region="$GCP_REGION" \
    --staging_bucket="$STAGING_BUCKET" \
    --agent_name="${AGENT_ENGINE_APP_NAME:-pi-system-assistant}" \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Deployment Successful! ===${NC}"
    echo ""
    echo "Your PI System Assistant agent is now deployed to Vertex AI!"
    echo ""
    echo "Next steps:"
    echo "1. Go to Google Cloud Console > Vertex AI > Agent Builder"
    echo "2. Find your agent: ${AGENT_ENGINE_APP_NAME:-pi-system-assistant}"
    echo "3. Test it in the Vertex AI interface"
    echo "4. Enable the tools search capability in the agent settings"
    echo ""
    echo "You can also access it via API or integrate it into applications."
else
    echo -e "${RED}Deployment failed!${NC}"
    exit 1
fi
