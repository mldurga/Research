/**
 * MCP Client Instrumentation for OpenTelemetry
 *
 * This module wraps MCP client calls to automatically trace all tool invocations
 * and send telemetry data to Opik.
 *
 * Usage:
 *   const { instrumentMCPClient } = require('./mcp-tracing');
 *   const tracedClient = instrumentMCPClient(mcpClient, { serverName: 'PI System' });
 */

const { traceMCPToolCall } = require('./otel');

/**
 * Instrument an MCP client to automatically trace all tool calls
 *
 * @param {object} mcpClient - The MCP client instance
 * @param {object} options - Configuration options
 * @param {string} options.serverName - Name of the MCP server
 * @param {Function} options.getConversationId - Function to get current conversation ID
 * @param {Function} options.getUserId - Function to get current user ID
 * @returns {Proxy} - Instrumented MCP client
 */
function instrumentMCPClient(mcpClient, options = {}) {
  const {
    serverName = 'MCP Server',
    getConversationId = () => null,
    getUserId = () => null,
  } = options;

  console.log(`[MCP-OTEL] Instrumenting MCP client for server: ${serverName}`);

  // Create a proxy that intercepts all method calls
  return new Proxy(mcpClient, {
    get(target, prop) {
      const originalMethod = target[prop];

      // Only intercept async methods (likely tool calls)
      if (typeof originalMethod === 'function') {
        return async function (...args) {
          // Check if this is a tool call
          // Tool calls typically have a specific pattern in MCP
          const isToolCall = prop === 'callTool' || prop === 'call_tool' || prop.startsWith('tool_');

          if (!isToolCall) {
            // Not a tool call, execute normally
            return originalMethod.apply(target, args);
          }

          // Extract tool name and input
          let toolName = prop;
          let toolInput = {};

          // Handle different MCP client patterns
          if (prop === 'callTool' || prop === 'call_tool') {
            toolName = args[0];
            toolInput = args[1] || {};
          } else {
            toolInput = args[0] || {};
          }

          // Get context metadata
          const metadata = {
            conversationId: getConversationId(),
            userId: getUserId(),
            mcpServerName: serverName,
          };

          // Trace the tool call
          return await traceMCPToolCall(
            toolName,
            toolInput,
            async () => originalMethod.apply(target, args),
            metadata
          );
        };
      }

      return originalMethod;
    },
  });
}

/**
 * Manually trace an MCP tool call (for custom implementations)
 *
 * @param {string} serverName - Name of the MCP server
 * @param {string} toolName - Name of the tool being called
 * @param {object} toolInput - Tool input parameters
 * @param {Function} executeFn - Async function to execute
 * @param {object} context - Request context (conversationId, userId)
 * @returns {Promise} - Tool execution result
 */
async function traceMCPTool(serverName, toolName, toolInput, executeFn, context = {}) {
  const metadata = {
    mcpServerName: serverName,
    conversationId: context.conversationId,
    userId: context.userId,
  };

  return await traceMCPToolCall(toolName, toolInput, executeFn, metadata);
}

/**
 * Express middleware to add MCP tracing context to requests
 *
 * This middleware extracts conversation and user context from requests
 * and makes it available to MCP tracing functions.
 */
function mcpTracingMiddleware(req, res, next) {
  // Extract context from request
  const conversationId = req.body?.conversationId || req.headers['x-conversation-id'];
  const userId = req.user?.id || req.headers['x-user-id'];

  // Store in request for later use
  req.mcpContext = {
    conversationId,
    userId,
  };

  next();
}

/**
 * Trace MCP server connection/initialization
 *
 * @param {string} serverName - Name of the MCP server
 * @param {string} serverUrl - URL of the MCP server
 * @param {Function} connectFn - Async function to connect
 * @returns {Promise} - Connection result
 */
async function traceMCPConnection(serverName, serverUrl, connectFn) {
  const { startSpan } = require('./otel');

  const span = startSpan(`MCP Connection: ${serverName}`, {
    'mcp.server.name': serverName,
    'mcp.server.url': serverUrl,
    'span.kind': 'client',
  });

  const startTime = Date.now();

  try {
    const result = await connectFn();
    const connectionTime = Date.now() - startTime;

    span.setAttributes({
      'mcp.connection.success': true,
      'mcp.connection.time_ms': connectionTime,
    });

    span.setStatus({ code: 1 }); // OK

    console.log(`[MCP-OTEL] Connected to ${serverName} (${connectionTime}ms)`);

    return result;
  } catch (error) {
    span.setAttributes({
      'mcp.connection.success': false,
      'mcp.connection.error': error.message,
    });

    span.setStatus({ code: 2, message: error.message }); // ERROR
    span.recordException(error);

    console.error(`[MCP-OTEL] Failed to connect to ${serverName}:`, error);

    throw error;
  } finally {
    span.end();
  }
}

/**
 * Batch trace multiple MCP tool calls
 *
 * Useful when multiple tools are called in sequence or parallel.
 *
 * @param {string} operationName - Name of the batch operation
 * @param {Array} toolCalls - Array of {serverName, toolName, input, executeFn}
 * @param {object} context - Request context
 * @returns {Promise<Array>} - Results of all tool calls
 */
async function traceBatchMCPCalls(operationName, toolCalls, context = {}) {
  const { startSpan } = require('./otel');

  const span = startSpan(`MCP Batch: ${operationName}`, {
    'mcp.batch.tool_count': toolCalls.length,
    'mcp.batch.operation': operationName,
    ...(context.conversationId && { 'conversation.id': context.conversationId }),
    ...(context.userId && { 'user.id': context.userId }),
  });

  const startTime = Date.now();

  try {
    // Execute all tool calls (can be parallel or sequential)
    const results = await Promise.all(
      toolCalls.map(({ serverName, toolName, input, executeFn }) =>
        traceMCPTool(serverName, toolName, input, executeFn, context)
      )
    );

    const executionTime = Date.now() - startTime;

    span.setAttributes({
      'mcp.batch.success': true,
      'mcp.batch.execution_time_ms': executionTime,
      'mcp.batch.completed_count': results.length,
    });

    span.setStatus({ code: 1 }); // OK

    console.log(`[MCP-OTEL] Batch operation completed: ${operationName} (${executionTime}ms, ${results.length} tools)`);

    return results;
  } catch (error) {
    span.setAttributes({
      'mcp.batch.success': false,
      'mcp.batch.error': error.message,
    });

    span.setStatus({ code: 2, message: error.message }); // ERROR
    span.recordException(error);

    console.error(`[MCP-OTEL] Batch operation failed: ${operationName}`, error);

    throw error;
  } finally {
    span.end();
  }
}

/**
 * Example: LibreChat integration for MCP tools
 *
 * This shows how to integrate MCP tracing into LibreChat's message handling.
 */
function createLibreChatMCPHandler(mcpClients) {
  return async function handleMCPTools(req, res, next) {
    // Check if the message requires MCP tools
    const { message, conversationId } = req.body;
    const userId = req.user?.id;

    // Example: Extract tool calls from LLM response
    // (This would be part of LibreChat's agent logic)
    const toolCalls = extractToolCalls(message);

    if (toolCalls.length === 0) {
      return next();
    }

    const context = { conversationId, userId };

    try {
      // Execute all tool calls with tracing
      const toolResults = await traceBatchMCPCalls(
        'LibreChat Tool Execution',
        toolCalls.map(tc => ({
          serverName: tc.server,
          toolName: tc.tool,
          input: tc.input,
          executeFn: async () => {
            const client = mcpClients[tc.server];
            if (!client) {
              throw new Error(`MCP server not found: ${tc.server}`);
            }
            return await client.callTool(tc.tool, tc.input);
          },
        })),
        context
      );

      // Attach results to request for further processing
      req.mcpToolResults = toolResults;

      next();
    } catch (error) {
      console.error('[MCP-OTEL] Error executing MCP tools:', error);
      next(error);
    }
  };
}

/**
 * Helper to extract tool calls from messages
 * (This is a placeholder - actual implementation depends on LibreChat's structure)
 */
function extractToolCalls(message) {
  // Placeholder implementation
  // Real implementation would parse function calls from LLM responses
  return [];
}

module.exports = {
  instrumentMCPClient,
  traceMCPTool,
  traceMCPConnection,
  traceBatchMCPCalls,
  mcpTracingMiddleware,
  createLibreChatMCPHandler,
};

console.log('[MCP-OTEL] MCP tracing utilities loaded');
