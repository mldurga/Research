# PI Vision Chat Interface

A comprehensive chat interface for AVEVA PI Vision that enables natural language interaction with PI System using LLMs, with full security integration and extensibility.

## Architecture Overview

This solution consists of several integrated components:

### 1. **PI Vision Extension** (Frontend)
- Custom PI Vision symbol/tool built with HTML/CSS/JavaScript
- Embedded chat interface within PI Vision
- Real-time WebSocket communication
- Context-aware PI element integration

### 2. **FastAPI Backend** (Python)
- RESTful API and WebSocket server
- AF SDK integration via pythonnet (.NET bridge)
- PI Web API fallback support
- PI Security integration (AD groups, element-level permissions)
- Session management and authentication

### 3. **LLM Integration Layer**
- Ollama for local model hosting
- Support for frontier models (GPT-4, Claude, etc.)
- Agent orchestration framework
- MCP (Model Context Protocol) tools integration

### 4. **Vector Database** (ChromaDB)
- PI System metadata embeddings
- Semantic search for elements, attributes, and PI points
- Conversation history and context
- Fast retrieval and RAG support

### 5. **Admin Panel** (React)
- Agent configuration and management
- MCP tools administration
- Security policy configuration
- Orchestration rules builder
- System monitoring

## Project Structure

```
pi-chat/
├── backend/                    # FastAPI backend service
│   ├── app/
│   │   ├── api/               # API routes
│   │   ├── core/              # Core functionality
│   │   ├── models/            # Data models
│   │   ├── services/          # Business logic
│   │   │   ├── af_sdk/        # AF SDK integration via pythonnet
│   │   │   ├── pi_webapi/     # PI Web API client
│   │   │   ├── llm/           # LLM integration (Ollama, OpenAI)
│   │   │   ├── vector_db/     # ChromaDB integration
│   │   │   ├── security/      # PI Security & AD integration
│   │   │   └── agents/        # Agent orchestration
│   │   └── main.py            # FastAPI application entry
│   ├── requirements.txt
│   └── config/
│       └── appsettings.json   # PI System configuration
│
├── pi-vision-extension/       # PI Vision custom symbol
│   ├── sym-pichat.js          # Main symbol implementation
│   ├── sym-pichat-template.html
│   ├── sym-pichat-config.js
│   └── README.md
│
├── admin-panel/               # React admin interface
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── shared/                    # Shared types and utilities
│   └── types/
│
├── deployment/                # Deployment configurations
│   ├── windows-service/       # Windows service setup
│   ├── iis/                   # IIS configuration
│   └── docker/                # Docker containers (optional)
│
└── docs/                      # Documentation
    ├── setup.md
    ├── architecture.md
    ├── security.md
    └── api.md
```

## Key Features

### Security
- **PI Security Integration**: Respects AF element and PI point security
- **AD Authentication**: Windows Authentication with Active Directory
- **Role-Based Access Control**: Configurable user roles and permissions
- **Data-Level Security**: Element and attribute-level permission checks

### LLM Capabilities
- **Multi-Model Support**: Ollama for local models, API support for frontier models
- **Agent Framework**: Custom agents with specialized capabilities
- **MCP Tools**: Extensible tool system for PI System operations
- **Context-Aware**: Uses vector DB for relevant context retrieval

### PI System Integration
- **AF SDK Primary**: High-performance .NET AF SDK via pythonnet
- **PI Web API Fallback**: REST API fallback for compatibility
- **Real-Time Data**: Live data streaming and subscriptions
- **Event Frames**: Query and analyze event frames
- **Asset Navigation**: Intelligent hierarchy traversal

## Installation & Deployment

See [docs/setup.md](docs/setup.md) for detailed installation instructions.

### Quick Start

1. **Backend Setup**
```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

2. **Install PI Vision Extension**
```bash
# Copy pi-vision-extension to PI Vision extensibility folder
# Typically: C:\Program Files\AVEVA\PI Vision\Scripts\app\editor\symbols\ext
```

3. **Admin Panel Setup**
```bash
cd admin-panel
npm install
npm run dev
```

4. **Configure Ollama**
```bash
# Install Ollama and pull required models
ollama pull llama3
ollama pull mistral
```

## Configuration

### Backend Configuration (appsettings.json)
```json
{
  "PISystem": {
    "AFServer": "your-af-server",
    "PIDataArchive": "your-pi-server",
    "DefaultDatabase": "your-database"
  },
  "Ollama": {
    "BaseUrl": "http://localhost:11434",
    "DefaultModel": "llama3"
  },
  "VectorDB": {
    "PersistDirectory": "./chroma_db",
    "CollectionName": "pi_metadata"
  },
  "Security": {
    "EnableWindowsAuth": true,
    "RequireElementPermissions": true
  }
}
```

## API Endpoints

### Chat API
- `POST /api/chat/message` - Send chat message
- `WS /api/chat/stream` - WebSocket for streaming responses
- `GET /api/chat/history` - Get conversation history

### PI System API
- `GET /api/pi/elements` - Search AF elements
- `GET /api/pi/elements/{path}/attributes` - Get element attributes
- `GET /api/pi/points/{name}/value` - Get PI point value
- `POST /api/pi/points/{name}/value` - Write PI point value

### Admin API
- `GET /api/admin/agents` - List configured agents
- `POST /api/admin/agents` - Create new agent
- `GET /api/admin/mcp-tools` - List MCP tools
- `POST /api/admin/mcp-tools` - Register new MCP tool

## Technologies Used

- **Backend**: FastAPI, pythonnet, AF SDK, httpx, ChromaDB
- **Frontend**: Vanilla JavaScript (PI Vision), React (Admin Panel)
- **LLM**: Ollama, OpenAI API, LangChain
- **Database**: ChromaDB (vector), SQLite (metadata)
- **Security**: Windows Authentication, PI Security API
- **Deployment**: Windows Service, IIS (PI Vision hosting)

## Development Roadmap

- [x] Project structure and architecture design
- [ ] FastAPI backend implementation
- [ ] AF SDK integration via pythonnet
- [ ] PI Security implementation
- [ ] Ollama integration
- [ ] Vector DB setup
- [ ] PI Vision extension development
- [ ] Admin panel implementation
- [ ] Agent orchestration framework
- [ ] MCP tools integration
- [ ] Deployment automation
- [ ] Documentation and testing

## License

MIT License

## Support

For issues and questions, please create an issue in the repository.
