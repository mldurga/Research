# LibreChat + Opik Integration Architecture

## Overview

This integration adds comprehensive OpenTelemetry-based observability to LibreChat using Opik, with special focus on tracking MCP (Model Context Protocol) server tool usage.

## Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                     LibreChat Frontend                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Browser OTEL SDK                                     │   │
│  │  - User Interactions                                  │   │
│  │  - Page Loads                                         │   │
│  │  - AJAX Requests                                      │   │
│  │  - Console Logs                                       │   │
│  └──────────────────────────┬───────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────┘
                              │ W3C TraceContext
                              │ HTTP Headers
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     LibreChat Backend                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Node.js OTEL SDK                                     │   │
│  │  - Express HTTP Tracing                               │   │
│  │  - MongoDB Queries                                    │   │
│  │  - Redis Operations                                   │   │
│  │  - LLM API Calls (OpenAI, Anthropic, etc.)          │   │
│  │  - MCP Server Tool Calls                             │   │
│  └──────────────────────────┬───────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────┘
                              │ OTLP/HTTP
                              │ Protocol Buffers
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Opik Platform                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Backend API (Port 8080)                              │   │
│  │  - OTEL Trace Ingestion                               │   │
│  │  - Metrics Processing                                 │   │
│  │  - Log Aggregation                                    │   │
│  │  └─────┬──────────────────────────────────────────┘  │   │
│  │        ▼                                              │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │  ClickHouse Analytics Database               │     │   │
│  │  │  - High-performance trace storage            │     │   │
│  │  │  - Fast queries for dashboards               │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │  MySQL Metadata Database                     │     │   │
│  │  │  - Projects, workspaces                      │     │   │
│  │  │  - User data                                 │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │  Frontend UI (Port 5173)                     │     │   │
│  │  │  - Trace visualization                       │     │   │
│  │  │  - LLM call monitoring                       │     │   │
│  │  │  - MCP tool usage analytics                  │     │   │
│  │  │  - Cost tracking                             │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. User Interaction Flow
```
User clicks "Send" in chat
  → Frontend OTEL creates root trace "Chat Request"
  → Frontend sends HTTP request with trace context headers
  → Backend OTEL continues trace (same trace ID)
  → Backend processes message
  → Backend calls LLM API (child span)
  → Backend may call MCP tools (child spans)
  → Response returns to frontend
  → Frontend completes trace
  → All spans exported to Opik
```

### 2. MCP Tool Call Flow
```
LLM decides to use MCP tool
  → Backend creates "MCP Tool Call" span
  → Span metadata includes:
    - Tool name (e.g., "search_pi_points")
    - Tool input parameters
    - MCP server name
  → Backend executes tool via MCP protocol
  → Tool returns data
  → Span updated with:
    - Tool output
    - Execution time
    - Success/error status
  → Span exported to Opik
```

### 3. Trace Hierarchy Example
```
Trace: "Chat Completion" (ID: abc123)
├─ Span: "HTTP POST /api/chat" (express)
│  ├─ Span: "MongoDB: findConversation" (mongodb)
│  ├─ Span: "Redis: getCache" (redis)
│  ├─ Span: "MCP Tool: search_af_elements_semantic" (custom)
│  │  └─ Metadata:
│  │     - tool_name: "search_af_elements_semantic"
│  │     - query: "temperature sensors"
│  │     - results_count: 5
│  │     - execution_time_ms: 234
│  ├─ Span: "OpenAI Chat Completion" (openai)
│  │  └─ Metadata:
│  │     - model: "gpt-4"
│  │     - prompt_tokens: 150
│  │     - completion_tokens: 75
│  │     - total_cost: 0.0045
│  └─ Span: "MongoDB: saveMessage" (mongodb)
```

## Key Features

### 1. End-to-End Tracing
- **Single Trace ID** spans from browser click to database write
- **W3C TraceContext** standard for distributed tracing
- **Parent-child relationships** show exact execution flow

### 2. MCP Tool Observability
- **Automatic instrumentation** of MCP tool calls
- **Detailed metadata** for each tool invocation
- **Performance metrics** (latency, success rate)
- **Tool usage patterns** visible in Opik dashboard

### 3. LLM Call Monitoring
- **Token usage** (prompt, completion, total)
- **Cost tracking** per model
- **Latency monitoring**
- **Error rate tracking**
- **Model comparison** across conversations

### 4. Conversation Context
- **Thread-based tracking** groups messages by conversation
- **User attribution** via metadata
- **Endpoint tracking** (openAI, anthropic, google, etc.)
- **Session persistence** across page refreshes

## Configuration

### Environment Variables

#### LibreChat Backend (.env)
```bash
# Opik Integration
OPIK_URL=http://opik-backend:8080
OPIK_API_KEY=your-api-key-here
OPIK_PROJECT_NAME=librechat
OPIK_WORKSPACE_NAME=default

# Enable OTEL
ENABLE_OTEL=true
OTEL_SERVICE_NAME=librechat-backend

# Debug (optional)
DEBUG_LOGGING=false
OTEL_LOG_LEVEL=info
```

#### LibreChat Frontend (.env)
```bash
# Frontend passes config from backend
# No direct configuration needed
```

#### Opik (.env)
```bash
OPIK_VERSION=0.1.10
ENABLE_OTEL_LOG_EXPORT=true
```

### Headers for Opik Integration

All OTEL traces sent to Opik must include:
```javascript
{
  "Authorization": "<OPIK_API_KEY>",
  "Comet-Workspace": "<OPIK_WORKSPACE_NAME>",
  "projectName": "<OPIK_PROJECT_NAME>",
  "Content-Type": "application/x-protobuf"
}
```

## MCP Server Integration

### Instrumentation Points

1. **MCP Client Initialization**
   - Track which MCP servers are connected
   - Monitor connection health

2. **Tool Discovery**
   - Log available tools from each MCP server
   - Track tool schema changes

3. **Tool Invocation**
   - Create span for each tool call
   - Include tool name, input, output, timing

4. **Error Handling**
   - Capture tool execution errors
   - Log error details in span attributes

### Custom Span Attributes for MCP Tools

```javascript
{
  "mcp.server.name": "PI System MCP",
  "mcp.tool.name": "search_af_elements_semantic",
  "mcp.tool.input": "{\"query\": \"temperature sensors\"}",
  "mcp.tool.output": "{\"results\": [...]}",
  "mcp.tool.execution_time_ms": 234,
  "mcp.tool.success": true,
  "mcp.tool.error": null,
  "mcp.tool.results_count": 5,

  // Additional context
  "conversation.id": "conv-123",
  "user.id": "user-456",
  "llm.request.id": "req-789"
}
```

## Deployment

### Prerequisites
- Docker & Docker Compose
- 8GB+ RAM (for Opik ClickHouse)
- Ports: 3080 (LibreChat), 5173 (Opik UI), 8080 (Opik API)

### Startup Sequence
```bash
# 1. Start Opik infrastructure
cd Librechat-opik-integration
docker compose --profile opik up -d

# Wait for Opik to be healthy (~30 seconds)
docker compose ps

# 2. Start LibreChat with OTEL enabled
docker compose --profile librechat up -d

# 3. Access services
# - LibreChat: http://localhost:3080
# - Opik UI: http://localhost:5173
```

### Health Checks
```bash
# Check Opik backend
curl http://localhost:8080/health

# Check LibreChat backend
curl http://localhost:3080/api/health

# Check Opik UI
curl http://localhost:5173
```

## Monitoring & Dashboards

### Opik UI Features

1. **Traces View**
   - All chat interactions with full trace trees
   - Filter by conversation, user, model
   - Search by trace ID or metadata

2. **LLM Analytics**
   - Token usage over time
   - Cost analysis by model
   - Latency percentiles (p50, p95, p99)
   - Error rates

3. **MCP Tool Analytics**
   - Most used tools
   - Tool success rates
   - Average execution time
   - Tool usage by conversation

4. **Feedback & Scoring**
   - Add user ratings to traces
   - Track conversation quality
   - Identify problematic interactions

### Custom Queries (ClickHouse)

Access ClickHouse directly for custom analytics:
```sql
-- Top 10 most used MCP tools
SELECT
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  COUNT(*) as usage_count,
  AVG(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as avg_time_ms
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.name')
GROUP BY tool_name
ORDER BY usage_count DESC
LIMIT 10;

-- LLM cost by model
SELECT
  JSONExtractString(attributes, 'llm.model') as model,
  SUM(CAST(JSONExtractString(attributes, 'llm.total_tokens') AS Int64)) as total_tokens,
  SUM(CAST(JSONExtractString(attributes, 'llm.cost') AS Float64)) as total_cost
FROM spans
WHERE JSONHas(attributes, 'llm.model')
GROUP BY model
ORDER BY total_cost DESC;
```

## Performance Considerations

### OTEL Overhead
- **Backend**: ~2-5ms per request (negligible)
- **Frontend**: ~1-3ms per interaction (negligible)
- **Network**: ~10-20ms for OTLP export (async, non-blocking)

### Opik Storage
- **ClickHouse**: Highly compressed, efficient storage
- **Typical trace size**: 5-10KB
- **1M traces/day**: ~5-10GB storage
- **Retention**: Configurable (default 30 days)

### Optimization Tips
1. **Batch exports**: OTEL SDK batches traces before sending
2. **Sampling**: Enable sampling for high-traffic deployments
3. **Async processing**: All OTEL operations are non-blocking
4. **Resource limits**: Configure OTEL SDK memory limits

## Security Considerations

1. **API Key Management**
   - Store in environment variables, not code
   - Rotate keys regularly
   - Use different keys for dev/staging/prod

2. **Network Security**
   - Use TLS for production Opik instances
   - Restrict Opik API access to backend only
   - Frontend sends traces via backend proxy

3. **Data Privacy**
   - Sensitive data (passwords, keys) excluded from traces
   - PII can be masked in span attributes
   - GDPR compliance: traces can be deleted by user ID

## Troubleshooting

### Traces not appearing in Opik

**Check 1**: Backend OTEL configuration
```bash
docker logs librechat-backend | grep -i otel
```

**Check 2**: Opik backend logs
```bash
docker logs opik-backend | grep -i trace
```

**Check 3**: Network connectivity
```bash
docker exec librechat-backend curl http://opik-backend:8080/health
```

### MCP tools not traced

**Check 1**: MCP middleware is loaded
```bash
grep -r "mcp-tracing" api/server/
```

**Check 2**: Active span context exists
```javascript
// In MCP tool call handler
const activeSpan = trace.getActiveSpan();
console.log('Active span:', activeSpan ? 'exists' : 'missing');
```

### High OTEL overhead

**Solution**: Enable sampling
```javascript
// In otel.js
sampler: new TraceIdRatioBasedSampler(0.1) // 10% sampling
```

## Future Enhancements

1. **Custom Metrics**
   - User satisfaction scores
   - Conversation quality metrics
   - MCP tool effectiveness ratings

2. **Alerts & Notifications**
   - High error rates
   - Slow LLM responses
   - MCP tool failures

3. **A/B Testing**
   - Compare models via Opik experiments
   - Test prompt variations
   - Measure tool usage impact

4. **Cost Optimization**
   - Identify expensive conversations
   - Suggest model alternatives
   - Track cost per user

## References

- [LibreChat Documentation](https://www.librechat.ai/)
- [Opik Documentation](https://www.comet.com/docs/opik/)
- [OpenTelemetry JavaScript](https://opentelemetry.io/docs/languages/js/)
- [W3C TraceContext Specification](https://www.w3.org/TR/trace-context/)
