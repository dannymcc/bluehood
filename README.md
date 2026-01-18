# Bluehood

**Bluetooth Neighborhood** - Track BLE devices in your area and analyze traffic patterns.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/d3hkz6gwle)

---

> **WARNING: Alpha Software**
>
> This project is in early development and is **not ready for production use**. Features may change, break, or be removed without notice. Use at your own risk. Data collected should be treated as experimental.

---

## Why?

This project was inspired by the [WhisperPair vulnerability](https://whisperpair.eu/) ([CVE-2025-36911](https://nvd.nist.gov/vuln/detail/CVE-2025-36911)), which highlighted privacy risks in Bluetooth devices.

Thousands of Bluetooth devices surround us at all times: phones, cars, TVs, headphones, hearing aids, delivery vehicles, and more. Bluehood demonstrates how simple it is to passively detect these devices and observe patterns in their presence.

With enough data, you could potentially:
- Understand what time someone typically walks their dog
- Detect when a visitor arrives at a house
- Identify patterns in daily routines based on device presence

This metadata can reveal surprisingly personal information without any active interaction with the devices.

**Bluehood is an educational tool to raise awareness about Bluetooth privacy.** It's a weekend project, but the implications are worth thinking about.

## What?

Bluehood is a Bluetooth Low Energy (BLE) scanner that:

- **Continuously scans** for nearby BLE devices
- **Identifies devices** by vendor (MAC address lookup) and BLE service UUIDs
- **Classifies devices** into categories (phones, audio, wearables, IoT, vehicles, etc.)
- **Tracks presence patterns** over time with hourly/daily heatmaps
- **Filters out noise** from randomized MAC addresses (privacy-rotated devices)
- **Provides a web dashboard** for monitoring and analysis

## Features

- Continuous Bluetooth LE scanning
- Web dashboard for real-time monitoring
- MAC address vendor lookup (local database + online API fallback)
- BLE service UUID fingerprinting for accurate device classification
- Device type detection (phones, audio, wearables, IoT, vehicles, etc.)
- 30-day presence timeline visualization
- Hourly and daily activity heatmaps
- Pattern analysis ("Weekdays, evenings 5PM-9PM")
- Mark devices as "Watched" for tracking personal devices
- Ignore unwanted devices
- Set friendly names for known devices
- Search by MAC, vendor, or name
- Date range search for historical queries
- Randomized MAC filtering (hidden from main view)

## How?

### Quick Start with Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/dannymcc/bluehood.git
cd bluehood

# Start with Docker Compose
docker compose up -d

# View logs
docker compose logs -f
```

The web dashboard will be available at **http://localhost:8080**

#### Docker Requirements

- Docker and Docker Compose
- Linux host with Bluetooth adapter
- BlueZ installed on the host (`apt install bluez` or `pacman -S bluez`)

> **Note**: Docker runs in privileged mode with host networking for Bluetooth access. This is required for BLE scanning.

#### Docker Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLUEHOOD_ADAPTER` | auto | Bluetooth adapter (e.g., `hci0`) |
| `BLUEHOOD_DATA_DIR` | `/data` | Database storage directory |

### Manual Installation

```bash
# Install system dependencies (Arch Linux)
sudo pacman -S bluez bluez-utils python-pip

# Install system dependencies (Debian/Ubuntu)
sudo apt install bluez python3-pip

# Clone and install
git clone https://github.com/dannymcc/bluehood.git
cd bluehood
pip install -e .
```

#### Bluetooth Permissions

Bluetooth scanning requires elevated privileges. Choose one:

1. **Run as root** (simplest):
   ```bash
   sudo bluehood
   ```

2. **Grant capabilities to Python**:
   ```bash
   sudo setcap 'cap_net_admin,cap_net_raw+eip' $(readlink -f $(which python))
   bluehood
   ```

3. **Use systemd service** (recommended for always-on):
   ```bash
   sudo cp bluehood.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now bluehood
   ```

## Usage

```bash
# Start with web dashboard (default port 8080)
bluehood

# Specify a different port
bluehood --port 9000

# Use a specific Bluetooth adapter
bluehood --adapter hci1

# List available adapters
bluehood --list-adapters

# Disable web dashboard (scanning only)
bluehood --no-web
```

## Web Dashboard

The dashboard provides:

- **Device list** with type icons, vendor, MAC, name, sightings, last seen
- **Device filters** by type (phones, audio, IoT, etc.) and watched status
- **Search** by MAC, vendor, or name
- **Date range search** to find devices seen in a specific time window
- **Device details** modal with:
  - BLE service fingerprints
  - Hourly/daily activity heatmaps
  - 30-day presence timeline
  - Signal strength (RSSI)
  - Pattern analysis

## Data Storage

Data is stored in `~/.local/share/bluehood/bluehood.db` (SQLite).

Override location with environment variables:
- `BLUEHOOD_DATA_DIR` - Directory for data files
- `BLUEHOOD_DB_PATH` - Direct path to database file

## How It Works

### Device Classification

Bluehood classifies devices using multiple signals (in priority order):

1. **BLE Service UUIDs** - Most accurate (Heart Rate = wearable, A2DP = audio, etc.)
2. **Device name patterns** - "iPhone", "Galaxy", "AirPods", etc.
3. **Vendor OUI lookup** - Apple, Samsung, Bose, etc.

### Randomized MACs

Modern devices randomize their MAC addresses for privacy. Bluehood:
- Detects randomized MACs (locally administered bit)
- Hides them from the main device list (not useful for tracking)
- Shows a count of hidden randomized devices

### Pattern Analysis

Bluehood analyzes sighting timestamps to detect patterns:

- **Time of day**: Morning, Afternoon, Evening, Night
- **Day of week**: Weekdays, Weekends
- **Frequency**: Constant, Daily, Regular, Occasional, Rare

Example patterns: "Daily, evenings (5PM-9PM)", "Weekdays, morning (8AM-12PM)"

## Troubleshooting

### No devices found
- Ensure Bluetooth adapter is enabled: `bluetoothctl power on`
- Check adapter is detected: `bluehood --list-adapters`
- Run with sudo if permission denied

### Docker issues
- Ensure BlueZ is installed on the host (not just in container)
- Verify Bluetooth service is running: `systemctl status bluetooth`

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Disclaimer

This tool is for educational purposes only. Be mindful of privacy laws in your jurisdiction when monitoring Bluetooth devices. The author is not responsible for any misuse of this software.

---

Created by [Danny McClelland](https://github.com/dannymcc)
