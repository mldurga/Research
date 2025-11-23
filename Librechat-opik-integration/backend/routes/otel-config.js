/**
 * OTEL Configuration Route
 *
 * Provides OpenTelemetry configuration to the frontend
 * This ensures frontend and backend use consistent settings
 *
 * Mount this route in your Express app:
 *   app.use('/api/config', require('./routes/otel-config'));
 */

const express = require('express');
const router = express.Router();

/**
 * GET /api/config/otel
 * Returns OTEL configuration for frontend initialization
 */
router.get('/otel', (req, res) => {
  const config = {
    enabled: process.env.ENABLE_OTEL === 'true',
    opikUrl: process.env.OPIK_URL || 'http://localhost:8080',
    apiKey: process.env.OPIK_API_KEY || '',
    projectName: process.env.OPIK_PROJECT_NAME || 'librechat',
    workspaceName: process.env.OPIK_WORKSPACE_NAME || 'default',
    serviceName: 'librechat-frontend',
    debugLogging: process.env.DEBUG_LOGGING === 'true',
  };

  res.json(config);
});

/**
 * POST /api/config/otel/test
 * Test OTEL configuration
 */
router.post('/otel/test', async (req, res) => {
  try {
    const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-proto');

    const opikUrl = process.env.OPIK_URL || 'http://localhost:8080';
    const apiKey = process.env.OPIK_API_KEY || '';
    const projectName = process.env.OPIK_PROJECT_NAME || 'librechat';
    const workspaceName = process.env.OPIK_WORKSPACE_NAME || 'default';

    // Create test exporter
    const exporter = new OTLPTraceExporter({
      url: `${opikUrl}/api/v1/private/otel/v1/traces`,
      headers: {
        'Authorization': apiKey,
        'Comet-Workspace': workspaceName,
        'projectName': projectName,
      },
    });

    // Try to export an empty span (this tests connectivity)
    const { BasicTracerProvider, BatchSpanProcessor } = require('@opentelemetry/sdk-trace-base');
    const provider = new BasicTracerProvider();
    provider.addSpanProcessor(new BatchSpanProcessor(exporter));
    provider.register();

    const tracer = provider.getTracer('test');
    const span = tracer.startSpan('otel_config_test');
    span.setAttribute('test', true);
    span.end();

    // Force export
    await provider.forceFlush();

    res.json({
      success: true,
      message: 'OTEL configuration is valid and Opik is reachable',
      config: {
        opikUrl,
        projectName,
        workspaceName,
      },
    });
  } catch (error) {
    console.error('[OTEL] Configuration test failed:', error);

    res.status(500).json({
      success: false,
      message: 'OTEL configuration test failed',
      error: error.message,
    });
  }
});

module.exports = router;
