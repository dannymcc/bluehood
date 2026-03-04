"""Configuration for bluehood."""

import os
from pathlib import Path

# Data directory
DATA_DIR = Path(os.environ.get("BLUEHOOD_DATA_DIR", Path.home() / ".local" / "share" / "bluehood"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path (can be overridden directly)
DB_PATH = Path(os.environ.get("BLUEHOOD_DB_PATH", DATA_DIR / "bluehood.db"))

# Socket path for daemon communication
SOCKET_PATH = Path("/tmp/bluehood.sock")

# Scanning interval in seconds
SCAN_INTERVAL = 10

# How long to scan for each cycle (seconds)
SCAN_DURATION = 5

# Bluetooth adapter (None = auto-select, or specify like "hci0")
BLUETOOTH_ADAPTER = os.environ.get("BLUEHOOD_ADAPTER", None)

# Identify BLE adapter by Bluetooth MAC address (takes precedence over hci name).
# When set, Bluehood resolves the hciX name dynamically on startup and after recovery.
BLUETOOTH_ADAPTER_MAC = os.environ.get("BLUEHOOD_ADAPTER_MAC", None)

# Prometheus metrics port (None = disabled)
METRICS_PORT = int(os.environ.get("BLUEHOOD_METRICS_PORT", 0)) or None

# Separate adapter for classic Bluetooth inquiry scans (None = use same as BLE).
# Setting this to a different adapter (e.g. a USB dongle) allows BLE and classic
# scans to run concurrently without adapter contention.
CLASSIC_BLUETOOTH_ADAPTER = os.environ.get("BLUEHOOD_CLASSIC_ADAPTER", None)

# Identify classic adapter by Bluetooth MAC address.
CLASSIC_BLUETOOTH_ADAPTER_MAC = os.environ.get("BLUEHOOD_CLASSIC_ADAPTER_MAC", None)

# Heartbeat check-in URL (None = disabled). POST JSON payload periodically.
HEARTBEAT_URL = os.environ.get("BLUEHOOD_HEARTBEAT_URL")
HEARTBEAT_INTERVAL = int(os.environ.get("BLUEHOOD_HEARTBEAT_INTERVAL", "300"))  # seconds

# Auto-prune sightings older than N days (0 = disabled)
PRUNE_DAYS = int(os.environ.get("BLUEHOOD_PRUNE_DAYS", "0"))

# Consecutive scans returning 0 BLE devices before triggering recovery (0 = disabled).
# Default 20 scans * 10s interval = ~3.3 minutes of zero devices.
STALE_SCAN_THRESHOLD = int(os.environ.get("BLUEHOOD_STALE_SCAN_THRESHOLD", "20"))

# Seconds since last successful scan (>0 devices) before /api/health returns 503.
HEALTH_MAX_SCAN_AGE = int(os.environ.get("BLUEHOOD_HEALTH_MAX_SCAN_AGE", "300"))
