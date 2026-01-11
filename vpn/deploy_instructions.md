# 🚀 One-Click Deployment Instructions

Choose your preferred platform and follow the instructions:

## ⚡ Render.com (EASIEST - 2 Minutes)

### Option 1: Deploy Button (Instant)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Click the button above
2. Sign in with GitHub
3. Click "Create Web Service"
4. Done! Access at: `https://vpn-server.onrender.com`

### Option 2: Manual Deploy (3 Minutes)

1. Go to https://render.com
2. Sign up (free, use GitHub)
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Settings:
   - **Name:** vpn-server
   - **Root Directory:** `vpn`
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python vpn_web_server.py`
6. Click "Create Web Service"
7. Wait 2-3 minutes for deployment
8. Access at your Render URL

**Your URL:** `https://[your-service-name].onrender.com`

---

## 🚂 Railway.app (Fast & Reliable)

### Deploy via CLI:

```bash
# 1. Install Railway CLI
npm i -g @railway/cli
# or
curl -fsSL https://railway.app/install.sh | sh

# 2. Login
railway login

# 3. Deploy
cd vpn
railway init
railway up

# 4. Add domain
railway domain
```

### Deploy via Dashboard:

1. Go to https://railway.app
2. Sign up with GitHub
3. "New Project" → "Deploy from GitHub repo"
4. Select your repository → `vpn` folder
5. Railway auto-detects Python
6. Click "Deploy"
7. Generate domain in settings

**Your URL:** `https://[your-project].up.railway.app`

---

## 🐍 PythonAnywhere (Always-On Free)

1. Sign up: https://www.pythonanywhere.com/registration/register/beginner/

2. Open Bash console:
```bash
git clone https://github.com/[your-username]/Research.git
cd Research/vpn
pip3 install --user -r requirements.txt
```

3. Go to "Web" tab → "Add a new web app"

4. Choose "Manual configuration" → Python 3.10

5. Set Source code: `/home/[yourusername]/Research/vpn`

6. Edit WSGI file (`/var/www/[yourusername]_pythonanywhere_com_wsgi.py`):
```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/[yourusername]/Research/vpn'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import Flask app
from vpn_web_server import app as application
```

7. Reload web app

**Your URL:** `https://[yourusername].pythonanywhere.com`

---

## ☁️ Oracle Cloud (Best Free VM - 24GB RAM!)

### Quick Setup Script:

```bash
# 1. Create account: https://oracle.com/cloud/free
# 2. Create Ubuntu 22.04 instance (Always Free - ARM recommended)
# 3. SSH into instance
# 4. Run this:

sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/[your-username]/Research.git
cd Research/vpn
pip3 install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/vpn-web.service > /dev/null <<EOF
[Unit]
Description=VPN Web Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=/usr/bin/python3 vpn_web_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable vpn-web
sudo systemctl start vpn-web

# Open firewall
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT
sudo netfilter-persistent save

echo "Done! Access at: http://$(curl -s ifconfig.me):5000"
```

**Your URL:** `http://[your-instance-ip]:5000`

---

## 🌐 Fly.io (Global CDN)

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Login
flyctl auth login

# 3. Deploy
cd vpn
flyctl launch --name vpn-server
flyctl deploy

# 4. Open
flyctl open
```

**Your URL:** `https://vpn-server.fly.dev`

---

## 🎯 Google Cloud Platform (GCP)

### Quick Setup:

```bash
# 1. Create account: https://cloud.google.com/free
# 2. Create project
# 3. Enable Compute Engine API
# 4. Create VM (e2-micro in us-central1, us-west1, or us-east1 for free tier)

# Via gcloud CLI:
gcloud compute instances create vpn-server \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=http-server

# SSH and setup
gcloud compute ssh vpn-server --zone=us-central1-a

# On VM:
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/[your-username]/Research.git
cd Research/vpn
pip3 install -r requirements.txt
nohup python3 vpn_web_server.py > vpn.log 2>&1 &

# Create firewall rule
gcloud compute firewall-rules create allow-vpn-server \
  --allow=tcp:5000 \
  --target-tags=http-server

# Get external IP
gcloud compute instances describe vpn-server --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

**Your URL:** `http://[external-ip]:5000`

---

## 📦 DigitalOcean ($200 Free Credit)

```bash
# 1. Sign up with referral: https://m.do.co/c/[referral] ($200 credit)
# 2. Create Droplet:
#    - Ubuntu 22.04
#    - Basic: $6/month
#    - Choose region
# 3. SSH into droplet

ssh root@[droplet-ip]

# Setup script:
apt update && apt install -y python3 python3-pip git
git clone https://github.com/[your-username]/Research.git
cd Research/vpn
pip3 install -r requirements.txt

# Create systemd service (same as Oracle example)
cat > /etc/systemd/system/vpn-web.service <<EOF
[Unit]
Description=VPN Web Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Research/vpn
ExecStart=/usr/bin/python3 vpn_web_server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl enable vpn-web
systemctl start vpn-web

# Check status
systemctl status vpn-web
```

**Your URL:** `http://[droplet-ip]:5000`

---

## 🔍 Verify Deployment

Test your deployment:

```bash
# Test the API
curl https://your-deployed-url/health

# Expected response:
{"status":"ok","servers_cached":0}

# Test from iPhone Safari:
# Go to: https://your-deployed-url
# You should see the VPN server interface
```

---

## 🎨 Custom Domain (Optional)

### Free Custom Domain with Cloudflare:

1. Get free domain from Freenom.com or use existing
2. Add to Cloudflare (free plan)
3. Point A record to your server IP
4. Enable Cloudflare proxy (free SSL)

Result: `https://vpn.yourdomain.com`

---

## 🔧 Troubleshooting

### "Application failed to start"
- Check logs in platform dashboard
- Verify `requirements.txt` has Flask
- Check Python version compatibility

### "502 Bad Gateway"
- Server might be starting (wait 30 seconds)
- Check if port is correct (5000)
- Verify firewall allows traffic

### "Cannot fetch servers"
- VPN Gate API might be slow
- Wait and refresh
- Check internet connectivity on server

### Platform sleeping (Render free tier)
- Normal behavior after 15 minutes
- Wakes automatically on request
- First request takes ~30 seconds

---

## 📊 Which Platform Should I Choose?

| Your Need | Platform | Why |
|-----------|----------|-----|
| Easiest deployment | Render | One-click, no config |
| Best free specs | Oracle Cloud | 24GB RAM free! |
| No credit card | Render/PythonAnywhere | Truly free signup |
| Long-term free | Oracle/GCP Always Free | Forever free tier |
| Best performance | Railway/Fly.io | No sleep, fast |
| Learning cloud | AWS/GCP | Industry standard |

---

## 🎉 Success!

Once deployed, your iPhone setup is:

1. **Open Safari** on iPhone
2. **Go to:** `https://your-deployed-url`
3. **Download** VPN config
4. **Open** in OpenVPN Connect
5. **Connect!** ✅

---

**Need help?** See [FREE_HOSTING.md](FREE_HOSTING.md) for detailed comparison of all options.
