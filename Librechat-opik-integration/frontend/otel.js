/**
 * OpenTelemetry Browser Instrumentation for LibreChat Frontend
 * Integrates with Opik for end-to-end tracing
 *
 * This file should be imported early in the application initialization
 * Usage: import './otel' at the top of your main.jsx or App.jsx
 */

import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { W3CTraceContextPropagator } from '@opentelemetry/core';
import { CompositePropagator, W3CBaggagePropagator } from '@opentelemetry/core';
import { ZoneContextManager } from '@opentelemetry/context-zone';

// Global configuration flag
let otelInitialized = false;
let otelConfig = null;

/**
 * Initialize OpenTelemetry for the browser
 * This should be called as early as possible in the app lifecycle
 */
export async function initializeOTEL() {
  if (otelInitialized) {
    console.log('[OTEL] Already initialized');
    return;
  }

  try {
    // Fetch OTEL configuration from backend
    // This ensures frontend uses the same config as backend
    const response = await fetch('/api/config/otel');
    if (!response.ok) {
      throw new Error('Failed to fetch OTEL configuration');
    }

    otelConfig = await response.json();

    if (!otelConfig.enabled) {
      console.log('[OTEL] OpenTelemetry disabled by backend configuration');
      return;
    }

    console.log('[OTEL] Initializing browser instrumentation');
    console.log('[OTEL] Opik URL:', otelConfig.opikUrl);
    console.log('[OTEL] Project:', otelConfig.projectName);

    // Create resource with service information
    const resource = new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: otelConfig.serviceName || 'librechat-frontend',
      [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: import.meta.env.MODE || 'development',
      // Opik-specific attributes
      'opik.project': otelConfig.projectName,
      'opik.workspace': otelConfig.workspaceName,
      // Browser-specific attributes
      'browser.user_agent': navigator.userAgent,
      'browser.language': navigator.language,
    });

    // Create OTLP trace exporter
    // For browser, we use HTTP protocol (not gRPC)
    const exporter = new OTLPTraceExporter({
      url: `${otelConfig.opikUrl}/api/v1/private/otel/v1/traces`,
      headers: {
        'Authorization': otelConfig.apiKey,
        'Comet-Workspace': otelConfig.workspaceName,
        'projectName': otelConfig.projectName,
      },
      // Browser-specific settings
      concurrencyLimit: 10,
    });

    // Create tracer provider
    const provider = new WebTracerProvider({
      resource,
    });

    // Configure span processor
    provider.addSpanProcessor(
      new BatchSpanProcessor(exporter, {
        maxQueueSize: 100,
        maxExportBatchSize: 10,
        scheduledDelayMillis: 1000, // Export every second
      })
    );

    // Configure context propagation
    // This is critical for end-to-end tracing between frontend and backend
    const propagator = new CompositePropagator({
      propagators: [
        new W3CTraceContextPropagator(),
        new W3CBaggagePropagator(),
      ],
    });

    provider.register({
      contextManager: new ZoneContextManager(),
      propagator,
    });

    // Register auto-instrumentations
    registerInstrumentations({
      instrumentations: [
        getWebAutoInstrumentations({
          '@opentelemetry/instrumentation-document-load': {
            enabled: true,
          },
          '@opentelemetry/instrumentation-user-interaction': {
            enabled: true,
            eventNames: ['click', 'submit', 'keydown'],
          },
          '@opentelemetry/instrumentation-fetch': {
            enabled: true,
            propagateTraceHeaderCorsUrls: [
              new RegExp(window.location.origin), // Same origin
              /^https?:\/\/localhost/, // Local backend
            ],
            clearTimingResources: true,
            applyCustomAttributesOnSpan: (span, request, result) => {
              // Add custom attributes to fetch spans
              const url = request.url || result.url;

              if (url.includes('/api/chat')) {
                span.setAttribute('chat.api_call', true);
              }

              if (url.includes('/api/ask')) {
                span.setAttribute('ask.api_call', true);
              }

              // Extract conversation ID from request if present
              if (request.body) {
                try {
                  const body = JSON.parse(request.body);
                  if (body.conversationId) {
                    span.setAttribute('conversation.id', body.conversationId);
                  }
                  if (body.endpoint) {
                    span.setAttribute('llm.endpoint', body.endpoint);
                  }
                  if (body.model) {
                    span.setAttribute('llm.model', body.model);
                  }
                } catch (e) {
                  // Ignore JSON parse errors
                }
              }
            },
          },
          '@opentelemetry/instrumentation-xml-http-request': {
            enabled: true,
            propagateTraceHeaderCorsUrls: [
              new RegExp(window.location.origin),
              /^https?:\/\/localhost/,
            ],
          },
        }),
      ],
    });

    // Instrument console methods to send logs to OTEL
    instrumentConsole(provider.getTracer('librechat-frontend'));

    // Listen for unhandled errors
    instrumentErrors(provider.getTracer('librechat-frontend'));

    otelInitialized = true;
    console.log('[OTEL] ✅ Browser instrumentation initialized successfully');
  } catch (error) {
    console.error('[OTEL] ❌ Failed to initialize browser instrumentation:', error);
  }
}

/**
 * Instrument console methods to create log spans
 * This captures console.log, console.error, etc. as spans
 */
function instrumentConsole(tracer) {
  const originalConsole = {
    log: console.log,
    info: console.info,
    warn: console.warn,
    error: console.error,
    debug: console.debug,
  };

  ['log', 'info', 'warn', 'error', 'debug'].forEach((method) => {
    console[method] = function (...args) {
      // Call original console method
      originalConsole[method].apply(console, args);

      // Create span for log event (only for warn and error to reduce noise)
      if (method === 'warn' || method === 'error') {
        const message = args.map(arg =>
          typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
        ).join(' ');

        const span = tracer.startSpan(`console.${method}`, {
          attributes: {
            'log.level': method,
            'log.message': message.substring(0, 500), // Truncate long messages
            'browser.url': window.location.href,
          },
        });

        span.end();
      }
    };
  });

  console.log('[OTEL] Console instrumentation enabled');
}

/**
 * Instrument error handling
 */
function instrumentErrors(tracer) {
  // Global error handler
  window.addEventListener('error', (event) => {
    const span = tracer.startSpan('unhandled_error', {
      attributes: {
        'error.message': event.message,
        'error.filename': event.filename,
        'error.lineno': event.lineno,
        'error.colno': event.colno,
        'browser.url': window.location.href,
      },
    });

    if (event.error) {
      span.recordException(event.error);
    }

    span.end();
  });

  // Promise rejection handler
  window.addEventListener('unhandledrejection', (event) => {
    const span = tracer.startSpan('unhandled_promise_rejection', {
      attributes: {
        'error.message': event.reason?.message || String(event.reason),
        'browser.url': window.location.href,
      },
    });

    if (event.reason instanceof Error) {
      span.recordException(event.reason);
    }

    span.end();
  });

  console.log('[OTEL] Error instrumentation enabled');
}

/**
 * Create a custom span for user actions
 * Useful for tracing specific user interactions
 *
 * @param {string} name - Span name
 * @param {Function} fn - Function to trace
 * @param {object} attributes - Custom attributes
 */
export async function traceUserAction(name, fn, attributes = {}) {
  if (!otelInitialized) {
    // OTEL not initialized, execute without tracing
    return await fn();
  }

  const { trace } = await import('@opentelemetry/api');
  const tracer = trace.getTracer('librechat-frontend');

  const span = tracer.startSpan(name, {
    attributes: {
      'user.action': name,
      'browser.url': window.location.href,
      ...attributes,
    },
  });

  try {
    const result = await fn();
    span.setStatus({ code: 1 }); // OK
    return result;
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message }); // ERROR
    throw error;
  } finally {
    span.end();
  }
}

/**
 * Add conversation context to current span
 * Call this when conversation context is available
 */
export function setConversationContext(conversationId, additionalContext = {}) {
  if (!otelInitialized) return;

  import('@opentelemetry/api').then(({ trace }) => {
    const activeSpan = trace.getActiveSpan();
    if (activeSpan) {
      activeSpan.setAttributes({
        'conversation.id': conversationId,
        ...additionalContext,
      });
    }
  });
}

/**
 * Example React hook for component-level tracing
 */
export function useOTELTrace(componentName) {
  const [tracer, setTracer] = React.useState(null);

  React.useEffect(() => {
    if (otelInitialized) {
      import('@opentelemetry/api').then(({ trace }) => {
        setTracer(trace.getTracer('librechat-frontend'));
      });
    }
  }, []);

  const traceAction = React.useCallback(
    async (actionName, fn, attributes = {}) => {
      if (!tracer) {
        return await fn();
      }

      const span = tracer.startSpan(`${componentName}.${actionName}`, {
        attributes: {
          'component.name': componentName,
          'component.action': actionName,
          ...attributes,
        },
      });

      try {
        const result = await fn();
        span.setStatus({ code: 1 }); // OK
        return result;
      } catch (error) {
        span.recordException(error);
        span.setStatus({ code: 2, message: error.message }); // ERROR
        throw error;
      } finally {
        span.end();
      }
    },
    [tracer, componentName]
  );

  return { traceAction };
}

// Export configuration checker
export function isOTELEnabled() {
  return otelInitialized;
}

export function getOTELConfig() {
  return otelConfig;
}

export default {
  initializeOTEL,
  traceUserAction,
  setConversationContext,
  useOTELTrace,
  isOTELEnabled,
  getOTELConfig,
};
