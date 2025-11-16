#!/bin/bash

# Setup script for Vertex AI Agent deployment
# This script prepares your environment for deploying the PI System Assistant

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Vertex AI Agent Setup - PI System Assistant            ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to prompt for input with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    read -p "$(echo -e ${YELLOW}${prompt} [${default}]: ${NC})" input
    eval $var_name="${input:-$default}"
}

# Step 1: Check Python installation
echo -e "${GREEN}[1/8] Checking Python installation...${NC}"
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "   ✅ Python $PYTHON_VERSION found"
else
    echo -e "${RED}   ❌ Python 3 not found. Please install Python 3.10 or later.${NC}"
    exit 1
fi

# Step 2: Install uv (ADK CLI)
echo -e "${GREEN}[2/8] Installing uv (ADK CLI tool)...${NC}"
if command_exists uv; then
    echo "   ✅ uv already installed"
else
    echo "   Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
    echo "   ✅ uv installed successfully"
fi

# Step 3: Install Python dependencies
echo -e "${GREEN}[3/8] Installing Python dependencies...${NC}"
uv pip install -r requirements.txt
echo "   ✅ Dependencies installed"

# Step 4: Install Google Cloud SDK (if not present)
echo -e "${GREEN}[4/8] Checking Google Cloud SDK...${NC}"
if command_exists gcloud; then
    echo "   ✅ gcloud SDK found"
else
    echo -e "${YELLOW}   Google Cloud SDK not found.${NC}"
    read -p "   Install Google Cloud SDK? [y/N]: " install_gcloud
    if [[ $install_gcloud =~ ^[Yy]$ ]]; then
        curl https://sdk.cloud.google.com | bash
        exec -l $SHELL
        echo "   ✅ gcloud SDK installed"
    else
        echo "   ⚠️  Skipping gcloud installation. You'll need it for deployment."
    fi
fi

# Step 5: Enable required APIs
echo -e "${GREEN}[5/8] Checking Google Cloud configuration...${NC}"

if command_exists gcloud; then
    # Get current project
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")

    if [ -z "$CURRENT_PROJECT" ]; then
        echo -e "${YELLOW}   No default project set in gcloud.${NC}"
        read -p "   Enter your GCP project ID: " GCP_PROJECT
        gcloud config set project $GCP_PROJECT
    else
        echo "   Current project: $CURRENT_PROJECT"
        prompt_with_default "   Use this project?" "yes" USE_CURRENT
        if [[ ! $USE_CURRENT =~ ^[Yy] ]]; then
            read -p "   Enter your GCP project ID: " GCP_PROJECT
            gcloud config set project $GCP_PROJECT
        else
            GCP_PROJECT=$CURRENT_PROJECT
        fi
    fi

    echo "   Enabling required APIs..."
    gcloud services enable aiplatform.googleapis.com --project=$GCP_PROJECT
    gcloud services enable storage.googleapis.com --project=$GCP_PROJECT
    echo "   ✅ APIs enabled"
else
    echo "   ⚠️  Skipping API enablement (gcloud not available)"
fi

# Step 6: Create .env file
echo -e "${GREEN}[6/8] Creating environment configuration...${NC}"

if [ -f .env ]; then
    echo -e "${YELLOW}   .env file already exists.${NC}"
    read -p "   Overwrite? [y/N]: " overwrite
    if [[ ! $overwrite =~ ^[Yy]$ ]]; then
        echo "   Keeping existing .env file"
    else
        rm .env
    fi
fi

if [ ! -f .env ]; then
    echo "   Creating .env file..."

    # Prompt for MCP Server URL
    read -p "$(echo -e ${YELLOW}   Enter your MCP Server URL \(Cloud Run\): ${NC})" MCP_URL
    while [ -z "$MCP_URL" ]; do
        echo -e "${RED}   MCP Server URL is required!${NC}"
        read -p "$(echo -e ${YELLOW}   Enter your MCP Server URL: ${NC})" MCP_URL
    done

    # Optional Bearer Token
    read -p "$(echo -e ${YELLOW}   Enter Bearer Token \(optional, press Enter to skip\): ${NC})" BEARER_TOKEN

    # GCP Configuration
    prompt_with_default "   Enter GCP Region" "us-central1" GCP_REGION
    prompt_with_default "   Enter Agent Name" "pi-system-assistant" AGENT_NAME

    # Create staging bucket name
    STAGING_BUCKET="gs://${GCP_PROJECT}-vertex-ai-staging"
    prompt_with_default "   Enter Staging Bucket" "$STAGING_BUCKET" STAGING_BUCKET

    # Write .env file
    cat > .env << EOF
# MCP Server Configuration
MCP_SERVER_URL=$MCP_URL
MCP_SERVER_BEARER_TOKEN=$BEARER_TOKEN

# Google Cloud Configuration
GCP_PROJECT_ID=$GCP_PROJECT
GCP_REGION=$GCP_REGION
STAGING_BUCKET=$STAGING_BUCKET

# Vertex AI Configuration
AGENT_ENGINE_LOCATION=$GCP_REGION
AGENT_ENGINE_APP_NAME=$AGENT_NAME
EOF

    echo "   ✅ .env file created"
else
    # Load existing .env
    export $(cat .env | grep -v '^#' | xargs)
fi

# Step 7: Create staging bucket if needed
echo -e "${GREEN}[7/8] Setting up staging bucket...${NC}"

if command_exists gsutil; then
    # Extract bucket name without gs:// prefix
    BUCKET_NAME=${STAGING_BUCKET#gs://}

    if gsutil ls -b gs://$BUCKET_NAME &>/dev/null; then
        echo "   ✅ Staging bucket exists: $STAGING_BUCKET"
    else
        echo "   Creating staging bucket: $STAGING_BUCKET"
        gsutil mb -p $GCP_PROJECT -l $GCP_REGION gs://$BUCKET_NAME
        echo "   ✅ Staging bucket created"
    fi
else
    echo "   ⚠️  gsutil not available. Please create staging bucket manually."
fi

# Step 8: Verify setup
echo -e "${GREEN}[8/8] Verifying setup...${NC}"

# Run tests
if python3 test_agent.py; then
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Setup Complete! ✅                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Review your configuration in .env file"
    echo "  2. Run deployment: ./deploy.sh"
    echo "  3. Access your agent in Vertex AI Console"
    echo ""
else
    echo ""
    echo -e "${YELLOW}⚠️  Setup complete but some tests failed.${NC}"
    echo "   Please review the errors above and fix before deploying."
    echo ""
fi
