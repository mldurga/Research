# AVEVA Predictive Analytics MCP Server

A Model Context Protocol (MCP) server that provides comprehensive integration with the AVEVA Predictive Analytics Web API, enabling LLM-powered agents to interact with industrial anomaly detection and predictive maintenance systems.

## Table of Contents

- [Overview](#overview)
- [Understanding AVEVA Predictive Analytics](#understanding-aveva-predictive-analytics)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Usage Examples](#usage-examples)
- [Architecture](#architecture)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Overview

This MCP server exposes the AVEVA Predictive Analytics (PA) Web REST API through a standardized interface, allowing AI agents and LLMs to:

- Monitor and manage industrial asset health
- Analyze anomaly detection alerts
- Investigate fault diagnostics
- Query historical time-series data
- Manage alert workflows
- Generate and analyze forecasts
- Access audit trails and system configuration

## Understanding AVEVA Predictive Analytics

### What is AVEVA Predictive Analytics?

AVEVA Predictive Analytics is an **asset-centric anomaly detection system** that:

- Learns **normal operational behavior** of industrial equipment from **historical data**
- Builds **Operational Profiles** (statistical behavior models)
- Continuously compares **current real-time data** against those profiles
- Detects **deviations (anomalies)** and raises **alerts**
- Supports **root-cause investigation** via deviation contribution analysis

It is **model-driven** (not rule-based), using historical correlations between signals.

### Core Domain Concepts

#### Project
A logical container for monitoring one asset or system. Contains:
- Project points (input signals)
- Training data
- Operational profiles
- Filters and alerts
- Notes and configuration

#### Operational Profile
A learned representation of *normal behavior*:
- Built from historical training data
- Groups signals into **data modes** (typical operating conditions)
- Captures **relationships between points**, not just limits
- Only one profile is active at a time per project

#### Key Metrics

| Metric | Description |
|--------|-------------|
| **Actual** | Observed/measured value |
| **Prediction** | Expected value from model |
| **Deviation** | Difference between actual and predicted |
| **Contribution** | Impact on overall deviation |
| **OMR (Overall Model Residual)** | Aggregate health score across all points |

#### Alert Lifecycle
1. **Open** - Threshold exceeded
2. **Persist** - Condition continues
3. **Escalate** - Tiered notifications
4. **Clear** - Resolved with classification
5. **Assign to Cases** - For investigation

### Mental Model for LLM Context

> *AVEVA Predictive Analytics continuously compares live industrial sensor data against statistically learned models of normal behavior, detects deviations across correlated signals, aggregates them into health metrics, and manages alerts, diagnostics, and historical backfill with strong data-quality governance.*

## Features

### Authentication
- Token-based security with automatic refresh
- Active Directory integration
- SSL/TLS support

### Alert Management
- Query alert status for assets, projects, and points
- Manage alert workflow states
- Configure alert thresholds
- Clear and classify alerts

### Historical Data
- Retrieve time-series data for any point
- Query OMR (Overall Model Residual) history
- Access output points (predictions, deviations, contributions)

### Fault Diagnostics
- Query fault diagnostic signatures
- Analyze fault matches
- Get root cause recommendations

### Forecasting
- Retrieve forecast predictions
- Manage forecast models
- Analyze time-remaining predictions

### Sensors
- Monitor sensor health
- Manage sensor alert states
- Filter and query sensor data

### Audit & Configuration
- Access audit history
- Manage user-defined properties
- Configure historian and calculation points

## Installation

### Prerequisites
- Python 3.11+
- Access to AVEVA Predictive Analytics Web server
- Valid user credentials with PA Web privileges

### Local Installation

```bash
# Clone or copy the server files
cd apa-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Docker Installation

```bash
# Build the image
docker build -t apa-mcp-server .

# Run the container
docker run -d \
  --name apa-mcp \
  -p 8002:8002 \
  -e APA_BASE_URL=https://your-server/avevapredictiveanalytics \
  -e APA_USERNAME=your_username \
  -e APA_PASSWORD=your_password \
  -e APA_DOMAIN=your_domain \
  apa-mcp-server
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APA_BASE_URL` | Base URL for PA Web | `https://localhost/avevapredictiveanalytics` |
| `APA_USERNAME` | Domain username | - |
| `APA_PASSWORD` | User password | - |
| `APA_DOMAIN` | Active Directory domain | - |
| `APA_VERIFY_SSL` | Verify SSL certificates | `true` |
| `APA_TIMEOUT` | Request timeout (seconds) | `60` |
| `APA_API_VERSION` | API version | `v1` |
| `SERVER_PORT` | MCP server port | `8002` |
| `SERVER_HOST` | MCP server host | `0.0.0.0` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `TOKEN_REFRESH_BUFFER` | Token refresh buffer (seconds) | `300` |

### Example .env File

```env
# AVEVA Predictive Analytics API Configuration
APA_BASE_URL=https://pa-server.company.com/avevapredictiveanalytics
APA_USERNAME=pa_api_user
APA_PASSWORD=secure_password
APA_DOMAIN=CORPORATE
APA_VERIFY_SSL=true
APA_TIMEOUT=60
APA_API_VERSION=v1

# Server Configuration
SERVER_PORT=8002
SERVER_HOST=0.0.0.0
LOG_LEVEL=INFO
```

## Available Tools

### Authentication

| Tool | Description |
|------|-------------|
| `authenticate_apa` | Authenticate with PA Web API |

### Alert Status

| Tool | Description |
|------|-------------|
| `get_asset_alert_status` | Get alert status for asset and children |
| `get_project_alert_status` | Get alert status for project and points |
| `get_point_alert_configuration` | Get point thresholds and output points |

### Historical Data

| Tool | Description |
|------|-------------|
| `get_historical_data` | Get time-series data for points |
| `get_omr_history` | Get OMR historical data |
| `get_output_points_history` | Get predictions, deviations, contributions |

### Alert Management

| Tool | Description |
|------|-------------|
| `get_alert_workflow_states` | Get available alert states |
| `get_alert_clear_parameters` | Get clear type options |
| `set_asset_alert_state` | Set alert state for asset |
| `set_project_alert_state` | Set alert state for project |
| `set_point_alert_state` | Set alert state for point |

### Alert Thresholds

| Tool | Description |
|------|-------------|
| `add_alert_threshold` | Add new threshold |
| `update_alert_threshold` | Update existing threshold |
| `delete_alert_threshold` | Delete threshold |
| `get_threshold_by_id` | Get threshold details |
| `get_thresholds_by_point` | Get all thresholds for point |
| `restore_template_thresholds` | Reset to template values |

### Fault Diagnostics

| Tool | Description |
|------|-------------|
| `get_fault_diagnostic` | Get fault details by ID |
| `get_fault_diagnostics_for_project` | Get faults for project |
| `get_fault_diagnostics_with_recent_match` | Filter by match percentage |
| `get_fault_details` | Get detailed fault info (up to 5 projects) |
| `get_fault_summary` | Get fault summary with signatures |

### Forecasting

| Tool | Description |
|------|-------------|
| `get_forecast` | Get forecast predictions |
| `get_forecast_deployment_parameters` | Get model deployment params |
| `save_forecast_deployment_parameters` | Save deployment params |
| `delete_forecast_model` | Delete forecast model |
| `retrain_forecast_model` | Retrain forecast model |
| `get_deployed_model_results` | Get deployed model results |

### Sensors

| Tool | Description |
|------|-------------|
| `get_sensors` | Get sensor information |
| `get_sensors_in_alert` | Get sensors in alert state |
| `change_sensor_alert_state` | Change sensor alert state |

### Configuration

| Tool | Description |
|------|-------------|
| `get_historian_points` | Get historian point info |
| `update_historian_points` | Update historian points |
| `get_calculation_points` | Get calculation point info |
| `update_calculation_points` | Update calculation points |
| `get_digital_groups` | Get digital point groups |

### Projects

| Tool | Description |
|------|-------------|
| `get_output_points_archive_statuses` | Get archive status |
| `get_training_dataset_by_project` | Get training dataset info |
| `get_training_dataset` | Get dataset by ID |

### Audit

| Tool | Description |
|------|-------------|
| `get_audit_users` | Get users with audit records |
| `get_audit_categories` | Get audit categories |
| `get_audit_history` | Get audit history records |

### User-Defined Properties

| Tool | Description |
|------|-------------|
| `get_user_defined_properties` | Get property details |
| `create_user_defined_property` | Create new property |
| `update_user_defined_property` | Update property |
| `delete_user_defined_property` | Delete property |
| `get_user_defined_property_types` | Get property types |

### System

| Tool | Description |
|------|-------------|
| `get_apa_system_health` | Get comprehensive system health |

## Usage Examples

### Basic Authentication and Status Check

```python
# Authenticate
result = await authenticate_apa()
print(f"Authenticated: {result['success']}")

# Get root asset status
assets = await get_asset_alert_status()
print(f"Root asset: {assets['asset']['Description']}")
```

### Investigate Anomaly

```python
# Get project alert status
project = await get_project_alert_status(project_id=123)

# Find points in alert
points_in_alert = [p for p in project['project']['Points'] 
                   if p['RunTimeState'] == 'Alert']

# Get historical data for investigation
history = await get_historical_data(
    point_ids=[p['ProjectPointId'] for p in points_in_alert],
    start_datetime="2024-01-15T00:00:00Z",
    end_datetime="2024-01-16T00:00:00Z",
    frequency_seconds=60
)

# Check fault diagnostics
faults = await get_fault_diagnostics_for_project(
    project_id=123,
    frequency_seconds=60,
    start_date="2024-01-15T00:00:00Z",
    end_date="2024-01-16T00:00:00Z"
)
```

### Clear an Alert

```python
# Get clear parameters
clear_params = await get_alert_clear_parameters()

# Clear the alert with classification
result = await set_project_alert_state(
    project_id=123,
    state_id=1,  # Clear state
    notes="Investigated - sensor drift corrected",
    clear_type_id=2,  # Electrical Problem
    action_type_id=11,  # Contact Plant
    classification_type_id=24  # Operational Issue
)
```

### Get Forecast

```python
forecast = await get_forecast(
    project_point_id=456,
    forecast_values_start="2024-01-16T00:00:00Z",
    forecast_values_end="2024-01-23T00:00:00Z",
    record_count=168  # Hourly for 7 days
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client (LLM Agent)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               AVEVA PA MCP Server (FastMCP)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Tools     │  │  Resources  │  │      Prompts        │ │
│  │  (40+ ops)  │  │  (3 static) │  │  (4 templates)      │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         └────────────────┼────────────────────┘            │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              APAWebAPIClient                         │   │
│  │  • Token-based authentication                       │   │
│  │  • Automatic token refresh                          │   │
│  │  • Retry with exponential backoff                   │   │
│  │  • Session management                               │   │
│  └──────────────────────┬──────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │ HTTPS/REST
                          ▼
┌─────────────────────────────────────────────────────────────┐
│            AVEVA Predictive Analytics Web API                │
│  ┌───────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │   Identity    │  │     Token      │  │  Data APIs    │  │
│  │  (Auth Step 1)│  │  (Auth Step 2) │  │  (40+ endpoints│  │
│  └───────────────┘  └────────────────┘  └───────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              AVEVA Predictive Analytics System               │
│  ┌───────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Central DB    │  │  PA Server     │  │ Archive DB    │  │
│  │ (SQL Server)  │  │  (Runtime)     │  │ (Historian)   │  │
│  └───────────────┘  └────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Security

### Authentication Flow

1. **Identity Endpoint** (`POST /api/identity`)
   - Sends base64-encoded credentials over SSL
   - Returns a one-time GUID if user is authorized

2. **Token Endpoint** (`POST /token`)
   - Exchanges GUID for access and refresh tokens
   - Access token included in all subsequent requests
   - Tokens automatically refreshed before expiration

### Best Practices

- Always use HTTPS in production
- Store credentials in environment variables, not code
- Use service accounts with minimal required permissions
- Monitor audit logs for unusual API access patterns
- Rotate credentials regularly

### Token Lifecycle

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Identity   │────▶│    Token     │────▶│  Data Calls  │
│   (GUID)     │     │ (access_token│     │  (Bearer)    │
└──────────────┘     │  refresh_token│    └──────────────┘
                     └───────┬──────┘            │
                             │                   │
                     ┌───────▼──────┐           │
                     │ Token Expires│◀──────────┘
                     │   (406)      │
                     └───────┬──────┘
                             │
                     ┌───────▼──────┐
                     │   Refresh    │
                     │   Token      │
                     └──────────────┘
```

## Troubleshooting

### Common Issues

#### Authentication Failures

```
Error: 401 UNAUTHORIZED
```
- Verify username/password are correct
- Check domain name format
- Ensure user has PA Web privileges

```
Error: 403 FORBIDDEN
```
- User authenticated but lacks access to requested resource
- Check security group permissions in PA

#### Connection Issues

```
Error: SSL certificate verify failed
```
- Set `APA_VERIFY_SSL=false` for self-signed certificates
- Or add CA certificate to trusted store

```
Error: Connection timeout
```
- Increase `APA_TIMEOUT` value
- Check network connectivity to PA server
- Verify firewall rules

#### Token Errors

```
Error: 406 NOT ACCEPTABLE
```
- Access token expired
- Server will automatically refresh token
- If persistent, check system clock synchronization

### Logging

Enable debug logging for detailed diagnostics:

```env
LOG_LEVEL=DEBUG
```

### Health Check

Use the system health tool to verify connectivity:

```python
health = await get_apa_system_health()
print(json.dumps(health, indent=2))
```

## License

This MCP server is provided for integration with AVEVA Predictive Analytics systems. Ensure compliance with your AVEVA software license agreement.

## Support

For issues with:
- **This MCP Server**: Open an issue in the repository
- **AVEVA Predictive Analytics**: Contact AVEVA Support at https://sw.aveva.com/support
- **API Documentation**: Access Swagger via Help menu in PA Web application

---

*Built for industrial AI integration with AVEVA Predictive Analytics*
