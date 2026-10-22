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

# Web dashboard port (the --port CLI flag takes precedence)
WEB_PORT = int(os.environ.get("BLUEHOOD_PORT", "8080"))

# ntfy server base URL. Point this at a self-hosted ntfy instance to avoid
# ntfy.sh. The value saved in the GUI settings takes precedence.
NTFY_SERVER = os.environ.get("BLUEHOOD_NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/") or "https://ntfy.sh"

# Bluetooth adapter (None = auto-select, or specify like "hci0")
BLUETOOTH_ADAPTER = os.environ.get("BLUEHOOD_ADAPTER", None)

# Prometheus metrics port (None = disabled)
METRICS_PORT = int(os.environ.get("BLUEHOOD_METRICS_PORT", 0)) or None

# Separate adapter for classic Bluetooth inquiry scans (None = use same as BLE).
# Setting this to a different adapter (e.g. a USB dongle) allows BLE and classic
# scans to run concurrently without adapter contention.
CLASSIC_BLUETOOTH_ADAPTER = os.environ.get("BLUEHOOD_CLASSIC_ADAPTER", None)

# ESPHome Bluetooth proxies to receive advertisements from (None = disabled).
# Comma-separated host[:port][@encryption_key] entries, e.g.
# "livingroom.local,192.168.1.50:6053@base64key=". Requires bluehood[esphome].
ESPHOME_PROXIES = os.environ.get("BLUEHOOD_ESPHOME_PROXIES")
# Default API encryption key / legacy password for proxies without their own key
ESPHOME_NOISE_PSK = os.environ.get("BLUEHOOD_ESPHOME_NOISE_PSK")
ESPHOME_PASSWORD = os.environ.get("BLUEHOOD_ESPHOME_PASSWORD")

# Scan with the local Bluetooth adapter. Disable to rely solely on ESPHome
# proxies (e.g. on a host without Bluetooth hardware).
LOCAL_SCAN = os.environ.get("BLUEHOOD_LOCAL_SCAN", "1").strip().lower() not in ("0", "false", "no", "off")

# Heartbeat check-in URL (None = disabled). POST JSON payload periodically.
HEARTBEAT_URL = os.environ.get("BLUEHOOD_HEARTBEAT_URL")
HEARTBEAT_INTERVAL = int(os.environ.get("BLUEHOOD_HEARTBEAT_INTERVAL", "300"))  # seconds

# Auto-prune sightings older than N days (0 = disabled)
PRUNE_DAYS = int(os.environ.get("BLUEHOOD_PRUNE_DAYS", "0"))

# When pruning, only remove stale devices with fewer than this many total
# sightings (0 = disabled; prune by age only, keeping device records).
PRUNE_MIN_SIGHTINGS = int(os.environ.get("BLUEHOOD_PRUNE_MIN_SIGHTINGS", "0"))
