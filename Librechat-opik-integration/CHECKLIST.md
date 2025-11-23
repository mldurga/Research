# LibreChat + Opik Integration - Setup Checklist

Use this checklist to verify your setup is complete and working correctly.

## 📋 Pre-Setup Checklist

- [ ] Docker installed and running
- [ ] Docker Compose available
- [ ] At least 8GB RAM available
- [ ] Ports available: 3080, 5173, 8080, 8000
- [ ] Git installed
- [ ] OpenAI API key (or other LLM provider keys)

## 🔧 Setup Checklist

### 1. Environment Configuration

- [ ] Copied `.env.example` to `.env`
- [ ] Added `OPENAI_API_KEY` to `.env`
- [ ] (Optional) Added `ANTHROPIC_API_KEY` to `.env`
- [ ] (Optional) Added `GOOGLE_API_KEY` to `.env`
- [ ] Set `OPIK_API_KEY` in `.env`
- [ ] Set `OPIK_PROJECT_NAME` in `.env`
- [ ] Set `OPIK_WORKSPACE_NAME` in `.env`

### 2. LibreChat Setup

- [ ] Cloned LibreChat repository
- [ ] Copied `backend/otel.js` to `librechat/api/server/middleware/`
- [ ] Copied `backend/mcp-tracing.js` to `librechat/api/server/middleware/`
- [ ] Copied `backend/routes/otel-config.js` to `librechat/api/server/routes/`
- [ ] Copied `frontend/otel.js` to `librechat/client/src/utils/`
- [ ] Modified `librechat/api/server/index.js` to load OTEL at the top
- [ ] Modified `librechat/client/src/main.jsx` to initialize OTEL
- [ ] Installed backend OTEL dependencies
- [ ] Installed frontend OTEL dependencies

### 3. Docker Deployment

- [ ] Started Opik: `docker compose --profile opik up -d`
- [ ] Waited 30-60 seconds for Opik to initialize
- [ ] Verified Opik health: `curl http://localhost:8080/health`
- [ ] Started LibreChat: `docker compose --profile librechat up -d`
- [ ] Waited for LibreChat to start
- [ ] Verified LibreChat health: `curl http://localhost:3080`

### 4. OTEL Verification

- [ ] Checked backend logs: `docker logs librechat-backend | grep OTEL`
- [ ] Saw "✅ OpenTelemetry SDK initialized successfully" in logs
- [ ] Tested OTEL config: `curl -X POST http://localhost:3080/api/config/otel/test`
- [ ] Received `{"success": true}` response
- [ ] Opened Opik dashboard: http://localhost:5173
- [ ] Opik dashboard loaded successfully

### 5. Integration Testing

- [ ] Opened LibreChat: http://localhost:3080
- [ ] Created an account / logged in
- [ ] Started a new conversation
- [ ] Sent a test message
- [ ] Received response from LLM
- [ ] Opened Opik dashboard
- [ ] Saw new trace in Opik Traces view
- [ ] Clicked trace to see details
- [ ] Saw HTTP request span
- [ ] Saw MongoDB query spans
- [ ] Saw LLM API call span with token usage

### 6. MCP Server Integration (Optional)

- [ ] MCP server code available in `../mcp/`
- [ ] Created MCP Dockerfile
- [ ] Set MCP environment variables in `.env`
- [ ] Started MCP server: `docker compose --profile mcp up -d`
- [ ] Verified MCP health: `curl http://localhost:8001/health`
- [ ] Sent message that uses MCP tools
- [ ] Saw MCP tool spans in Opik trace

## 🔍 Verification Tests

### Test 1: Basic Chat with OTEL

```bash
# Send a test message
curl -X POST http://localhost:3080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "Hello, what is 2+2?",
    "model": "gpt-4"
  }'
```

- [ ] Response received successfully
- [ ] Trace appeared in Opik dashboard within 5-10 seconds
- [ ] Trace contains LLM span with token usage

### Test 2: OTEL Configuration

```bash
# Test OTEL configuration
curl -X POST http://localhost:3080/api/config/otel/test
```

Expected response:
```json
{
  "success": true,
  "message": "OTEL configuration is valid and Opik is reachable",
  "config": {
    "opikUrl": "http://opik-backend:8080",
    "projectName": "librechat",
    "workspaceName": "default"
  }
}
```

- [ ] Test passed successfully

### Test 3: Frontend OTEL

- [ ] Opened browser developer console
- [ ] Navigated to LibreChat
- [ ] Checked console for OTEL messages
- [ ] Saw "[OTEL] Browser instrumentation initialized successfully"
- [ ] No JavaScript errors related to OTEL

### Test 4: MCP Tool Tracing (if MCP enabled)

- [ ] Sent message that triggers MCP tool usage
- [ ] Saw MCP tool span in Opik trace
- [ ] MCP tool span has attributes:
  - `mcp.tool.name`
  - `mcp.tool.execution_time_ms`
  - `mcp.tool.success`
  - `mcp.server.name`

### Test 5: Analytics Queries

```bash
# Access ClickHouse
docker exec -it opik-clickhouse clickhouse-client

# Run test query
SELECT COUNT(*) FROM spans WHERE timestamp > now() - INTERVAL 1 HOUR;
```

- [ ] Query executed successfully
- [ ] Returned non-zero count

## 📊 Post-Setup Checklist

### Opik Dashboard Exploration

- [ ] Navigated to Traces view
- [ ] Filtered traces by time range
- [ ] Searched for specific conversation ID
- [ ] Viewed trace details with span tree
- [ ] Checked LLM span for token usage and cost
- [ ] Navigated to Analytics tab
- [ ] Viewed token usage over time chart
- [ ] Viewed cost analysis chart

### Performance Check

- [ ] LibreChat response time feels normal (no noticeable slowdown)
- [ ] Backend logs show no OTEL errors
- [ ] Opik backend logs show traces being ingested
- [ ] ClickHouse memory usage is acceptable

### Security Check

- [ ] `.env` file is not committed to git
- [ ] API keys are set in environment variables, not code
- [ ] OPIK_API_KEY is unique and secure
- [ ] (Production) Opik API uses HTTPS
- [ ] (Production) Opik dashboard requires authentication

## 🐛 Troubleshooting

If any checklist item fails, refer to:

- **README.md** - Detailed setup instructions
- **ARCHITECTURE.md** - Technical architecture details
- **Troubleshooting section in README.md** - Common issues and solutions

### Common Issues

| Issue | Quick Fix |
|-------|-----------|
| Traces not appearing | Check `docker logs librechat-backend \| grep OTEL` |
| Opik not starting | Check `docker logs opik-backend` |
| LibreChat not connecting to Opik | Verify `OPIK_URL` in `.env` |
| MCP tools not traced | Check MCP client is wrapped with `instrumentMCPClient()` |

## ✅ Final Verification

All systems are operational when:

- [ ] ✅ LibreChat UI accessible at http://localhost:3080
- [ ] ✅ Opik UI accessible at http://localhost:5173
- [ ] ✅ Chat messages generate traces in Opik
- [ ] ✅ LLM calls show token usage and costs
- [ ] ✅ (If MCP enabled) Tool calls are traced
- [ ] ✅ No errors in any container logs
- [ ] ✅ Response times are acceptable

## 🎉 Success!

If all items are checked, your LibreChat + Opik integration is complete and working!

### Next Steps:

1. **Explore the Dashboard**: Try different filters and views in Opik
2. **Run Analytics Queries**: Use examples from `examples/opik-queries.sql`
3. **Monitor Costs**: Set up alerts for high token usage
4. **Optimize Performance**: Review slow traces and optimize
5. **Read Documentation**: Check ARCHITECTURE.md for advanced usage

---

**Need Help?**
- Check the troubleshooting section in README.md
- Review logs: `docker logs <container-name>`
- Open an issue with detailed logs and error messages
