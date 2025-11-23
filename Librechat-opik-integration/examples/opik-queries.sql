-- ClickHouse Queries for Opik LLM Observability
-- Access ClickHouse: docker exec -it opik-clickhouse clickhouse-client

-- ========================================
-- MCP Tool Usage Analytics
-- ========================================

-- 1. Top 10 Most Used MCP Tools
SELECT
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  COUNT(*) as usage_count,
  AVG(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as avg_time_ms,
  MIN(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as min_time_ms,
  MAX(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as max_time_ms
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.name')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY tool_name
ORDER BY usage_count DESC
LIMIT 10;

-- 2. MCP Tool Success Rates
SELECT
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  COUNT(*) as total_calls,
  SUM(CASE WHEN JSONExtractString(attributes, 'mcp.tool.success') = 'true' THEN 1 ELSE 0 END) as successful_calls,
  (successful_calls * 100.0 / total_calls) as success_rate_percent
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.name')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY tool_name
ORDER BY success_rate_percent ASC;

-- 3. MCP Tool Usage by MCP Server
SELECT
  JSONExtractString(attributes, 'mcp.server.name') as server_name,
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  COUNT(*) as usage_count,
  AVG(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as avg_time_ms
FROM spans
WHERE JSONHas(attributes, 'mcp.server.name')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY server_name, tool_name
ORDER BY usage_count DESC;

-- 4. MCP Tool Errors (Last 24 Hours)
SELECT
  timestamp,
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  JSONExtractString(attributes, 'mcp.server.name') as server_name,
  JSONExtractString(attributes, 'mcp.tool.error') as error_message,
  JSONExtractString(attributes, 'conversation.id') as conversation_id
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.error')
  AND JSONExtractString(attributes, 'mcp.tool.success') = 'false'
  AND timestamp > now() - INTERVAL 1 DAY
ORDER BY timestamp DESC
LIMIT 20;

-- 5. Slowest MCP Tool Calls
SELECT
  timestamp,
  JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
  CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64) as execution_time_ms,
  JSONExtractString(attributes, 'conversation.id') as conversation_id,
  JSONExtractString(attributes, 'user.id') as user_id
FROM spans
WHERE JSONHas(attributes, 'mcp.tool.name')
  AND timestamp > now() - INTERVAL 1 DAY
ORDER BY execution_time_ms DESC
LIMIT 10;

-- ========================================
-- LLM Call Analytics
-- ========================================

-- 6. LLM Token Usage by Model
SELECT
  JSONExtractString(attributes, 'llm.model') as model,
  COUNT(*) as total_calls,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as total_tokens,
  AVG(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as avg_tokens_per_call,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.prompt_tokens') AS Int64)) as prompt_tokens,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.completion_tokens') AS Int64)) as completion_tokens
FROM spans
WHERE JSONHas(attributes, 'llm.model')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY model
ORDER BY total_tokens DESC;

-- 7. LLM Cost Analysis
SELECT
  JSONExtractString(attributes, 'llm.provider') as provider,
  JSONExtractString(attributes, 'llm.model') as model,
  COUNT(*) as total_calls,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as total_cost,
  AVG(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as avg_cost_per_call
FROM spans
WHERE JSONHas(attributes, 'llm.model')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY provider, model
ORDER BY total_cost DESC;

-- 8. LLM Call Latency Percentiles
SELECT
  JSONExtractString(attributes, 'llm.model') as model,
  COUNT(*) as total_calls,
  AVG(CAST(JSONExtractString(attributes, 'llm.response.latency_ms') AS Float64)) as avg_latency,
  quantile(0.5)(CAST(JSONExtractString(attributes, 'llm.response.latency_ms') AS Float64)) as p50_latency,
  quantile(0.95)(CAST(JSONExtractString(attributes, 'llm.response.latency_ms') AS Float64)) as p95_latency,
  quantile(0.99)(CAST(JSONExtractString(attributes, 'llm.response.latency_ms') AS Float64)) as p99_latency
FROM spans
WHERE JSONHas(attributes, 'llm.model')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY model;

-- 9. LLM Errors by Provider
SELECT
  JSONExtractString(attributes, 'llm.provider') as provider,
  JSONExtractString(attributes, 'llm.model') as model,
  JSONExtractString(attributes, 'error.message') as error_message,
  COUNT(*) as error_count
FROM spans
WHERE JSONHas(attributes, 'llm.model')
  AND JSONHas(attributes, 'error')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY provider, model, error_message
ORDER BY error_count DESC;

-- 10. LLM Calls with MCP Tool Usage (Correlated)
SELECT
  trace_id,
  timestamp,
  JSONExtractString(attributes, 'llm.model') as llm_model,
  JSONExtractString(attributes, 'mcp.tool.name') as mcp_tool_used,
  JSONExtractString(attributes, 'conversation.id') as conversation_id
FROM spans
WHERE trace_id IN (
  SELECT DISTINCT trace_id
  FROM spans
  WHERE JSONHas(attributes, 'mcp.tool.name')
    AND timestamp > now() - INTERVAL 1 DAY
)
  AND (JSONHas(attributes, 'llm.model') OR JSONHas(attributes, 'mcp.tool.name'))
ORDER BY timestamp DESC
LIMIT 100;

-- ========================================
-- Conversation Analytics
-- ========================================

-- 11. Most Active Conversations
SELECT
  JSONExtractString(attributes, 'conversation.id') as conversation_id,
  COUNT(DISTINCT trace_id) as message_count,
  COUNT(DISTINCT CASE WHEN JSONHas(attributes, 'mcp.tool.name') THEN span_id END) as mcp_tool_calls,
  COUNT(DISTINCT CASE WHEN JSONHas(attributes, 'llm.model') THEN span_id END) as llm_calls,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as total_tokens
FROM spans
WHERE JSONHas(attributes, 'conversation.id')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY conversation_id
ORDER BY message_count DESC
LIMIT 20;

-- 12. User Activity Summary
SELECT
  JSONExtractString(attributes, 'user.id') as user_id,
  COUNT(DISTINCT JSONExtractString(attributes, 'conversation.id')) as conversation_count,
  COUNT(DISTINCT trace_id) as message_count,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as total_tokens,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as total_cost
FROM spans
WHERE JSONHas(attributes, 'user.id')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY user_id
ORDER BY total_cost DESC;

-- 13. Hourly Traffic Pattern
SELECT
  toStartOfHour(timestamp) as hour,
  COUNT(DISTINCT trace_id) as request_count,
  COUNT(DISTINCT CASE WHEN JSONHas(attributes, 'llm.model') THEN span_id END) as llm_call_count,
  COUNT(DISTINCT CASE WHEN JSONHas(attributes, 'mcp.tool.name') THEN span_id END) as mcp_tool_count
FROM spans
WHERE timestamp > now() - INTERVAL 7 DAY
GROUP BY hour
ORDER BY hour DESC;

-- ========================================
-- Performance & Health Monitoring
-- ========================================

-- 14. HTTP Request Latency by Endpoint
SELECT
  JSONExtractString(attributes, 'http.route') as route,
  COUNT(*) as request_count,
  AVG(duration_ms) as avg_latency_ms,
  quantile(0.95)(duration_ms) as p95_latency_ms,
  quantile(0.99)(duration_ms) as p99_latency_ms
FROM spans
WHERE JSONHas(attributes, 'http.route')
  AND timestamp > now() - INTERVAL 1 DAY
GROUP BY route
ORDER BY avg_latency_ms DESC;

-- 15. Database Query Performance
SELECT
  JSONExtractString(attributes, 'db.operation') as operation,
  JSONExtractString(attributes, 'db.mongodb.collection') as collection,
  COUNT(*) as query_count,
  AVG(duration_ms) as avg_duration_ms,
  MAX(duration_ms) as max_duration_ms
FROM spans
WHERE JSONHas(attributes, 'db.operation')
  AND timestamp > now() - INTERVAL 1 DAY
GROUP BY operation, collection
ORDER BY avg_duration_ms DESC
LIMIT 20;

-- 16. Error Rate Over Time
SELECT
  toStartOfHour(timestamp) as hour,
  COUNT(*) as total_spans,
  SUM(CASE WHEN JSONHas(attributes, 'error') THEN 1 ELSE 0 END) as error_count,
  (error_count * 100.0 / total_spans) as error_rate_percent
FROM spans
WHERE timestamp > now() - INTERVAL 7 DAY
GROUP BY hour
ORDER BY hour DESC;

-- 17. Slowest Traces (End-to-End)
SELECT
  trace_id,
  MIN(timestamp) as start_time,
  MAX(timestamp + INTERVAL duration_ms MILLISECOND) as end_time,
  dateDiff('millisecond', start_time, end_time) as total_duration_ms,
  COUNT(*) as span_count,
  ANY(JSONExtractString(attributes, 'conversation.id')) as conversation_id
FROM spans
WHERE timestamp > now() - INTERVAL 1 DAY
GROUP BY trace_id
ORDER BY total_duration_ms DESC
LIMIT 10;

-- ========================================
-- Cost Optimization Insights
-- ========================================

-- 18. Cost per Conversation
SELECT
  JSONExtractString(attributes, 'conversation.id') as conversation_id,
  COUNT(DISTINCT CASE WHEN JSONHas(attributes, 'llm.model') THEN span_id END) as llm_calls,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as total_tokens,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as total_cost,
  AVG(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as avg_cost_per_call
FROM spans
WHERE JSONHas(attributes, 'conversation.id')
  AND JSONHas(attributes, 'llm.response.estimated_cost')
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY conversation_id
ORDER BY total_cost DESC
LIMIT 20;

-- 19. Most Expensive Users
SELECT
  JSONExtractString(attributes, 'user.id') as user_id,
  COUNT(DISTINCT JSONExtractString(attributes, 'conversation.id')) as conversation_count,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as total_tokens,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as total_cost
FROM spans
WHERE JSONHas(attributes, 'user.id')
  AND JSONHas(attributes, 'llm.response.estimated_cost')
  AND timestamp > now() - INTERVAL 30 DAY
GROUP BY user_id
ORDER BY total_cost DESC
LIMIT 10;

-- 20. Token Usage Trends (Daily)
SELECT
  toDate(timestamp) as date,
  JSONExtractString(attributes, 'llm.model') as model,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.total_tokens') AS Int64)) as daily_tokens,
  SUM(CAST(JSONExtractString(attributes, 'llm.response.estimated_cost') AS Float64)) as daily_cost
FROM spans
WHERE JSONHas(attributes, 'llm.model')
  AND timestamp > now() - INTERVAL 30 DAY
GROUP BY date, model
ORDER BY date DESC, daily_cost DESC;

-- ========================================
-- Custom Views for Common Queries
-- ========================================

-- Create materialized view for quick MCP tool analytics
-- (Run this once to create the view)

-- CREATE MATERIALIZED VIEW IF NOT EXISTS mcp_tool_summary
-- ENGINE = SummingMergeTree()
-- ORDER BY (tool_name, server_name, toDate(timestamp))
-- AS SELECT
--   toDate(timestamp) as date,
--   JSONExtractString(attributes, 'mcp.server.name') as server_name,
--   JSONExtractString(attributes, 'mcp.tool.name') as tool_name,
--   COUNT(*) as call_count,
--   SUM(CAST(JSONExtractString(attributes, 'mcp.tool.execution_time_ms') AS Float64)) as total_exec_time,
--   SUM(CASE WHEN JSONExtractString(attributes, 'mcp.tool.success') = 'true' THEN 1 ELSE 0 END) as success_count
-- FROM spans
-- WHERE JSONHas(attributes, 'mcp.tool.name')
-- GROUP BY date, server_name, tool_name;

-- Query the materialized view (much faster for aggregations)
-- SELECT
--   tool_name,
--   SUM(call_count) as total_calls,
--   AVG(total_exec_time / call_count) as avg_exec_time,
--   (SUM(success_count) * 100.0 / SUM(call_count)) as success_rate
-- FROM mcp_tool_summary
-- WHERE date >= today() - 7
-- GROUP BY tool_name
-- ORDER BY total_calls DESC;
