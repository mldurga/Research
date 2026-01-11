"""
VPN Web Server for iPhone/Mobile Access
Provides web interface to browse and download VPN configurations
"""

from flask import Flask, render_template, jsonify, send_file, request
from flask_cors import CORS
import io
import os
from vpngate_api import VPNGateAPI

app = Flask(__name__)
CORS(app)

# Global VPNGate API instance
vpn_api = VPNGateAPI()
servers_cache = []


@app.route('/')
def index():
    """Main page - mobile-friendly interface"""
    return render_template('index.html')


@app.route('/api/servers')
def get_servers():
    """API endpoint to get available VPN servers"""
    global servers_cache

    # Get filter parameters
    min_speed = request.args.get('min_speed', 5, type=int)
    max_servers = request.args.get('max_servers', 50, type=int)
    country = request.args.get('country', '', type=str)

    # Fetch servers if cache is empty
    if not servers_cache:
        servers_cache = vpn_api.fetch_servers(
            min_speed=min_speed * 1000000,
            max_servers=max_servers
        )

    # Filter by country if specified
    filtered_servers = servers_cache
    if country:
        filtered_servers = [s for s in servers_cache
                          if country.lower() in s.country.lower()]

    # Convert to JSON-friendly format
    servers_data = []
    for i, server in enumerate(filtered_servers):
        servers_data.append({
            'index': i + 1,
            'id': server.id,
            'name': server.name,
            'country': server.country,
            'city': server.city,
            'server_address': server.server_address,
            'speed_mbps': server.metadata.get('speed_mbps', 0),
            'ping': server.metadata.get('ping', '?'),
            'score': server.metadata.get('score', 0)
        })

    return jsonify({'servers': servers_data, 'count': len(servers_data)})


@app.route('/api/countries')
def get_countries():
    """Get list of available countries"""
    global servers_cache

    if not servers_cache:
        servers_cache = vpn_api.fetch_servers(min_speed=5000000, max_servers=50)

    countries = sorted(list(set(s.country for s in servers_cache)))
    return jsonify({'countries': countries})


@app.route('/api/download/<int:server_index>')
def download_config(server_index):
    """Download OpenVPN configuration file for iPhone"""
    global servers_cache

    if not servers_cache:
        return jsonify({'error': 'No servers available'}), 404

    if server_index < 1 or server_index > len(servers_cache):
        return jsonify({'error': 'Invalid server index'}), 400

    server = servers_cache[server_index - 1]

    # Get OpenVPN configuration
    config = vpn_api.get_openvpn_config(server)
    if not config:
        return jsonify({'error': 'Failed to get configuration'}), 500

    # Create file-like object
    config_bytes = config.encode('utf-8')
    config_file = io.BytesIO(config_bytes)

    # Generate filename
    filename = f"vpngate_{server.country.replace(' ', '_')}_{server_index}.ovpn"

    return send_file(
        config_file,
        mimetype='application/x-openvpn-profile',
        as_attachment=True,
        download_name=filename
    )


@app.route('/api/refresh')
def refresh_servers():
    """Refresh server list"""
    global servers_cache

    min_speed = request.args.get('min_speed', 5, type=int)
    max_servers = request.args.get('max_servers', 50, type=int)

    servers_cache = vpn_api.fetch_servers(
        min_speed=min_speed * 1000000,
        max_servers=max_servers
    )

    return jsonify({
        'status': 'success',
        'count': len(servers_cache),
        'message': f'Refreshed {len(servers_cache)} servers'
    })


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'servers_cached': len(servers_cache)})


def run_server(host='0.0.0.0', port=5000, debug=False):
    """Run the web server"""
    print("=" * 70)
    print("VPN Web Server for iPhone/Mobile")
    print("=" * 70)
    print(f"\nServer running on: http://{host}:{port}")
    print("\nAccess from iPhone:")
    print("1. Connect iPhone to same WiFi network")
    print("2. Find your computer's IP address:")
    print("   - Linux/Mac: Run 'hostname -I' or 'ifconfig'")
    print("   - Windows: Run 'ipconfig'")
    print("3. Open Safari on iPhone and go to:")
    print(f"   http://YOUR_COMPUTER_IP:{port}")
    print("\nExample: http://192.168.1.100:5000")
    print("\n" + "=" * 70)
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70 + "\n")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server(debug=True)
