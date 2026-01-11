# VPN Client with Location Switching

A comprehensive Python-based VPN client that supports multiple VPN locations with easy switching capabilities. This implementation provides both a flexible framework for development and a **production-ready client** that connects to **FREE VPN servers worldwide** via VPN Gate.

## 🚀 Quick Start - Production VPN (FREE Servers)

**Want to connect to real FREE VPN servers right now?** See [QUICKSTART.md](QUICKSTART.md)

```bash
# Install OpenVPN
sudo bash install.sh

# List available free servers
sudo python3 vpn_prod.py list

# Connect to server #1
sudo python3 vpn_prod.py connect 1

# Or connect to a specific country
sudo python3 vpn_prod.py country Japan
```

**Features:**
- ✅ **6000+ FREE VPN servers** worldwide (via VPN Gate)
- ✅ **60+ countries** available
- ✅ **Production-ready** - actually connects to real VPN servers
- ✅ **No registration** or payment required
- ✅ **OpenVPN protocol** - industry standard

---

## 📖 Two Versions Available

This repository contains **TWO implementations**:

1. **Production VPN Client** (`vpn_prod.py`) - **Ready to use NOW**
   - Connects to real FREE VPN servers from VPN Gate
   - No configuration needed
   - See [QUICKSTART.md](QUICKSTART.md) for usage

2. **VPN Framework** (other files) - For developers
   - Flexible architecture for building custom VPN clients
   - Supports custom VPN providers
   - See sections below for framework documentation

---

A comprehensive Python-based VPN client that supports multiple VPN locations with easy switching capabilities. This implementation provides a flexible framework for managing VPN connections across different geographical locations.

## Features

- **Multiple VPN Locations**: Support for multiple VPN server locations worldwide
- **Easy Location Switching**: Seamlessly switch between different VPN locations
- **Country-based Connection**: Connect to any server in a specific country
- **Connection Management**: Connect, disconnect, and monitor VPN status
- **Configuration Management**: Persistent configuration with JSON storage
- **CLI Interface**: Command-line interface for easy VPN operations
- **Protocol Support**: Framework supports OpenVPN and WireGuard protocols
- **Location History**: Track recently used VPN locations
- **Extensible Architecture**: Easy to add new locations and features

## Architecture

The VPN client consists of several modular components:

### Production Components (Real VPN Connections)

7. **VPNGateAPI** (`vpngate_api.py`)
   - Fetches real free VPN servers from VPN Gate
   - Parses CSV server list
   - Decodes OpenVPN configurations
   - Filters servers by speed/ping/country

8. **VPNConnectionProd** (`vpn_connection_prod.py`)
   - Production connection manager
   - Actually connects to VPN servers (not simulation)
   - Manages OpenVPN processes
   - Verifies connections and IP changes

9. **VPN Production CLI** (`vpn_prod.py`)
   - Command-line interface for production use
   - Lists real servers, connects, disconnects
   - Country-based selection
   - Status monitoring

### Framework Components (Development)

These are for building custom VPN clients:

### Core Components

1. **VPNLocation** (`vpn_location.py`)
   - Data model for VPN server locations
   - Stores connection details (server, port, protocol, credentials)

2. **ConfigManager** (`config_manager.py`)
   - Manages VPN configuration and available locations
   - Handles persistent storage in JSON format
   - Provides default locations

3. **VPNConnection** (`vpn_connection.py`)
   - Manages VPN connection lifecycle
   - Handles connect, disconnect, and status operations
   - Supports multiple protocols (OpenVPN, WireGuard)

4. **LocationManager** (`location_manager.py`)
   - Manages location switching logic
   - Provides country/city-based filtering
   - Tracks location usage history

5. **VPNClient** (`vpn_client.py`)
   - Main client interface
   - Integrates all components
   - Provides high-level API

6. **VPN CLI** (`vpn_cli.py`)
   - Command-line interface
   - Interactive VPN operations

## Installation

### Requirements

- Python 3.7 or higher
- For actual VPN connections (production):
  - OpenVPN client
  - WireGuard tools (optional)

### Setup

```bash
# Clone or navigate to the vpn directory
cd vpn

# Install optional dependencies (if needed)
pip install -r requirements.txt

# Make CLI executable
chmod +x vpn_cli.py
```

## Usage

### Command Line Interface

#### Quick Connect
```bash
# Quick connect to default location
python vpn_cli.py connect

# Connect to specific location
python vpn_cli.py connect --location us-ny-01
```

#### Disconnect
```bash
python vpn_cli.py disconnect
```

#### Check Status
```bash
python vpn_cli.py status
```

#### List Locations
```bash
# List all available locations
python vpn_cli.py list

# List available countries
python vpn_cli.py countries
```

#### Switch Locations
```bash
# Switch to different location
python vpn_cli.py switch uk-lon-01

# Connect to any server in a country
python vpn_cli.py country "United Kingdom"
```

#### Manage Locations
```bash
# Add new location
python vpn_cli.py add \
  --id ca-tor-01 \
  --name "Canada Toronto 01" \
  --country Canada \
  --city Toronto \
  --server ca-tor-01.vpn.example.com \
  --port 1194 \
  --protocol openvpn

# Remove location
python vpn_cli.py remove ca-tor-01

# Show recent locations
python vpn_cli.py recent
```

### Python API

```python
from vpn_client import VPNClient
from vpn_location import VPNLocation

# Initialize client
client = VPNClient()

# Quick connect
client.connect()

# Connect to specific location
client.connect("us-ny-01")

# Switch location while connected
client.switch_location("uk-lon-01")

# Connect to country
client.connect_to_country("Japan")

# Check status
status = client.get_status()
print(f"Status: {status['status']}")
print(f"Location: {status['location']}")

# List all locations
client.list_locations()

# List countries
client.list_countries()

# Add custom location
new_location = VPNLocation(
    id="custom-01",
    name="Custom Server",
    country="Custom Country",
    city="Custom City",
    server_address="vpn.example.com",
    port=1194,
    protocol="openvpn"
)
client.add_location(new_location)

# Disconnect
client.disconnect()
```

## Default Locations

The system comes with pre-configured sample locations:

| ID | Location | Server |
|---|---|---|
| us-ny-01 | New York, USA | us-ny-01.vpn.example.com |
| uk-lon-01 | London, UK | uk-lon-01.vpn.example.com |
| jp-tok-01 | Tokyo, Japan | jp-tok-01.vpn.example.com |
| de-ber-01 | Berlin, Germany | de-ber-01.vpn.example.com |
| au-syd-01 | Sydney, Australia | au-syd-01.vpn.example.com |

## Configuration

Configuration is stored in `vpn_config.json`:

```json
{
  "locations": [
    {
      "id": "us-ny-01",
      "name": "US New York 01",
      "country": "United States",
      "city": "New York",
      "server_address": "us-ny-01.vpn.example.com",
      "port": 1194,
      "protocol": "openvpn",
      "username": null,
      "password": null,
      "config_file": null
    }
  ],
  "current_location_id": "us-ny-01"
}
```

## Connection States

The VPN connection can be in one of the following states:

- **DISCONNECTED**: Not connected to any VPN
- **CONNECTING**: Establishing connection
- **CONNECTED**: Successfully connected
- **DISCONNECTING**: Terminating connection
- **ERROR**: Connection error occurred

## Example Usage Script

Run the provided example script to see all features in action:

```bash
python example_usage.py
```

This will demonstrate:
- Listing locations and countries
- Quick connect
- Status checking
- Location switching
- Country-based connection
- Adding custom locations
- Recent locations tracking

## Advanced Features

### Location Switching

The client supports seamless location switching:

```python
# Automatically disconnect from current and connect to new location
client.switch_location("jp-tok-01")
```

### Country-Based Connection

Connect to any server in a specific country:

```python
# Connects to first available server in Germany
client.connect_to_country("Germany")
```

### Location History

Track recently used locations:

```python
client.get_recent_locations()
```

## File Structure

```
vpn/
├── __init__.py              # Package initialization
├── vpn_location.py          # Location data model
├── config_manager.py        # Configuration management
├── vpn_connection.py        # Connection management
├── location_manager.py      # Location switching logic
├── vpn_client.py           # Main client interface
├── vpn_cli.py              # Command-line interface
├── example_usage.py        # Usage examples
├── requirements.txt        # Dependencies
├── README.md              # This file
└── vpn_config.json        # Configuration (auto-generated)
```

## Extending the System

### Adding New Protocols

To add support for new VPN protocols:

1. Edit `vpn_connection.py`
2. Add a new method (e.g., `_connect_ikev2`)
3. Update the `connect` method to handle the new protocol

### Adding Location Attributes

To add new attributes to locations:

1. Update the `VPNLocation` dataclass in `vpn_location.py`
2. Update `to_dict` and `from_dict` methods
3. Update configuration loading in `config_manager.py`

### Custom Location Selection

Implement custom location selection logic in `location_manager.py`:

```python
def get_fastest_location(self):
    # Implement ping-based selection
    # Measure latency to each location
    # Return location with lowest latency
    pass
```

## Security Notes

This implementation is a framework/demonstration. For production use:

1. **Credentials**: Store credentials securely (use keyring/keychain)
2. **Encryption**: Ensure proper encryption for config files
3. **VPN Protocols**: Use actual VPN clients (OpenVPN, WireGuard)
4. **DNS Leaks**: Implement DNS leak protection
5. **Kill Switch**: Add network kill switch for connection drops
6. **Authentication**: Implement proper authentication mechanisms

## Where Can I Run This?

### ✅ Production VPN (`vpn_prod.py`) - Works On:

- **Local Linux Machine** with sudo access ✅ RECOMMENDED
- **Local macOS** with sudo access ✅ RECOMMENDED
- **AWS/GCP/Azure/DigitalOcean VM** with root access ✅
- **VirtualBox/VMware VM** with root access ✅
- **WSL2 (Windows Subsystem for Linux)** with root access ✅
- **Docker** with `--privileged --cap-add=NET_ADMIN` flags ✅

### ❌ Production VPN - Does NOT Work On:

- **GitHub Actions** ❌ - No root access, network restrictions
- **GitHub Codespaces** ❌ - No root access for VPN
- **Docker** without `--privileged` ❌ - Cannot create network interfaces
- **Shared hosting** ❌ - No root access
- **Windows (directly)** ❌ - Use WSL2 instead

### ✅ Framework/Demo - Works Everywhere:

The framework components (`vpn_client.py`, `vpn_cli.py`, `example_usage.py`) work in **any Python environment** including GitHub Actions/Codespaces, but only demonstrate the architecture (simulate connections).

### Quick Test:

```bash
# Test if you can run production VPN
sudo python3 vpn_prod.py list

# If this works, you're good to go!
# If not, you're on a restricted environment
```

## Troubleshooting

### Connection Issues

- Verify VPN server addresses are correct
- Check network connectivity
- Ensure VPN client software (OpenVPN/WireGuard) is installed
- Check firewall settings

### Configuration Issues

- Delete `vpn_config.json` to reset to defaults
- Verify JSON syntax in configuration file
- Check file permissions

## Future Enhancements

Potential improvements:

- [ ] Automatic server selection based on latency
- [ ] Load balancing across multiple servers
- [ ] Connection retry logic
- [ ] Split tunneling support
- [ ] Kill switch implementation
- [ ] DNS leak protection
- [ ] GUI interface
- [ ] Multi-hop VPN connections
- [ ] Bandwidth monitoring
- [ ] Connection logs and analytics

## License

This is a demonstration/framework implementation for educational purposes.

## Contributing

To contribute:

1. Add new features or fix bugs
2. Update documentation
3. Add test cases
4. Submit improvements

## Support

For issues or questions:

- Check the troubleshooting section
- Review example usage
- Examine the code comments

---

**Version**: 2.0.0 (Production Ready)
**VPN Provider**: VPN Gate (University of Tsukuba, Japan)
**Last Updated**: 2026-01-11

## Credits

- **VPN Gate Project**: https://www.vpngate.net/ - Free VPN relay service by volunteers
- **University of Tsukuba, Japan** - Academic research project
- **OpenVPN**: https://openvpn.net/ - Industry standard VPN protocol
