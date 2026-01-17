"""Database operations for bluehood."""

import aiosqlite
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from .config import DB_PATH


@dataclass
class Device:
    """Represents a Bluetooth device."""
    mac: str
    vendor: Optional[str] = None
    friendly_name: Optional[str] = None
    ignored: bool = False
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_sightings: int = 0


@dataclass
class Sighting:
    """Represents a device sighting."""
    id: int
    mac: str
    timestamp: datetime
    rssi: Optional[int] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    vendor TEXT,
    friendly_name TEXT,
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

CREATE INDEX IF NOT EXISTS idx_sightings_mac_time ON sightings(mac, timestamp);
CREATE INDEX IF NOT EXISTS idx_sightings_timestamp ON sightings(timestamp);
"""


async def init_db() -> None:
    """Initialize the database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_device(mac: str) -> Optional[Device]:
    """Get a device by MAC address."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE mac = ?", (mac,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Device(
                    mac=row["mac"],
                    vendor=row["vendor"],
                    friendly_name=row["friendly_name"],
                    ignored=bool(row["ignored"]),
                    first_seen=datetime.fromisoformat(row["first_seen"]) if row["first_seen"] else None,
                    last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
                    total_sightings=row["total_sightings"],
                )
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
            return [
                Device(
                    mac=row["mac"],
                    vendor=row["vendor"],
                    friendly_name=row["friendly_name"],
                    ignored=bool(row["ignored"]),
                    first_seen=datetime.fromisoformat(row["first_seen"]) if row["first_seen"] else None,
                    last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
                    total_sightings=row["total_sightings"],
                )
                for row in rows
            ]


async def upsert_device(mac: str, vendor: Optional[str] = None, rssi: Optional[int] = None) -> Device:
    """Insert or update a device and record a sighting."""
    now = datetime.now()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Check if device exists
        async with db.execute("SELECT * FROM devices WHERE mac = ?", (mac,)) as cursor:
            existing = await cursor.fetchone()

        if existing:
            # Update existing device - also update vendor if we have one and device doesn't
            if vendor and not existing["vendor"]:
                await db.execute(
                    """
                    UPDATE devices
                    SET last_seen = ?, total_sightings = total_sightings + 1, vendor = ?
                    WHERE mac = ?
                    """,
                    (now.isoformat(), vendor, mac)
                )
            else:
                await db.execute(
                    """
                    UPDATE devices
                    SET last_seen = ?, total_sightings = total_sightings + 1
                    WHERE mac = ?
                    """,
                    (now.isoformat(), mac)
                )
        else:
            # Insert new device
            await db.execute(
                """
                INSERT INTO devices (mac, vendor, first_seen, last_seen, total_sightings)
                VALUES (?, ?, ?, ?, 1)
                """,
                (mac, vendor, now.isoformat(), now.isoformat())
            )

        # Record sighting
        await db.execute(
            "INSERT INTO sightings (mac, timestamp, rssi) VALUES (?, ?, ?)",
            (mac, now.isoformat(), rssi)
        )

        await db.commit()

    return await get_device(mac)


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
