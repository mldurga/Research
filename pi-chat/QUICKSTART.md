# Quick Start Guide - PI Vision Chat Interface

Get up and running quickly with the PI Vision Chat Interface.

## Prerequisites Checklist

- [ ] Windows Server with IIS installed
- [ ] AVEVA PI Vision installed
- [ ] AVEVA AF SDK installed
- [ ] Python 3.9+ installed
- [ ] Ollama installed and running
- [ ] Access to PI AF Server and PI Data Archive

## 5-Minute Setup (Development)

### 1. Install Ollama and Pull Models (2 min)

```powershell
# Install Ollama from https://ollama.ai
# Then pull required models:
ollama pull llama3
ollama pull nomic-embed-text
```

### 2. Setup Backend (2 min)

```powershell
cd pi-chat/backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure
cd config
Copy-Item appsettings.example.json appsettings.json

# Edit appsettings.json with your PI System details
notepad appsettings.json

# Run backend
cd ..
python -m app.main
```

Backend will start on http://localhost:8000

### 3. Install PI Vision Extension (1 min)

```powershell
# Run as Administrator
cd ..\deployment\iis
.\install-pivision-extension.ps1
```

## Verify Installation

1. **Check Backend Health**:
   ```powershell
   Invoke-WebRequest http://localhost:8000/api/health
   ```

2. **Open PI Vision**:
   - Navigate to your PI Vision URL
   - Go to Edit mode
   - Look for "PI Chat" in symbol palette
   - Drag onto a display

3. **Test Chat**:
   - Type: "What elements are available?"
   - Should get response from LLM

## Production Deployment

### Install as Windows Service

```powershell
# Run as Administrator
cd deployment\windows-service
.\install-service.ps1
```

### Configure CORS in Backend

Edit `backend/config/appsettings.json`:

```json
{
  "API": {
    "AllowedOrigins": [
      "http://your-pivision-server",
      "https://your-pivision-server"
    ]
  }
}
```

### Index PI System Metadata

```powershell
# Index elements for semantic search
Invoke-WebRequest -Uri "http://localhost:8000/api/admin/vector-db/index" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"force_reindex": true}'
```

## Common Issues & Solutions

### Backend won't start

**Issue**: "pythonnet fails to load AF SDK"

**Solution**:
```powershell
# Verify AF SDK installation
Test-Path "C:\Program Files\AVEVA\PI System\AF\PublicAssemblies\4.0\OSIsoft.AFSDK.dll"

# If path is different, update in backend/app/services/af_sdk/client.py
```

### PI Vision symbol not showing

**Solution**:
```powershell
# Restart IIS
iisreset

# Clear browser cache
# Ctrl + Shift + Delete -> Clear cache
```

### Can't connect to PI System

**Solution**:
```powershell
# Verify PI System names in appsettings.json
# Test connection using PI System Explorer
# Check Windows Authentication is enabled
# Verify network connectivity to PI servers
```

### Ollama not responding

**Solution**:
```powershell
# Check if Ollama is running
Get-Service ollama

# Restart Ollama
Restart-Service ollama

# Verify models are pulled
ollama list
```

## Next Steps

1. **Configure Security**:
   - Enable Windows Authentication
   - Configure AD group permissions
   - Set up element-level security

2. **Customize Agents**:
   - Access admin panel (if deployed)
   - Create custom agents for specific tasks
   - Configure MCP tools

3. **Create Displays**:
   - Design PI Vision displays with chat
   - Associate PI elements for context
   - Share with users

4. **Monitor Performance**:
   - Check logs in `backend/logs/`
   - Review API metrics
   - Monitor Ollama resource usage

## Useful Commands

```powershell
# Backend
Start-Service PIVisionChatBackend          # Start service
Stop-Service PIVisionChatBackend           # Stop service
Restart-Service PIVisionChatBackend        # Restart service
Get-Service PIVisionChatBackend            # Check status

# Logs
Get-Content backend\logs\pi_chat_*.log -Tail 50        # View logs
Get-Content backend\logs\errors_*.log -Tail 20         # View errors

# IIS
iisreset                                   # Restart IIS
Restart-WebAppPool -Name "PI Vision"       # Restart app pool

# Ollama
ollama list                                # List models
ollama pull <model>                        # Pull new model
ollama serve                               # Start Ollama server
```

## Getting Help

- **Documentation**: See `docs/` folder
- **API Docs**: http://localhost:8000/api/docs
- **Logs**: `backend/logs/`
- **Architecture**: `docs/architecture.md`
- **Full Setup**: `docs/setup.md`

## Sample Queries to Try

Once installed, try these queries:

1. "What PI elements are available in the system?"
2. "Show me the current value of [element path]"
3. "What were the values for [attribute] over the last 24 hours?"
4. "Explain the purpose of [element name]"
5. "Find all temperature sensors"

## Performance Tips

- Use smaller Ollama models for faster responses (mistral vs llama3:70b)
- Index PI metadata in vector DB for better search
- Enable caching in backend configuration
- Deploy on server with GPU for Ollama
- Use SSD for ChromaDB storage

## Security Checklist

- [ ] Windows Authentication enabled
- [ ] HTTPS configured for production
- [ ] CORS properly configured (not allowing *)
- [ ] Element permissions enforced
- [ ] Admin API access restricted
- [ ] Logs secured and monitored
- [ ] Regular security updates applied

## Support & Community

For issues, questions, or contributions, please refer to the project repository.

---

**Ready to go!** You now have a working PI Vision Chat Interface. Start chatting with your PI System! 🚀
