# Quick Start Guide - Production VPN Client

Connect to **FREE VPN servers worldwide** using VPN Gate network.

## ⚡ Quick Start (3 Steps)

### 1. Install OpenVPN

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y openvpn curl

# CentOS/RHEL/Fedora
sudo yum install -y openvpn curl

# Or use the install script
cd vpn
sudo bash install.sh
```

### 2. List Available Servers

```bash
sudo python3 vpn_prod.py list
```

You'll see something like:

```
Available Free VPN Servers
======================================================================

[1] VPNGate Japan
    Country: Japan
    Server: 219.100.37.123
    Speed: 45.2 Mbps | Ping: 12ms | Score: 14523

[2] VPNGate United States
    Country: United States
    Server: 73.198.211.45
    Speed: 38.7 Mbps | Ping: 45ms | Score: 12389

[3] VPNGate South Korea
    Country: South Korea
    Server: 211.234.118.92
    Speed: 33.1 Mbps | Ping: 8ms | Score: 11242
...
```

### 3. Connect!

```bash
# Connect to server #1 (fastest)
sudo python3 vpn_prod.py connect 1

# Or connect to a specific country
sudo python3 vpn_prod.py country Japan
```

## 📋 All Commands

```bash
# List available servers
sudo python3 vpn_prod.py list

# Connect to server (by number from list)
sudo python3 vpn_prod.py connect 1

# Connect to specific country
sudo python3 vpn_prod.py country Japan
sudo python3 vpn_prod.py country "United States"
sudo python3 vpn_prod.py country "South Korea"

# Check connection status
sudo python3 vpn_prod.py status

# Disconnect
sudo python3 vpn_prod.py disconnect
```

## 🌍 Available Countries

VPN Gate provides servers in 60+ countries including:
- Japan
- United States
- South Korea
- United Kingdom
- Germany
- Canada
- Australia
- France
- Netherlands
- Singapore
- And many more!

## ⚙️ Options

```bash
# Filter by minimum speed (default: 5 Mbps)
sudo python3 vpn_prod.py list --speed 10

# Limit number of servers (default: 30)
sudo python3 vpn_prod.py list --max 50

# Combine options
sudo python3 vpn_prod.py connect 1 --speed 20 --max 10
```

## ✅ Requirements

- **Linux/macOS** with root access
- **Python 3.7+** (usually pre-installed)
- **OpenVPN** client (installed via install.sh)
- **Internet connection**

## ❌ Limitations (GitHub Actions/Codespaces)

**CANNOT run in:**
- ❌ GitHub Actions - No root access, network restrictions
- ❌ GitHub Codespaces - No root access for VPN
- ❌ Docker without `--privileged` flag

**CAN run on:**
- ✅ Local Linux machine with sudo
- ✅ Local macOS with sudo
- ✅ AWS/GCP/Azure VM with root access
- ✅ Docker with `--privileged --cap-add=NET_ADMIN`
- ✅ VirtualBox/VMware VM with root access

## 🔐 Security Notes

- VPN Gate is run by volunteers - don't use for highly sensitive data
- Servers are free and public - expect logging
- Good for: Bypassing geo-restrictions, privacy from ISP, general browsing
- Not for: Banking, highly sensitive communications

## 🐛 Troubleshooting

### "OpenVPN is not installed"
```bash
sudo apt-get install openvpn
```

### "Root privileges required"
Always use `sudo`:
```bash
sudo python3 vpn_prod.py connect 1
```

### "No servers available"
Check internet connection or try again later

### Connection fails
Try a different server:
```bash
sudo python3 vpn_prod.py connect 2
```

### Check if VPN is working
```bash
# Check your IP before connecting
curl https://api.ipify.org

# Connect to VPN
sudo python3 vpn_prod.py connect 1

# Check your IP after connecting (should be different)
curl https://api.ipify.org
```

## 📚 More Info

- **VPN Gate Website**: https://www.vpngate.net/
- **Academic Project**: University of Tsukuba, Japan
- **Protocol**: OpenVPN (UDP/TCP)
- **Cost**: Completely FREE
- **Servers**: 6000+ active volunteers worldwide

## 🎯 Example Session

```bash
# Install (one time)
$ sudo bash install.sh

# List servers
$ sudo python3 vpn_prod.py list
Fetching free VPN servers from VPN Gate...
Found 30 VPN servers

[1] VPNGate Japan
    Speed: 45.2 Mbps | Ping: 12ms
[2] VPNGate United States
    Speed: 38.7 Mbps | Ping: 45ms
...

# Connect to Japan
$ sudo python3 vpn_prod.py connect 1
Connecting to: VPNGate Japan (Japan)
Current IP: 98.234.112.45
Starting OpenVPN...
✓ VPN CONNECTION ESTABLISHED!
New IP: 219.100.37.123
✓ IP address changed successfully!

# Check status
$ sudo python3 vpn_prod.py status
Status: CONNECTED
Location: VPNGate Japan
Connected for: 2m 15s
Current IP: 219.100.37.123

# Disconnect
$ sudo python3 vpn_prod.py disconnect
✓ VPN DISCONNECTED
```

---

**Ready to start? Run:**
```bash
cd vpn
sudo python3 vpn_prod.py list
```
