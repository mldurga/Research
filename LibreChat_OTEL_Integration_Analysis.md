# LibreChat OpenTelemetry Integration Analysis

## Executive Summary

This document provides a comprehensive analysis of the OpenTelemetry (OTEL) integration in the LibreChat fork by kvasir-cone-snail. The integration adds full observability support including distributed tracing, metrics collection, and structured logging to both the backend (Node.js/Express) and frontend (React/Vite) applications.

**Repository URLs:**
- OTEL Fork: https://github.com/kvasir-cone-snail/LibreChat/tree/feat/otel
- Original: https://github.com/danny-avila/LibreChat

---

## 1. Files Modified and Added for OTEL Support

### Backend (API)

#### **New Files Created:**
1. **`/api/server/middleware/otelMiddleware.js`**
   - Main OTEL initialization for backend
   - Configures SDK, exporters, and instrumentation
   - ~150 lines of code

2. **`/api/server/middleware/otelLoggingIntegration.js`**
   - Custom Winston transport for OTEL logs
   - Bridges Winston logging to OpenTelemetry API
   - ~60 lines of code

3. **`/api/server/services/Config/otel.js`**
   - Configuration service for OTEL settings
   - Provides OTEL config to frontend via API
   - ~20 lines of code

#### **Modified Files:**
1. **`/api/server/index.js`**
   - Added OTEL initialization at startup (before Express app creation)
   - Added imports and function call

2. **`/api/server/routes/config.js`**
   - Added `getOtelConfig()` import
   - Included OTEL config in startup payload

3. **`/api/package.json`**
   - Added 11 OpenTelemetry dependencies

### Frontend (Client)

#### **New Files Created:**
1. **`/client/src/utils/otelMiddleware.ts`**
   - Main OTEL initialization for frontend
   - Configures web tracing, metrics, and logging
   - ~180 lines of TypeScript

2. **`/client/src/utils/otelLoggingIntegration.ts`**
   - Custom console logger that forwards to OTEL
   - Intercepts console methods (log, error, warn, debug, info)
   - Prevents recursion and handles circular references
   - ~200+ lines of TypeScript

#### **Modified Files:**
1. **`/client/src/main.jsx`**
   - Added `initializeFrontendOtel()` import
   - Called initialization before React root creation

2. **`/client/package.json`**
   - Added 10 OpenTelemetry dependencies

### Configuration Files

#### **Modified:**
1. **`.env.example`**
   - Added OTEL environment variables section:
     ```bash
     # OpenTelemetry
     OTEL_ENDPOINT=
     OTEL_API_KEY=
     ```

---

## 2. Dependencies Added

### Backend Dependencies (`api/package.json`)

```json
{
  "@opentelemetry/api": "^1.9.0",
  "@opentelemetry/api-logs": "^0.201.0",
  "@opentelemetry/auto-instrumentations-node": "^0.59.0",
  "@opentelemetry/exporter-logs-otlp-http": "^0.202.0",
  "@opentelemetry/exporter-metrics-otlp-proto": "^0.202.0",
  "@opentelemetry/exporter-trace-otlp-proto": "^0.202.0",
  "@opentelemetry/resources": "^2.0.1",
  "@opentelemetry/sdk-logs": "^0.202.0",
  "@opentelemetry/sdk-metrics": "^2.0.1",
  "@opentelemetry/sdk-node": "^0.202.0",
  "@opentelemetry/semantic-conventions": "^1.34.0"
}
```

**Total: 11 packages**

**Key Packages:**
- **auto-instrumentations-node**: Automatic instrumentation for Express, HTTP, MongoDB, Redis, etc.
- **sdk-node**: Complete Node.js SDK for OTEL
- **exporter-*-otlp-proto**: OTLP exporters for traces, metrics, and logs
- **semantic-conventions**: Standard attribute naming

### Frontend Dependencies (`client/package.json`)

```json
{
  "@opentelemetry/api": "^1.9.0",
  "@opentelemetry/auto-configuration-propagators": "^0.4.1",
  "@opentelemetry/auto-instrumentations-web": "^0.48.0",
  "@opentelemetry/exporter-logs-otlp-http": "^0.202.0",
  "@opentelemetry/instrumentation": "^0.202.0",
  "@opentelemetry/resources": "^2.0.1",
  "@opentelemetry/sdk-metrics": "^2.0.1",
  "@opentelemetry/sdk-trace-base": "^2.0.1",
  "@opentelemetry/sdk-trace-web": "^2.0.1",
  "@opentelemetry/semantic-conventions": "^1.34.0"
}
```

**Total: 10 packages**

**Key Packages:**
- **auto-instrumentations-web**: Auto-instruments document load, user interactions, XHR requests
- **sdk-trace-web**: Web-specific tracing SDK
- **sdk-metrics**: Metrics collection for browser
- **exporter-logs-otlp-http**: HTTP-based log exporter for browser

---

## 3. Key Code Changes and Patterns

### Backend Implementation

#### A. OTEL Initialization (`api/server/middleware/otelMiddleware.js`)

**Pattern: Early Initialization**
```javascript
// In api/server/index.js - BEFORE Express app creation
const initializeBackendOtel = require('./middleware/otelMiddleware');
initializeBackendOtel();  // Called at line 32
const app = express();     // Created at line 34
```

**Configuration Validation:**
```javascript
function initializeBackendOtel() {
  // Check both OTEL_ENDPOINT and OTEL_API_KEY are set
  const otelEnabled = !!process.env.OTEL_ENDPOINT && !!process.env.OTEL_API_KEY;

  if (!otelEnabled) {
    logger.info('Open Telemetry is not enabled');
    return;
  }

  // Validate endpoint and API key are not empty strings
  if (!OTEL_ENDPOINT || OTEL_ENDPOINT.trim() === '') {
    logger.info('Open Telemetry End Point is not set: Open Telemetry will be turned off');
    return;
  }

  if (!OTEL_API_KEY || OTEL_API_KEY.trim() === '') {
    logger.info('Open Telemetry Api Key is not set: Open Telemetry will be turned off.');
    return;
  }

  logger.debug('Open Telemetry Backend is active!');
  // ... initialization continues
}
```

**Resource Attributes:**
```javascript
const attributes = {
  [ATTR_SERVICE_NAME]: name,                                    // From package.json
  [ATTR_SERVICE_VERSION]: version,                              // From package.json
  [ATTR_TELEMETRY_SDK_LANGUAGE]: TELEMETRY_SDK_LANGUAGE_VALUE_NODEJS,
  [ATTR_TELEMETRY_SDK_NAME]: 'opentelemetry',
  [ATTR_TELEMETRY_SDK_VERSION]: `${dependencies['@opentelemetry/api']}`,
  hostname: getHostname(),                                      // From os.hostname()
  username: os.userInfo().username,
};
```

**Exporters Configuration:**
```javascript
const headers = {
  'api-key': configTraces.key,  // OTEL_API_KEY from env
};

const sdk = new NodeSDK({
  resource: resourceBuilder,

  // Traces -> OTEL_ENDPOINT/traces
  traceExporter: new OTLPTraceExporter({
    url: `${configTraces.url}/traces`,
    headers: headers,
  }),

  // Metrics -> OTEL_ENDPOINT/metrics
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: `${configTraces.url}/metrics`,
      headers: headers,
    }),
  }),

  // Logs -> OTEL_ENDPOINT/logs
  logRecordProcessor: new SimpleLogRecordProcessor(
    new OTLPLogExporter({
      url: `${configTraces.url}/logs`,
      headers: headers,
    }),
  ),

  // Auto-instrumentation for Express, MongoDB, Redis, etc.
  instrumentations: [getNodeAutoInstrumentations()],
});
```

**Propagation Strategy:**
```javascript
// W3C TraceContext and Baggage for distributed tracing
const compositePropagator = new CompositePropagator({
  propagators: [
    new W3CBaggagePropagator(),
    new W3CTraceContextPropagator()
  ],
});

propagation.setGlobalPropagator(compositePropagator);
sdk.start();
```

#### B. Winston Integration (`api/server/middleware/otelLoggingIntegration.js`)

**Custom Winston Transport:**
```javascript
function OpenTelemetryTransport(opts) {
  Transport.call(this, opts);
  this.name = 'opentelemetry';
  this.level = opts.level || 'debug';
  this.loggerProvider = opts.loggerProvider;
  this.logger = this.loggerProvider.getLogger(opts.loggerName || 'winston-logger');
}

OpenTelemetryTransport.prototype.log = function (info, callback) {
  // Map Winston levels to OTEL severity
  const severityMap = {
    error: logsAPI.SeverityNumber.ERROR,
    warn: logsAPI.SeverityNumber.WARN,
    info: logsAPI.SeverityNumber.INFO,
    http: logsAPI.SeverityNumber.INFO,
    verbose: logsAPI.SeverityNumber.DEBUG,
    debug: logsAPI.SeverityNumber.DEBUG,
    silly: logsAPI.SeverityNumber.TRACE,
  };

  // Emit to OTEL with all metadata
  this.logger.emit({
    severityNumber: severityMap[info.level] || logsAPI.SeverityNumber.INFO,
    severityText: info.level.toUpperCase(),
    body: info.message,
    attributes: attributes,
  });
};
```

**Adding to Winston Logger:**
```javascript
// Determine log level based on environment
const level = () => {
  const env = NODE_ENV || 'development';
  const isDevelopment = env === 'development';
  return isDevelopment ? 'debug' : 'warn';
};

let envLevel = level();
const useDebugLogging =
  (typeof DEBUG_LOGGING === 'string' && DEBUG_LOGGING?.toLowerCase() === 'true') ||
  DEBUG_LOGGING === true;

if (useDebugLogging) {
  envLevel = 'debug';
}

// Add OTEL transport to existing Winston logger
logger.add(
  new OpenTelemetryTransport({
    level: envLevel,
    loggerProvider: loggerProvider,
    loggerName: 'otel-logger',
  }),
);
```

#### C. Configuration Service (`api/server/services/Config/otel.js`)

**Simple Environment-Based Config:**
```javascript
const getOtelConfig = () => {
  const otelEnabled = !!process.env.OTEL_ENDPOINT && !!process.env.OTEL_API_KEY;

  const otel = {
    enabled: otelEnabled,
  };

  if (!otelEnabled) {
    return otel;
  }

  // Only include sensitive data if enabled
  otel.otelEndpoint = process.env.OTEL_ENDPOINT;
  otel.otelApiKey = process.env.OTEL_API_KEY;

  return otel;
};
```

**Used in Startup Config API:**
```javascript
// In api/server/routes/config.js
const { getOtelConfig } = require('~/server/services/Config/otel');

router.get('/', async (req, res) => {
  // ... other config
  const otel = getOtelConfig();

  const payload = {
    // ... other startup config
  };

  if (otel) {
    payload.otel = otel;  // Include OTEL config for frontend
  }

  res.send(payload);
});
```

### Frontend Implementation

#### A. OTEL Initialization (`client/src/utils/otelMiddleware.ts`)

**Pattern: Async Configuration Fetch**
```typescript
export async function initializeFrontendOtel() {
  // Fetch config from backend API
  const configs = await dataService.getStartupConfig();

  if (!configs.otel?.enabled) {
    console.info('Open Telemetry is not enabled');
    return;
  }

  const user = await dataService.getUser();

  // Validate configuration
  if (!configs.otel?.otelEndpoint || configs.otel?.otelEndpoint.trim() === '') {
    console.info('Open Telemetry End Point is not set: Open Telemetry will be turned off.');
    return;
  }

  if (!configs.otel?.otelApiKey || configs.otel?.otelApiKey.trim() === '') {
    console.info('Open Telemetry Api Key is not set: Open Telemetry will be turned off.');
    return;
  }

  console.debug('Open Telemetry Frontend is active!');
  // ... initialization continues
}
```

**Resource Attributes with User Context:**
```typescript
const attributes = {
  [ATTR_SERVICE_NAME]: `${packageJson.name}`,
  [ATTR_SERVICE_VERSION]: packageJson.version,
  [ATTR_TELEMETRY_SDK_LANGUAGE]: TELEMETRY_SDK_LANGUAGE_VALUE_NODEJS,
  [ATTR_TELEMETRY_SDK_NAME]: 'opentelemetry',
  [ATTR_TELEMETRY_SDK_VERSION]: `${packageJson.dependencies['@opentelemetry/api']}`,
  hostname: os.hostname(),
  username: user.username?.trim() || user.name,  // User-specific context
  email: user.email,
};
```

**Web-Specific Exporters:**
```typescript
const headers = {
  'api-key': configTraces.key,
};

// All use HTTP exporters (not proto) for browser compatibility
const traceConfigs = {
  url: `${configTraces.url}/traces`,
  headers: headers,
} as OTLPExporterNodeConfigBase;

const logConfigs = {
  url: `${configTraces.url}/logs`,
  headers: headers,
} as OTLPExporterNodeConfigBase;

const metricsConfigs = {
  url: `${configTraces.url}/metrics`,
  headers: headers,
} as OTLPExporterNodeConfigBase;

// Create exporters
const traceExporterProcessor = new SimpleSpanProcessor(
  new OTLPTraceExporter(traceConfigs)
);
const logExporterProcessor = new SimpleLogRecordProcessor(
  new OTLPLogExporter(logConfigs)
);
const metricExporter = new OTLPMetricExporter(metricsConfigs);
```

**Web Tracer Provider:**
```typescript
const provider = new WebTracerProvider({
  resource: resourceBuilder,
  spanProcessors: [traceExporterProcessor],
});

const loggerProvider = new LoggerProvider({
  resource: resourceBuilder,
  processors: [logExporterProcessor],
});

// Metrics with 1-second export interval
const periodicReader = new PeriodicExportingMetricReader({
  exporter: metricExporter,
  exportIntervalMillis: 1000,
});

const meterProvider = new MeterProvider({
  resource: resourceBuilder,
  readers: [periodicReader],
});
```

**Browser-Specific Instrumentation:**
```typescript
// Same W3C propagation as backend
const compositePropagator = new CompositePropagator({
  propagators: [
    new W3CBaggagePropagator(),
    new W3CTraceContextPropagator()
  ],
});

// Set global providers
metrics.setGlobalMeterProvider(meterProvider);
propagation.setGlobalPropagator(compositePropagator);

// Global logger accessible from console
const logger = new OpenTelemetryConsoleLogger({
  loggerProvider: loggerProvider,
  loggerName: 'otel-frontend-logger',
});
(window as any).otelLogger = logger;

// Register provider with propagation
provider.register({
  propagator: compositePropagator,
});

// Auto-instrument browser events
registerInstrumentations({
  tracerProvider: provider,
  loggerProvider: loggerProvider,
  meterProvider: meterProvider,
  instrumentations: [
    new DocumentLoadInstrumentation(),      // Page load events
    new UserInteractionInstrumentation(),   // Clicks, interactions
    new XMLHttpRequestInstrumentation(),    // AJAX requests
  ],
});
```

#### B. Console Logger Integration (`client/src/utils/otelLoggingIntegration.ts`)

**Console Method Interception:**
```typescript
class OpenTelemetryConsoleLogger {
  private originalConsole: {
    log: any;
    error: any;
    warn: any;
    debug: any;
    info: any;
  };
  private isLogging = false;  // Prevents recursion
  private loggerProvider: LoggerProvider;
  private logger: any;
  private loggerName: string;

  constructor(options: ConsoleLoggerOptions) {
    this.loggerProvider = options.loggerProvider;
    this.loggerName = options.loggerName || 'console-logger';
    this.logger = this.loggerProvider.getLogger(this.loggerName);

    // Store original console methods
    this.originalConsole = {
      log: console.log,
      error: console.error,
      warn: console.warn,
      debug: console.debug,
      info: console.info,
    };

    this.interceptConsole();
  }

  private interceptConsole() {
    const self = this;

    // Override console.log
    console.log = function (...args: any[]) {
      self.originalConsole.log.apply(console, args);
      self.captureLog('info', args);
    };

    // Override console.error
    console.error = function (...args: any[]) {
      self.originalConsole.error.apply(console, args);
      self.captureLog('error', args);
    };

    // Similar for warn, debug, info...
  }

  private captureLog(level: string, args: any[]) {
    if (this.isLogging) return;  // Prevent infinite loops

    try {
      this.isLogging = true;
      const message = this.formatArgs(args);

      if (message.length > 50000) {
        this.originalConsole.warn('Log message too long, skipping OTEL export');
        return;
      }

      this.logToOpenTelemetry({
        level,
        message,
        timestamp: new Date().toISOString(),
      });
    } finally {
      this.isLogging = false;
    }
  }

  private safeStringify(obj: any): string {
    const seen = new WeakSet();
    return JSON.stringify(
      obj,
      (key, value) => {
        if (typeof value === 'object' && value !== null) {
          if (seen.has(value)) {
            return '[Circular]';
          }
          seen.add(value);
        }
        return value;
      },
      2
    ).substring(0, 10000);  // Limit to 10k chars
  }

  private formatArgs(args: any[]): string {
    return args
      .map((arg) => {
        if (typeof arg === 'object' && arg !== null) {
          return this.safeStringify(arg);
        }
        return String(arg);
      })
      .join(' ');
  }

  private logToOpenTelemetry(logInfo: LogInfo) {
    const severityMap: Record<string, number> = {
      error: 17,   // SeverityNumber.ERROR
      warn: 13,    // SeverityNumber.WARN
      info: 9,     // SeverityNumber.INFO
      debug: 5,    // SeverityNumber.DEBUG
      log: 9,      // SeverityNumber.INFO
    };

    this.logger.emit({
      severityNumber: severityMap[logInfo.level] || 9,
      severityText: logInfo.level.toUpperCase(),
      body: logInfo.message,
      attributes: {
        'log.type': 'console',
        timestamp: logInfo.timestamp,
        ...logInfo.attributes,
      },
    });
  }

  // Public API
  public log(...args: any[]) {
    if (!this.isLogging) {
      this.originalConsole.log.apply(console, args);
      this.captureLog('info', args);
    }
  }

  public error(...args: any[]) {
    if (!this.isLogging) {
      this.originalConsole.error.apply(console, args);
      this.captureLog('error', args);
    }
  }

  // Similar for warn, info, debug...

  public restoreConsole() {
    console.log = this.originalConsole.log;
    console.error = this.originalConsole.error;
    console.warn = this.originalConsole.warn;
    console.debug = this.originalConsole.debug;
    console.info = this.originalConsole.info;
  }
}
```

---

## 4. Configuration Requirements

### Environment Variables

**Required for Backend:**
```bash
# .env file
OTEL_ENDPOINT=https://your-otel-collector.example.com
OTEL_API_KEY=your_api_key_here

# Optional - controls log verbosity
DEBUG_LOGGING=true  # or false

# Existing env vars used
NODE_ENV=development  # or production
```

**Frontend Configuration:**
- No direct environment variables needed
- Configuration fetched from backend via `/api/config` endpoint
- Backend passes OTEL_ENDPOINT and OTEL_API_KEY to frontend through API

### OTEL Collector Endpoints

The implementation expects three endpoints on your OTEL collector:

1. **Traces**: `${OTEL_ENDPOINT}/traces`
   - Backend: OTLP/Proto
   - Frontend: OTLP/HTTP

2. **Metrics**: `${OTEL_ENDPOINT}/metrics`
   - Backend: OTLP/Proto
   - Frontend: OTLP/HTTP

3. **Logs**: `${OTEL_ENDPOINT}/logs`
   - Backend: OTLP/HTTP
   - Frontend: OTLP/HTTP

### Authentication

All exports use API key authentication:
```javascript
headers: {
  'api-key': process.env.OTEL_API_KEY
}
```

---

## 5. How to Enable/Configure OTEL

### Step-by-Step Setup

#### 1. Set Up OTEL Collector

You need an OpenTelemetry collector that accepts OTLP data. Options include:

**Commercial:**
- Datadog
- New Relic
- Honeycomb
- Grafana Cloud
- Lightstep
- **Opik** (your target - OTEL-based)

**Self-Hosted:**
- OpenTelemetry Collector
- Jaeger
- Zipkin
- Tempo (Grafana)

#### 2. Configure Environment Variables

```bash
# .env
OTEL_ENDPOINT=https://api.opik.example.com
OTEL_API_KEY=opik_api_key_12345

# Optional: Enable debug logging
DEBUG_LOGGING=true

# Ensure NODE_ENV is set
NODE_ENV=production
```

#### 3. Install Dependencies

**Backend:**
```bash
cd api
npm install @opentelemetry/api@^1.9.0 \
  @opentelemetry/api-logs@^0.201.0 \
  @opentelemetry/auto-instrumentations-node@^0.59.0 \
  @opentelemetry/exporter-logs-otlp-http@^0.202.0 \
  @opentelemetry/exporter-metrics-otlp-proto@^0.202.0 \
  @opentelemetry/exporter-trace-otlp-proto@^0.202.0 \
  @opentelemetry/resources@^2.0.1 \
  @opentelemetry/sdk-logs@^0.202.0 \
  @opentelemetry/sdk-metrics@^2.0.1 \
  @opentelemetry/sdk-node@^0.202.0 \
  @opentelemetry/semantic-conventions@^1.34.0
```

**Frontend:**
```bash
cd client
npm install @opentelemetry/api@^1.9.0 \
  @opentelemetry/auto-configuration-propagators@^0.4.1 \
  @opentelemetry/auto-instrumentations-web@^0.48.0 \
  @opentelemetry/exporter-logs-otlp-http@^0.202.0 \
  @opentelemetry/instrumentation@^0.202.0 \
  @opentelemetry/resources@^2.0.1 \
  @opentelemetry/sdk-metrics@^2.0.1 \
  @opentelemetry/sdk-trace-base@^2.0.1 \
  @opentelemetry/sdk-trace-web@^2.0.1 \
  @opentelemetry/semantic-conventions@^1.34.0
```

#### 4. Add OTEL Files

Copy the following files from the OTEL fork:

**Backend:**
- `/api/server/middleware/otelMiddleware.js`
- `/api/server/middleware/otelLoggingIntegration.js`
- `/api/server/services/Config/otel.js`

**Frontend:**
- `/client/src/utils/otelMiddleware.ts`
- `/client/src/utils/otelLoggingIntegration.ts`

#### 5. Modify Existing Files

**Backend - `/api/server/index.js`:**
```javascript
// Add near top (after other requires, around line 24)
const initializeBackendOtel = require('./middleware/otelMiddleware');

// Add before Express app creation (around line 32)
initializeBackendOtel();

const app = express();
```

**Backend - `/api/server/routes/config.js`:**
```javascript
// Add import
const { getOtelConfig } = require('~/server/services/Config/otel');

// In the route handler, add:
router.get('/', async (req, res) => {
  // ... existing config code
  const otel = getOtelConfig();

  const payload = {
    // ... existing payload properties
  };

  if (otel) {
    payload.otel = otel;
  }

  res.send(payload);
});
```

**Frontend - `/client/src/main.jsx`:**
```javascript
// Add import at top
import { initializeFrontendOtel } from './utils/otelMiddleware';

// Add before createRoot
initializeFrontendOtel();

const container = document.getElementById('root');
const root = createRoot(container);
// ... rest of code
```

#### 6. Update `.env.example`

Add to your `.env.example`:
```bash
# OpenTelemetry
OTEL_ENDPOINT=
OTEL_API_KEY=
```

#### 7. Verify Setup

**Start the application:**
```bash
# Development
npm run dev

# Production
npm start
```

**Check logs:**
```
[INFO] Open Telemetry Backend is active!
[DEBUG] Open Telemetry Frontend is active!
```

If OTEL is disabled:
```
[INFO] Open Telemetry is not enabled
```

---

## 6. What Gets Instrumented

### Backend (Automatic)

The `@opentelemetry/auto-instrumentations-node` package automatically instruments:

- **HTTP/HTTPS** - All incoming and outgoing HTTP requests
- **Express** - Route handling, middleware execution
- **MongoDB** - All database queries (via Mongoose)
- **Redis** - All cache operations (via ioredis)
- **DNS** - DNS lookups
- **Net** - Network operations
- **FS** - File system operations (optional)

**What You Get:**
- Span for every API request with route, method, status code
- Span for every MongoDB query with collection, operation
- Span for every Redis command
- Complete distributed trace from HTTP request through all downstream calls

### Frontend (Automatic)

The browser instrumentations capture:

- **Document Load** - Page load timing, resource loading
- **User Interactions** - Click events, form submissions
- **XMLHttpRequest** - All AJAX/Fetch API calls
- **Console Logs** - All console.log/error/warn/debug/info calls

**What You Get:**
- Performance metrics for page loads
- User interaction traces
- Frontend-to-backend trace correlation (via W3C TraceContext)
- All console output forwarded to OTEL

### Manual Instrumentation (Optional)

You can add custom spans/metrics:

**Backend:**
```javascript
const { trace } = require('@opentelemetry/api');

async function myFunction() {
  const tracer = trace.getTracer('my-service');
  const span = tracer.startSpan('my-operation');

  try {
    // Your code here
    span.setAttribute('custom.attribute', 'value');
    return result;
  } catch (error) {
    span.recordException(error);
    throw error;
  } finally {
    span.end();
  }
}
```

**Frontend:**
```typescript
import { trace } from '@opentelemetry/api';

function trackUserAction() {
  const tracer = trace.getTracer('frontend');
  const span = tracer.startSpan('user-clicked-button');

  span.setAttribute('button.id', 'submit-button');
  // ... perform action
  span.end();
}
```

---

## 7. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        LibreChat                             │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                       │
│  BACKEND (Node.js)   │        FRONTEND (React/Browser)      │
│                      │                                       │
│  1. server/index.js  │        1. main.jsx                   │
│     ↓                │           ↓                           │
│  2. initializeBackendOtel()     2. initializeFrontendOtel() │
│     ↓                │           ↓                           │
│  3. NodeSDK          │        3. Fetch /api/config          │
│     - TraceExporter  │           ↓                           │
│     - MetricExporter │        4. Get OTEL config from API   │
│     - LogExporter    │           ↓                           │
│     ↓                │        5. WebTracerProvider          │
│  4. Auto-instrument: │           - TraceExporter            │
│     - Express        │           - MetricExporter           │
│     - MongoDB        │           - LogExporter              │
│     - Redis          │           ↓                           │
│     - HTTP           │        6. Auto-instrument:           │
│     ↓                │           - DocumentLoad             │
│  5. Winston → OTEL   │           - UserInteraction          │
│                      │           - XMLHttpRequest           │
│                      │           ↓                           │
│                      │        7. Console → OTEL Logger      │
│                      │                                       │
├──────────────────────┴───────────────────┬───────────────────┤
│                                          │                   │
│              W3C TraceContext Propagation                    │
│              (traceparent, tracestate headers)               │
│                                          ↓                   │
└──────────────────────────────────────────┼───────────────────┘
                                           │
                                           ↓
                   ┌───────────────────────────────────┐
                   │    OTLP Export (with api-key)     │
                   └───────────────────────────────────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        ↓                  ↓                  ↓
                   /traces            /metrics           /logs
                        │                  │                  │
                        └──────────────────┼──────────────────┘
                                           │
                                           ↓
                              ┌────────────────────────┐
                              │  OTEL Collector/Backend │
                              │  (Opik, Jaeger, etc.)   │
                              └────────────────────────┘
```

---

## 8. Key Design Decisions

### 1. **Early Initialization (Backend)**
   - OTEL initialized BEFORE Express app creation
   - Ensures all framework code is instrumented
   - Critical for accurate tracing

### 2. **Graceful Degradation**
   - Missing OTEL config → Silent disable, not crash
   - App works perfectly without OTEL
   - Good for development/staging environments

### 3. **Frontend Config via API**
   - OTEL settings fetched from backend
   - Single source of truth (environment variables)
   - No need to rebuild frontend for config changes

### 4. **W3C Trace Context**
   - Standard propagation between frontend and backend
   - Enables end-to-end tracing across services
   - Compatible with any OTEL-compliant backend

### 5. **Separate HTTP/Proto Exporters**
   - Backend uses Proto (more efficient)
   - Frontend uses HTTP (browser compatible)
   - Both target same endpoints

### 6. **Console Interception (Frontend)**
   - All console output forwarded to OTEL
   - Original console behavior preserved
   - Recursion prevention built-in

### 7. **Winston Integration (Backend)**
   - Custom transport instead of replacing Winston
   - Existing logging infrastructure unchanged
   - Dual output: local logs + OTEL

### 8. **Auto-Instrumentation First**
   - Minimal manual span creation needed
   - Comprehensive coverage out-of-box
   - Extensible with manual instrumentation

---

## 9. Adapting for Opik Integration

Since Opik is OTEL-based, this integration should work with minimal changes:

### Required Changes

1. **Update Endpoint URLs** (if Opik uses different paths):
   ```javascript
   // If Opik expects /v1/traces instead of /traces
   traceExporter: new OTLPTraceExporter({
     url: `${configTraces.url}/v1/traces`,  // Adjust as needed
     headers: headers,
   })
   ```

2. **Update Authentication** (if Opik uses different header):
   ```javascript
   // If Opik uses 'Authorization: Bearer <token>'
   const headers = {
     'Authorization': `Bearer ${process.env.OPIK_API_KEY}`
   };
   ```

3. **Add Opik-Specific Attributes**:
   ```javascript
   const attributes = {
     // ... existing attributes
     'opik.project': process.env.OPIK_PROJECT,
     'opik.workspace': process.env.OPIK_WORKSPACE,
     // Add any Opik-specific metadata
   };
   ```

4. **Environment Variables**:
   ```bash
   # Rename for clarity
   OPIK_ENDPOINT=https://api.opik.ai
   OPIK_API_KEY=your_opik_api_key
   OPIK_PROJECT=librechat
   OPIK_WORKSPACE=production
   ```

### Opik-Specific Features

If Opik provides additional features beyond standard OTEL:

1. **Custom Exporters** - Replace OTLP exporters with Opik SDK if available
2. **Enhanced Metadata** - Add Opik-specific resource attributes
3. **Sampling** - Configure Opik-recommended sampling rates
4. **Custom Spans** - Add Opik-specific span attributes for LLM calls

---

## 10. Testing OTEL Integration

### Verify Backend Tracing

1. Start the app with OTEL enabled
2. Make an API request: `curl http://localhost:3080/api/config`
3. Check your OTEL backend for:
   - Trace with spans for HTTP request, route handler
   - Child spans for any database/cache calls

### Verify Frontend Tracing

1. Open browser DevTools → Console
2. Navigate to LibreChat
3. Check for: `Open Telemetry Frontend is active!`
4. Click around the UI
5. Check OTEL backend for:
   - Page load traces
   - User interaction spans
   - XHR request spans to backend API

### Verify End-to-End Tracing

1. Make a request from frontend (e.g., send a chat message)
2. In your OTEL backend, find the trace
3. Verify trace includes:
   - Frontend span (XHR request)
   - Backend span (HTTP request received)
   - Backend child spans (database queries, LLM API calls)
   - All spans have same `traceId`

### Verify Logging

**Backend:**
```bash
# Any Winston log should appear in OTEL
logger.info('Test message');
# Check OTEL logs for this message
```

**Frontend:**
```javascript
console.log('Test frontend log');
// Check OTEL logs for this message
```

---

## 11. Performance Considerations

### Overhead

- **Backend**: ~1-3% CPU overhead from auto-instrumentation
- **Frontend**: ~1-2% overhead from browser instrumentation
- **Network**: Additional HTTP requests for telemetry export

### Optimization Options

1. **Sampling**:
   ```javascript
   // Only trace 10% of requests
   const sdk = new NodeSDK({
     // ... other config
     sampler: new TraceIdRatioBasedSampler(0.1),
   });
   ```

2. **Batch Export**:
   ```javascript
   // Already using periodic export for metrics (1s interval)
   // Can adjust for traces too:
   spanProcessor: new BatchSpanProcessor(traceExporter, {
     maxQueueSize: 100,
     maxExportBatchSize: 10,
     scheduledDelayMillis: 5000,  // Export every 5s
   })
   ```

3. **Disable in Development**:
   ```javascript
   if (NODE_ENV === 'production') {
     initializeBackendOtel();
   }
   ```

---

## 12. Summary of Files

### New Files (6 total)

**Backend (3):**
1. `/api/server/middleware/otelMiddleware.js` - Main OTEL initialization
2. `/api/server/middleware/otelLoggingIntegration.js` - Winston transport
3. `/api/server/services/Config/otel.js` - Config service

**Frontend (3):**
1. `/client/src/utils/otelMiddleware.ts` - Main OTEL initialization
2. `/client/src/utils/otelLoggingIntegration.ts` - Console logger
3. (No new types file - uses existing TypeScript setup)

### Modified Files (5 total)

**Backend (3):**
1. `/api/server/index.js` - Added OTEL init call
2. `/api/server/routes/config.js` - Added OTEL config endpoint
3. `/api/package.json` - Added 11 dependencies

**Frontend (2):**
1. `/client/src/main.jsx` - Added OTEL init call
2. `/client/package.json` - Added 10 dependencies

**Config (1):**
1. `/.env.example` - Added OTEL environment variables

---

## 13. Complete Dependency List

### Backend (11 packages)
```json
{
  "@opentelemetry/api": "^1.9.0",
  "@opentelemetry/api-logs": "^0.201.0",
  "@opentelemetry/auto-instrumentations-node": "^0.59.0",
  "@opentelemetry/exporter-logs-otlp-http": "^0.202.0",
  "@opentelemetry/exporter-metrics-otlp-proto": "^0.202.0",
  "@opentelemetry/exporter-trace-otlp-proto": "^0.202.0",
  "@opentelemetry/resources": "^2.0.1",
  "@opentelemetry/sdk-logs": "^0.202.0",
  "@opentelemetry/sdk-metrics": "^2.0.1",
  "@opentelemetry/sdk-node": "^0.202.0",
  "@opentelemetry/semantic-conventions": "^1.34.0"
}
```

### Frontend (10 packages)
```json
{
  "@opentelemetry/api": "^1.9.0",
  "@opentelemetry/auto-configuration-propagators": "^0.4.1",
  "@opentelemetry/auto-instrumentations-web": "^0.48.0",
  "@opentelemetry/exporter-logs-otlp-http": "^0.202.0",
  "@opentelemetry/instrumentation": "^0.202.0",
  "@opentelemetry/resources": "^2.0.1",
  "@opentelemetry/sdk-metrics": "^2.0.1",
  "@opentelemetry/sdk-trace-base": "^2.0.1",
  "@opentelemetry/sdk-trace-web": "^2.0.1",
  "@opentelemetry/semantic-conventions": "^1.34.0"
}
```

**Total: 21 packages (some overlap between backend/frontend)**

---

## 14. Next Steps for Opik Integration

1. **Clone the OTEL fork** or copy the 6 new files
2. **Install dependencies** on both backend and frontend
3. **Update configuration** for Opik-specific endpoints/auth
4. **Test locally** with Opik instance
5. **Add custom instrumentation** for LibreChat-specific features:
   - LLM conversation tracking
   - Token usage metrics
   - Model switching traces
   - RAG query spans
6. **Configure sampling** for production load
7. **Set up dashboards** in Opik for LibreChat metrics
8. **Document** for LibreChat users wanting observability

---

## Additional Resources

- **OpenTelemetry Docs**: https://opentelemetry.io/docs/
- **OTLP Specification**: https://opentelemetry.io/docs/specs/otlp/
- **W3C Trace Context**: https://www.w3.org/TR/trace-context/
- **Node.js Auto-Instrumentation**: https://github.com/open-telemetry/opentelemetry-js-contrib/tree/main/metapackages/auto-instrumentations-node
- **Web Auto-Instrumentation**: https://github.com/open-telemetry/opentelemetry-js-contrib/tree/main/metapackages/auto-instrumentations-web

---

**Analysis Date**: 2025-11-23
**LibreChat OTEL Fork**: https://github.com/kvasir-cone-snail/LibreChat/tree/feat/otel
**Original LibreChat**: https://github.com/danny-avila/LibreChat
