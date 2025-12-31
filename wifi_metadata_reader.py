#!/usr/bin/env python3
"""
WiFi Metadata Reader
Comprehensive tool to read WiFi network name (SSID) and detailed metadata

Works on Linux, Windows, and macOS
"""

import subprocess
import platform
import re
import json

def get_wifi_linux():
    """Get WiFi info on Linux"""
    wifi_info = {}

    # Method 1: nmcli (Most common on modern Linux)
    try:
        # Get active connection
        result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid,bssid,chan,freq,rate,signal,security',
                               'dev', 'wifi', 'list'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('yes:'):
                    parts = line.split(':')
                    if len(parts) >= 8:
                        wifi_info['ssid'] = parts[1]
                        wifi_info['bssid'] = parts[2]
                        wifi_info['channel'] = parts[3]
                        wifi_info['frequency'] = parts[4]
                        wifi_info['rate'] = parts[5]
                        wifi_info['signal'] = parts[6]
                        wifi_info['security'] = parts[7]

        # Get more detailed connection info
        result2 = subprocess.run(['nmcli', 'connection', 'show', '--active'],
                               capture_output=True, text=True, timeout=5)
        if result2.returncode == 0:
            wifi_info['connection_details'] = result2.stdout

    except Exception as e:
        print(f"  nmcli method failed: {e}")

    # Method 2: iwconfig
    try:
        result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout

            # Parse SSID
            ssid_match = re.search(r'ESSID:"([^"]+)"', output)
            if ssid_match and 'ssid' not in wifi_info:
                wifi_info['ssid'] = ssid_match.group(1)

            # Parse other details
            if 'Frequency' in output:
                freq_match = re.search(r'Frequency:([^\s]+)', output)
                if freq_match:
                    wifi_info['frequency'] = freq_match.group(1)

            if 'Bit Rate' in output:
                rate_match = re.search(r'Bit Rate[=:]([^\s]+)', output)
                if rate_match:
                    wifi_info['bitrate'] = rate_match.group(1)

            if 'Signal level' in output:
                signal_match = re.search(r'Signal level[=:]([^\s]+)', output)
                if signal_match:
                    wifi_info['signal_level'] = signal_match.group(1)

            wifi_info['iwconfig_raw'] = output

    except Exception as e:
        print(f"  iwconfig method failed: {e}")

    # Method 3: iw
    try:
        # First get interface name
        result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            interface_match = re.search(r'Interface\s+(\w+)', result.stdout)
            if interface_match:
                interface = interface_match.group(1)
                wifi_info['interface'] = interface

                # Get link info
                result2 = subprocess.run(['iw', interface, 'link'],
                                       capture_output=True, text=True, timeout=5)
                if result2.returncode == 0:
                    link_output = result2.stdout

                    # Parse SSID
                    ssid_match = re.search(r'SSID:\s*(.+)', link_output)
                    if ssid_match and 'ssid' not in wifi_info:
                        wifi_info['ssid'] = ssid_match.group(1).strip()

                    # Parse frequency
                    freq_match = re.search(r'freq:\s*(\d+)', link_output)
                    if freq_match:
                        wifi_info['frequency_mhz'] = freq_match.group(1)

                    # Parse signal
                    signal_match = re.search(r'signal:\s*([-\d]+)', link_output)
                    if signal_match:
                        wifi_info['signal_dbm'] = signal_match.group(1)

                    wifi_info['iw_link_raw'] = link_output

                # Get station info
                result3 = subprocess.run(['iw', interface, 'info'],
                                       capture_output=True, text=True, timeout=5)
                if result3.returncode == 0:
                    wifi_info['iw_info_raw'] = result3.stdout

    except Exception as e:
        print(f"  iw method failed: {e}")

    return wifi_info

def get_wifi_windows():
    """Get WiFi info on Windows"""
    wifi_info = {}

    try:
        result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout

            for line in output.split('\n'):
                line = line.strip()
                if 'SSID' in line and 'BSSID' not in line:
                    wifi_info['ssid'] = line.split(':', 1)[1].strip()
                elif 'BSSID' in line:
                    wifi_info['bssid'] = line.split(':', 1)[1].strip()
                elif 'Signal' in line:
                    wifi_info['signal'] = line.split(':', 1)[1].strip()
                elif 'Channel' in line:
                    wifi_info['channel'] = line.split(':', 1)[1].strip()
                elif 'Radio type' in line:
                    wifi_info['radio_type'] = line.split(':', 1)[1].strip()
                elif 'Authentication' in line:
                    wifi_info['authentication'] = line.split(':', 1)[1].strip()
                elif 'Cipher' in line:
                    wifi_info['cipher'] = line.split(':', 1)[1].strip()
                elif 'Receive rate' in line:
                    wifi_info['rx_rate'] = line.split(':', 1)[1].strip()
                elif 'Transmit rate' in line:
                    wifi_info['tx_rate'] = line.split(':', 1)[1].strip()

            wifi_info['raw_output'] = output

    except Exception as e:
        print(f"  Windows method failed: {e}")

    return wifi_info

def get_wifi_macos():
    """Get WiFi info on macOS"""
    wifi_info = {}

    try:
        # Method 1: airport utility
        airport_path = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
        result = subprocess.run([airport_path, '-I'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout

            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('SSID:'):
                    wifi_info['ssid'] = line.split(':', 1)[1].strip()
                elif line.startswith('BSSID:'):
                    wifi_info['bssid'] = line.split(':', 1)[1].strip()
                elif 'channel' in line.lower():
                    wifi_info['channel'] = line.split(':', 1)[1].strip()
                elif 'agrCtlRSSI' in line:
                    wifi_info['rssi'] = line.split(':', 1)[1].strip()
                elif 'agrCtlNoise' in line:
                    wifi_info['noise'] = line.split(':', 1)[1].strip()
                elif 'state' in line.lower():
                    wifi_info['state'] = line.split(':', 1)[1].strip()
                elif 'lastTxRate' in line:
                    wifi_info['tx_rate'] = line.split(':', 1)[1].strip()

            wifi_info['raw_output'] = output

        # Method 2: networksetup
        result2 = subprocess.run(['networksetup', '-getairportnetwork', 'en0'],
                               capture_output=True, text=True, timeout=5)
        if result2.returncode == 0 and 'Current Wi-Fi Network' in result2.stdout:
            ssid = result2.stdout.split(':', 1)[1].strip()
            if 'ssid' not in wifi_info:
                wifi_info['ssid'] = ssid

    except Exception as e:
        print(f"  macOS method failed: {e}")

    return wifi_info

def main():
    print("=" * 70)
    print("WiFi Metadata Reader")
    print("=" * 70)

    os_type = platform.system()
    print(f"\nDetected OS: {os_type}")

    wifi_info = {}

    if os_type == 'Linux':
        print("\nReading WiFi information using Linux tools...\n")
        wifi_info = get_wifi_linux()
    elif os_type == 'Windows':
        print("\nReading WiFi information using Windows tools...\n")
        wifi_info = get_wifi_windows()
    elif os_type == 'Darwin':
        print("\nReading WiFi information using macOS tools...\n")
        wifi_info = get_wifi_macos()
    else:
        print(f"\nUnsupported OS: {os_type}")
        return

    if not wifi_info or 'ssid' not in wifi_info:
        print("⚠️  Could not retrieve WiFi information.")
        print("   Possible reasons:")
        print("   • No WiFi adapter present")
        print("   • Not connected to WiFi")
        print("   • Running in a container/VM without WiFi access")
        print("   • Insufficient permissions (try running with sudo)")
        return

    # Display results
    print("\n" + "=" * 70)
    print("WIFI NETWORK INFORMATION")
    print("=" * 70)

    print(f"\n📶 Network Name (SSID): {wifi_info.get('ssid', 'N/A')}")

    if 'bssid' in wifi_info:
        print(f"🏷️  MAC Address (BSSID): {wifi_info['bssid']}")

    if 'channel' in wifi_info:
        print(f"📡 Channel: {wifi_info['channel']}")

    if 'frequency' in wifi_info or 'frequency_mhz' in wifi_info:
        freq = wifi_info.get('frequency', wifi_info.get('frequency_mhz', 'N/A'))
        print(f"📻 Frequency: {freq}")

    if 'signal' in wifi_info or 'signal_dbm' in wifi_info or 'rssi' in wifi_info:
        signal = wifi_info.get('signal', wifi_info.get('signal_dbm', wifi_info.get('rssi', 'N/A')))
        print(f"📊 Signal Strength: {signal}")

    if 'rate' in wifi_info or 'bitrate' in wifi_info or 'tx_rate' in wifi_info:
        rate = wifi_info.get('rate', wifi_info.get('bitrate', wifi_info.get('tx_rate', 'N/A')))
        print(f"⚡ Data Rate: {rate}")

    if 'security' in wifi_info or 'authentication' in wifi_info:
        security = wifi_info.get('security', wifi_info.get('authentication', 'N/A'))
        print(f"🔒 Security: {security}")

    if 'cipher' in wifi_info:
        print(f"🔐 Cipher: {wifi_info['cipher']}")

    if 'interface' in wifi_info:
        print(f"🔌 Interface: {wifi_info['interface']}")

    if 'radio_type' in wifi_info:
        print(f"📱 Radio Type: {wifi_info['radio_type']}")

    # Save to JSON file
    output_file = '/home/user/Research/wifi_metadata.json'
    with open(output_file, 'w') as f:
        json.dump(wifi_info, f, indent=2)

    print(f"\n💾 Full metadata saved to: {output_file}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
