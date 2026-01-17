# Bluehood

Bluetooth neighborhood monitor - track devices in your area and analyze traffic patterns.

## Features

- Continuous Bluetooth LE scanning
- MAC address vendor lookup
- Track sighting counts and patterns
- Time-based pattern analysis (e.g., "Evenings 5PM-9PM, Weekdays")
- Ignore unwanted devices
- Set friendly names for known devices
- TUI works over SSH
- Daemon + TUI architecture for background scanning

## Installation

```bash
# Install dependencies
pip install textual bleak aiosqlite mac-vendor-lookup

# Install bluehood
cd ~/projects/bluehood
pip install -e .
```

### Bluetooth Permissions

Bluetooth scanning requires elevated privileges. Options:

1. **Run daemon as root** (simplest):
   ```bash
   sudo bluehood-daemon
   ```

2. **Grant capabilities to Python**:
   ```bash
   sudo setcap 'cap_net_admin,cap_net_raw+eip' $(readlink -f $(which python))
   ```

3. **Use systemd service** (recommended for production):
   ```bash
   sudo cp bluehood.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now bluehood
   ```

## Usage

### Start the daemon

```bash
# In one terminal
bluehood-daemon

# Or with sudo if needed
sudo bluehood-daemon
```

### Launch the TUI

```bash
# In another terminal (can be over SSH)
bluehood
```

### TUI Keybindings

| Key | Action |
|-----|--------|
| `r` | Refresh device list |
| `i` | Toggle ignore on selected device |
| `n` | Set friendly name |
| `d` | Show detailed view with heatmaps |
| `f` | Toggle filter (all / active only) |
| `q` | Quit |

## Data Storage

Data is stored in `~/.local/share/bluehood/`:
- `bluehood.db` - SQLite database with devices and sightings

## Architecture

```
[Bluetooth Adapter] -> [bluehood-daemon] -> [SQLite DB]
                            |                    ^
                            v                    |
                    [Unix Socket] <-> [bluehood TUI]
```

The daemon runs continuously, scanning for Bluetooth devices every 10 seconds.
The TUI connects to the daemon via Unix socket to query and manage devices.

## Pattern Analysis

Bluehood analyzes sighting timestamps to detect patterns:

- **Time of day**: Early morning, Morning, Afternoon, Evening, Night
- **Day of week**: Weekdays, Weekends, specific days
- **Frequency**: Constant, Daily, Regular, Occasional, Rare

Example patterns:
- "Daily, evenings (5PM-9PM)"
- "Weekdays, morning (8AM-12PM)"
- "Occasional, all day"
