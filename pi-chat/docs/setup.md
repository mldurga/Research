# PI Vision Chat Interface - Setup Guide

Complete installation and configuration guide for the PI Vision Chat Interface.

## Prerequisites

### Software Requirements

1. **AVEVA PI System**
   - PI Data Archive
   - PI Asset Framework (AF) Server
   - PI Vision 2023 or later

2. **Windows Server**
   - Windows Server 2019 or later
   - IIS 10.0 or later
   - .NET Framework 4.8 or later
   - .NET Core 8.0 or later

3. **Python Environment**
   - Python 3.9 or later
   - pip package manager
   - virtualenv (recommended)

4. **Ollama**
   - Ollama installed and running
   - At least one model pulled (e.g., llama3, mistral)

5. **Additional Software**
   - Node.js 18+ (for admin panel)
   - Git (optional, for version control)

### Hardware Requirements

- **Minimum**:
  - 8 GB RAM
  - 4 CPU cores
  - 50 GB disk space

- **Recommended**:
  - 16 GB RAM
  - 8 CPU cores
  - 100 GB SSD

## Installation Steps

### 1. Install AF SDK

The AF SDK is required for the backend to communicate with PI System.

1. Download AF SDK from AVEVA Customer Portal
2. Install AF Client on the server where the backend will run
3. Verify installation:
   ```powershell
   Test-Path "C:\Program Files\AVEVA\PI System\AF\PublicAssemblies\4.0\OSIsoft.AFSDK.dll"
   ```

### 2. Install Ollama

1. Download Ollama from https://ollama.ai
2. Install Ollama:
   ```powershell
   # Download and run the installer
   # Ollama will be installed as a Windows service
   ```

3. Pull required models:
   ```powershell
   ollama pull llama3
   ollama pull mistral
   ollama pull nomic-embed-text  # For embeddings
   ```

4. Verify Ollama is running:
   ```powershell
   ollama list
   ```

### 3. Setup Python Backend

#### 3.1. Clone or Copy Repository

```powershell
cd C:\
git clone <repository-url> pi-chat
# OR copy the pi-chat folder to C:\pi-chat
```

#### 3.2. Create Virtual Environment

```powershell
cd C:\pi-chat\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 3.3. Install Dependencies

```powershell
pip install -r requirements.txt
```

Note: Installing pythonnet may require Visual C++ Build Tools.

#### 3.4. Configure Application

1. Copy example configuration:
   ```powershell
   cd config
   Copy-Item appsettings.example.json appsettings.json
   ```

2. Edit `appsettings.json`:
   ```json
   {
     "PISystem": {
       "AFServer": "YOUR_AF_SERVER",
       "PIDataArchive": "YOUR_PI_SERVER",
       "DefaultDatabase": "YOUR_DATABASE"
     },
     "API": {
       "Host": "0.0.0.0",
       "Port": 8000,
       "AllowedOrigins": [
         "http://your-pivision-server",
         "https://your-pivision-server"
       ]
     }
   }
   ```

#### 3.5. Test Backend

```powershell
python -m app.main
```

Open browser to http://localhost:8000/api/docs to verify API is running.

### 4. Install as Windows Service

#### 4.1. Install NSSM (Non-Sucking Service Manager)

```powershell
# Download NSSM from https://nssm.cc/download
# Extract to C:\nssm

C:\nssm\nssm.exe install PIVisionChatBackend "C:\pi-chat\backend\venv\Scripts\python.exe" "C:\pi-chat\backend\app\main.py"

# Configure service
C:\nssm\nssm.exe set PIVisionChatBackend AppDirectory "C:\pi-chat\backend"
C:\nssm\nssm.exe set PIVisionChatBackend DisplayName "PI Vision Chat Backend"
C:\nssm\nssm.exe set PIVisionChatBackend Description "FastAPI backend for PI Vision Chat Interface"
C:\nssm\nssm.exe set PIVisionChatBackend Start SERVICE_AUTO_START

# Start service
Start-Service PIVisionChatBackend
```

#### 4.2. Verify Service

```powershell
Get-Service PIVisionChatBackend
```

### 5. Install PI Vision Extension

#### 5.1. Copy Extension Files

```powershell
$pivisionPath = "C:\Program Files\AVEVA\PI Vision\Scripts\app\editor\symbols\ext"
New-Item -Path "$pivisionPath\pichat" -ItemType Directory -Force

Copy-Item "C:\pi-chat\pi-vision-extension\*" -Destination "$pivisionPath\pichat" -Recurse
```

#### 5.2. Set Permissions

```powershell
$acl = Get-Acl "$pivisionPath\pichat"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("IIS_IUSRS", "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.SetAccessRule($rule)
Set-Acl "$pivisionPath\pichat" $acl
```

#### 5.3. Restart IIS

```powershell
iisreset
```

#### 5.4. Verify Installation

1. Open PI Vision in a browser
2. Go to Edit mode
3. Look for "PI Chat" symbol in the symbol palette
4. If not visible, clear browser cache and refresh

### 6. Configure CORS in PI Vision

PI Vision needs to allow requests to the backend API.

1. Edit PI Vision web.config:
   ```xml
   <system.webServer>
     <httpProtocol>
       <customHeaders>
         <add name="Access-Control-Allow-Origin" value="http://localhost:8000" />
         <add name="Access-Control-Allow-Methods" value="GET,POST,PUT,DELETE,OPTIONS" />
         <add name="Access-Control-Allow-Headers" value="Content-Type,Authorization" />
       </customHeaders>
     </httpProtocol>
   </system.webServer>
   ```

2. Restart IIS

### 7. Setup Admin Panel (Optional)

#### 7.1. Install Dependencies

```powershell
cd C:\pi-chat\admin-panel
npm install
```

#### 7.2. Configure Environment

Create `.env` file:
```
VITE_API_URL=http://localhost:8000
```

#### 7.3. Build for Production

```powershell
npm run build
```

#### 7.4. Deploy to IIS

1. Create new IIS site for admin panel
2. Point to `dist` folder
3. Configure URL rewrite for SPA

### 8. Initialize Vector Database

Index PI System metadata for semantic search:

```powershell
# Using curl or Invoke-WebRequest
Invoke-WebRequest -Uri "http://localhost:8000/api/admin/vector-db/index" -Method POST -ContentType "application/json" -Body '{"force_reindex": true}'
```

## Verification

### Test Backend

1. Health check:
   ```powershell
   Invoke-WebRequest http://localhost:8000/api/health
   ```

2. Test AF SDK connection:
   ```powershell
   Invoke-WebRequest http://localhost:8000/api/health/detailed
   ```

### Test PI Vision Extension

1. Open PI Vision
2. Create new display
3. Add "PI Chat" symbol
4. Try sending a message

### Test End-to-End

1. In PI Vision, add PI Chat symbol
2. Associate some PI elements with the symbol
3. Ask: "What elements are available?"
4. Verify response includes associated elements

## Troubleshooting

### Backend Issues

**pythonnet fails to load AF SDK:**
- Verify AF SDK is installed
- Check DLL path in `app/services/af_sdk/client.py`
- Ensure Python architecture (x64) matches AF SDK

**Connection to PI System fails:**
- Verify AF Server and PI Server names in config
- Check Windows authentication
- Verify network connectivity
- Check PI System security settings

**Ollama not available:**
- Verify Ollama service is running
- Check `http://localhost:11434` is accessible
- Ensure models are pulled

### PI Vision Extension Issues

**Symbol doesn't appear:**
- Check file permissions
- Verify files are in correct directory
- Clear browser cache
- Check browser console for errors

**Backend connection fails:**
- Check CORS configuration
- Verify backend URL in symbol config
- Check network/firewall rules

### Performance Issues

**Slow responses:**
- Check Ollama model size (use smaller models)
- Increase backend timeout settings
- Check network latency to PI System
- Consider caching frequently accessed data

**High memory usage:**
- Reduce vector DB collection size
- Limit conversation history
- Use model quantization in Ollama

## Security Considerations

1. **Authentication:**
   - Enable Windows Authentication in backend
   - Configure PI Security integration
   - Use HTTPS in production

2. **Authorization:**
   - Implement element-level permissions
   - Restrict admin API access
   - Configure CORS properly

3. **Network:**
   - Use firewall rules to restrict backend access
   - Deploy backend on internal network only
   - Use VPN for remote access

## Next Steps

- Configure agents in admin panel
- Set up MCP tools for specialized queries
- Create custom PI Vision displays with chat
- Train team on usage and best practices

## Support

For issues and questions:
- Check logs in `backend/logs/`
- Review API documentation at `/api/docs`
- Contact PI System administrator
