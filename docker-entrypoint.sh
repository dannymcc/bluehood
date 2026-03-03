#!/bin/bash
set -e

PUID=${PUID:-0}
PGID=${PGID:-0}

# Validate PUID/PGID are numeric
if ! echo "$PUID" | grep -qE '^[0-9]+$' || ! echo "$PGID" | grep -qE '^[0-9]+$'; then
    echo "ERROR: PUID and PGID must be numeric (got PUID=$PUID, PGID=$PGID)" >&2
    exit 1
fi

echo "Starting with data owned by UID: $PUID, GID: $PGID"

# Fix ownership of data directory to match host user
chown -R "$PUID:$PGID" /data

# Run daemon as root — BLE scanning and adapter recovery require
# sysfs access (/sys/bus/usb, /sys/class/rfkill) which needs root.
# The container must be privileged anyway for Bluetooth hardware access,
# so running as root inside adds no meaningful attack surface.
exec "$@"
