"""Database operations for bluehood."""

import json
import aiosqlite
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

from .config import DB_PATH


@dataclass
class Device:
    """Represents a Bluetooth device."""
    mac: str
    vendor: Optional[str] = None
    friendly_name: Optional[str] = None
    device_type: Optional[str] = None
    ignored: bool = False
    watched: bool = False  # Device of Interest
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_sightings: int = 0
    service_uuids: list[str] = None  # BLE service UUIDs for fingerprinting
    bt_type: str = "ble"  # "ble" or "classic"
    device_class: Optional[int] = None  # Classic BT device class
    group_id: Optional[int] = None  # Device group
    notes: Optional[str] = None  # Operator notes

    def __post_init__(self):
        if self.service_uuids is None:
            self.service_uuids = []


@dataclass
class Sighting:
    """Represents a device sighting."""
    id: int
    mac: str
    timestamp: datetime
    rssi: Optional[int] = None


@dataclass
class DeviceGroup:
    """Represents a device group/alias."""
    id: int
    name: str
    color: str = "#3b82f6"  # Default blue
    icon: str = "📁"


@dataclass
class Settings:
    """Application settings."""
    # Notification settings
    ntfy_topic: Optional[str] = None
    ntfy_enabled: bool = False
    notify_new_device: bool = False
    notify_watched_return: bool = True
    notify_watched_leave: bool = True
    watched_absence_minutes: int = 30  # Minutes before "left"
    watched_return_minutes: int = 5    # Minutes of absence before "return" triggers
    # Authentication settings
    auth_enabled: bool = False
    auth_username: Optional[str] = None
    auth_password_hash: Optional[str] = None  # bcrypt hash


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    vendor TEXT,
    friendly_name TEXT,
    device_type TEXT,
    ignored INTEGER DEFAULT 0,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    total_sightings INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    rssi INTEGER,
    FOREIGN KEY (mac) REFERENCES devices(mac)
);

CREATE TABLE IF NOT EXISTS device_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#3b82f6',
    icon TEXT DEFAULT '📁'
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_sightings_mac_time ON sightings(mac, timestamp);
CREATE INDEX IF NOT EXISTS idx_sightings_timestamp ON sightings(timestamp);
"""


async def init_db() -> None:
    """Initialize the database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)

        # Migrations for devices table columns
        migrations = [
            ("device_type", "TEXT"),
            ("watched", "INTEGER DEFAULT 0"),
            ("service_uuids", "TEXT"),
            ("bt_type", "TEXT DEFAULT 'ble'"),
            ("device_class", "INTEGER"),
            ("group_id", "INTEGER REFERENCES device_groups(id)"),
            ("notes", "TEXT"),
        ]

        for column, column_type in migrations:
            try:
                await db.execute(f"ALTER TABLE devices ADD COLUMN {column} {column_type}")
                await db.commit()
            except Exception:
                pass  # Column already exists

        await db.commit()


def _parse_device_row(row) -> Device:
    """Parse a database row into a Device object."""
    keys = row.keys()

    # Parse service_uuids from JSON
    service_uuids = []
    if "service_uuids" in keys and row["service_uuids"]:
        try:
            service_uuids = json.loads(row["service_uuids"])
        except (json.JSONDecodeError, TypeError):
            pass

    return Device(
        mac=row["mac"],
        vendor=row["vendor"],
        friendly_name=row["friendly_name"],
        device_type=row["device_type"] if "device_type" in keys else None,
        ignored=bool(row["ignored"]),
        watched=bool(row["watched"]) if "watched" in keys else False,
        first_seen=datetime.fromisoformat(row["first_seen"]) if row["first_seen"] else None,
        last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
        total_sightings=row["total_sightings"],
        service_uuids=service_uuids,
        bt_type=row["bt_type"] if "bt_type" in keys and row["bt_type"] else "ble",
        device_class=row["device_class"] if "device_class" in keys else None,
        group_id=row["group_id"] if "group_id" in keys else None,
        notes=row["notes"] if "notes" in keys else None,
    )


async def get_device(mac: str) -> Optional[Device]:
    """Get a device by MAC address."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE mac = ?", (mac,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return _parse_device_row(row)
            return None


async def get_all_devices(include_ignored: bool = True) -> list[Device]:
    """Get all devices."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM devices"
        if not include_ignored:
            query += " WHERE ignored = 0"
        query += " ORDER BY last_seen DESC"

        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


async def upsert_device(
    mac: str,
    vendor: Optional[str] = None,
    friendly_name: Optional[str] = None,
    rssi: Optional[int] = None,
    service_uuids: Optional[list[str]] = None,
    bt_type: str = "ble",
    device_class: Optional[int] = None,
) -> tuple[Device, bool]:
    """Insert or update a device and record a sighting.

    Returns tuple of (device, is_new) where is_new indicates first sighting.
    """
    now = datetime.now(tz=timezone.utc)
    uuids_json = json.dumps(service_uuids) if service_uuids else None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Check if device exists
        async with db.execute("SELECT * FROM devices WHERE mac = ?", (mac,)) as cursor:
            existing = await cursor.fetchone()

        is_new = existing is None

        if existing:
            # Build update based on what we have
            updates = ["last_seen = ?", "total_sightings = total_sightings + 1"]
            params = [now.isoformat()]

            # Update friendly_name if we have one and device doesn't
            if friendly_name and not existing["friendly_name"]:
                updates.append("friendly_name = ?")
                params.append(friendly_name)

            # Update vendor if we have one and device doesn't
            if vendor and not existing["vendor"]:
                updates.append("vendor = ?")
                params.append(vendor)

            # Update/merge service_uuids if we have new ones
            if service_uuids:
                existing_uuids = []
                if "service_uuids" in existing.keys() and existing["service_uuids"]:
                    try:
                        existing_uuids = json.loads(existing["service_uuids"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                # Merge UUIDs (keep unique)
                merged = list(set(existing_uuids + service_uuids))
                updates.append("service_uuids = ?")
                params.append(json.dumps(merged))

            # Update bt_type if we got classic BT info for a device we only had BLE for
            existing_bt_type = existing["bt_type"] if "bt_type" in existing.keys() else "ble"
            if bt_type == "classic" and existing_bt_type == "ble":
                updates.append("bt_type = ?")
                params.append("both")
            elif bt_type == "ble" and existing_bt_type == "classic":
                updates.append("bt_type = ?")
                params.append("both")

            # Update device_class if we have it and didn't before
            existing_device_class = existing["device_class"] if "device_class" in existing.keys() else None
            if device_class and not existing_device_class:
                updates.append("device_class = ?")
                params.append(device_class)

            params.append(mac)
            await db.execute(
                f"UPDATE devices SET {', '.join(updates)} WHERE mac = ?",
                params
            )
        else:
            # Insert new device
            await db.execute(
                """
                INSERT INTO devices (mac, vendor, friendly_name, first_seen, last_seen, total_sightings, service_uuids, bt_type, device_class)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (mac, vendor, friendly_name, now.isoformat(), now.isoformat(), uuids_json, bt_type, device_class)
            )

        # Record sighting
        await db.execute(
            "INSERT INTO sightings (mac, timestamp, rssi) VALUES (?, ?, ?)",
            (mac, now.isoformat(), rssi)
        )

        await db.commit()

    device = await get_device(mac)
    return device, is_new


async def set_friendly_name(mac: str, name: str) -> None:
    """Set a friendly name for a device."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET friendly_name = ? WHERE mac = ?",
            (name, mac)
        )
        await db.commit()


async def set_ignored(mac: str, ignored: bool) -> None:
    """Set whether a device is ignored."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET ignored = ? WHERE mac = ?",
            (1 if ignored else 0, mac)
        )
        await db.commit()


async def set_watched(mac: str, watched: bool) -> None:
    """Set whether a device is a Device of Interest (watched)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET watched = ? WHERE mac = ?",
            (1 if watched else 0, mac)
        )
        await db.commit()


async def set_device_type(mac: str, device_type: str) -> None:
    """Set the device type for a device."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET device_type = ? WHERE mac = ?",
            (device_type, mac)
        )
        await db.commit()


async def set_device_notes(mac: str, notes: Optional[str]) -> None:
    """Set operator notes for a device."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET notes = ? WHERE mac = ?",
            (notes if notes else None, mac)
        )
        await db.commit()


async def get_sightings(mac: str, days: int = 30) -> list[Sighting]:
    """Get sightings for a device within the last N days."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            ORDER BY timestamp DESC
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                Sighting(
                    id=row["id"],
                    mac=row["mac"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    rssi=row["rssi"],
                )
                for row in rows
            ]


async def get_hourly_distribution(mac: str, days: int = 30) -> dict[int, int]:
    """Get hourly distribution of sightings for pattern analysis."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            GROUP BY hour
            ORDER BY hour
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()
            return {int(row[0]): row[1] for row in rows}


async def get_daily_distribution(mac: str, days: int = 30) -> dict[int, int]:
    """Get daily distribution of sightings (0=Monday, 6=Sunday)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT strftime('%w', timestamp) as day, COUNT(*) as count
            FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            GROUP BY day
            ORDER BY day
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()
            # SQLite %w: 0=Sunday, 1=Monday... Convert to 0=Monday
            return {(int(row[0]) - 1) % 7: row[1] for row in rows}


async def get_daily_sightings(mac: str, days: int = 30) -> list[dict]:
    """Get daily sighting counts for timeline visualization."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT date(timestamp) as date, COUNT(*) as count, AVG(rssi) as avg_rssi
            FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            GROUP BY date(timestamp)
            ORDER BY date ASC
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "date": row[0],
                    "count": row[1],
                    "avg_rssi": round(row[2]) if row[2] else None,
                }
                for row in rows
            ]


async def cleanup_old_sightings(days: int = 90) -> int:
    """Remove sightings older than N days. Returns count deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM sightings WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",)
        )
        await db.commit()
        return cursor.rowcount


async def search_devices(
    mac_filter: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[dict]:
    """
    Search for devices by MAC and/or time range.
    Returns devices with sighting count in the specified range.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Build query based on filters
        if start_time or end_time:
            # Search by time range - find devices seen in that range
            conditions = []
            params = []

            if mac_filter:
                conditions.append("d.mac LIKE ?")
                params.append(f"%{mac_filter}%")

            if start_time:
                conditions.append("s.timestamp >= ?")
                params.append(start_time.isoformat())

            if end_time:
                conditions.append("s.timestamp <= ?")
                params.append(end_time.isoformat())

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT d.*, COUNT(s.id) as range_sightings,
                       MIN(s.timestamp) as range_first,
                       MAX(s.timestamp) as range_last
                FROM devices d
                JOIN sightings s ON d.mac = s.mac
                WHERE {where_clause}
                GROUP BY d.mac
                ORDER BY range_sightings DESC
            """
        else:
            # Just MAC filter, no time range
            if mac_filter:
                query = """
                    SELECT *, total_sightings as range_sightings,
                           first_seen as range_first, last_seen as range_last
                    FROM devices
                    WHERE mac LIKE ? OR friendly_name LIKE ? OR vendor LIKE ?
                    ORDER BY last_seen DESC
                """
                params = [f"%{mac_filter}%", f"%{mac_filter}%", f"%{mac_filter}%"]
            else:
                query = """
                    SELECT *, total_sightings as range_sightings,
                           first_seen as range_first, last_seen as range_last
                    FROM devices
                    ORDER BY last_seen DESC
                """
                params = []

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "mac": row["mac"],
                    "vendor": row["vendor"],
                    "friendly_name": row["friendly_name"],
                    "ignored": bool(row["ignored"]),
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"],
                    "total_sightings": row["total_sightings"],
                    "range_sightings": row["range_sightings"],
                    "range_first": row["range_first"],
                    "range_last": row["range_last"],
                }
                for row in rows
            ]


# ============================================================================
# Settings Management
# ============================================================================

async def get_settings() -> Settings:
    """Get all application settings."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            settings_dict = {row["key"]: row["value"] for row in rows}

    return Settings(
        ntfy_topic=settings_dict.get("ntfy_topic"),
        ntfy_enabled=settings_dict.get("ntfy_enabled", "0") == "1",
        notify_new_device=settings_dict.get("notify_new_device", "0") == "1",
        notify_watched_return=settings_dict.get("notify_watched_return", "1") == "1",
        notify_watched_leave=settings_dict.get("notify_watched_leave", "1") == "1",
        watched_absence_minutes=int(settings_dict.get("watched_absence_minutes", "30")),
        watched_return_minutes=int(settings_dict.get("watched_return_minutes", "5")),
        auth_enabled=settings_dict.get("auth_enabled", "0") == "1",
        auth_username=settings_dict.get("auth_username"),
        auth_password_hash=settings_dict.get("auth_password_hash"),
    )


async def set_setting(key: str, value: str) -> None:
    """Set a single setting value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def update_settings(settings: Settings) -> None:
    """Update all settings from a Settings object."""
    async with aiosqlite.connect(DB_PATH) as db:
        settings_pairs = [
            ("ntfy_topic", settings.ntfy_topic or ""),
            ("ntfy_enabled", "1" if settings.ntfy_enabled else "0"),
            ("notify_new_device", "1" if settings.notify_new_device else "0"),
            ("notify_watched_return", "1" if settings.notify_watched_return else "0"),
            ("notify_watched_leave", "1" if settings.notify_watched_leave else "0"),
            ("watched_absence_minutes", str(settings.watched_absence_minutes)),
            ("watched_return_minutes", str(settings.watched_return_minutes)),
        ]
        for key, value in settings_pairs:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        await db.commit()


async def update_auth_settings(
    enabled: bool,
    username: Optional[str] = None,
    password_hash: Optional[str] = None
) -> None:
    """Update authentication settings."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("auth_enabled", "1" if enabled else "0")
        )
        if username is not None:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("auth_username", username)
            )
        if password_hash is not None:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("auth_password_hash", password_hash)
            )
        await db.commit()


# ============================================================================
# Device Groups Management
# ============================================================================

async def get_groups() -> list[DeviceGroup]:
    """Get all device groups."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM device_groups ORDER BY name") as cursor:
            rows = await cursor.fetchall()
            return [
                DeviceGroup(
                    id=row["id"],
                    name=row["name"],
                    color=row["color"] or "#3b82f6",
                    icon=row["icon"] or "📁",
                )
                for row in rows
            ]


async def get_group(group_id: int) -> Optional[DeviceGroup]:
    """Get a device group by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM device_groups WHERE id = ?", (group_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return DeviceGroup(
                    id=row["id"],
                    name=row["name"],
                    color=row["color"] or "#3b82f6",
                    icon=row["icon"] or "📁",
                )
            return None


async def create_group(name: str, color: str = "#3b82f6", icon: str = "📁") -> DeviceGroup:
    """Create a new device group."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO device_groups (name, color, icon) VALUES (?, ?, ?)",
            (name, color, icon)
        )
        await db.commit()
        return DeviceGroup(id=cursor.lastrowid, name=name, color=color, icon=icon)


async def update_group(group_id: int, name: str, color: str, icon: str) -> None:
    """Update a device group."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE device_groups SET name = ?, color = ?, icon = ? WHERE id = ?",
            (name, color, icon, group_id)
        )
        await db.commit()


async def delete_group(group_id: int) -> None:
    """Delete a device group and unassign all devices."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Unassign devices from this group
        await db.execute(
            "UPDATE devices SET group_id = NULL WHERE group_id = ?",
            (group_id,)
        )
        # Delete the group
        await db.execute("DELETE FROM device_groups WHERE id = ?", (group_id,))
        await db.commit()


async def set_device_group(mac: str, group_id: Optional[int]) -> None:
    """Assign a device to a group (or remove from group if None)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET group_id = ? WHERE mac = ?",
            (group_id, mac)
        )
        await db.commit()


async def get_devices_by_group(group_id: int) -> list[Device]:
    """Get all devices in a group."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE group_id = ? ORDER BY last_seen DESC",
            (group_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


async def get_watched_devices() -> list[Device]:
    """Get all watched (devices of interest)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE watched = 1 ORDER BY last_seen DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


async def get_rssi_history(mac: str, days: int = 7) -> list[dict]:
    """Get RSSI history for a device for charting."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT timestamp, rssi
            FROM sightings
            WHERE mac = ? AND rssi IS NOT NULL AND timestamp > datetime('now', ?)
            ORDER BY timestamp ASC
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {"timestamp": row[0], "rssi": row[1]}
                for row in rows
            ]


# ============================================================================
# Dwell Time Analysis
# ============================================================================

async def get_dwell_time(mac: str, days: int = 30, gap_minutes: int = 15) -> dict:
    """Calculate dwell time statistics for a device.

    Dwell time is calculated as continuous presence periods, where gaps
    larger than gap_minutes start a new session.

    Returns:
        dict with total_minutes, session_count, avg_session_minutes,
        longest_session_minutes, sessions list
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT timestamp FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            ORDER BY timestamp ASC
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return {
            "total_minutes": 0,
            "session_count": 0,
            "avg_session_minutes": 0,
            "longest_session_minutes": 0,
            "sessions": []
        }

    # Parse timestamps and calculate sessions
    timestamps = [datetime.fromisoformat(row[0]) for row in rows]
    gap_threshold = gap_minutes * 60  # Convert to seconds

    sessions = []
    session_start = timestamps[0]
    session_end = timestamps[0]

    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - session_end).total_seconds()
        if gap > gap_threshold:
            # End current session, start new one
            duration = (session_end - session_start).total_seconds() / 60
            sessions.append({
                "start": session_start.isoformat() + "Z",
                "end": session_end.isoformat() + "Z",
                "duration_minutes": round(duration, 1)
            })
            session_start = timestamps[i]
        session_end = timestamps[i]

    # Don't forget the last session
    duration = (session_end - session_start).total_seconds() / 60
    sessions.append({
        "start": session_start.isoformat() + "Z",
        "end": session_end.isoformat() + "Z",
        "duration_minutes": round(duration, 1)
    })

    total_minutes = sum(s["duration_minutes"] for s in sessions)
    longest = max(s["duration_minutes"] for s in sessions) if sessions else 0

    return {
        "total_minutes": round(total_minutes, 1),
        "session_count": len(sessions),
        "avg_session_minutes": round(total_minutes / len(sessions), 1) if sessions else 0,
        "longest_session_minutes": round(longest, 1),
        "sessions": sessions[-10:]  # Return last 10 sessions
    }


# ============================================================================
# Device Correlation Analysis
# ============================================================================

async def get_correlated_devices(mac: str, days: int = 30, window_minutes: int = 5) -> list[dict]:
    """Find devices frequently seen around the same time as the target device.

    This helps identify devices that may belong to the same person or group.

    Args:
        mac: Target device MAC address
        days: Number of days to analyze
        window_minutes: Time window for co-occurrence (default 5 minutes)

    Returns:
        List of correlated devices with correlation score
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get all sightings of the target device
        async with db.execute(
            """
            SELECT timestamp FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            """,
            (mac, f"-{days} days")
        ) as cursor:
            target_sightings = await cursor.fetchall()

        if not target_sightings:
            return []

        target_count = len(target_sightings)

        # For each target sighting, find other devices seen within the window
        # Using a single query for efficiency
        async with db.execute(
            """
            SELECT
                s2.mac,
                d.vendor,
                d.friendly_name,
                d.device_type,
                COUNT(*) as co_occurrences,
                d.total_sightings
            FROM sightings s1
            JOIN sightings s2 ON s2.mac != s1.mac
                AND s2.timestamp BETWEEN datetime(s1.timestamp, ?) AND datetime(s1.timestamp, ?)
            JOIN devices d ON d.mac = s2.mac
            WHERE s1.mac = ?
                AND s1.timestamp > datetime('now', ?)
                AND d.ignored = 0
            GROUP BY s2.mac
            HAVING co_occurrences >= 2
            ORDER BY co_occurrences DESC
            LIMIT 20
            """,
            (f"-{window_minutes} minutes", f"+{window_minutes} minutes", mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            # Calculate correlation score (0-100)
            # Based on ratio of co-occurrences to target sightings
            correlation = min(100, round((row["co_occurrences"] / target_count) * 100))

            results.append({
                "mac": row["mac"],
                "vendor": row["vendor"],
                "friendly_name": row["friendly_name"],
                "device_type": row["device_type"],
                "co_occurrences": row["co_occurrences"],
                "total_sightings": row["total_sightings"],
                "correlation_score": correlation
            })

        return results


# ============================================================================
# Proximity Zone Helpers
# ============================================================================

def rssi_to_proximity_zone(rssi: int) -> str:
    """Convert RSSI value to a proximity zone label.

    RSSI ranges are approximate and vary by device/environment:
    - Immediate: Very close (< 1m)
    - Near: Close proximity (1-3m)
    - Far: Same room/area (3-10m)
    - Remote: Detectable but far (> 10m)
    """
    if rssi is None:
        return "unknown"
    if rssi >= -50:
        return "immediate"
    elif rssi >= -65:
        return "near"
    elif rssi >= -80:
        return "far"
    else:
        return "remote"


async def get_proximity_stats(mac: str, days: int = 7) -> dict:
    """Get proximity zone statistics for a device.

    Returns distribution of sightings across proximity zones.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT rssi FROM sightings
            WHERE mac = ? AND rssi IS NOT NULL AND timestamp > datetime('now', ?)
            """,
            (mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()

    zones = {"immediate": 0, "near": 0, "far": 0, "remote": 0}
    for row in rows:
        zone = rssi_to_proximity_zone(row[0])
        if zone in zones:
            zones[zone] += 1

    total = sum(zones.values())
    if total > 0:
        zones_pct = {k: round(v / total * 100, 1) for k, v in zones.items()}
    else:
        zones_pct = {k: 0 for k in zones}

    # Determine dominant zone
    dominant = max(zones.items(), key=lambda x: x[1])[0] if total > 0 else "unknown"

    return {
        "zones": zones,
        "zones_percent": zones_pct,
        "total_readings": total,
        "dominant_zone": dominant
    }
