# Self-Hosted Production Deployment Guide

## 📋 Overview

This guide covers deploying LibreChat + Opik in a **fully self-hosted production environment**. All services run on your infrastructure with no external dependencies.

## 🏗️ Architecture

```
Your Infrastructure
├── LibreChat (Chat UI)
├── Opik Platform (Observability)
│   ├── MySQL (metadata)
│   ├── Redis (cache)
│   ├── ClickHouse (analytics)
│   ├── ZooKeeper (coordination)
│   └── MinIO (object storage)
└── (Optional) Nginx (reverse proxy + SSL)
```

**Key Point**: Everything runs locally. No data leaves your infrastructure.

## 🔧 Prerequisites

### Hardware Requirements

**Minimum (Development/Small Team)**:
- CPU: 4 cores
- RAM: 8GB
- Storage: 50GB SSD
- Network: 100Mbps

**Recommended (Production)**:
- CPU: 8+ cores
- RAM: 16GB+
- Storage: 200GB+ SSD (NVMe preferred)
- Network: 1Gbps

**High-Load (Enterprise)**:
- CPU: 16+ cores
- RAM: 32GB+
- Storage: 500GB+ SSD RAID
- Network: 10Gbps

### Software Requirements

- **OS**: Ubuntu 22.04 LTS (recommended) or RHEL/CentOS 8+
- **Docker**: 24.0+ with Compose V2
- **Firewall**: Ports 80, 443 accessible
- **SSL Certificates**: Let's Encrypt or commercial CA

## 📦 Installation Steps

### 1. Prepare the Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose V2
sudo apt install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### 2. Create Directory Structure

```bash
# Create application directory
sudo mkdir -p /opt/librechat-opik
cd /opt/librechat-opik

# Clone the integration
git clone <your-repo> .

# Create data directories
sudo mkdir -p data/{opik-mysql,opik-redis,opik-clickhouse,opik-zookeeper,opik-minio,librechat-mongodb}
sudo mkdir -p backups/{mysql,mongodb,clickhouse,redis,configs}
sudo mkdir -p logs ssl nginx

# Set ownership
sudo chown -R $USER:$USER /opt/librechat-opik

# Set permissions
chmod 700 data backups
chmod 755 logs
```

### 3. Generate Strong Passwords

```bash
# Generate 10 random passwords
echo "Copy these passwords to .env.production:"
echo ""
for i in {1..10}; do
    echo "Password $i: $(openssl rand -hex 32)"
done
echo ""

# Generate JWT secrets (64 chars)
echo "JWT Secrets:"
for i in {1..3}; do
    echo "Secret $i: $(openssl rand -hex 64)"
done
```

### 4. Configure Environment

```bash
# Copy production environment template
cp .env.production.example .env.production

# Edit with generated passwords
nano .env.production
```

**Required Changes in `.env.production`**:

1. Replace all `CHANGE_ME` values with generated passwords
2. Set `DATA_PATH=/opt/librechat-opik/data`
3. Set `BACKUP_PATH=/opt/librechat-opik/backups`
4. Add your LLM API keys
5. (Optional) Configure domain names for `ALLOWED_ORIGINS`

**Security Checklist**:
- [ ] All passwords are unique and strong (32+ chars)
- [ ] JWT secrets are 64+ characters
- [ ] No default/example passwords remain
- [ ] `.env.production` has permissions 600

```bash
chmod 600 .env.production
```

### 5. Initialize Databases

```bash
# Start database services first
docker compose --profile opik up -d opik-mysql opik-redis opik-clickhouse opik-zookeeper opik-minio librechat-mongodb

# Wait for initialization (2-3 minutes)
echo "Waiting for databases to initialize..."
sleep 120

# Verify databases are healthy
docker compose ps
```

All services should show "healthy" status.

### 6. Deploy Application Services

```bash
# Start Opik application
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile opik up -d

# Wait for Opik to be ready
echo "Waiting for Opik to start..."
sleep 30

# Verify Opik health
curl http://localhost:8080/health
# Should return: {"status": "ok"}

# Start LibreChat
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile librechat up -d

# Verify LibreChat health
curl http://localhost:3080/api/health
```

### 7. Configure SSL/TLS (Production)

#### Option A: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot

# Generate certificates
sudo certbot certonly --standalone \
    -d chat.yourdomain.com \
    -d opik.yourdomain.com \
    --agree-tos \
    --email admin@yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/chat.yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/chat.yourdomain.com/privkey.pem ssl/
sudo chown $USER:$USER ssl/*.pem

# Set up auto-renewal
sudo certbot renew --dry-run
```

#### Option B: Self-Signed (Development Only)

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/privkey.pem \
    -out ssl/fullchain.pem \
    -subj "/CN=localhost"
```

### 8. Configure Nginx Reverse Proxy

```bash
# Create nginx configuration
cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=librechat:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=opik:10m rate=20r/s;

    # LibreChat
    server {
        listen 80;
        server_name chat.yourdomain.com;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name chat.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        location / {
            limit_req zone=librechat burst=20 nodelay;

            proxy_pass http://librechat-backend:3080;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 300s;
        }
    }

    # Opik Dashboard
    server {
        listen 80;
        server_name opik.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name opik.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Basic auth for additional security
        auth_basic "Opik Dashboard";
        auth_basic_user_file /etc/nginx/htpasswd;

        location / {
            limit_req zone=opik burst=50 nodelay;

            proxy_pass http://opik-frontend:5173;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
        }

        location /api {
            proxy_pass http://opik-backend:8080;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF

# Create htpasswd for Opik dashboard
sudo apt install apache2-utils
htpasswd -c nginx/htpasswd admin
# Enter password when prompted

# Start nginx
docker compose --profile production up -d nginx
```

### 9. Set Up Automated Backups

```bash
# Make backup script executable
chmod +x scripts/backup.sh

# Test backup
./scripts/backup.sh

# Set up cron job for daily backups at 2 AM
crontab -e
```

Add this line:
```cron
0 2 * * * cd /opt/librechat-opik && ./scripts/backup.sh >> logs/backup.log 2>&1
```

### 10. Configure Monitoring (Optional)

```bash
# Install monitoring tools
sudo apt install prometheus grafana

# Configure Prometheus to scrape Opik metrics
cat > /etc/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'opik-backend'
    static_configs:
      - targets: ['localhost:8080']

  - job_name: 'librechat-backend'
    static_configs:
      - targets: ['localhost:3080']
EOF

# Restart Prometheus
sudo systemctl restart prometheus
```

## 🔒 Security Hardening

### 1. Firewall Configuration

```bash
# Install UFW
sudo apt install ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

### 2. Docker Security

```bash
# Run Docker in rootless mode (optional but recommended)
dockerd-rootless-setuptool.sh install

# Set resource limits in docker-compose.prod.yml (already configured)
```

### 3. Network Isolation

All services communicate via internal Docker networks. No direct external access to databases.

### 4. Secrets Management

```bash
# Never commit .env.production
echo ".env.production" >> .gitignore

# Use Docker secrets (advanced)
# See: https://docs.docker.com/engine/swarm/secrets/
```

## 📊 Monitoring & Maintenance

### Health Checks

```bash
# Check all services
docker compose ps

# Check logs
docker compose logs -f

# Check specific service
docker logs -f librechat-backend

# Check resource usage
docker stats
```

### Performance Monitoring

Access Opik dashboard at `https://opik.yourdomain.com` to monitor:
- LLM token usage and costs
- Request latency and error rates
- Database query performance
- MCP tool usage

### Log Management

```bash
# View aggregated logs
docker compose logs --since 1h

# Export logs
docker compose logs > logs/app-$(date +%Y%m%d).log

# Configure log rotation in /etc/logrotate.d/
```

## 🔄 Updates & Maintenance

### Updating Opik

```bash
# Backup first!
./scripts/backup.sh

# Pull latest images
docker compose pull

# Restart with new images
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile opik --profile librechat up -d

# Verify update
curl http://localhost:8080/health
```

### Updating LibreChat

```bash
# Backup
./scripts/backup.sh

# Update code
cd librechat
git pull
npm install

# Rebuild images
docker compose -f ../docker-compose.yml -f ../docker-compose.prod.yml build librechat-backend librechat-frontend

# Restart
docker compose -f ../docker-compose.yml -f ../docker-compose.prod.yml restart librechat-backend librechat-frontend
```

### Database Maintenance

```bash
# Optimize MySQL
docker exec opik-mysql mysqlcheck -u root -p"${MYSQL_ROOT_PASSWORD}" --optimize --all-databases

# Optimize MongoDB
docker exec librechat-mongodb mongosh admin -u admin -p "${MONGO_ROOT_PASSWORD}" --eval "db.runCommand({compact: 'collection_name'})"

# Optimize ClickHouse
docker exec opik-clickhouse clickhouse-client --query="OPTIMIZE TABLE opik.traces"
```

## 🐛 Troubleshooting

### Services Not Starting

```bash
# Check docker logs
docker compose logs

# Check disk space
df -h

# Check memory
free -h

# Restart all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile opik --profile librechat restart
```

### High Memory Usage

```bash
# Check per-service memory
docker stats --no-stream

# If ClickHouse is using too much memory, reduce in docker-compose.prod.yml:
# max_server_memory_usage_to_ram_ratio=0.6
```

### Database Connection Errors

```bash
# Verify databases are healthy
docker compose ps

# Check database logs
docker logs opik-mysql
docker logs librechat-mongodb

# Restart database
docker compose restart opik-mysql
```

## 📈 Scaling for High Load

### Horizontal Scaling

For high-traffic deployments:

1. **Load Balancer**: Add nginx upstream with multiple LibreChat backends
2. **Database Clustering**:
   - MySQL: Use Galera cluster
   - MongoDB: Use replica sets
   - ClickHouse: Use distributed tables
3. **Redis Clustering**: Use Redis Cluster mode

### Vertical Scaling

Increase resources in `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 16G
```

## 📚 Additional Resources

- [Docker Production Guide](https://docs.docker.com/config/containers/resource_constraints/)
- [ClickHouse Performance](https://clickhouse.com/docs/en/operations/performance/)
- [MongoDB Production Notes](https://docs.mongodb.com/manual/administration/production-notes/)
- [Nginx Best Practices](https://nginx.org/en/docs/)

## ✅ Production Checklist

- [ ] All passwords changed from defaults
- [ ] SSL/TLS certificates configured
- [ ] Firewall enabled and configured
- [ ] Automated backups set up
- [ ] Backup restoration tested
- [ ] Monitoring configured
- [ ] Log rotation configured
- [ ] Domain names configured
- [ ] Rate limiting enabled
- [ ] Health checks passing
- [ ] Documentation updated for your environment

---

**Your data never leaves your infrastructure. Everything is self-hosted and under your control.**
