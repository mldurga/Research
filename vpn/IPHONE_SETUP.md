# 📱 iPhone VPN Setup Guide

Complete guide to using FREE VPN servers on your iPhone using VPN Gate.

## 🎯 Overview

Since iPhone doesn't allow running Python scripts directly, we use a **web interface** approach:

1. **Web Server** runs on your computer (or cloud server)
2. **iPhone Safari** accesses the web interface
3. **Download VPN configs** (.ovpn files)
4. **OpenVPN Connect app** connects to VPN

## ✅ What You Need

### On iPhone:
- ✅ **OpenVPN Connect** app (FREE from App Store)
- ✅ Safari browser (built-in)
- ✅ WiFi connection (same network as computer, or internet for cloud server)

### On Computer/Server:
- ✅ Python 3.7+
- ✅ Flask and Flask-CORS (installed automatically)
- ✅ Internet connection

## 📥 Step 1: Install OpenVPN Connect on iPhone

1. Open **App Store** on your iPhone
2. Search for **"OpenVPN Connect"**
3. Install the app by OpenVPN Inc. (FREE)
4. Open the app to verify it works

**Download Link**: [OpenVPN Connect on App Store](https://apps.apple.com/app/openvpn-connect/id590379981)

## 💻 Step 2: Set Up Web Server

### Option A: Local Computer (Same WiFi)

**On your Linux/Mac/Windows computer:**

```bash
cd vpn

# Install Python dependencies
pip install -r requirements.txt

# Start the web server
python3 vpn_web_server.py
```

The server will display:
```
VPN Web Server for iPhone/Mobile
======================================================================

Server running on: http://0.0.0.0:5000

Access from iPhone:
1. Connect iPhone to same WiFi network
2. Find your computer's IP address
3. Open Safari on iPhone and go to:
   http://YOUR_COMPUTER_IP:5000

Example: http://192.168.1.100:5000
```

**Find Your Computer's IP Address:**

```bash
# Linux/Mac
hostname -I
# or
ifconfig | grep "inet "

# Windows (Command Prompt)
ipconfig
```

Look for an IP like `192.168.1.100` or `10.0.0.50`

### Option B: Cloud Server (Access from Anywhere)

**Deploy on AWS/GCP/DigitalOcean/etc:**

```bash
# SSH into your server
ssh user@your-server.com

# Clone your repo
git clone https://github.com/mldurga/Research.git
cd Research/vpn

# Install dependencies
pip3 install -r requirements.txt

# Run server (publicly accessible)
python3 vpn_web_server.py

# Or use nohup to keep running after logout
nohup python3 vpn_web_server.py > vpn.log 2>&1 &
```

**Important**: Make sure port 5000 is open in your firewall:
```bash
# Ubuntu/Debian
sudo ufw allow 5000

# CentOS/RHEL
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

## 📱 Step 3: Access Web Interface on iPhone

1. **Open Safari** on your iPhone

2. **Enter the URL**:
   - Local: `http://192.168.1.100:5000` (replace with your IP)
   - Cloud: `http://your-server.com:5000`

3. You'll see a **mobile-friendly interface** with:
   - List of free VPN servers
   - Country filter
   - Speed filter
   - Download buttons

## 🌍 Step 4: Download VPN Configuration

1. **Browse available servers** in the list
   - Servers are sorted by speed/score
   - Each shows: Country, Speed, Ping, Score

2. **Select a server** (recommend fastest or nearest country)

3. **Tap "📥 Download Config"** button

4. Safari will download a `.ovpn` file

5. **Tap the downloaded file** in Safari's download list

6. **Choose "OpenVPN"** when prompted "Open in..."

## 🔌 Step 5: Connect to VPN

1. OpenVPN Connect app will **open automatically**

2. You'll see the VPN configuration

3. **Tap "ADD"** to add the profile

4. Review the profile details

5. **Tap the toggle switch** to connect

6. **Allow VPN configuration** when iOS prompts
   - You may need to enter your iPhone passcode
   - Tap "Allow" to add VPN configuration

7. **Wait for connection** (usually 5-10 seconds)

8. ✅ **You're connected!**
   - VPN icon appears in status bar
   - All traffic now goes through VPN

## 🎛️ Step 6: Verify Connection

### Check Your IP Address:

1. Open **Safari** on iPhone
2. Go to: https://whatismyipaddress.com/
3. Your IP should show the **VPN server's country**

### Alternative IP Check Sites:
- https://www.whatismyip.com/
- https://ipinfo.io/
- https://api.ipify.org/

## 🔄 Step 7: Switch VPN Locations

To switch to a different location:

1. **Disconnect** in OpenVPN Connect app
2. **Go back to Safari** web interface
3. **Download config** for new location
4. **Open in OpenVPN Connect**
5. **Connect** to new location

## ⚙️ Advanced Options

### Filter by Country

In the web interface:
1. Tap **"Filter by Country"** dropdown
2. Select desired country (e.g., Japan, United States)
3. Tap **"🔄 Refresh Servers"**
4. Only servers from that country will show

### Minimum Speed Filter

1. Change **"Minimum Speed (Mbps)"** value
2. Tap **"🔄 Refresh Servers"**
3. Only faster servers will show

### Save Multiple Profiles

You can save multiple VPN profiles:
1. Download configs for different countries
2. Each opens as separate profile in OpenVPN Connect
3. Switch between them easily in the app

## 🔧 Troubleshooting

### "Cannot Connect to Server" in Safari

**Problem**: Safari can't reach the web server

**Solutions**:
- ✅ Check iPhone is on same WiFi network (for local server)
- ✅ Verify computer's IP address is correct
- ✅ Make sure web server is running on computer
- ✅ Check firewall isn't blocking port 5000
- ✅ Try `http://` not `https://`

### "No Servers Found"

**Problem**: Server list is empty

**Solutions**:
- ✅ Check internet connection on computer running server
- ✅ Wait a moment and tap "🔄 Refresh Servers"
- ✅ Lower the minimum speed filter
- ✅ Clear country filter (select "All Countries")
- ✅ Check server logs for errors

### VPN Won't Connect in OpenVPN App

**Problem**: Connection fails in OpenVPN Connect

**Solutions**:
- ✅ Download a different server config (some servers may be offline)
- ✅ Try servers from different countries
- ✅ Check iPhone has internet connection
- ✅ Make sure OpenVPN Connect app is up to date
- ✅ Restart OpenVPN Connect app
- ✅ Try downloading config again

### VPN Connects But No Internet

**Problem**: VPN connected but websites don't load

**Solutions**:
- ✅ Disconnect and try a different server
- ✅ Some free servers may be overloaded
- ✅ Switch to a server with higher speed rating
- ✅ Check if DNS is working (try 8.8.8.8)

### Download Button Doesn't Work

**Problem**: Tapping download does nothing

**Solutions**:
- ✅ Wait for page to fully load
- ✅ Refresh the page in Safari
- ✅ Clear Safari cache: Settings > Safari > Clear History
- ✅ Try a different server
- ✅ Restart Safari app

## 📊 Recommended Servers by Use Case

### For Speed (Streaming/Downloads):
- Look for **>20 Mbps** speed
- Low ping (<50ms)
- High score (>10000)
- Countries: Japan, South Korea, United States

### For Privacy:
- Countries with strong privacy laws
- Examples: Switzerland, Iceland, Netherlands

### For Gaming:
- **Lowest ping** (<30ms)
- Nearest country to your location
- Stable connection (high score)

### For Bypassing Geo-Restrictions:
- Select country where content is available
- Example: US servers for US content, UK for BBC, etc.

## 🌐 Using VPN on Multiple Devices

You can use the **same web server** for multiple iPhones/iPads:

1. Keep web server running on computer
2. Connect all devices to same WiFi
3. Access the web interface from each device
4. Download configs on each device

## 🔒 Security & Privacy Notes

### Important Information:

1. **VPN Gate is FREE but PUBLIC**
   - Run by volunteers
   - Traffic may be logged for 3 months
   - Not suitable for highly sensitive data

2. **Good For**:
   - ✅ Bypassing geo-restrictions
   - ✅ Privacy from ISP
   - ✅ Public WiFi protection
   - ✅ General browsing privacy

3. **NOT Recommended For**:
   - ❌ Banking/financial transactions
   - ❌ Illegal activities
   - ❌ Highly sensitive communications
   - ❌ Work/corporate VPN replacement

4. **DNS Leaks**:
   - Free VPNs may have DNS leaks
   - Test at: https://dnsleaktest.com/

## 🚀 Running Server 24/7

### Keep Server Running on Computer:

**Linux/Mac (using screen or tmux):**
```bash
# Install screen
sudo apt-get install screen  # Ubuntu/Debian
brew install screen          # macOS

# Start screen session
screen -S vpn-server

# Run server
python3 vpn_web_server.py

# Detach: Press Ctrl+A then D
# Reattach: screen -r vpn-server
```

**Using systemd (Linux):**
```bash
# Create service file
sudo nano /etc/systemd/system/vpn-web.service

# Add:
[Unit]
Description=VPN Web Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Research/vpn
ExecStart=/usr/bin/python3 vpn_web_server.py
Restart=always

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable vpn-web
sudo systemctl start vpn-web
```

### Cloud Server (Always Online):

Deploy to:
- **DigitalOcean** ($6/month droplet)
- **AWS EC2** (free tier available)
- **Google Cloud** (free tier available)
- **Heroku** (free tier available)
- **Render** (free tier available)

## 📞 Quick Reference

### URLs to Remember:

- **App Store**: OpenVPN Connect
- **IP Check**: https://whatismyipaddress.com/
- **DNS Leak Test**: https://dnsleaktest.com/
- **VPN Gate Info**: https://www.vpngate.net/

### Key Commands:

```bash
# Start server
python3 vpn_web_server.py

# Install dependencies
pip install -r requirements.txt

# Find computer IP
hostname -I

# Stop server
Press Ctrl+C
```

## 🎉 Success!

You now have **FREE VPN** working on your iPhone!

**Next Steps**:
1. Test different servers to find fastest
2. Save multiple country profiles
3. Keep web server running for easy access
4. Share with friends/family on same network

---

**Need Help?**
- Check troubleshooting section above
- Review the main README.md
- VPN Gate documentation: https://www.vpngate.net/en/

**Version**: 1.0 for iPhone
**Last Updated**: 2026-01-11
