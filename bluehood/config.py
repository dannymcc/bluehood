"""Configuration for bluehood."""

import os
from pathlib import Path

# Data directory
DATA_DIR = Path(os.environ.get("BLUEHOOD_DATA_DIR", Path.home() / ".local" / "share" / "bluehood"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path
DB_PATH = DATA_DIR / "bluehood.db"

# Socket path for daemon communication
SOCKET_PATH = Path("/tmp/bluehood.sock")

# Scanning interval in seconds
SCAN_INTERVAL = 10

# How long to scan for each cycle (seconds)
SCAN_DURATION = 5
