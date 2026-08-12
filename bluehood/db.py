"""Database operations for bluehood."""

import bisect
import json
import logging
import re
import statistics
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from .config import DB_PATH, HEARTBEAT_URL, HEARTBEAT_INTERVAL, PRUNE_DAYS, PRUNE_MIN_SIGHTINGS

logger = logging.getLogger(__name__)


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
    new_device_notified: bool = True  # Whether new-device notification has been sent

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
    new_device_threshold_minutes: int = 0  # 0 = immediate, >0 = deferred
    # Operations settings
    heartbeat_url: Optional[str] = None       # None = disabled
    heartbeat_interval: int = 300             # seconds
    prune_days: int = 0                       # 0 = disabled
    prune_min_sightings: int = 0              # 0 = prune by age only (keep device records)
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

_CANONICAL_MAC_GLOB = (
    "[0-9A-Fa-f][0-9A-Fa-f]:[0-9A-Fa-f][0-9A-Fa-f]:[0-9A-Fa-f][0-9A-Fa-f]:"
    "[0-9A-Fa-f][0-9A-Fa-f]:[0-9A-Fa-f][0-9A-Fa-f]:[0-9A-Fa-f][0-9A-Fa-f]"
)
_RANDOMIZED_SECOND_NIBBLES = ("2", "3", "6", "7", "a", "b", "e", "f")
_DEVICE_FILTER_TYPES = {
    "phone": ("phone",),
    "laptop": ("laptop", "computer"),
    "audio": ("audio", "speaker"),
    "smart": ("smart",),
    "unknown": ("unknown",),
}


# The daemon runs the scan loop, the web server, and the prune loop in a single
# event loop, but each call below opens its own connection (each in its own
# thread). Those connections contend for SQLite's single write lock, and WAL can
# silently fall back to rollback-journal mode on some Docker bind mounts (where
# reads also block writes). Give every connection a generous busy timeout so it
# waits for the lock instead of immediately raising "database is locked".
_DB_TIMEOUT_SECONDS = 30.0


def _connect() -> aiosqlite.Connection:
    """Open a database connection sharing a common busy timeout."""
    return aiosqlite.connect(DB_PATH, timeout=_DB_TIMEOUT_SECONDS)


async def _enable_wal(db: aiosqlite.Connection) -> None:
    """Enable WAL mode and warn loudly if SQLite silently falls back.

    WAL is far more resilient to corruption on an unclean shutdown than the
    default rollback journal. The PRAGMA can be accepted but silently fall back
    to 'delete'/'truncate' mode on some filesystems (notably certain Docker
    bind mounts) — which is exactly the condition that lets an interrupted write
    leave an index out of sync with its table. Read the mode back and surface
    the fallback so it is diagnosable rather than silent.
    """
    async with db.execute("PRAGMA journal_mode=WAL") as cursor:
        row = await cursor.fetchone()
    mode = (row[0] if row else "") or ""
    if mode.lower() != "wal":
        logger.warning(
            "SQLite journal_mode is %r, not 'wal' (WAL fallback). The database "
            "is more vulnerable to corruption on unclean shutdown; check the "
            "filesystem backing %s.", mode, DB_PATH,
        )


_TREE_PAGE_RE = re.compile(r"\btree\s+(\d+)\s+page\b", re.IGNORECASE)


async def _index_rootpages(db: aiosqlite.Connection) -> dict:
    """Map each b-tree root page number to its object type ('table'/'index').

    integrity_check reports page-level damage as "Tree N page M ..." where N is
    the b-tree's root page. Resolving N back to its type lets us tell index
    corruption (rebuildable) from table corruption (data loss) when the message
    itself doesn't name an index.
    """
    async with db.execute(
        "SELECT rootpage, type FROM sqlite_master WHERE rootpage IS NOT NULL"
    ) as cursor:
        return {row[0]: row[1] for row in await cursor.fetchall()}


def _is_index_only(problems: list, roots: dict) -> bool:
    """True only if every reported problem is confined to an index b-tree.

    A line is index-related if it names an index, or points at a "Tree N" whose
    root page belongs to an index. Anything ambiguous or table-related makes this
    return False so we refuse to auto-repair and advise a restore instead.
    """
    for problem in problems:
        for line in problem.splitlines():
            line = line.strip()
            if not line or line.startswith("***"):  # section header, not a fault
                continue
            if "index" in line.lower():
                continue
            match = _TREE_PAGE_RE.search(line)
            if match and roots.get(int(match.group(1))) == "index":
                continue
            return False
    return True


async def _check_and_repair_integrity(db: aiosqlite.Connection) -> None:
    """Verify integrity at startup and self-heal index-only corruption.

    SQLite index corruption (e.g. "wrong # of entries in index ...") is fully
    recoverable from the intact table data via REINDEX, with no data loss, so we
    rebuild automatically. Corruption that touches table/page data is NOT safely
    auto-repairable; we surface it loudly and leave the file untouched for manual
    recovery from a backup.
    """
    try:
        async with db.execute("PRAGMA integrity_check") as cursor:
            rows = await cursor.fetchall()
    except aiosqlite.DatabaseError as exc:
        logger.error(
            "Integrity check could not run (%s); the database may be severely "
            "corrupt. Restore %s from a backup.", exc, DB_PATH,
        )
        return

    problems = [r[0] for r in rows if r and r[0] != "ok"]
    if not problems:
        return

    sample = "; ".join(problems[:5])
    roots = await _index_rootpages(db)
    if not _is_index_only(problems, roots):
        logger.error(
            "Database corruption detected that is NOT index-only (%d issue(s)): "
            "%s. This is not safely auto-repairable; restore %s from a backup.",
            len(problems), sample, DB_PATH,
        )
        return

    logger.warning(
        "Index corruption detected (%d issue(s)); rebuilding indexes via "
        "REINDEX: %s", len(problems), sample,
    )
    try:
        await db.execute("REINDEX")
        await db.commit()
        async with db.execute("PRAGMA integrity_check") as cursor:
            rows = await cursor.fetchall()
    except aiosqlite.DatabaseError as exc:
        logger.error("REINDEX failed (%s); restore %s from a backup.", exc, DB_PATH)
        return

    remaining = [r[0] for r in rows if r and r[0] != "ok"]
    if remaining:
        logger.error(
            "Index rebuild did not fully repair the database; %d issue(s) "
            "remain: %s. Restore %s from a backup.",
            len(remaining), "; ".join(remaining[:5]), DB_PATH,
        )
    else:
        logger.info("Database integrity restored: REINDEX successful.")


async def init_db() -> None:
    """Initialize the database schema."""
    async with _connect() as db:
        await _enable_wal(db)
        await _check_and_repair_integrity(db)
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
            ("new_device_notified", "INTEGER DEFAULT 1"),
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
        new_device_notified=bool(row["new_device_notified"]) if "new_device_notified" in keys else True,
    )


async def get_device(mac: str) -> Optional[Device]:
    """Get a device by MAC address."""
    async with _connect() as db:
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
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM devices"
        if not include_ignored:
            query += " WHERE ignored = 0"
        query += " ORDER BY last_seen DESC"

        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


def _randomized_mac_sql(column: str) -> str:
    """SQL expression for locally-administered (randomized) MAC addresses."""
    nibbles = ", ".join(f"'{n}'" for n in _RANDOMIZED_SECOND_NIBBLES)
    return (
        f"({column} GLOB '{_CANONICAL_MAC_GLOB}' "
        f"AND lower(substr({column}, 2, 1)) IN ({nibbles}))"
    )


def _build_device_query_filters(
    include_ignored: bool,
    device_filter: str,
    search: Optional[str],
    exclude_randomized: bool,
) -> tuple[str, list]:
    """Build WHERE clause and parameters for device list queries."""
    conditions: list[str] = []
    params: list = []

    if not include_ignored:
        conditions.append("d.ignored = 0")

    if exclude_randomized:
        conditions.append(f"NOT {_randomized_mac_sql('d.mac')}")

    filter_key = (device_filter or "all").strip().lower()
    if filter_key == "watched":
        conditions.append("d.watched = 1")
    elif filter_key in _DEVICE_FILTER_TYPES:
        filter_types = _DEVICE_FILTER_TYPES[filter_key]
        placeholders = ", ".join("?" for _ in filter_types)
        conditions.append(f"COALESCE(d.device_type, 'unknown') IN ({placeholders})")
        params.extend(filter_types)

    search_value = (search or "").strip()
    if search_value:
        wildcard = f"%{search_value}%"
        conditions.append(
            "(d.mac LIKE ? OR COALESCE(d.vendor, '') LIKE ? OR COALESCE(d.friendly_name, '') LIKE ?)"
        )
        params.extend([wildcard, wildcard, wildcard])

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


_DEVICE_SORT_MAP = {
    "class": "COALESCE(d.device_type, 'unknown')",
    "mac": "d.mac",
    "vendor": "COALESCE(d.vendor, '')",
    "identifier": "COALESCE(d.friendly_name, '')",
    "sightings": "d.total_sightings",
    "last_seen": "COALESCE(d.last_seen, '')",
    "group": "COALESCE(g.name, '')",
}


async def get_devices_page(
    page: int = 1,
    page_size: int = 50,
    include_ignored: bool = True,
    device_filter: str = "all",
    search: Optional[str] = None,
    sort_column: str = "last_seen",
    sort_direction: str = "desc",
    exclude_randomized: bool = True,
) -> tuple[list[Device], int]:
    """Get a single page of devices and total count for the current query."""
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 500))
    offset = (safe_page - 1) * safe_page_size

    sort_expr = _DEVICE_SORT_MAP.get(sort_column, _DEVICE_SORT_MAP["last_seen"])
    direction = "ASC" if str(sort_direction).lower() == "asc" else "DESC"

    where_clause, params = _build_device_query_filters(
        include_ignored=include_ignored,
        device_filter=device_filter,
        search=search,
        exclude_randomized=exclude_randomized,
    )

    base_query = "FROM devices d LEFT JOIN device_groups g ON g.id = d.group_id"
    order_clause = f" ORDER BY {sort_expr} {direction}, d.mac ASC"

    async with _connect() as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            f"SELECT COUNT(*) AS total {base_query}{where_clause}",
            params,
        ) as cursor:
            count_row = await cursor.fetchone()
            total = int(count_row["total"]) if count_row else 0

        page_params = [*params, safe_page_size, offset]
        async with db.execute(
            f"SELECT d.* {base_query}{where_clause}{order_clause} LIMIT ? OFFSET ?",
            page_params,
        ) as cursor:
            rows = await cursor.fetchall()
            return ([_parse_device_row(row) for row in rows], total)


async def get_devices_export(
    include_ignored: bool = True,
    device_filter: str = "all",
    search: Optional[str] = None,
    sort_column: str = "last_seen",
    sort_direction: str = "desc",
    exclude_randomized: bool = True,
) -> list[Device]:
    """Return every device matching the query (no pagination), for CSV export."""
    sort_expr = _DEVICE_SORT_MAP.get(sort_column, _DEVICE_SORT_MAP["last_seen"])
    direction = "ASC" if str(sort_direction).lower() == "asc" else "DESC"

    where_clause, params = _build_device_query_filters(
        include_ignored=include_ignored,
        device_filter=device_filter,
        search=search,
        exclude_randomized=exclude_randomized,
    )

    base_query = "FROM devices d LEFT JOIN device_groups g ON g.id = d.group_id"
    order_clause = f" ORDER BY {sort_expr} {direction}, d.mac ASC"

    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT d.* {base_query}{where_clause}{order_clause}",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


async def get_sightings_for_export(
    macs: list[str],
    days: Optional[int] = None,
) -> list[dict]:
    """Return every raw sighting (mac, timestamp, rssi) for the given devices.

    This is the un-aggregated detail behind the device export: one record per
    actual contact, not a summary. ``days`` limits to the last N days when set;
    the default (None) exports the full history. Sightings are pulled in MAC
    chunks to stay within SQLite's bound-parameter limit on large exports and
    returned ordered by MAC then time.
    """
    if not macs:
        return []

    rows_out: list[dict] = []
    chunk = 400  # well under SQLite's default bound-parameter limit

    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        for start in range(0, len(macs), chunk):
            subset = macs[start:start + chunk]
            placeholders = ", ".join("?" for _ in subset)
            where = f"mac IN ({placeholders})"
            params: list = list(subset)
            if days is not None:
                where += " AND timestamp > datetime('now', ?)"
                params.append(f"-{days} days")

            async with db.execute(
                f"""
                SELECT mac, timestamp, rssi FROM sightings
                WHERE {where}
                ORDER BY mac ASC, timestamp ASC
                """,
                params,
            ) as cursor:
                async for row in cursor:
                    rows_out.append({
                        "mac": row["mac"],
                        "timestamp": row["timestamp"],
                        "rssi": row["rssi"],
                    })

    return rows_out


async def get_dashboard_stats(include_ignored: bool = True) -> dict:
    """Get dashboard stats and server-side filter counts without loading all rows."""
    now = datetime.now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    one_hour_ago = now - timedelta(hours=1)

    randomized_sql = _randomized_mac_sql("d.mac")
    non_randomized_sql = f"NOT {randomized_sql}"
    where_clause = "" if include_ignored else "WHERE d.ignored = 0"

    query = f"""
        SELECT
            SUM(CASE WHEN {non_randomized_sql} THEN 1 ELSE 0 END) AS total,
            SUM(CASE WHEN {randomized_sql} THEN 1 ELSE 0 END) AS randomized_count,
            SUM(CASE WHEN {non_randomized_sql} AND d.last_seen >= ? THEN 1 ELSE 0 END) AS active_today,
            SUM(CASE WHEN {non_randomized_sql} AND d.first_seen >= ? THEN 1 ELSE 0 END) AS new_past_hour,
            SUM(CASE WHEN {non_randomized_sql} AND d.watched = 1 THEN 1 ELSE 0 END) AS watched_count,
            SUM(CASE WHEN {non_randomized_sql} AND COALESCE(d.device_type, 'unknown') = 'phone' THEN 1 ELSE 0 END) AS phone_count,
            SUM(CASE WHEN {non_randomized_sql} AND COALESCE(d.device_type, 'unknown') IN ('laptop', 'computer') THEN 1 ELSE 0 END) AS laptop_count,
            SUM(CASE WHEN {non_randomized_sql} AND COALESCE(d.device_type, 'unknown') IN ('audio', 'speaker') THEN 1 ELSE 0 END) AS audio_count,
            SUM(CASE WHEN {non_randomized_sql} AND COALESCE(d.device_type, 'unknown') = 'smart' THEN 1 ELSE 0 END) AS smart_count,
            SUM(CASE WHEN {non_randomized_sql} AND COALESCE(d.device_type, 'unknown') = 'unknown' THEN 1 ELSE 0 END) AS unknown_count
        FROM devices d
        {where_clause}
    """

    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (today_start.isoformat(), one_hour_ago.isoformat())) as cursor:
            row = await cursor.fetchone()

    if not row:
        return {
            "total": 0,
            "randomized_count": 0,
            "active_today": 0,
            "new_past_hour": 0,
            "filter_counts": {"all": 0, "watched": 0, "phone": 0, "laptop": 0, "audio": 0, "smart": 0, "unknown": 0},
        }

    total = int(row["total"] or 0)
    filter_counts = {
        "all": total,
        "watched": int(row["watched_count"] or 0),
        "phone": int(row["phone_count"] or 0),
        "laptop": int(row["laptop_count"] or 0),
        "audio": int(row["audio_count"] or 0),
        "smart": int(row["smart_count"] or 0),
        "unknown": int(row["unknown_count"] or 0),
    }

    return {
        "total": total,
        "randomized_count": int(row["randomized_count"] or 0),
        "active_today": int(row["active_today"] or 0),
        "new_past_hour": int(row["new_past_hour"] or 0),
        "filter_counts": filter_counts,
    }


async def get_global_stats(include_ignored: bool = True) -> dict:
    """Get global device totals without loading full row data."""
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).isoformat()
    where_clause = "" if include_ignored else "WHERE ignored = 0"

    query = f"""
        SELECT
            COUNT(*) AS total_devices,
            SUM(CASE WHEN last_seen >= ? THEN 1 ELSE 0 END) AS active_today,
            SUM(total_sightings) AS total_sightings
        FROM devices
        {where_clause}
    """

    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (today_start,)) as cursor:
            row = await cursor.fetchone()

    if not row:
        return {"total_devices": 0, "active_today": 0, "total_sightings": 0}

    return {
        "total_devices": int(row["total_devices"] or 0),
        "active_today": int(row["active_today"] or 0),
        "total_sightings": int(row["total_sightings"] or 0),
    }


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
    now = datetime.now()
    uuids_json = json.dumps(service_uuids) if service_uuids else None

    async with _connect() as db:
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
                INSERT INTO devices (mac, vendor, friendly_name, first_seen, last_seen, total_sightings, service_uuids, bt_type, device_class, new_device_notified)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, 0)
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
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET friendly_name = ? WHERE mac = ?",
            (name, mac)
        )
        await db.commit()


async def set_ignored(mac: str, ignored: bool) -> None:
    """Set whether a device is ignored."""
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET ignored = ? WHERE mac = ?",
            (1 if ignored else 0, mac)
        )
        await db.commit()


async def set_watched(mac: str, watched: bool) -> None:
    """Set whether a device is a Device of Interest (watched)."""
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET watched = ? WHERE mac = ?",
            (1 if watched else 0, mac)
        )
        await db.commit()


async def set_device_type(mac: str, device_type: str) -> None:
    """Set the device type for a device."""
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET device_type = ? WHERE mac = ?",
            (device_type, mac)
        )
        await db.commit()


async def set_device_notes(mac: str, notes: Optional[str]) -> None:
    """Set operator notes for a device."""
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET notes = ? WHERE mac = ?",
            (notes if notes else None, mac)
        )
        await db.commit()


async def mark_new_device_notified(mac: str) -> None:
    """Mark a device's new-device notification as sent."""
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET new_device_notified = 1 WHERE mac = ?",
            (mac,)
        )
        await db.commit()


async def get_sightings(mac: str, days: int = 30) -> list[Sighting]:
    """Get sightings for a device within the last N days."""
    async with _connect() as db:
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
    async with _connect() as db:
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
    async with _connect() as db:
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
    async with _connect() as db:
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
    async with _connect() as db:
        cursor = await db.execute(
            "DELETE FROM sightings WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",)
        )
        await db.commit()
        return cursor.rowcount


async def vacuum_if_fragmented(min_free_mb: float = 64.0) -> float:
    """VACUUM the database when it has accumulated free pages worth reclaiming.

    Deleting rows (e.g. pruning stale devices) frees pages inside the file but
    does not shrink the file on disk — only VACUUM does, by rewriting it. VACUUM
    is expensive and takes a brief exclusive lock, so we only run it once the
    freelist is large enough to be worth the cost. After a VACUUM the freelist
    drops back to ~0, so this self-throttles: it fires after a big prune and then
    stays quiet until fragmentation builds up again.

    Returns the approximate megabytes that were free before vacuuming (0.0 when
    skipped).
    """
    async with _connect() as db:
        async with db.execute("PRAGMA freelist_count") as cursor:
            free_pages = (await cursor.fetchone())[0]
        async with db.execute("PRAGMA page_size") as cursor:
            page_size = (await cursor.fetchone())[0]

        free_mb = free_pages * page_size / (1024 * 1024)
        if free_mb < min_free_mb:
            return 0.0

        # VACUUM cannot run inside a transaction; make sure none is open.
        await db.commit()
        await db.execute("VACUUM")
        return round(free_mb, 1)


async def prune_stale_devices(days: int, min_sightings: int) -> int:
    """Delete stale devices and all of their sightings.

    A device is pruned only when it has not been seen for more than `days`
    days AND has accumulated fewer than `min_sightings` total sightings.
    Watched devices (Devices of Interest) are never pruned. The foreign key
    on sightings is not enforced by SQLite, so the sighting rows are removed
    explicitly. Returns the number of devices deleted.

    Deletions are done in small MAC batches, each committed on its own. On a
    large database a single bulk DELETE can hold the write lock for over a
    minute, which both freezes the scanner and trips the busy timeout when the
    scanner is actively writing — so the prune would throw and silently delete
    nothing. Short, frequently-committed transactions let the scanner interleave.
    """
    if days <= 0 or min_sightings <= 0:
        return 0

    async with _connect() as db:
        cutoff = f"-{days} days"
        async with db.execute(
            """
            SELECT mac FROM devices
            WHERE COALESCE(watched, 0) = 0
              AND last_seen < datetime('now', ?)
              AND total_sightings < ?
            """,
            (cutoff, min_sightings),
        ) as cursor:
            macs = [row[0] for row in await cursor.fetchall()]

        if not macs:
            return 0

        deleted = 0
        chunk = 400  # short transactions; also stays under SQLite's bound-param limit
        for start in range(0, len(macs), chunk):
            subset = macs[start:start + chunk]
            placeholders = ", ".join("?" for _ in subset)
            await db.execute(
                f"DELETE FROM sightings WHERE mac IN ({placeholders})", subset
            )
            cursor = await db.execute(
                f"DELETE FROM devices WHERE mac IN ({placeholders})", subset
            )
            await db.commit()
            deleted += cursor.rowcount
        return deleted


async def search_devices(
    mac_filter: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[dict]:
    """
    Search for devices by MAC and/or time range.
    Returns devices with sighting count in the specified range.
    """
    async with _connect() as db:
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
                    "device_type": row["device_type"] if "device_type" in row.keys() else None,
                    "device_class": row["device_class"] if "device_class" in row.keys() else None,
                    "group_id": row["group_id"] if "group_id" in row.keys() else None,
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
    async with _connect() as db:
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
        new_device_threshold_minutes=int(settings_dict.get("new_device_threshold_minutes", "0")),
        heartbeat_url=settings_dict.get("heartbeat_url", HEARTBEAT_URL),
        heartbeat_interval=int(settings_dict.get("heartbeat_interval", str(HEARTBEAT_INTERVAL))),
        prune_days=int(settings_dict.get("prune_days", str(PRUNE_DAYS))),
        prune_min_sightings=int(settings_dict.get("prune_min_sightings", str(PRUNE_MIN_SIGHTINGS))),
        auth_enabled=settings_dict.get("auth_enabled", "0") == "1",
        auth_username=settings_dict.get("auth_username"),
        auth_password_hash=settings_dict.get("auth_password_hash"),
    )


async def set_setting(key: str, value: str) -> None:
    """Set a single setting value."""
    async with _connect() as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def update_settings(settings: Settings) -> None:
    """Update all settings from a Settings object."""
    async with _connect() as db:
        settings_pairs = [
            ("ntfy_topic", settings.ntfy_topic or ""),
            ("ntfy_enabled", "1" if settings.ntfy_enabled else "0"),
            ("notify_new_device", "1" if settings.notify_new_device else "0"),
            ("notify_watched_return", "1" if settings.notify_watched_return else "0"),
            ("notify_watched_leave", "1" if settings.notify_watched_leave else "0"),
            ("watched_absence_minutes", str(settings.watched_absence_minutes)),
            ("watched_return_minutes", str(settings.watched_return_minutes)),
            ("new_device_threshold_minutes", str(settings.new_device_threshold_minutes)),
            ("heartbeat_url", settings.heartbeat_url or ""),
            ("heartbeat_interval", str(settings.heartbeat_interval)),
            ("prune_days", str(settings.prune_days)),
            ("prune_min_sightings", str(settings.prune_min_sightings)),
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
    async with _connect() as db:
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
    async with _connect() as db:
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
    async with _connect() as db:
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
    async with _connect() as db:
        cursor = await db.execute(
            "INSERT INTO device_groups (name, color, icon) VALUES (?, ?, ?)",
            (name, color, icon)
        )
        await db.commit()
        return DeviceGroup(id=cursor.lastrowid, name=name, color=color, icon=icon)


async def update_group(group_id: int, name: str, color: str, icon: str) -> None:
    """Update a device group."""
    async with _connect() as db:
        await db.execute(
            "UPDATE device_groups SET name = ?, color = ?, icon = ? WHERE id = ?",
            (name, color, icon, group_id)
        )
        await db.commit()


async def delete_group(group_id: int) -> None:
    """Delete a device group and unassign all devices."""
    async with _connect() as db:
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
    async with _connect() as db:
        await db.execute(
            "UPDATE devices SET group_id = ? WHERE mac = ?",
            (group_id, mac)
        )
        await db.commit()


async def get_devices_by_group(group_id: int) -> list[Device]:
    """Get all devices in a group."""
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE group_id = ? ORDER BY last_seen DESC",
            (group_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


async def get_watched_devices() -> list[Device]:
    """Get all watched (devices of interest)."""
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE watched = 1 ORDER BY last_seen DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [_parse_device_row(row) for row in rows]


async def get_rssi_history(mac: str, days: int = 7) -> list[dict]:
    """Get RSSI history for a device for charting."""
    async with _connect() as db:
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
    async with _connect() as db:
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

def _sessions_from_timestamps(timestamps: list[datetime], gap_seconds: float) -> list[tuple[datetime, datetime]]:
    """Collapse a sorted list of sighting timestamps into presence sessions.

    A gap larger than ``gap_seconds`` between consecutive sightings ends the
    current session and starts a new one. Returns a list of (start, end)
    tuples — start is an "arrival" (came online), end is a "departure"
    (went offline).
    """
    if not timestamps:
        return []

    sessions: list[tuple[datetime, datetime]] = []
    start = end = timestamps[0]
    for ts in timestamps[1:]:
        if (ts - end).total_seconds() > gap_seconds:
            sessions.append((start, end))
            start = ts
        end = ts
    sessions.append((start, end))
    return sessions


def _count_aligned_events(
    target_events: list[datetime],
    candidate_events: list[datetime],
    window_seconds: float,
) -> int:
    """Count target events that have a candidate event within ``window_seconds``.

    Both lists must be sorted ascending. Each target event contributes at most
    one match, so the result is in ``[0, len(target_events)]``.
    """
    if not target_events or not candidate_events:
        return 0

    matched = 0
    for event in target_events:
        idx = bisect.bisect_left(candidate_events, event)
        # Nearest candidate event is either at idx or idx-1.
        nearest = None
        if idx < len(candidate_events):
            nearest = (candidate_events[idx] - event).total_seconds()
        if idx > 0:
            prev = (event - candidate_events[idx - 1]).total_seconds()
            nearest = prev if nearest is None else min(nearest, prev)
        if nearest is not None and nearest <= window_seconds:
            matched += 1
    return matched


async def get_correlated_devices(
    mac: str,
    days: int = 30,
    window_minutes: int = 5,
    gap_minutes: int = 15,
    edge_minutes: Optional[int] = None,
) -> list[dict]:
    """Find devices that share presence patterns with the target device.

    Two complementary signals are combined, so this surfaces devices that may
    belong to the same person or group:

    * **Co-occurrence** — how often the two devices are seen at the same time
      (within ``window_minutes``).
    * **Transition sync** — how often they come online and go offline around
      the same time. Sightings are collapsed into presence sessions (a gap
      longer than ``gap_minutes`` starts a new session); a candidate's
      session arrivals/departures are matched against the target's within
      ``edge_minutes``. This distinguishes devices that genuinely arrive and
      leave together from those that merely happen to be around a lot.

    Args:
        mac: Target device MAC address
        days: Number of days to analyze
        window_minutes: Time window for co-occurrence (default 5 minutes)
        gap_minutes: Idle gap that ends a presence session (default 15 minutes)
        edge_minutes: Tolerance for matching arrivals/departures
            (defaults to ``window_minutes``)

    Returns:
        List of correlated devices, each with a combined ``correlation_score``
        plus the ``cooccurrence_score`` and ``transition_score`` components and
        the number of synced arrivals/departures.
    """
    if edge_minutes is None:
        edge_minutes = window_minutes
    edge_seconds = edge_minutes * 60
    gap_seconds = gap_minutes * 60

    async with _connect() as db:
        db.row_factory = aiosqlite.Row

        # Get all sightings of the target device (ordered, for session building).
        async with db.execute(
            """
            SELECT timestamp FROM sightings
            WHERE mac = ? AND timestamp > datetime('now', ?)
            ORDER BY timestamp ASC
            """,
            (mac, f"-{days} days")
        ) as cursor:
            target_rows = await cursor.fetchall()

        if not target_rows:
            return []

        target_count = len(target_rows)
        target_ts = [datetime.fromisoformat(row[0]) for row in target_rows]
        target_sessions = _sessions_from_timestamps(target_ts, gap_seconds)
        target_arrivals = [s[0] for s in target_sessions]
        target_departures = [s[1] for s in target_sessions]
        target_edge_count = len(target_arrivals) + len(target_departures)

        # Candidate pool: devices co-occurring with the target. We pull a wider
        # pool than we return so transition sync can re-rank the results.
        #
        # Each window bound is computed from s1 with datetime() and rewritten to
        # the 'T'-separated form that timestamps are stored in, so the bare,
        # indexed s2.timestamp can be range-compared as a raw string. Wrapping
        # the column itself in datetime() (the obvious way to normalize) forces a
        # full scan of the sightings table per target sighting; seeking the index
        # instead turns a ~30s query into single-digit milliseconds on a large
        # database. datetime() truncates to whole seconds, so the upper bound is
        # the next second (exclusive) to keep the boundary second inclusive,
        # exactly matching the previous datetime()-on-both-sides comparison.
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
                AND s2.timestamp >= replace(datetime(s1.timestamp, ?), ' ', 'T')
                AND s2.timestamp <  replace(datetime(s1.timestamp, ?, '+1 second'), ' ', 'T')
            JOIN devices d ON d.mac = s2.mac
            WHERE s1.mac = ?
                AND s1.timestamp > datetime('now', ?)
                AND d.ignored = 0
            GROUP BY s2.mac
            HAVING co_occurrences >= 2
            ORDER BY co_occurrences DESC
            LIMIT 50
            """,
            (f"-{window_minutes} minutes", f"+{window_minutes} minutes", mac, f"-{days} days")
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            return []

        # Fetch every candidate's sightings in one pass and group by MAC so we
        # can build their presence sessions in Python.
        candidate_macs = [row["mac"] for row in rows]
        placeholders = ", ".join("?" for _ in candidate_macs)
        async with db.execute(
            f"""
            SELECT mac, timestamp FROM sightings
            WHERE mac IN ({placeholders}) AND timestamp > datetime('now', ?)
            ORDER BY mac ASC, timestamp ASC
            """,
            (*candidate_macs, f"-{days} days")
        ) as cursor:
            sighting_rows = await cursor.fetchall()

        sightings_by_mac: dict[str, list[datetime]] = {}
        for row in sighting_rows:
            sightings_by_mac.setdefault(row["mac"], []).append(
                datetime.fromisoformat(row["timestamp"])
            )

        results = []
        for row in rows:
            # Co-occurrence: ratio of co-sightings to the target's sightings.
            cooccurrence_score = min(100, round((row["co_occurrences"] / target_count) * 100))

            # Transition sync: how many of the target's arrivals/departures the
            # candidate matches with one of its own.
            cand_sessions = _sessions_from_timestamps(
                sightings_by_mac.get(row["mac"], []), gap_seconds
            )
            cand_arrivals = [s[0] for s in cand_sessions]
            cand_departures = [s[1] for s in cand_sessions]
            synced_arrivals = _count_aligned_events(target_arrivals, cand_arrivals, edge_seconds)
            synced_departures = _count_aligned_events(target_departures, cand_departures, edge_seconds)
            transition_score = (
                round(((synced_arrivals + synced_departures) / target_edge_count) * 100)
                if target_edge_count else 0
            )

            # Combined score weights co-presence and synchronized transitions
            # equally so co-travellers outrank devices that are merely always around.
            correlation = round(0.5 * cooccurrence_score + 0.5 * transition_score)

            results.append({
                "mac": row["mac"],
                "vendor": row["vendor"],
                "friendly_name": row["friendly_name"],
                "device_type": row["device_type"],
                "co_occurrences": row["co_occurrences"],
                "total_sightings": row["total_sightings"],
                "correlation_score": correlation,
                "cooccurrence_score": cooccurrence_score,
                "transition_score": transition_score,
                "synced_arrivals": synced_arrivals,
                "synced_departures": synced_departures,
            })

        results.sort(key=lambda r: (r["correlation_score"], r["co_occurrences"]), reverse=True)
        return results[:20]


def _median_ping_gap(timestamps: list[datetime]) -> Optional[float]:
    """Median seconds between consecutive sightings (a device's ping cadence).

    The median shrugs off the occasional long absence between presence
    sessions, so it reflects the typical advertising interval.
    """
    if len(timestamps) < 2:
        return None
    gaps = [
        (timestamps[i] - timestamps[i - 1]).total_seconds()
        for i in range(1, len(timestamps))
    ]
    gaps = [g for g in gaps if g > 0]
    return statistics.median(gaps) if gaps else None


async def get_rotation_candidates(
    mac: str,
    days: int = 7,
    rssi_tolerance: int = 6,
    overlap_window_seconds: int = 30,
    max_overlap_ratio: float = 0.1,
    max_handoff_seconds: int = 1800,
    min_sightings: int = 5,
) -> dict:
    """Find devices that are likely the *same physical device* as ``mac``.

    Modern devices rotate their Bluetooth MAC for privacy, so one phone shows
    up as many short-lived randomized identifiers. Two identifiers are flagged
    as likely the same device when they:

    * are both **randomized** (locally-administered) MACs,
    * **coexist in the same overall period** but are essentially never seen at
      the same instant — the old identity goes quiet as the new one appears
      (a handoff rather than two co-present devices),
    * sit at a **similar signal strength** (mean RSSI within ``rssi_tolerance``
      dB), and
    * **ping at a similar cadence**.

    This is a probabilistic heuristic, not proof — RSSI is noisy and devices at
    similar distances can coincide. Returns a dict with the target's own signal
    profile and a confidence-ranked list of candidates.
    """
    empty = {"target": None, "candidates": []}

    async with _connect() as db:
        db.row_factory = aiosqlite.Row

        # The advertised name is a strong same-device signal: some devices keep
        # a constant local name (AirPods, named accessories) while rotating MAC.
        async with db.execute(
            "SELECT friendly_name FROM devices WHERE mac = ?", (mac,)
        ) as cursor:
            name_row = await cursor.fetchone()
        target_name = ((name_row["friendly_name"] if name_row else "") or "").strip()

        async with db.execute(
            """
            SELECT timestamp, rssi FROM sightings
            WHERE mac = ? AND rssi IS NOT NULL AND timestamp > datetime('now', ?)
            ORDER BY timestamp ASC
            """,
            (mac, f"-{days} days")
        ) as cursor:
            target_rows = await cursor.fetchall()

        if len(target_rows) < min_sightings:
            return empty

        t_ts = [datetime.fromisoformat(r["timestamp"]) for r in target_rows]
        t_rssi = [r["rssi"] for r in target_rows]
        t_mean = statistics.fmean(t_rssi)
        t_std = statistics.pstdev(t_rssi) if len(t_rssi) > 1 else 0.0
        t_gap = _median_ping_gap(t_ts)
        t_first, t_last = t_ts[0], t_ts[-1]

        # Candidate pool: randomized, non-ignored devices at a comparable mean
        # RSSI, with enough sightings to be meaningful. Filtered in SQL to keep
        # the per-candidate Python work bounded. A device that shares the
        # target's exact advertised name is admitted even when its RSSI falls
        # outside the tolerance — the name is reason enough to evaluate it, and
        # the handoff/non-overlap checks below still gate it on rotation shape.
        randomized = _randomized_mac_sql("d.mac")
        params = [mac, f"-{days} days", min_sightings, t_mean, rssi_tolerance]
        name_having = ""
        if target_name:
            name_having = " OR lower(d.friendly_name) = lower(?)"
            params.append(target_name)
        async with db.execute(
            f"""
            SELECT s.mac AS mac, AVG(s.rssi) AS mean_rssi, COUNT(*) AS cnt
            FROM sightings s
            JOIN devices d ON d.mac = s.mac
            WHERE s.mac != ?
              AND s.rssi IS NOT NULL
              AND s.timestamp > datetime('now', ?)
              AND d.ignored = 0
              AND {randomized}
            GROUP BY s.mac
            HAVING cnt >= ? AND (ABS(AVG(s.rssi) - ?) <= ?{name_having})
            """,
            params
        ) as cursor:
            cand_rows = await cursor.fetchall()

        if not cand_rows:
            return {"target": _rotation_target_profile(t_mean, t_std, t_gap, len(t_ts)), "candidates": []}

        cand_macs = [r["mac"] for r in cand_rows]
        placeholders = ", ".join("?" for _ in cand_macs)
        async with db.execute(
            f"""
            SELECT mac, timestamp, rssi FROM sightings
            WHERE mac IN ({placeholders}) AND rssi IS NOT NULL
              AND timestamp > datetime('now', ?)
            ORDER BY mac ASC, timestamp ASC
            """,
            (*cand_macs, f"-{days} days")
        ) as cursor:
            sighting_rows = await cursor.fetchall()

        async with db.execute(
            f"SELECT mac, vendor, friendly_name, device_type FROM devices WHERE mac IN ({placeholders})",
            cand_macs
        ) as cursor:
            meta = {r["mac"]: r for r in await cursor.fetchall()}

    by_mac: dict[str, list] = {}
    for r in sighting_rows:
        by_mac.setdefault(r["mac"], []).append(
            (datetime.fromisoformat(r["timestamp"]), r["rssi"])
        )

    results = []
    for cmac, pts in by_mac.items():
        if len(pts) < min_sightings:
            continue
        c_ts = [p[0] for p in pts]
        c_rssi = [p[1] for p in pts]
        c_first, c_last = c_ts[0], c_ts[-1]

        # Must belong to the same continuous presence: either the active windows
        # overlap (interleaved rotation) or they sit back-to-back within a
        # handoff gap (old identity goes quiet, new one appears shortly after).
        if c_last < t_first:
            handoff_gap = (t_first - c_last).total_seconds()
        elif t_last < c_first:
            handoff_gap = (c_first - t_last).total_seconds()
        else:
            handoff_gap = 0.0
        if handoff_gap > max_handoff_seconds:
            continue

        # ...but must NOT ping simultaneously: the same physical device only
        # broadcasts one random MAC at a time.
        simultaneous = _count_aligned_events(c_ts, t_ts, overlap_window_seconds)
        overlap_ratio = simultaneous / min(len(c_ts), len(t_ts))
        if overlap_ratio > max_overlap_ratio:
            continue

        c_mean = statistics.fmean(c_rssi)
        c_std = statistics.pstdev(c_rssi) if len(c_rssi) > 1 else 0.0
        c_gap = _median_ping_gap(c_ts)

        rssi_delta = abs(c_mean - t_mean)
        rssi_sim = 1 - min(1.0, rssi_delta / rssi_tolerance)
        cadence_sim = (min(t_gap, c_gap) / max(t_gap, c_gap)) if (t_gap and c_gap) else 0.0
        separation = 1 - overlap_ratio
        base = 0.4 * rssi_sim + 0.3 * separation + 0.3 * cadence_sim

        m = meta[cmac]
        cand_name = ((m["friendly_name"] or "")).strip()
        name_match = bool(target_name) and cand_name.lower() == target_name.lower()
        # A shared advertised name floors confidence at 60 and scales the signal
        # heuristics into the top band; without it, the heuristics stand alone.
        confidence = round(100 * (0.6 + 0.4 * base)) if name_match else round(100 * base)

        results.append({
            "mac": cmac,
            "vendor": m["vendor"],
            "friendly_name": m["friendly_name"],
            "device_type": m["device_type"],
            "name_match": name_match,
            "confidence": confidence,
            "mean_rssi": round(c_mean, 1),
            "rssi_delta": round(rssi_delta, 1),
            "rssi_stddev": round(c_std, 1),
            "ping_interval_seconds": round(c_gap) if c_gap else None,
            "overlap_ratio": round(overlap_ratio, 3),
            "handoff_seconds": round(handoff_gap),
            "sightings": len(c_ts),
            "first_seen": c_first.isoformat() + "Z",
            "last_seen": c_last.isoformat() + "Z",
        })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return {
        "target": _rotation_target_profile(t_mean, t_std, t_gap, len(t_ts)),
        "candidates": results[:10],
    }


def _rotation_target_profile(mean: float, std: float, gap: Optional[float], count: int) -> dict:
    """Signal profile for the device being inspected (shown for context)."""
    return {
        "mean_rssi": round(mean, 1),
        "rssi_stddev": round(std, 1),
        "ping_interval_seconds": round(gap) if gap else None,
        "sightings": count,
    }


# ============================================================================
# Name-based Grouping
# ============================================================================

async def get_name_groups(
    min_devices: int = 2,
    include_ignored: bool = False,
) -> list[dict]:
    """Group devices that advertise the same name across different MAC addresses.

    Apple-style MAC randomization makes a single physical device surface as many
    rows that share an identical advertised name. This collapses devices by their
    exact (case-insensitive) ``friendly_name`` and returns only the names carried
    by more than one MAC, so duplicates from rotation are visible at a glance.

    Randomized MACs are intentionally included here — they are the whole point of
    the view. Each group reports how many of its members are randomized so a
    genuine rotating device (mostly randomized) reads differently from several
    distinct devices that merely happen to share a generic name.
    """
    conditions = ["friendly_name IS NOT NULL", "TRIM(friendly_name) != ''"]
    if not include_ignored:
        conditions.append("ignored = 0")
    where_clause = " AND ".join(conditions)
    randomized_count_sql = _randomized_mac_sql("mac")
    safe_min = max(2, min_devices)

    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""
            SELECT
                MIN(friendly_name) AS name,
                COUNT(*) AS device_count,
                SUM(CASE WHEN {randomized_count_sql} THEN 1 ELSE 0 END) AS randomized_count,
                SUM(COALESCE(total_sightings, 0)) AS total_sightings,
                MIN(first_seen) AS first_seen,
                MAX(last_seen) AS last_seen,
                GROUP_CONCAT(mac, '||') AS macs,
                GROUP_CONCAT(COALESCE(vendor, ''), '||') AS vendors,
                GROUP_CONCAT(COALESCE(device_type, ''), '||') AS device_types
            FROM devices
            WHERE {where_clause}
            GROUP BY lower(friendly_name)
            HAVING device_count >= ?
            ORDER BY device_count DESC, last_seen DESC
            """,
            (safe_min,),
        ) as cursor:
            rows = await cursor.fetchall()

    results = []
    for row in rows:
        macs = [m for m in (row["macs"] or "").split("||") if m]
        vendors = [v for v in (row["vendors"] or "").split("||") if v]
        types = [t for t in (row["device_types"] or "").split("||") if t]
        results.append({
            "name": row["name"],
            "device_count": int(row["device_count"] or 0),
            "randomized_count": int(row["randomized_count"] or 0),
            "total_sightings": int(row["total_sightings"] or 0),
            "first_seen": (row["first_seen"] + "Z") if row["first_seen"] else None,
            "last_seen": (row["last_seen"] + "Z") if row["last_seen"] else None,
            "macs": macs,
            "vendor": vendors[0] if vendors else None,
            "device_type": types[0] if types else None,
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
    async with _connect() as db:
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
