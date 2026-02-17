# Bluehood

**Bluetooth Neighborhood** - Track BLE devices in your area and analyze traffic patterns.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/d3hkz6gwle)

---

> **WARNING: Alpha Software**
>
> This project is in early development and is **not ready for production use**. Features may change, break, or be removed without notice. Use at your own risk. Data collected should be treated as experimental.

---

## Screenshots

![Dashboard](screenshots/dashboard.png)
*Main dashboard showing device list with filtering, search, and real-time statistics*

![Settings](screenshots/settings.png)
*Configuration page for push notifications and alert triggers*

![About](screenshots/about.png)
*Intel page with project information and capabilities overview*

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

Bluehood is a Bluetooth scanner that:

- **Continuously scans** for nearby Bluetooth devices (both BLE and Classic)
- **Identifies devices** by vendor (MAC address lookup) and BLE service UUIDs
- **Classifies devices** into categories (phones, audio, wearables, IoT, vehicles, etc.)
- **Tracks presence patterns** over time with hourly/daily heatmaps
- **Filters out noise** from randomized MAC addresses (privacy-rotated devices)
- **Analyzes device correlations** to find devices that appear together
- **Sends push notifications** when watched devices arrive or leave
- **Provides a web dashboard** for monitoring and analysis

## Features

### Scanning
- Dual-mode scanning: Bluetooth Low Energy (BLE) and Classic Bluetooth
- MAC address vendor lookup (local database + online API fallback)
- BLE service UUID fingerprinting for accurate device classification
- Classic Bluetooth device class parsing
- Randomized MAC filtering (hidden from main view)

### Device Management
- Mark devices as "Watched" for tracking personal devices
- Organize devices into custom groups
- Set friendly names for known devices
- Add custom notes/tags to any device
- Device type detection (phones, audio, wearables, IoT, vehicles, etc.)

### Analytics
- **30-day presence timeline** visualization
- **Signal strength (RSSI) history** chart with 7-day data
- **Hourly and daily activity heatmaps** showing when devices are active
- **Pattern analysis** ("Weekdays, evenings 5PM-9PM")
- **Dwell time analysis** showing total time devices spend in range
- **Device correlation** detection to find devices that appear together
- **Proximity zones** (immediate, near, far, remote) based on signal strength
- Search by MAC, vendor, or name
- Date range search for historical queries

### Notifications (via ntfy.sh)
- Push notifications to your phone/desktop
- Notify when new devices are detected
- Notify when watched devices return
- Notify when watched devices leave
- Configurable thresholds for arrival/departure

### Web Interface
- **Compact/Detailed view toggle** for different display preferences
- **Screenshot mode** to obfuscate MACs and names for safe sharing
- **Keyboard shortcuts** for power users (press `?` to view)
- **CSV export** of device data
- **Device groups** for organizing related devices
- **Optional authentication** to secure access

## How?

### Quick Start with Docker (Recommended)

```bash
# Create a docker-compose.yml or download the one from this repo
# Then start with Docker Compose
docker compose up -d

# View logs
docker compose logs -f
```

The Docker image is available on GitHub Container Registry:

```
ghcr.io/dannymcc/bluehood:latest
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

### Manual Installation (Linux)

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

### macOS

Bluehood works natively on macOS without Docker. macOS uses CoreBluetooth instead of BlueZ, which is handled automatically by the `bleak` library.

```bash
# Clone the repository
git clone https://github.com/dannymcc/bluehood.git
cd bluehood

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Run
python -m bluehood.daemon
```

The web dashboard will be available at **http://localhost:8080**

> **Note**: On first run, macOS will prompt you to allow Bluetooth access. You must grant this permission for scanning to work.

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
- **Settings** for configuring notifications, groups, and authentication
- **Device details** modal with:
  - BLE service fingerprints
  - Hourly/daily activity heatmaps
  - 30-day presence timeline
  - Signal strength (RSSI) history chart
  - Pattern analysis
  - Dwell time statistics
  - Correlated devices list
  - Proximity zone indicator
  - Operator notes field
  - Group assignment

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search bar |
| `r` | Refresh device list |
| `c` | Toggle compact view |
| `w` | Toggle watch on selected device |
| `Esc` | Close modal |
| `?` | Show keyboard shortcuts |

### Screenshot Mode

Enable screenshot mode from the sidebar to obfuscate sensitive data before sharing screenshots:
- MAC addresses show only first 2 octets (e.g., `AA:BB:XX:XX:XX:XX`)
- Friendly names show only first 2 characters (e.g., `Da********`)
- CSV exports also respect screenshot mode

## Push Notifications

Bluehood can send push notifications via [ntfy.sh](https://ntfy.sh), a free, open-source notification service.

1. Create a topic at ntfy.sh (e.g., `bluehood-myname-alerts`)
2. Subscribe to the topic on your phone using the ntfy app
3. In Bluehood settings, enter your topic name and enable notifications
4. Configure which events trigger notifications:
   - New device detected
   - Watched device returns (after being absent)
   - Watched device leaves (not seen for X minutes)

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

### Device Correlation

Bluehood detects devices that frequently appear together within a configurable time window. This can reveal:
- Devices owned by the same person (phone + smartwatch)
- People who travel together
- Devices that share a schedule

### Proximity Zones

Based on RSSI signal strength, devices are classified into proximity zones:
- **Immediate** (> -50 dBm): Very close, within a few meters
- **Near** (-50 to -60 dBm): Nearby, same room
- **Far** (-60 to -70 dBm): Further away, adjacent rooms
- **Remote** (< -70 dBm): Distant, at edge of detection range

### Dwell Time Analysis

Tracks how long devices spend in range by analyzing gaps between sightings. A configurable gap threshold (default 15 minutes) determines when a new "session" begins.

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

### Contributors

- [@martinh2011](https://github.com/martinh2011) (Martin Hüser) - MAC vendor cache improvements
- [@hatedabamboo](https://github.com/hatedabamboo) (Kirill Solovei) - Light theme support
- [@krnltrp](https://github.com/krnltrp) - Web UI enhancements
- [@jacobpretorius](https://github.com/jacobpretorius) (Jacob Pretorius) - CSV export JS fix (#14)

## License

MIT License - See [LICENSE](LICENSE) for details.

## Disclaimer

This tool is for educational purposes only. Be mindful of privacy laws in your jurisdiction when monitoring Bluetooth devices. The author is not responsible for any misuse of this software.

---

Created by [Danny McClelland](https://github.com/dannymcc)
