# Offline Installation Guide

This guide explains how to install and deploy the PI Notification POC in a secure, air-gapped ADNOC environment without internet access.

## Prerequisites

### On an Internet-Connected Machine

You need a Windows machine with internet access to download the required packages.

1. **Python 3.8 or higher** installed
2. **pip** package manager
3. **Same OS architecture** as target machine (x64 recommended)

### On the Target ADNOC Machine

1. **Windows Server or Windows 10/11**
2. **Python 3.8 or higher** installed (offline installer)
3. **Microsoft Outlook** installed and configured
4. **PI SDK** installed (for PIconnect)
5. **Ollama** installed as Windows service
6. **Network access** to PI Data Archive server

## Step 1: Download Python Packages (Internet-Connected Machine)

### 1.1 Create a Download Directory

```cmd
mkdir C:\pi-notification-packages
cd C:\pi-notification-packages
```

### 1.2 Download All Dependencies

Copy the `requirements.txt` file to this machine, then run:

```cmd
pip download -r requirements.txt -d packages
```

This will download all packages and their dependencies to the `packages` folder.

### 1.3 Download Python Offline Installer (if needed)

If Python is not installed on the target machine:

1. Download Python installer from https://www.python.org/downloads/windows/
2. Choose "Windows installer (64-bit)" for offline installation
3. Save the `.exe` file

### 1.4 Download Ollama for Windows

1. Download Ollama from https://ollama.ai/download/windows
2. Save the installer

### 1.5 Package Everything

Copy the entire project folder and packages:

```cmd
C:\pi-notification-packages\
├── packages\               # Downloaded pip packages
├── python-installer.exe    # Python offline installer (if needed)
├── ollama-windows.exe      # Ollama installer
└── pi-notification-poc\    # Project source code
```

Transfer this folder to the target machine using approved media (USB drive, network share, etc.).

## Step 2: Install Python (Target Machine)

If Python is not installed:

```cmd
python-installer.exe /quiet PrependPath=1 Include_test=0
```

Verify installation:

```cmd
python --version
pip --version
```

## Step 3: Install Ollama (Target Machine)

### 3.1 Run Ollama Installer

```cmd
ollama-windows.exe
```

### 3.2 Download Required Model (Requires Internet - Do Before Deployment)

On a machine with internet access:

```cmd
ollama pull llama3.2
```

Then copy the Ollama models to the target machine. Models are typically stored at:
- Windows: `C:\Users\<username>\.ollama\models`

Copy the entire `.ollama` folder to the same location on the target machine.

### 3.3 Configure Ollama as Windows Service

Create a batch file `install-ollama-service.bat`:

```batch
@echo off
REM Install Ollama as Windows Service

sc create OllamaService binPath="C:\Program Files\Ollama\ollama.exe serve" start=auto
sc description OllamaService "Ollama LLM Service for PI Notification"
sc start OllamaService

echo Ollama service installed and started
pause
```

Run as Administrator:

```cmd
install-ollama-service.bat
```

Verify Ollama is running:

```cmd
curl http://localhost:11434/api/tags
```

## Step 4: Install Python Dependencies (Target Machine)

Navigate to the packages directory:

```cmd
cd C:\pi-notification-packages
```

Install packages from local directory:

```cmd
pip install --no-index --find-links=packages -r pi-notification-poc\requirements.txt
```

Verify installation:

```cmd
python -c "import yaml; import PyPDF2; import win32com.client; print('All packages installed successfully')"
```

## Step 5: Install PI SDK

The PI SDK must be installed separately. Contact your OSIsoft administrator for:

1. PI SDK installer
2. Installation instructions
3. PI Data Archive server connection details

After PI SDK installation, verify PIconnect:

```cmd
python -c "import PIconnect; print('PIconnect available')"
```

## Step 6: Configure the Application

### 6.1 Copy Project Files

Copy the `pi-notification-poc` folder to the target location:

```cmd
xcopy /E /I C:\pi-notification-packages\pi-notification-poc C:\PINotificationPOC
```

### 6.2 Edit Configuration

Edit `C:\PINotificationPOC\config\config.yaml`:

```yaml
# Update these settings for your environment
email:
  target_subject: "PI Data Update"  # Your email subject

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.2"

pi:
  server_name: "YOUR_PI_SERVER_NAME"  # Update with actual PI server
  auth_method: "windows"
```

## Step 7: Test the Application

Run the application manually first:

```cmd
cd C:\PINotificationPOC
python src\main.py
```

Verify:
- ✓ Outlook connection successful
- ✓ Ollama connection successful
- ✓ PI server connection successful

Send a test email with a PDF attachment to trigger processing.

## Step 8: Install as Windows Service

Once testing is complete, install as a Windows service:

```cmd
cd C:\PINotificationPOC\src
python windows_service.py install
```

Configure service to start automatically:

```cmd
sc config PINotificationService start=auto
```

Start the service:

```cmd
python windows_service.py start
```

Or use Services Manager (services.msc):
1. Open Services (Run → services.msc)
2. Find "PI Notification Email Processor"
3. Right-click → Properties
4. Set "Startup type" to "Automatic"
5. Click "Start"

## Step 9: Verify Service Operation

Check service status:

```cmd
sc query PINotificationService
```

View service logs:

```cmd
type C:\PINotificationPOC\logs\pi_notification.log
```

## Troubleshooting

### Common Issues

#### 1. "Cannot connect to Outlook"

**Solution:**
- Ensure Outlook is installed and configured with a profile
- Run as the same user account that has Outlook configured
- Check Windows Event Viewer for COM errors

#### 2. "Cannot connect to Ollama"

**Solution:**
- Verify Ollama service is running: `sc query OllamaService`
- Check Ollama is listening: `netstat -an | findstr 11434`
- Test connection: `curl http://localhost:11434/api/tags`

#### 3. "PIconnect import error"

**Solution:**
- Verify PI SDK is installed
- Check PI SDK version compatibility with PIconnect
- Reinstall PIconnect: `pip install --force-reinstall PIconnect`

#### 4. "Cannot connect to PI server"

**Solution:**
- Verify network connectivity to PI server
- Check PI server name in configuration
- Verify Windows authentication has PI access
- Test connection using PI SDK tools

#### 5. Service won't start

**Solution:**
- Check service log: `C:\PINotificationPOC\logs\service.log`
- Verify service account has required permissions
- Check Windows Event Viewer → Application logs

### Log Files

- **Application logs**: `C:\PINotificationPOC\logs\pi_notification.log`
- **Service logs**: `C:\PINotificationPOC\logs\service.log`
- **Windows Event Logs**: Event Viewer → Application

## Security Considerations

1. **File Permissions**: Restrict access to configuration files containing credentials
2. **Service Account**: Use dedicated service account with minimal required permissions
3. **Network Security**: Ensure only required ports are open (11434 for Ollama)
4. **Audit Logs**: Regularly review application logs for security events
5. **Updates**: Maintain offline update process for security patches

## Updating the Application

To update in an offline environment:

1. Download new version on internet-connected machine
2. Download any new dependencies: `pip download -r requirements.txt -d packages-new`
3. Transfer to target machine
4. Stop service: `python windows_service.py stop`
5. Backup current installation
6. Update files
7. Install new dependencies: `pip install --no-index --find-links=packages-new -r requirements.txt`
8. Start service: `python windows_service.py start`

## Uninstallation

To remove the service:

```cmd
python windows_service.py stop
python windows_service.py uninstall
```

To remove Ollama service:

```cmd
sc stop OllamaService
sc delete OllamaService
```

## Support

For issues specific to:
- **PI System**: Contact OSIsoft support or your PI administrator
- **Ollama**: Check Ollama documentation at https://ollama.ai/docs
- **Python packages**: Refer to package documentation
