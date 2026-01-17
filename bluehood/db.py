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
        # Check if device exists
        async with db.execute("SELECT * FROM devices WHERE mac = ?", (mac,)) as cursor:
            existing = await cursor.fetchone()

        if existing:
            # Update existing device
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
