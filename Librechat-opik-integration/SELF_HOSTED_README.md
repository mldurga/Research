# Self-Hosted LibreChat + Opik - Quick Reference

## ✅ YES - This is 100% Self-Hosted!

**All services run on YOUR infrastructure. No external dependencies. No data leaves your servers.**

## 🏗️ What's Included

### Self-Hosted Opik Platform
- ✅ MySQL (metadata storage)
- ✅ Redis (caching layer)
- ✅ ClickHouse (analytics database)
- ✅ ZooKeeper (coordination)
- ✅ MinIO (object storage)
- ✅ Opik Backend API
- ✅ Opik Frontend UI

### Self-Hosted LibreChat
- ✅ MongoDB (conversation storage)
- ✅ RAG API (document retrieval)
- ✅ LibreChat Backend
- ✅ LibreChat Frontend

### All Data Stays Local
- ✅ LLM traces stored in your ClickHouse
- ✅ Chat history in your MongoDB
- ✅ No cloud services required
- ✅ Complete data sovereignty

## 🚀 Quick Start (Development)

```bash
cd Librechat-opik-integration

# Copy environment file
cp .env.example .env

# Edit and add your API keys
nano .env

# Start everything
docker compose --profile opik --profile librechat up -d

# Access services
# - LibreChat: http://localhost:3080
# - Opik: http://localhost:5173
```

## 🏭 Production Deployment

See **SELF_HOSTED_DEPLOYMENT.md** for complete production setup with:
- SSL/TLS certificates
- Nginx reverse proxy
- Strong password generation
- Automated backups
- Monitoring setup
- Security hardening

### Quick Production Start

```bash
# 1. Generate passwords
for i in {1..10}; do openssl rand -hex 32; done

# 2. Configure production environment
cp .env.production.example .env.production
nano .env.production  # Add generated passwords

# 3. Create data directories
sudo mkdir -p /opt/librechat-opik/{data,backups}
sudo chown -R $USER:$USER /opt/librechat-opik

# 4. Deploy production stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile opik --profile librechat up -d

# 5. Set up automated backups
chmod +x scripts/backup.sh
crontab -e
# Add: 0 2 * * * /opt/librechat-opik/scripts/backup.sh
```

## 📦 What Makes This Self-Hosted?

### Development Setup (docker-compose.yml)
- Uses Docker volumes on local machine
- No external services
- All data in local containers

### Production Setup (docker-compose.prod.yml)
- Data stored in `/opt/librechat-opik/data`
- Backups in `/opt/librechat-opik/backups`
- All databases run locally
- No cloud API calls except to LLM providers

### Network Architecture
```
Internet
    ↓ (Only LLM API calls)
Your Server
    ├── LibreChat (chat interface)
    ├── Opik (observability)
    └── All Databases (local)
        ├── MySQL
        ├── MongoDB
        ├── ClickHouse
        ├── Redis
        └── MinIO

All data flows within your infrastructure!
```

## 🔒 Data Privacy

**What stays on your server:**
- ✅ All chat conversations
- ✅ All LLM traces and telemetry
- ✅ All analytics data
- ✅ User information
- ✅ MCP tool usage logs
- ✅ Performance metrics

**What goes to external services:**
- ❌ Only LLM API calls (OpenAI, Anthropic, etc.)
- ❌ Nothing else!

## 💾 Backup & Restore

### Automated Backups
```bash
# Manual backup
./scripts/backup.sh

# Automated daily backups
0 2 * * * /opt/librechat-opik/scripts/backup.sh
```

### Restore from Backup
```bash
# List available backups
ls backups/mysql/

# Restore specific backup
./scripts/restore.sh 20250123_140530
```

## 📊 Resource Requirements

### Minimum (Small Team)
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 50GB SSD
- **Users**: 5-10 concurrent

### Recommended (Production)
- **CPU**: 8 cores
- **RAM**: 16GB
- **Storage**: 200GB SSD
- **Users**: 50-100 concurrent

### Enterprise (High Load)
- **CPU**: 16+ cores
- **RAM**: 32GB+
- **Storage**: 500GB+ SSD RAID
- **Users**: 500+ concurrent

## 🔐 Security Features

### Built-in Security
- ✅ All services on private Docker networks
- ✅ No external database access
- ✅ Password-protected databases
- ✅ JWT-based authentication
- ✅ Session management

### Production Security (in docker-compose.prod.yml)
- ✅ Resource limits per service
- ✅ SSL/TLS support
- ✅ Nginx reverse proxy
- ✅ Rate limiting
- ✅ Basic auth for Opik dashboard
- ✅ Security headers

## 📁 Configuration Files

### For Self-Hosted Setup

| File | Purpose |
|------|---------|
| `.env.example` | Development environment template |
| `.env.production.example` | Production environment template |
| `docker-compose.yml` | Base self-hosted stack |
| `docker-compose.prod.yml` | Production overrides with resource limits |
| `SELF_HOSTED_DEPLOYMENT.md` | Complete production deployment guide |
| `scripts/backup.sh` | Automated backup script |
| `scripts/restore.sh` | Restore from backup script |

## 🆘 Common Questions

### Q: Does any data go to Opik's cloud?
**A: NO.** Opik runs entirely on your server. We use Opik's Docker images, but all data stays local.

### Q: What about the LLM calls?
**A: Those go to OpenAI/Anthropic/etc.** But we capture the traces BEFORE sending and AFTER receiving, storing everything in your ClickHouse.

### Q: Can I run this on-premises?
**A: Yes!** That's exactly what this is designed for.

### Q: Can I run this on a VPS?
**A: Yes!** Any server where you can run Docker works.

### Q: Can I run this air-gapped?
**A: Almost.** You need internet for LLM API calls, but everything else is local. For true air-gap, you'd need to run local LLMs (Ollama, etc.).

### Q: What about compliance (GDPR, HIPAA)?
**A: Since all data is on your infrastructure**, you have full control. Ensure your server location and backups comply with regulations.

## 📞 Support & Documentation

- **Full Setup Guide**: `README.md`
- **Production Deployment**: `SELF_HOSTED_DEPLOYMENT.md`
- **Architecture Details**: `ARCHITECTURE.md`
- **Setup Checklist**: `CHECKLIST.md`
- **Integration Summary**: `INTEGRATION_SUMMARY.md`

## ✅ Verification

To confirm everything is self-hosted:

```bash
# 1. Check all services are running locally
docker compose ps

# 2. Verify no external connections (except LLM APIs)
docker logs librechat-backend | grep -i "opik"
# Should show: http://opik-backend:8080 (internal)

# 3. Check data is stored locally
ls -lh /opt/librechat-opik/data/
```

---

## 🎉 Summary

**You have:**
- ✅ Complete self-hosted LibreChat + Opik stack
- ✅ All observability data on your infrastructure
- ✅ Full data sovereignty and privacy
- ✅ Production-ready with backups and monitoring
- ✅ No vendor lock-in
- ✅ No external data dependencies

**Deploy with confidence knowing your data stays on YOUR servers! 🔒**
