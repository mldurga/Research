# PI Notification POC

**Automated Email-to-PI Data Pipeline for Secure ADNOC Environment**

This proof-of-concept system monitors Microsoft Outlook for emails with specific subjects, extracts data from PDF attachments using Ollama LLM, and writes the extracted data to OSIsoft PI System attributes.

## 🎯 Overview

The PI Notification POC is designed for highly secure, air-gapped environments like ADNOC where:
- Internet access is restricted
- Ollama runs as a Windows service for local LLM processing
- Python acts as middleware between Outlook, Ollama, and PI System
- All operations are logged and auditable
- Minimal dependencies for offline deployment

## 🏗️ Architecture

```
┌─────────────┐
│   Outlook   │
│   Emails    │
└──────┬──────┘
       │
       │ PDF Attachments
       ▼
┌─────────────────┐
│  Email Monitor  │ ◄── Monitors for specific subject lines
└────────┬────────┘
         │
         │ Extract PDFs
         ▼
┌─────────────────┐
│   PDF Parser    │ ◄── Extracts text from PDF files
└────────┬────────┘
         │
         │ Raw Text
         ▼
┌─────────────────┐
│ Ollama Client   │ ◄── Processes text, extracts structured data
│  (llama3.2)     │     (Tag names, values, timestamps)
└────────┬────────┘
         │
         │ Structured Data
         ▼
┌─────────────────┐
│   PI Writer     │ ◄── Writes data to PI System attributes
│  (PIconnect)    │
└─────────────────┘
```

## ✨ Features

- **Automated Email Monitoring**: Continuously monitors Outlook inbox for emails with specific subjects
- **PDF Data Extraction**: Parses PDF attachments and extracts text content
- **AI-Powered Data Processing**: Uses Ollama (local LLM) to extract structured data from unstructured text
- **PI System Integration**: Writes extracted data to OSIsoft PI System tags/attributes
- **Windows Service**: Runs as a Windows service for automatic startup and background operation
- **Offline Operation**: Designed for air-gapped environments with no internet access
- **Comprehensive Logging**: Detailed logging with rotation for troubleshooting and audit trails
- **Error Handling**: Robust error handling with retry logic and graceful degradation
- **Configurable**: YAML-based configuration for easy customization

## 📋 Requirements

### Software Requirements

- **Windows Server 2016+** or **Windows 10/11**
- **Python 3.8+**
- **Microsoft Outlook** (with configured email account)
- **Ollama** (for LLM processing)
- **OSIsoft PI SDK** (for PI System connectivity)

### Python Dependencies

See `requirements.txt` for complete list. Key dependencies:
- `pywin32` - Windows COM automation for Outlook
- `PyPDF2` - PDF text extraction
- `requests` - HTTP client for Ollama API
- `PyYAML` - Configuration file parsing
- `PIconnect` - PI System interface

## 🚀 Quick Start

### 1. Clone or Copy the Project

```cmd
git clone <repository-url>
cd pi-notification-poc
```

### 2. Install Dependencies

For online environments:
```cmd
pip install -r requirements.txt
```

For offline environments, see [OFFLINE_INSTALLATION.md](docs/OFFLINE_INSTALLATION.md).

### 3. Configure the Application

Edit `config/config.yaml`:

```yaml
email:
  target_subject: "PI Data Update"  # Email subject to monitor
  check_interval: 60                # Check every 60 seconds

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.2"

pi:
  server_name: "YOUR_PI_SERVER"     # Your PI Data Archive server
  auth_method: "windows"
```

### 4. Run the Application

Test mode (console):
```cmd
python src/main.py
```

Install as Windows service:
```cmd
python src/windows_service.py install
python src/windows_service.py start
```

## 📁 Project Structure

```
pi-notification-poc/
├── config/
│   └── config.yaml              # Main configuration file
├── src/
│   ├── main.py                  # Main application orchestrator
│   ├── email_monitor.py         # Outlook email monitoring
│   ├── pdf_parser.py            # PDF text extraction
│   ├── ollama_client.py         # Ollama LLM client
│   ├── pi_writer.py             # PI System writer
│   ├── config_loader.py         # Configuration loader
│   └── windows_service.py       # Windows service wrapper
├── docs/
│   └── OFFLINE_INSTALLATION.md  # Offline installation guide
├── logs/                        # Application logs (auto-created)
├── temp_pdfs/                   # Temporary PDF storage (auto-created)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 🔧 Configuration Guide

### Email Configuration

```yaml
email:
  target_subject: "PI Data Update"      # Subject line to match (case-insensitive)
  folder_name: "Inbox"                  # Outlook folder to monitor
  check_interval: 60                    # Check interval in seconds
  mark_as_read: true                    # Mark processed emails as read
  processed_folder: "Processed PI Updates"  # Move processed emails here
```

### PDF Configuration

```yaml
pdf:
  temp_dir: "./temp_pdfs"               # Temporary directory for PDF extraction
  max_size_mb: 50                       # Maximum PDF size in MB
  extract_images: false                 # Extract images (text-only for now)
```

### Ollama Configuration

```yaml
ollama:
  base_url: "http://localhost:11434"    # Ollama service URL
  model: "llama3.2"                     # Model to use
  timeout: 300                          # Request timeout in seconds
  temperature: 0.1                      # LLM temperature (0.0-1.0)
  system_prompt: |                      # Custom extraction prompt
    Extract tag names, values, and timestamps from the text.
    Return as JSON array.
```

### PI System Configuration

```yaml
pi:
  server_name: "YOUR_PI_SERVER"         # PI Data Archive server name
  auth_method: "windows"                # "windows" or "explicit"
  username: ""                          # For explicit auth only
  password: ""                          # For explicit auth only
  timeout: 30                           # Connection timeout
  retry_attempts: 3                     # Retry failed writes
  retry_delay: 5                        # Delay between retries
  tag_prefix: "EMAIL_"                  # Optional tag prefix
```

### Logging Configuration

```yaml
logging:
  level: "INFO"                         # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file_path: "./logs/pi_notification.log"
  max_size_mb: 10                       # Max log file size
  backup_count: 5                       # Number of backup logs
  console_output: true                  # Also log to console
```

## 🔒 Security Considerations

1. **Credentials**: Never commit credentials to version control
2. **File Permissions**: Restrict access to config files and logs
3. **Service Account**: Run service with minimal required permissions
4. **Network Security**: Use firewall rules to restrict access
5. **Audit Logging**: Regularly review logs for security events
6. **Data Validation**: All extracted data is validated before PI writes

## 📊 Usage Example

### Email Format

**Subject:** PI Data Update - Daily Report

**Attachment:** `sensor_readings.pdf`

**PDF Content:**
```
Daily Sensor Readings - 2025-12-20

Temperature Sensor A: 45.5°C
Pressure Sensor B: 120.3 PSI
Flow Rate C: 250 GPM
```

### Ollama Extraction

The system will extract:
```json
[
  {
    "tag_name": "TEMP_SENSOR_A",
    "value": 45.5,
    "unit": "°C",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "PRESSURE_SENSOR_B",
    "value": 120.3,
    "unit": "PSI",
    "timestamp": "2025-12-20T00:00:00"
  },
  {
    "tag_name": "FLOW_RATE_C",
    "value": 250,
    "unit": "GPM",
    "timestamp": "2025-12-20T00:00:00"
  }
]
```

### PI System Result

Data written to PI tags:
- `EMAIL_TEMP_SENSOR_A` = 45.5
- `EMAIL_PRESSURE_SENSOR_B` = 120.3
- `EMAIL_FLOW_RATE_C` = 250

## 🔍 Monitoring and Troubleshooting

### Check Service Status

```cmd
sc query PINotificationService
```

### View Logs

```cmd
type logs\pi_notification.log
```

### Test Components Individually

```python
# Test Outlook connection
python -c "from src.email_monitor import OutlookEmailMonitor; print('OK')"

# Test Ollama connection
curl http://localhost:11434/api/tags

# Test PI connection
python -c "import PIconnect; print('OK')"
```

### Common Issues

See [OFFLINE_INSTALLATION.md](docs/OFFLINE_INSTALLATION.md) for troubleshooting guide.

## 🛠️ Development and Testing

### Run in Debug Mode

Edit `config/config.yaml`:
```yaml
logging:
  level: "DEBUG"
  console_output: true
```

Run:
```cmd
python src/main.py
```

### Test Individual Components

```python
# Test PDF parsing
from src.pdf_parser import PDFParser
parser = PDFParser(config, logger)
text = parser.extract_text_from_pdf("test.pdf")

# Test Ollama extraction
from src.ollama_client import OllamaClient
client = OllamaClient(config, logger)
data = client.extract_data_from_text(text)

# Test PI writing (simulation mode if PI not available)
from src.pi_writer import PIWriter
writer = PIWriter(config, logger)
writer.connect()
writer.write_value("TEST_TAG", 123.45)
```

## 📦 Deployment

### For Air-Gapped Environments

1. Follow the complete [Offline Installation Guide](docs/OFFLINE_INSTALLATION.md)
2. Download all dependencies on internet-connected machine
3. Transfer packages and code to target environment
4. Install Ollama and download models offline
5. Configure and test
6. Deploy as Windows service

### Service Management

```cmd
# Install service
python src/windows_service.py install

# Start service
python src/windows_service.py start

# Stop service
python src/windows_service.py stop

# Restart service
python src/windows_service.py restart

# Uninstall service
python src/windows_service.py uninstall
```

## 📝 License

This is a proof-of-concept project for ADNOC. Please ensure compliance with your organization's policies and licenses for all components (Ollama, PI System, etc.).

## 🤝 Contributing

This is an internal POC. For modifications:
1. Test thoroughly in development environment
2. Update configuration as needed
3. Document changes in code comments
4. Update README if adding features

## 📞 Support

For issues related to:
- **PI System**: Contact your PI System administrator
- **Ollama**: See https://ollama.ai/docs
- **Application bugs**: Check logs and troubleshooting guide

## 🗺️ Roadmap

Potential enhancements:
- [ ] Support for multiple email accounts
- [ ] OCR for scanned PDFs
- [ ] Excel attachment support
- [ ] Custom extraction templates per email type
- [ ] Web dashboard for monitoring
- [ ] Email notifications on errors
- [ ] Integration with PI Asset Framework (AF)

## ⚠️ Disclaimer

This is a proof-of-concept system. Before production deployment:
- Conduct security review
- Perform load testing
- Implement backup and recovery procedures
- Establish monitoring and alerting
- Train operators on system management

---

**Version:** 1.0.0
**Last Updated:** 2025-12-20
**Environment:** Windows Server / ADNOC Secure Environment
