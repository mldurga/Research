# PI Vision Chat Interface - Architecture

Detailed architecture documentation for the PI Vision Chat Interface system.

## System Overview

The PI Vision Chat Interface is a multi-tier architecture that integrates:
- PI Vision frontend (custom extensibility symbol)
- FastAPI backend (Python)
- AF SDK for PI System access (.NET via pythonnet)
- Ollama for LLM capabilities
- ChromaDB for semantic search
- Optional admin panel for configuration

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Web Browser (PI Vision)                                  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  PI Chat Custom Symbol                              │  │  │
│  │  │  - HTML/CSS/JavaScript                              │  │  │
│  │  │  - WebSocket/REST client                            │  │  │
│  │  │  - Context management                               │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────────────┘
                  │ HTTPS/WSS
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer (FastAPI)                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  API Gateway                                              │  │
│  │  - Authentication & Authorization                         │  │
│  │  - Request routing                                        │  │
│  │  - Rate limiting                                          │  │
│  │  - CORS handling                                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Service Layer                                            │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │  Chat       │  │  PI System   │  │  Vector DB      │  │  │
│  │  │  Service    │  │  Service     │  │  Service        │  │  │
│  │  └─────────────┘  └──────────────┘  └─────────────────┘  │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │  LLM        │  │  Security    │  │  Agent          │  │  │
│  │  │  Service    │  │  Service     │  │  Orchestrator   │  │  │
│  │  └─────────────┘  └──────────────┘  └─────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                  │                        │
                  ▼                        ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│     Integration Layer        │  │    Data Layer              │
│  ┌────────────────────────┐  │  │  ┌──────────────────────┐  │
│  │  AF SDK Client         │  │  │  │  ChromaDB            │  │
│  │  (pythonnet bridge)    │  │  │  │  - Embeddings        │  │
│  │  - .NET interop        │  │  │  │  - Metadata          │  │
│  │  - Connection mgmt     │  │  │  │  - Semantic search   │  │
│  └────────────────────────┘  │  │  └──────────────────────┘  │
│  ┌────────────────────────┐  │  │  ┌──────────────────────┐  │
│  │  PI Web API Client     │  │  │  │  SQLite              │  │
│  │  (Fallback)            │  │  │  │  - Conversations     │  │
│  │  - REST client         │  │  │  │  - User sessions     │  │
│  └────────────────────────┘  │  │  └──────────────────────┘  │
│  ┌────────────────────────┐  │  └────────────────────────────┘
│  │  Ollama Client         │  │
│  │  - Local models        │  │
│  │  - Frontier API proxy  │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     External Systems                             │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  PI AF Server │  │  PI Data     │  │  Ollama Service    │   │
│  │               │  │  Archive     │  │  - llama3          │   │
│  │  - Elements   │  │  - PI Points │  │  - mistral         │   │
│  │  - Templates  │  │  - Archives  │  │  - custom models   │   │
│  │  - Security   │  │  - Security  │  │                    │   │
│  └───────────────┘  └──────────────┘  └────────────────────┘   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Active Directory                                         │  │
│  │  - User authentication                                    │  │
│  │  - Group membership                                       │  │
│  │  - Security policies                                      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. PI Vision Custom Symbol

**Technology**: JavaScript, HTML, CSS

**Responsibilities**:
- Render chat UI within PI Vision displays
- Manage user interactions
- Communicate with backend via REST/WebSocket
- Handle PI element context
- Display responses and visualizations

**Key Files**:
- `sym-pichat.js`: Symbol implementation
- `sym-pichat-template.html`: UI template
- `sym-pichat-config.js`: Configuration panel

### 2. FastAPI Backend

**Technology**: Python, FastAPI, uvicorn

**Responsibilities**:
- API endpoint management
- Request/response handling
- Service orchestration
- WebSocket management
- Authentication/authorization
- Error handling and logging

**Key Modules**:
- `app/main.py`: Application entry point
- `app/api/`: API route handlers
- `app/core/`: Core functionality (config, logging)
- `app/models/`: Pydantic models

### 3. AF SDK Integration

**Technology**: pythonnet, .NET AF SDK

**Responsibilities**:
- Bridge Python to .NET AF SDK
- Manage connections to AF Server
- Query AF elements and hierarchies
- Read/write PI Point data
- Handle AF security

**Key Features**:
- Element search and navigation
- Attribute value retrieval
- Recorded values queries
- Event frame access
- Security permission checks

**Challenges & Solutions**:
- **Python to .NET bridge**: Use pythonnet with proper type conversion
- **Memory management**: Explicit disposal of .NET objects
- **Threading**: AF SDK operations on dedicated thread pool
- **Error handling**: Translate .NET exceptions to Python

### 4. LLM Integration (Ollama)

**Technology**: Ollama REST API, httpx

**Responsibilities**:
- Generate chat responses
- Create embeddings for semantic search
- Stream responses to client
- Manage multiple models
- Handle context and prompts

**Supported Models**:
- Local models (llama3, mistral, codellama)
- Embedding models (nomic-embed-text)
- Frontier models via API proxy (GPT-4, Claude)

**Features**:
- Streaming responses
- Temperature and token control
- System prompts for PI System context
- Model switching

### 5. Vector Database (ChromaDB)

**Technology**: ChromaDB, sentence-transformers

**Responsibilities**:
- Store PI System metadata embeddings
- Semantic search for elements
- Context retrieval for LLM
- Conversation history

**Indexed Content**:
- AF element names and descriptions
- PI Point names and descriptions
- Template information
- Attribute metadata
- Categories and relationships

**Search Capabilities**:
- Semantic similarity search
- Metadata filtering
- Distance-based ranking
- Hybrid search (text + metadata)

### 6. Security Service

**Technology**: Python, pywin32, ldap

**Responsibilities**:
- Windows authentication
- AD group membership checking
- PI element permission validation
- PI Point permission validation
- Permission caching
- JWT token management

**Security Layers**:
1. **Authentication**: Windows auth, JWT tokens
2. **Authorization**: Role-based access control
3. **PI Security**: Element and point-level permissions
4. **AD Integration**: Group-based policies

### 7. Agent Orchestration

**Technology**: LangChain, custom agents

**Responsibilities**:
- Agent lifecycle management
- Tool/function calling
- Multi-agent coordination
- MCP (Model Context Protocol) integration
- Task planning and execution

**Agent Types**:
- PI System query agent
- Data analysis agent
- Trend analysis agent
- Alarm investigation agent
- Custom user-defined agents

## Data Flow

### Chat Message Flow

1. **User Input**:
   - User types message in PI Vision chat symbol
   - Symbol includes PI element context if available
   - Message sent to backend via POST /api/chat/message

2. **Backend Processing**:
   - Authenticate user
   - Extract context elements
   - Query vector DB for relevant PI metadata
   - Build enhanced prompt with context
   - Send to Ollama LLM

3. **LLM Processing**:
   - Generate response based on prompt
   - May include PI System queries
   - Stream or return complete response

4. **Response Handling**:
   - Backend receives LLM response
   - Optionally query PI System for data
   - Format response with sources
   - Return to client

5. **UI Update**:
   - Symbol receives response
   - Display in chat interface
   - Show sources and references

### PI System Query Flow

1. **Query Initiation**:
   - LLM determines PI System query needed
   - Backend receives structured query

2. **AF SDK Execution**:
   - Check user permissions
   - Execute query via AF SDK
   - Retrieve data from PI System

3. **Data Processing**:
   - Format data for display
   - Apply business logic
   - Cache if appropriate

4. **Response**:
   - Return data to LLM for interpretation
   - LLM generates natural language response

## Deployment Architecture

### Production Deployment

```
┌─────────────────────────────────────────────────────────────┐
│  Windows Server (IIS)                                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  PI Vision (IIS Site)                                  │  │
│  │  - Custom symbol loaded                                │  │
│  │  - HTTPS enabled                                       │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  FastAPI Backend (Windows Service)                     │  │
│  │  - NSSM service wrapper                                │  │
│  │  - Auto-restart on failure                             │  │
│  │  - Logging to file                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Ollama Service                                        │  │
│  │  - Models loaded in memory                             │  │
│  │  - GPU acceleration if available                       │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ChromaDB (Persistent)                                 │  │
│  │  - File-based storage                                  │  │
│  │  - Regular backups                                     │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Scaling Considerations

1. **Horizontal Scaling**:
   - Multiple FastAPI instances behind load balancer
   - Shared ChromaDB via client/server mode
   - Redis for distributed caching

2. **Vertical Scaling**:
   - GPU for Ollama (faster inference)
   - More RAM for model loading
   - SSD for ChromaDB

3. **Performance Optimization**:
   - Connection pooling for PI System
   - Response caching
   - Async operations throughout
   - Request queuing for LLM

## Security Architecture

### Authentication Flow

```
User -> PI Vision -> Backend -> Windows Auth -> AD
                               -> JWT Token -> Subsequent Requests
```

### Authorization Flow

```
Request -> Backend -> Check JWT -> Check PI Security -> Execute
                                 -> Check AD Groups
                                 -> Cache Result
```

### Data Security

- **In Transit**: HTTPS/TLS 1.2+
- **At Rest**: File system encryption, Windows DPAPI
- **Credentials**: Windows Credential Manager, environment variables
- **Secrets**: Azure Key Vault or HashiCorp Vault (optional)

## Monitoring & Observability

### Logging

- **Application Logs**: loguru to file and console
- **Service Logs**: Windows Event Log
- **Access Logs**: FastAPI access logs
- **Error Tracking**: Sentry (optional)

### Metrics

- **API Metrics**: Request count, latency, errors
- **LLM Metrics**: Token usage, response time, model performance
- **PI System Metrics**: Query count, response time
- **System Metrics**: CPU, memory, disk

### Health Checks

- `/api/health`: Basic health check
- `/api/health/detailed`: Component-level health
- Windows Service monitoring
- Ollama availability check

## Extensibility

### Adding New Agents

1. Create agent configuration in admin panel
2. Define system prompt and tools
3. Register MCP tools if needed
4. Test and deploy

### Adding New MCP Tools

1. Implement tool function in Python
2. Define tool schema (parameters, returns)
3. Register in admin panel
4. Make available to agents

### Custom PI System Integrations

1. Extend AF SDK client with new methods
2. Create new API endpoints
3. Update PI Vision symbol if needed
4. Document new capabilities

## Future Enhancements

1. **Multi-Modal Support**: Images, charts in responses
2. **Voice Interface**: Speech-to-text, text-to-speech
3. **Advanced Analytics**: Predictive models, anomaly detection
4. **Collaboration**: Multi-user conversations, sharing
5. **Mobile App**: Native mobile interface
6. **Notifications**: Proactive alerts and insights
