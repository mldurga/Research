# LibreChat + Opik Integration

Complete OpenTelemetry-based observability for LibreChat with Opik, including MCP server tool tracking.

## 🎯 What This Integration Provides

- **End-to-End Tracing**: Single trace ID from browser click to database write
- **LLM Call Monitoring**: Token usage, costs, latency, and error tracking
- **MCP Tool Observability**: Automatic tracing of all MCP server tool invocations
- **Conversation Analytics**: Thread-based tracking, user attribution, and session persistence
- **Performance Insights**: P50/P95/P99 latencies, throughput metrics
- **Cost Tracking**: Per-conversation, per-user, per-model cost analysis
- **Self-Hosted**: All data stays in your infrastructure

## 📋 Prerequisites

- Docker & Docker Compose
- 8GB+ RAM (for Opik's ClickHouse database)
- LibreChat repository cloned
- (Optional) MCP server for tool tracking

## 🚀 Quick Start

### 1. Clone This Repository

```bash
cd /path/to/your/workspace
git clone <this-repo-url> librechat-opik-integration
cd librechat-opik-integration
```

### 2. Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

**Required environment variables:**
```bash
OPENAI_API_KEY=sk-your-key-here
OPIK_API_KEY=opik-default-key-change-in-production
```

### 3. Clone LibreChat

```bash
# Clone LibreChat into this directory
git clone https://github.com/danny-avila/LibreChat.git librechat
cd librechat
```

### 4. Apply OpenTelemetry Instrumentation

```bash
# Copy OTEL files to LibreChat
cp ../backend/otel.js ./api/server/middleware/
cp ../backend/mcp-tracing.js ./api/server/middleware/
cp ../backend/routes/otel-config.js ./api/server/routes/

# Copy frontend OTEL
cp ../frontend/otel.js ./client/src/utils/
```

### 5. Modify LibreChat to Load OTEL

#### Backend (api/server/index.js)

Add at the **very top** of the file (before any other imports):

```javascript
// Initialize OpenTelemetry FIRST
if (process.env.ENABLE_OTEL === 'true') {
  require('./middleware/otel');
  console.log('[LibreChat] OpenTelemetry instrumentation loaded');
}

// ... rest of your imports
const express = require('express');
// etc.
```

#### Backend - Add OTEL Config Route (api/server/index.js)

After mounting other routes:

```javascript
const otelConfigRouter = require('./routes/otel-config');
app.use('/api/config', otelConfigRouter);
```

#### Frontend (client/src/main.jsx)

Add near the top:

```javascript
import { initializeOTEL } from './utils/otel';

// Initialize OTEL as early as possible
if (import.meta.env.MODE !== 'test') {
  initializeOTEL().catch(console.error);
}

// ... rest of your app initialization
```

### 6. Update package.json Dependencies

#### Backend (package.json)

Add these dependencies:

```json
{
  "dependencies": {
    "@opentelemetry/api": "^1.7.0",
    "@opentelemetry/sdk-node": "^0.48.0",
    "@opentelemetry/auto-instrumentations-node": "^0.41.0",
    "@opentelemetry/exporter-trace-otlp-proto": "^0.48.0",
    "@opentelemetry/exporter-metrics-otlp-proto": "^0.48.0",
    "@opentelemetry/sdk-trace-base": "^1.21.0",
    "@opentelemetry/sdk-metrics": "^1.21.0",
    "@opentelemetry/resources": "^1.21.0",
    "@opentelemetry/semantic-conventions": "^1.21.0"
  }
}
```

#### Frontend (client/package.json)

Add these dependencies:

```json
{
  "dependencies": {
    "@opentelemetry/api": "^1.7.0",
    "@opentelemetry/sdk-trace-web": "^1.21.0",
    "@opentelemetry/exporter-trace-otlp-http": "^0.48.0",
    "@opentelemetry/auto-instrumentations-web": "^0.36.0",
    "@opentelemetry/instrumentation": "^0.48.0",
    "@opentelemetry/context-zone": "^1.21.0",
    "@opentelemetry/core": "^1.21.0",
    "@opentelemetry/resources": "^1.21.0",
    "@opentelemetry/semantic-conventions": "^1.21.0"
  }
}
```

### 7. Build Docker Images

```bash
# From librechat-opik-integration directory
cd librechat

# Install dependencies
npm install
cd client && npm install && cd ..

cd ..
```

### 8. Start Services

```bash
# Start Opik infrastructure
docker compose --profile opik up -d

# Wait ~30 seconds for Opik to initialize
echo "Waiting for Opik to start..."
sleep 30

# Check Opik health
curl http://localhost:8080/health

# Start LibreChat
docker compose --profile librechat up -d

# (Optional) Start MCP server
docker compose --profile mcp up -d
```

### 9. Access the Services

- **LibreChat UI**: http://localhost:3080
- **Opik Dashboard**: http://localhost:5173
- **Opik API**: http://localhost:8080
- **MCP Server** (if enabled): http://localhost:8001

### 10. Verify OTEL is Working

```bash
# Check backend logs
docker logs librechat-backend | grep OTEL

# Should see:
# [OTEL] Initializing OpenTelemetry for librechat-backend
# [OTEL] ✅ OpenTelemetry SDK initialized successfully
```

#### Test OTEL Configuration

```bash
curl -X POST http://localhost:3080/api/config/otel/test
```

Should return:
```json
{
  "success": true,
  "message": "OTEL configuration is valid and Opik is reachable"
}
```

## 🔧 MCP Server Integration

### Instrumenting MCP Clients in LibreChat

If you're using MCP servers with LibreChat, wrap your MCP clients with tracing:

```javascript
// In your MCP client initialization code
const { instrumentMCPClient } = require('./middleware/mcp-tracing');

// Original MCP client
const mcpClient = new MCPClient({
  serverUrl: process.env.MCP_SERVER_PI_URL,
  // ... other options
});

// Wrap with instrumentation
const tracedMCPClient = instrumentMCPClient(mcpClient, {
  serverName: 'PI System MCP',
  getConversationId: () => currentConversationId, // Function to get conversation ID
  getUserId: () => currentUserId, // Function to get user ID
});

// Use tracedMCPClient instead of mcpClient
// All tool calls will be automatically traced!
```

### Manual MCP Tool Tracing

For custom implementations:

```javascript
const { traceMCPTool } = require('./middleware/mcp-tracing');

async function myCustomMCPCall(conversationId, userId) {
  const result = await traceMCPTool(
    'PI System MCP',
    'search_af_elements_semantic',
    { query: 'temperature sensors', max_results: 10 },
    async () => {
      // Your actual MCP call logic
      return await mcpClient.callTool('search_af_elements_semantic', {
        query: 'temperature sensors',
        max_results: 10,
      });
    },
    { conversationId, userId }
  );

  return result;
}
```

### Express Middleware for MCP Context

Add this middleware to extract conversation context:

```javascript
const { mcpTracingMiddleware } = require('./middleware/mcp-tracing');

// Add to your Express app
app.use(mcpTracingMiddleware);

// Now req.mcpContext contains conversationId and userId
```

## 📊 Using Opik Dashboard

### Viewing Traces

1. Open http://localhost:5173
2. Navigate to **Traces**
3. You'll see all chat interactions with full trace trees
4. Click any trace to see:
   - HTTP requests
   - Database queries
   - LLM API calls
   - MCP tool invocations
   - Timing breakdown

### Filtering Traces

Use the search and filter options:
- Filter by **conversation ID**
- Filter by **user ID**
- Filter by **model** (gpt-4, claude-3-opus, etc.)
- Filter by **MCP tool name**
- Search by **trace ID**

### LLM Analytics

Navigate to **Analytics** tab:
- **Token Usage Over Time**: Daily/hourly token consumption
- **Cost Analysis**: Cost per model, per user, per conversation
- **Latency Metrics**: P50, P95, P99 latencies
- **Error Rates**: Failed LLM calls, timeouts

### MCP Tool Analytics

Custom queries in **ClickHouse**:

```sql
-- Top 10 most used MCP tools
SELECT
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  COUNT(*) as usage_count,
  AVG(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as avg_time_ms
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.name')
  AND timestamp > now() - INTERVAL 1 DAY
GROUP BY tool_name
ORDER BY usage_count DESC
LIMIT 10;

-- MCP tool success rates
SELECT
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  COUNT(*) as total_calls,
  SUM(CAST(JSONExtractString(attributes, 'mcp.tool.success') AS UInt8)) as successful_calls,
  (successful_calls / total_calls) * 100 as success_rate
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.name')
GROUP BY tool_name;
```

Access ClickHouse:
```bash
docker exec -it opik-clickhouse clickhouse-client
```

## 🧪 Testing the Integration

### 1. Send a Chat Message

```bash
curl -X POST http://localhost:3080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "Hello, what is the weather?",
    "conversationId": "test-conv-123",
    "model": "gpt-4"
  }'
```

### 2. Check Opik Dashboard

1. Go to http://localhost:5173
2. Navigate to **Traces**
3. You should see a new trace: `HTTP POST /api/chat`
4. Click to expand and see:
   - MongoDB query spans
   - OpenAI API call span
   - Response generation

### 3. Test MCP Tool Tracking

If using MCP servers, send a message that triggers tool usage:

```bash
curl -X POST http://localhost:3080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "Search for temperature sensors in the PI system",
    "conversationId": "test-conv-123",
    "model": "gpt-4"
  }'
```

In Opik, you should see:
- HTTP request span
- LLM API call span
- **MCP Tool: search_af_elements_semantic** span
  - With attributes: tool name, input, output, execution time

## 🔍 Advanced Usage

### Tracing Custom Operations

#### Backend

```javascript
const { traceLLMCall } = require('./middleware/otel');

async function customLLMCall(messages, conversationId, userId) {
  return await traceLLMCall(
    'openai',
    'gpt-4',
    { messages, temperature: 0.7 },
    async () => {
      // Your actual OpenAI call
      return await openai.chat.completions.create({
        model: 'gpt-4',
        messages,
      });
    },
    { conversationId, userId, endpoint: 'custom' }
  );
}
```

#### Frontend

```javascript
import { traceUserAction, setConversationContext } from './utils/otel';

function ChatComponent() {
  const handleSendMessage = async (message) => {
    // Set conversation context
    setConversationContext(conversationId, {
      'user.id': userId,
      'chat.endpoint': selectedEndpoint,
    });

    // Trace the send action
    await traceUserAction(
      'send_message',
      async () => {
        const response = await fetch('/api/chat', {
          method: 'POST',
          body: JSON.stringify({ message, conversationId }),
        });
        return await response.json();
      },
      {
        'message.length': message.length,
        'model': selectedModel,
      }
    );
  };

  return <button onClick={() => handleSendMessage('Hello!')}>Send</button>;
}
```

### React Hook for Component Tracing

```javascript
import { useOTELTrace } from './utils/otel';

function MyComponent() {
  const { traceAction } = useOTELTrace('MyComponent');

  const handleClick = async () => {
    await traceAction('button_click', async () => {
      // Your logic here
      await someAsyncOperation();
    }, {
      'button.id': 'submit-btn',
    });
  };

  return <button onClick={handleClick}>Click Me</button>;
}
```

## 🐛 Troubleshooting

### OTEL Not Initializing

**Symptom**: No traces in Opik dashboard

**Check 1**: Backend logs
```bash
docker logs librechat-backend | grep OTEL
```

Should see:
```
[OTEL] Initializing OpenTelemetry for librechat-backend
[OTEL] ✅ OpenTelemetry SDK initialized successfully
```

**Check 2**: Environment variables
```bash
docker exec librechat-backend env | grep OTEL
docker exec librechat-backend env | grep OPIK
```

**Check 3**: OTEL module is loaded
```bash
docker exec librechat-backend cat /app/api/server/index.js | head -5
```

Should see `require('./middleware/otel')` at the top.

### Opik Backend Not Reachable

**Symptom**: Error logs mention connection refused

**Check 1**: Opik health
```bash
curl http://localhost:8080/health
docker logs opik-backend
```

**Check 2**: Network connectivity
```bash
docker exec librechat-backend ping opik-backend
```

**Check 3**: Opik containers running
```bash
docker compose ps
```

All Opik services should be "Up" and "healthy".

### MCP Tools Not Traced

**Symptom**: LLM calls visible but no MCP tool spans

**Check 1**: MCP middleware is loaded
```bash
docker exec librechat-backend ls /app/api/server/middleware/mcp-tracing.js
```

**Check 2**: MCP client is instrumented
Search your code for `instrumentMCPClient` usage.

**Check 3**: Debug logging
Set `DEBUG_LOGGING=true` in .env and restart:
```bash
docker compose --profile librechat restart
docker logs -f librechat-backend | grep MCP
```

### High OTEL Overhead

**Symptom**: Slow responses

**Solution 1**: Enable sampling
In `backend/otel.js`, add:
```javascript
const { TraceIdRatioBasedSampler } = require('@opentelemetry/sdk-trace-base');

const sdk = new NodeSDK({
  // ... other config
  sampler: new TraceIdRatioBasedSampler(0.1), // 10% sampling
});
```

**Solution 2**: Disable file system instrumentation
Already done in the provided config:
```javascript
'@opentelemetry/instrumentation-fs': {
  enabled: false,
},
```

**Solution 3**: Increase batch export interval
In `backend/otel.js`:
```javascript
spanProcessor: new BatchSpanProcessor(traceExporter, {
  scheduledDelayMillis: 10000, // 10 seconds instead of 5
}),
```

## 📖 Additional Resources

### Documentation

- [LibreChat Documentation](https://www.librechat.ai/)
- [Opik Documentation](https://www.comet.com/docs/opik/)
- [OpenTelemetry JavaScript](https://opentelemetry.io/docs/languages/js/)
- [Architecture Guide](./ARCHITECTURE.md)

### Example Queries

See `examples/opik-queries.sql` for more ClickHouse queries.

### MCP Server Example

See `../mcp/` for a complete MCP server implementation with PI System integration.

## 🤝 Contributing

Found a bug? Have a feature request? Open an issue!

Want to contribute? PRs welcome!

## 📄 License

This integration code is provided as-is for educational and integration purposes.

## 🙏 Acknowledgments

- [LibreChat](https://github.com/danny-avila/LibreChat) - Amazing open-source ChatGPT alternative
- [Opik](https://github.com/comet-ml/opik) - Powerful LLM observability platform
- [OpenTelemetry](https://opentelemetry.io/) - Vendor-neutral observability framework
- [kvasir-cone-snail's OTEL fork](https://github.com/kvasir-cone-snail/LibreChat/tree/feat/otel) - Inspiration for this integration
