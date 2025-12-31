# WiFi Network and Port Scanner

A Python-based network scanner to discover active hosts and open ports on your local WiFi network.

## ⚠️ Important Warning

**Only use this tool on networks you own or have explicit permission to scan.** Unauthorized network scanning may be illegal and unethical.

## Features

- **Auto-detect local network**: Automatically identifies your network range
- **Host discovery**: Pings all hosts in the network to find active devices
- **Port scanning**: Scans common or specified ports on active hosts
- **Service detection**: Identifies services running on open ports
- **Concurrent scanning**: Uses multi-threading for fast scanning
- **Hostname resolution**: Attempts to resolve hostnames for discovered IPs

## Requirements

```bash
python3 (3.6+)
```

No external dependencies required - uses only Python standard library.

## Usage

### Basic Usage (Auto-detect network, scan common ports)

```bash
python3 wifi_network_scanner.py
```

### Scan Specific Network

```bash
python3 wifi_network_scanner.py -n 192.168.1.0/24
```

### Ping Only (No Port Scanning)

```bash
python3 wifi_network_scanner.py --ping-only
```

### Scan Specific Ports

```bash
python3 wifi_network_scanner.py -p 22,80,443,8080
```

### Scan All Ports (1-1024)

```bash
python3 wifi_network_scanner.py --all-ports
```

### Adjust Timeout

```bash
python3 wifi_network_scanner.py --timeout 1.0
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `-n, --network` | Network to scan (e.g., 192.168.1.0/24) |
| `-p, --ports` | Comma-separated ports to scan (e.g., 22,80,443) |
| `--all-ports` | Scan all ports 1-1024 |
| `--ping-only` | Only discover hosts, skip port scanning |
| `--timeout` | Port scan timeout in seconds (default: 0.5) |

## Default Common Ports Scanned

- 21 (FTP)
- 22 (SSH)
- 23 (Telnet)
- 25 (SMTP)
- 53 (DNS)
- 80 (HTTP)
- 110 (POP3)
- 143 (IMAP)
- 443 (HTTPS)
- 445 (SMB)
- 3306 (MySQL)
- 3389 (RDP)
- 5432 (PostgreSQL)
- 5900 (VNC)
- 8080 (HTTP-Alt)
- 8443 (HTTPS-Alt)
- 9200 (Elasticsearch)
- 27017 (MongoDB)

## Example Output

```
======================================================================
WiFi Network and Port Scanner
======================================================================

WARNING: Only use this tool on networks you own or have permission to scan!

[*] Detected local network: 192.168.1.0/24
[*] Your IP: 192.168.1.100
[*] Scanning common ports: [21, 22, 80, 443, ...]

[*] Scanning network: 192.168.1.0/24
[*] Total hosts to check: 254

[*] Phase 1: Discovering active hosts...
  [+] Found active host: 192.168.1.1
  [+] Found active host: 192.168.1.50
  [+] Found active host: 192.168.1.100

[*] Found 3 active hosts

[*] Phase 2: Scanning ports on active hosts...

[*] Scanning 192.168.1.1...
  [+] Found 2 open ports on 192.168.1.1
      Port 80 (http)
      Port 443 (https)

======================================================================
SCAN RESULTS
======================================================================

[+] Host: 192.168.1.1 (router.local)
    Pingable: Yes
    Open Ports:
      -    80/tcp  http
      -   443/tcp  https

[+] Host: 192.168.1.50 (desktop.local)
    Pingable: Yes
    Open Ports:
      -    22/tcp  ssh

[*] Scan completed in 45.23 seconds
[*] Total hosts scanned: 3
======================================================================
```

## How It Works

1. **Network Detection**: Detects your local IP and assumes a /24 subnet
2. **Host Discovery**: Uses ICMP ping to find active hosts
3. **Port Scanning**: Uses TCP connect scans to test ports
4. **Service Identification**: Uses socket.getservbyport() to identify services
5. **Results**: Displays all active hosts and their open ports

## Performance Tips

- Use `--ping-only` for quick host discovery
- Reduce timeout for faster scanning: `--timeout 0.3`
- Scan specific ports instead of all ports for speed
- The scanner uses concurrent threading for optimal performance

## Security Considerations

- This tool performs TCP connect scans (full connection)
- All scans are logged by target systems
- Use responsibly and only on authorized networks
- Consider firewall rules that may block scans

## Troubleshooting

**"Could not detect network"**
- Manually specify network with `-n 192.168.1.0/24`

**"Permission denied" errors**
- ICMP ping may require elevated privileges on some systems
- Try running with sudo: `sudo python3 wifi_network_scanner.py`

**Slow scanning**
- Reduce timeout: `--timeout 0.3`
- Scan fewer ports: `-p 22,80,443`
- Use ping-only mode first to find active hosts

## License

This tool is for educational and authorized security testing purposes only.
