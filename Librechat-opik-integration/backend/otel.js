/**
 * OpenTelemetry Instrumentation for LibreChat Backend
 * Integrates with Opik for LLM observability
 *
 * This file must be loaded BEFORE any other application code
 * Usage: node -r ./backend/otel.js server.js
 */

const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-proto');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-proto');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const { BatchSpanProcessor } = require('@opentelemetry/sdk-trace-base');
const { context, trace, SpanStatusCode } = require('@opentelemetry/api');

// Check if OTEL is enabled
const ENABLE_OTEL = process.env.ENABLE_OTEL === 'true';
const DEBUG_LOGGING = process.env.DEBUG_LOGGING === 'true';

if (!ENABLE_OTEL) {
  console.log('[OTEL] OpenTelemetry disabled (ENABLE_OTEL=false)');
  module.exports = {
    traceMCPToolCall: () => {},
    traceLLMCall: () => {},
    getActiveSpan: () => null,
    startSpan: () => ({ end: () => {} }),
  };
  return;
}

// Opik configuration
const OPIK_URL = process.env.OPIK_URL || 'http://localhost:8080';
const OPIK_API_KEY = process.env.OPIK_API_KEY || '';
const OPIK_PROJECT_NAME = process.env.OPIK_PROJECT_NAME || 'librechat';
const OPIK_WORKSPACE_NAME = process.env.OPIK_WORKSPACE_NAME || 'default';
const OTEL_SERVICE_NAME = process.env.OTEL_SERVICE_NAME || 'librechat-backend';

console.log(`[OTEL] Initializing OpenTelemetry for ${OTEL_SERVICE_NAME}`);
console.log(`[OTEL] Opik URL: ${OPIK_URL}`);
console.log(`[OTEL] Opik Project: ${OPIK_PROJECT_NAME}`);
console.log(`[OTEL] Opik Workspace: ${OPIK_WORKSPACE_NAME}`);

// Configure OTLP Trace Exporter for Opik
const traceExporter = new OTLPTraceExporter({
  url: `${OPIK_URL}/api/v1/private/otel/v1/traces`,
  headers: {
    'Authorization': OPIK_API_KEY,
    'Comet-Workspace': OPIK_WORKSPACE_NAME,
    'projectName': OPIK_PROJECT_NAME,
    'Content-Type': 'application/x-protobuf',
  },
  timeoutMillis: 15000,
});

// Configure OTLP Metrics Exporter for Opik
const metricExporter = new OTLPMetricExporter({
  url: `${OPIK_URL}/api/v1/private/otel/v1/metrics`,
  headers: {
    'Authorization': OPIK_API_KEY,
    'Comet-Workspace': OPIK_WORKSPACE_NAME,
    'projectName': OPIK_PROJECT_NAME,
    'Content-Type': 'application/x-protobuf',
  },
  timeoutMillis: 15000,
});

// Create metric reader
const metricReader = new PeriodicExportingMetricReader({
  exporter: metricExporter,
  exportIntervalMillis: 60000, // Export every 60 seconds
});

// Configure resource attributes
const resource = new Resource({
  [SemanticResourceAttributes.SERVICE_NAME]: OTEL_SERVICE_NAME,
  [SemanticResourceAttributes.SERVICE_VERSION]: process.env.npm_package_version || '1.0.0',
  [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
  // Opik-specific attributes
  'opik.project': OPIK_PROJECT_NAME,
  'opik.workspace': OPIK_WORKSPACE_NAME,
});

// Initialize OpenTelemetry SDK
const sdk = new NodeSDK({
  resource,
  traceExporter,
  metricReader,
  spanProcessor: new BatchSpanProcessor(traceExporter, {
    maxQueueSize: 2048,
    maxExportBatchSize: 512,
    scheduledDelayMillis: 5000,
  }),
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': {
        enabled: false, // Disable file system instrumentation (too noisy)
      },
      '@opentelemetry/instrumentation-http': {
        enabled: true,
        ignoreIncomingPaths: ['/health', '/favicon.ico'],
        requestHook: (span, request) => {
          // Add custom attributes to HTTP spans
          span.setAttribute('http.user_agent', request.headers['user-agent'] || 'unknown');

          // Extract conversation/user context from headers if present
          if (request.headers['x-conversation-id']) {
            span.setAttribute('conversation.id', request.headers['x-conversation-id']);
          }
          if (request.headers['x-user-id']) {
            span.setAttribute('user.id', request.headers['x-user-id']);
          }
        },
      },
      '@opentelemetry/instrumentation-express': {
        enabled: true,
        requestHook: (span, req) => {
          // Add Express-specific metadata
          span.setAttribute('express.route', req.route?.path || 'unknown');
        },
      },
      '@opentelemetry/instrumentation-mongodb': {
        enabled: true,
        enhancedDatabaseReporting: true,
      },
      '@opentelemetry/instrumentation-redis': {
        enabled: true,
      },
    }),
  ],
});

// Start the SDK
sdk.start()
  .then(() => {
    console.log('[OTEL] ✅ OpenTelemetry SDK initialized successfully');
    console.log('[OTEL] Traces will be sent to Opik at', OPIK_URL);
  })
  .catch((error) => {
    console.error('[OTEL] ❌ Error initializing OpenTelemetry SDK:', error);
  });

// Graceful shutdown
process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('[OTEL] SDK shut down successfully'))
    .catch((error) => console.error('[OTEL] Error shutting down SDK:', error))
    .finally(() => process.exit(0));
});

// ===================================
// Helper Functions for Custom Tracing
// ===================================

/**
 * Get the tracer instance
 */
const tracer = trace.getTracer(OTEL_SERVICE_NAME);

/**
 * Get the currently active span
 */
function getActiveSpan() {
  return trace.getActiveSpan();
}

/**
 * Start a new span (generic)
 */
function startSpan(name, attributes = {}, options = {}) {
  return tracer.startSpan(name, {
    attributes,
    ...options,
  });
}

/**
 * Trace an MCP tool call
 *
 * @param {string} toolName - Name of the MCP tool
 * @param {object} toolInput - Input parameters for the tool
 * @param {Function} executeFn - Async function that executes the tool
 * @param {object} metadata - Additional metadata (conversationId, userId, etc.)
 * @returns {Promise} - Result of the tool execution
 */
async function traceMCPToolCall(toolName, toolInput, executeFn, metadata = {}) {
  const span = tracer.startSpan(`MCP Tool: ${toolName}`, {
    attributes: {
      'mcp.tool.name': toolName,
      'mcp.tool.input': JSON.stringify(toolInput),
      'span.kind': 'internal',
      'component': 'mcp-client',

      // Add conversation context
      ...(metadata.conversationId && { 'conversation.id': metadata.conversationId }),
      ...(metadata.userId && { 'user.id': metadata.userId }),
      ...(metadata.mcpServerName && { 'mcp.server.name': metadata.mcpServerName }),
    },
  });

  const startTime = Date.now();

  try {
    if (DEBUG_LOGGING) {
      console.log(`[OTEL] Starting MCP tool call: ${toolName}`);
    }

    // Execute the tool within the span context
    const result = await context.with(trace.setSpan(context.active(), span), async () => {
      return await executeFn();
    });

    const executionTime = Date.now() - startTime;

    // Update span with successful result
    span.setAttributes({
      'mcp.tool.success': true,
      'mcp.tool.execution_time_ms': executionTime,
      'mcp.tool.output': JSON.stringify(result).substring(0, 1000), // Truncate large outputs
    });

    // Add result metadata if available
    if (result && typeof result === 'object') {
      if (result.count !== undefined) {
        span.setAttribute('mcp.tool.results_count', result.count);
      }
      if (result.error) {
        span.setAttribute('mcp.tool.error', result.error);
      }
    }

    span.setStatus({ code: SpanStatusCode.OK });

    if (DEBUG_LOGGING) {
      console.log(`[OTEL] MCP tool call completed: ${toolName} (${executionTime}ms)`);
    }

    return result;
  } catch (error) {
    const executionTime = Date.now() - startTime;

    // Record error in span
    span.setAttributes({
      'mcp.tool.success': false,
      'mcp.tool.execution_time_ms': executionTime,
      'mcp.tool.error': error.message,
      'error': true,
    });

    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error.message,
    });

    span.recordException(error);

    console.error(`[OTEL] MCP tool call failed: ${toolName}`, error);

    throw error;
  } finally {
    span.end();
  }
}

/**
 * Trace an LLM API call
 *
 * @param {string} provider - LLM provider (openai, anthropic, google, etc.)
 * @param {string} model - Model name (gpt-4, claude-3-opus, etc.)
 * @param {object} request - LLM request parameters
 * @param {Function} executeFn - Async function that makes the LLM call
 * @param {object} metadata - Additional metadata
 * @returns {Promise} - Result of the LLM call
 */
async function traceLLMCall(provider, model, request, executeFn, metadata = {}) {
  const span = tracer.startSpan(`LLM Call: ${provider}/${model}`, {
    attributes: {
      'llm.provider': provider,
      'llm.model': model,
      'llm.request.messages_count': request.messages?.length || 0,
      'llm.request.temperature': request.temperature,
      'llm.request.max_tokens': request.max_tokens,
      'llm.request.stream': request.stream || false,
      'span.kind': 'client',
      'component': 'llm-client',

      // Add conversation context
      ...(metadata.conversationId && { 'conversation.id': metadata.conversationId }),
      ...(metadata.userId && { 'user.id': metadata.userId }),
      ...(metadata.endpoint && { 'llm.endpoint': metadata.endpoint }),
    },
  });

  const startTime = Date.now();

  try {
    if (DEBUG_LOGGING) {
      console.log(`[OTEL] Starting LLM call: ${provider}/${model}`);
    }

    // Execute the LLM call within the span context
    const result = await context.with(trace.setSpan(context.active(), span), async () => {
      return await executeFn();
    });

    const executionTime = Date.now() - startTime;

    // Extract token usage from result
    const usage = result.usage || {};
    const promptTokens = usage.prompt_tokens || 0;
    const completionTokens = usage.completion_tokens || 0;
    const totalTokens = usage.total_tokens || promptTokens + completionTokens;

    // Calculate cost (simplified - actual cost calculation would be more complex)
    const estimatedCost = calculateLLMCost(provider, model, promptTokens, completionTokens);

    // Update span with result metadata
    span.setAttributes({
      'llm.response.prompt_tokens': promptTokens,
      'llm.response.completion_tokens': completionTokens,
      'llm.response.total_tokens': totalTokens,
      'llm.response.finish_reason': result.choices?.[0]?.finish_reason || 'unknown',
      'llm.response.latency_ms': executionTime,
      'llm.response.estimated_cost': estimatedCost,
    });

    span.setStatus({ code: SpanStatusCode.OK });

    if (DEBUG_LOGGING) {
      console.log(`[OTEL] LLM call completed: ${provider}/${model} (${executionTime}ms, ${totalTokens} tokens, $${estimatedCost.toFixed(4)})`);
    }

    return result;
  } catch (error) {
    const executionTime = Date.now() - startTime;

    // Record error in span
    span.setAttributes({
      'llm.response.latency_ms': executionTime,
      'error': true,
      'error.message': error.message,
      'error.type': error.constructor.name,
    });

    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error.message,
    });

    span.recordException(error);

    console.error(`[OTEL] LLM call failed: ${provider}/${model}`, error);

    throw error;
  } finally {
    span.end();
  }
}

/**
 * Calculate estimated cost for LLM calls
 * (Simplified version - real implementation should use current pricing)
 */
function calculateLLMCost(provider, model, promptTokens, completionTokens) {
  // Pricing per 1M tokens (as of 2024)
  const pricing = {
    openai: {
      'gpt-4': { prompt: 30, completion: 60 },
      'gpt-4-turbo': { prompt: 10, completion: 30 },
      'gpt-3.5-turbo': { prompt: 0.5, completion: 1.5 },
    },
    anthropic: {
      'claude-3-opus': { prompt: 15, completion: 75 },
      'claude-3-sonnet': { prompt: 3, completion: 15 },
      'claude-3-haiku': { prompt: 0.25, completion: 1.25 },
    },
    google: {
      'gemini-pro': { prompt: 0.5, completion: 1.5 },
    },
  };

  const modelPricing = pricing[provider]?.[model] || { prompt: 1, completion: 2 };

  const promptCost = (promptTokens / 1000000) * modelPricing.prompt;
  const completionCost = (completionTokens / 1000000) * modelPricing.completion;

  return promptCost + completionCost;
}

// Export tracing utilities
module.exports = {
  sdk,
  tracer,
  traceMCPToolCall,
  traceLLMCall,
  getActiveSpan,
  startSpan,
};

console.log('[OTEL] Tracing utilities exported');
