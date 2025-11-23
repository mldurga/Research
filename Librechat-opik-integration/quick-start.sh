#!/bin/bash
#
# LibreChat + Opik Quick Start Script
# This script automates the setup process
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_msg() {
  local color=$1
  shift
  echo -e "${color}$@${NC}"
}

print_header() {
  echo ""
  print_msg "$BLUE" "============================================"
  print_msg "$BLUE" "$@"
  print_msg "$BLUE" "============================================"
  echo ""
}

print_success() {
  print_msg "$GREEN" "✓ $@"
}

print_error() {
  print_msg "$RED" "✗ $@"
}

print_warning() {
  print_msg "$YELLOW" "⚠ $@"
}

# Check prerequisites
check_prerequisites() {
  print_header "Checking Prerequisites"

  # Check Docker
  if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker first."
    exit 1
  fi
  print_success "Docker found: $(docker --version)"

  # Check Docker Compose
  if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose not found. Please install Docker Compose first."
    exit 1
  fi
  print_success "Docker Compose found"

  # Check available memory
  total_mem=$(free -g | awk '/^Mem:/{print $2}')
  if [ "$total_mem" -lt 8 ]; then
    print_warning "System has less than 8GB RAM. Opik may run slowly."
  else
    print_success "System has ${total_mem}GB RAM"
  fi
}

# Setup environment file
setup_env() {
  print_header "Setting Up Environment"

  if [ -f .env ]; then
    print_warning ".env file already exists. Skipping..."
    return
  fi

  print_msg "$BLUE" "Copying .env.example to .env..."
  cp .env.example .env

  print_success ".env file created"

  print_warning "IMPORTANT: Edit .env file and add your API keys:"
  print_warning "  - OPENAI_API_KEY"
  print_warning "  - ANTHROPIC_API_KEY (optional)"
  print_warning "  - GOOGLE_API_KEY (optional)"
  print_warning ""
  print_warning "Press Enter when done, or Ctrl+C to exit and edit manually..."

  read -p ""
}

# Clone LibreChat
clone_librechat() {
  print_header "Setting Up LibreChat"

  if [ -d "librechat" ]; then
    print_warning "librechat directory already exists. Skipping clone..."
    return
  fi

  print_msg "$BLUE" "Cloning LibreChat repository..."
  git clone https://github.com/danny-avila/LibreChat.git librechat
  print_success "LibreChat cloned"
}

# Apply OTEL instrumentation
apply_otel() {
  print_header "Applying OpenTelemetry Instrumentation"

  if [ ! -d "librechat" ]; then
    print_error "librechat directory not found. Run this script from librechat-opik-integration directory."
    exit 1
  fi

  # Backend files
  print_msg "$BLUE" "Copying backend OTEL files..."
  mkdir -p librechat/api/server/middleware
  mkdir -p librechat/api/server/routes

  cp backend/otel.js librechat/api/server/middleware/
  cp backend/mcp-tracing.js librechat/api/server/middleware/
  cp backend/routes/otel-config.js librechat/api/server/routes/

  print_success "Backend OTEL files copied"

  # Frontend files
  print_msg "$BLUE" "Copying frontend OTEL files..."
  mkdir -p librechat/client/src/utils

  cp frontend/otel.js librechat/client/src/utils/

  print_success "Frontend OTEL files copied"

  # Check if modifications are needed
  print_warning "MANUAL STEP REQUIRED:"
  print_warning "You need to modify the following LibreChat files:"
  print_warning "  1. librechat/api/server/index.js - Add OTEL initialization at the top"
  print_warning "  2. librechat/client/src/main.jsx - Import and call initializeOTEL()"
  print_warning ""
  print_warning "See README.md for detailed instructions."
  print_warning ""
  print_warning "Press Enter when done, or Ctrl+C to exit..."

  read -p ""
}

# Install dependencies
install_dependencies() {
  print_header "Installing Dependencies"

  print_msg "$BLUE" "Installing backend dependencies..."
  cd librechat
  npm install --save \
    @opentelemetry/api \
    @opentelemetry/sdk-node \
    @opentelemetry/auto-instrumentations-node \
    @opentelemetry/exporter-trace-otlp-proto \
    @opentelemetry/exporter-metrics-otlp-proto \
    @opentelemetry/sdk-trace-base \
    @opentelemetry/sdk-metrics \
    @opentelemetry/resources \
    @opentelemetry/semantic-conventions

  print_success "Backend dependencies installed"

  print_msg "$BLUE" "Installing frontend dependencies..."
  cd client
  npm install --save \
    @opentelemetry/api \
    @opentelemetry/sdk-trace-web \
    @opentelemetry/exporter-trace-otlp-http \
    @opentelemetry/auto-instrumentations-web \
    @opentelemetry/instrumentation \
    @opentelemetry/context-zone \
    @opentelemetry/core \
    @opentelemetry/resources \
    @opentelemetry/semantic-conventions

  cd ../..

  print_success "Frontend dependencies installed"
}

# Start Opik
start_opik() {
  print_header "Starting Opik Platform"

  print_msg "$BLUE" "Starting Opik infrastructure..."
  docker compose --profile opik up -d

  print_msg "$BLUE" "Waiting for Opik to initialize (this may take 30-60 seconds)..."

  # Wait for Opik backend to be healthy
  max_wait=60
  wait_time=0
  while [ $wait_time -lt $max_wait ]; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
      print_success "Opik is ready!"
      break
    fi
    echo -n "."
    sleep 2
    wait_time=$((wait_time + 2))
  done

  if [ $wait_time -ge $max_wait ]; then
    print_error "Opik failed to start within ${max_wait} seconds"
    print_error "Check logs: docker logs opik-backend"
    exit 1
  fi

  print_success "Opik platform started successfully"
  print_success "Opik Dashboard: http://localhost:5173"
  print_success "Opik API: http://localhost:8080"
}

# Start LibreChat
start_librechat() {
  print_header "Starting LibreChat"

  print_msg "$BLUE" "Starting LibreChat services..."
  docker compose --profile librechat up -d

  print_msg "$BLUE" "Waiting for LibreChat to be ready..."

  max_wait=60
  wait_time=0
  while [ $wait_time -lt $max_wait ]; do
    if curl -s http://localhost:3080 > /dev/null 2>&1; then
      print_success "LibreChat is ready!"
      break
    fi
    echo -n "."
    sleep 2
    wait_time=$((wait_time + 2))
  done

  if [ $wait_time -ge $max_wait ]; then
    print_error "LibreChat failed to start within ${max_wait} seconds"
    print_error "Check logs: docker logs librechat-backend"
    exit 1
  fi

  print_success "LibreChat started successfully"
  print_success "LibreChat UI: http://localhost:3080"
}

# Verify OTEL integration
verify_otel() {
  print_header "Verifying OTEL Integration"

  print_msg "$BLUE" "Checking backend OTEL logs..."
  if docker logs librechat-backend 2>&1 | grep -q "OpenTelemetry SDK initialized successfully"; then
    print_success "Backend OTEL initialized"
  else
    print_warning "Backend OTEL may not be initialized. Check logs:"
    print_warning "  docker logs librechat-backend | grep OTEL"
  fi

  print_msg "$BLUE" "Testing OTEL configuration..."
  response=$(curl -s -X POST http://localhost:3080/api/config/otel/test)
  if echo "$response" | grep -q "success.*true"; then
    print_success "OTEL configuration is valid"
  else
    print_warning "OTEL configuration test failed. Response:"
    echo "$response"
  fi
}

# Start MCP server (optional)
start_mcp() {
  print_header "Starting MCP Server (Optional)"

  print_msg "$BLUE" "Do you want to start the PI System MCP server? (y/n)"
  read -p "" start_mcp

  if [ "$start_mcp" = "y" ] || [ "$start_mcp" = "Y" ]; then
    if [ ! -f "../mcp/Dockerfile" ]; then
      print_warning "MCP Dockerfile not found. Skipping MCP server..."
      return
    fi

    print_msg "$BLUE" "Starting MCP server..."
    docker compose --profile mcp up -d

    print_success "MCP server started"
    print_success "MCP server: http://localhost:8001"
  else
    print_warning "Skipping MCP server"
  fi
}

# Print summary
print_summary() {
  print_header "Setup Complete!"

  echo ""
  print_success "All services are running!"
  echo ""
  print_msg "$GREEN" "Access your services:"
  print_msg "$GREEN" "  • LibreChat UI:    http://localhost:3080"
  print_msg "$GREEN" "  • Opik Dashboard:  http://localhost:5173"
  print_msg "$GREEN" "  • Opik API:        http://localhost:8080"
  echo ""
  print_msg "$YELLOW" "Next steps:"
  print_msg "$YELLOW" "  1. Open LibreChat and start a conversation"
  print_msg "$YELLOW" "  2. Open Opik Dashboard to see traces"
  print_msg "$YELLOW" "  3. Check README.md for advanced usage"
  echo ""
  print_msg "$BLUE" "Useful commands:"
  print_msg "$BLUE" "  • View logs:        docker logs -f librechat-backend"
  print_msg "$BLUE" "  • Stop services:    docker compose --profile opik --profile librechat down"
  print_msg "$BLUE" "  • Restart:          docker compose --profile opik --profile librechat restart"
  echo ""
}

# Main execution
main() {
  print_header "LibreChat + Opik Integration Setup"

  check_prerequisites
  setup_env
  clone_librechat
  apply_otel
  install_dependencies
  start_opik
  start_librechat
  verify_otel
  start_mcp
  print_summary
}

# Run main function
main
