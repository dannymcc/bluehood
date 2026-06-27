"""Web server for the Bluehood dashboard."""

import csv
import hashlib
import io
import json
import logging
import math
import secrets
from datetime import datetime, timedelta

from aiohttp import web

from .. import db
from ..classifier import classify_device, get_type_icon, get_type_label, get_all_types, is_randomized_mac, is_macos_uuid, get_uuid_names
from ..patterns import generate_hourly_heatmap, generate_daily_heatmap
from .templates import ABOUT_TEMPLATE, HTML_TEMPLATE, LOGIN_TEMPLATE, SETTINGS_TEMPLATE

logger = logging.getLogger(__name__)

# Routes reachable without a valid session when auth is enabled. Everything
# else is gated by _auth_middleware. /api/auth/setup is allowed through so the
# initial-setup flow works; the handler itself enforces that credentials can
# only be *changed* by an already-authenticated user.
PUBLIC_PATHS = frozenset({
    "/login",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
    "/api/auth/setup",
})

# Import for type hints (will be None at runtime if not used)
try:
    from ..notifications import NotificationManager
except ImportError:
    NotificationManager = None

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}:{hash_obj.hexdigest()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, hash_value = stored_hash.split(":", 1)
    hash_obj = hashlib.sha256((salt + password).encode())
    return hash_obj.hexdigest() == hash_value


class WebServer:
    """Web server for Bluehood dashboard."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, notifications=None):
        self.host = host
        self.port = port
        self.app = web.Application(middlewares=[self._auth_middleware])
        self._notifications = notifications
        self._sessions: dict[str, datetime] = {}  # session_token -> expiry
        self._session_duration = timedelta(hours=24)
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/login", self.login_page)
        self.app.router.add_get("/settings", self.settings_page)
        self.app.router.add_get("/about", self.about_page)
        self.app.router.add_get("/api/devices", self.api_devices)
        self.app.router.add_get("/api/devices/export", self.api_export_devices)
        self.app.router.add_post("/api/devices/export", self.api_export_devices)
        self.app.router.add_get("/api/device/{mac}", self.api_device)
        self.app.router.add_post("/api/device/{mac}/watch", self.api_toggle_watch)
        self.app.router.add_post("/api/device/{mac}/group", self.api_set_device_group)
        self.app.router.add_post("/api/device/{mac}/name", self.api_set_device_name)
        self.app.router.add_get("/api/device/{mac}/rssi", self.api_device_rssi)
        self.app.router.add_get("/api/device/{mac}/dwell", self.api_device_dwell)
        self.app.router.add_get("/api/device/{mac}/correlation", self.api_device_correlation)
        self.app.router.add_get("/api/device/{mac}/rotation", self.api_device_rotation)
        self.app.router.add_get("/api/device/{mac}/proximity", self.api_device_proximity)
        self.app.router.add_post("/api/device/{mac}/notes", self.api_set_device_notes)
        self.app.router.add_get("/api/name-groups", self.api_name_groups)
        self.app.router.add_get("/api/search", self.api_search)
        self.app.router.add_get("/api/stats", self.api_stats)
        # Settings
        self.app.router.add_get("/api/settings", self.api_get_settings)
        self.app.router.add_post("/api/settings", self.api_update_settings)
        # Groups
        self.app.router.add_get("/api/groups", self.api_get_groups)
        self.app.router.add_post("/api/groups", self.api_create_group)
        self.app.router.add_put("/api/groups/{group_id}", self.api_update_group)
        self.app.router.add_delete("/api/groups/{group_id}", self.api_delete_group)
        # Authentication
        self.app.router.add_post("/api/auth/login", self.api_login)
        self.app.router.add_post("/api/auth/logout", self.api_logout)
        self.app.router.add_get("/api/auth/status", self.api_auth_status)
        self.app.router.add_post("/api/auth/setup", self.api_auth_setup)

    def _create_session(self) -> str:
        """Create a new session token."""
        token = secrets.token_urlsafe(32)
        self._sessions[token] = datetime.now() + self._session_duration
        return token

    def _validate_session(self, token: str) -> bool:
        """Check if a session token is valid."""
        if not token or token not in self._sessions:
            return False
        if datetime.now() > self._sessions[token]:
            del self._sessions[token]
            return False
        return True

    async def _check_auth(self, request: web.Request) -> bool:
        """Check if request is authenticated (when auth is enabled)."""
        settings = await db.get_settings()
        if not settings.auth_enabled:
            return True  # Auth disabled, allow all

        token = request.cookies.get("session")
        return self._validate_session(token)

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        """Default-deny: every route requires a valid session unless listed in PUBLIC_PATHS."""
        if request.path in PUBLIC_PATHS:
            return await handler(request)
        if not await self._check_auth(request):
            if request.path.startswith("/api/"):
                return web.json_response({"error": "Unauthorized"}, status=401)
            raise web.HTTPFound("/login")
        return await handler(request)

    async def index(self, request: web.Request) -> web.Response:
        """Serve the main dashboard."""
        return web.Response(text=HTML_TEMPLATE, content_type="text/html")

    async def login_page(self, request: web.Request) -> web.Response:
        """Serve the login page."""
        # If already authenticated, redirect to home
        if await self._check_auth(request):
            settings = await db.get_settings()
            if settings.auth_enabled:
                raise web.HTTPFound("/")
        return web.Response(text=LOGIN_TEMPLATE, content_type="text/html")

    async def settings_page(self, request: web.Request) -> web.Response:
        """Serve the settings page."""
        return web.Response(text=SETTINGS_TEMPLATE, content_type="text/html")

    async def about_page(self, request: web.Request) -> web.Response:
        """Serve the about page."""
        return web.Response(text=ABOUT_TEMPLATE, content_type="text/html")

    async def api_devices(self, request: web.Request) -> web.Response:
        """Get paginated devices and dashboard stats."""
        def _safe_int(value: str, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        page = max(1, _safe_int(request.query.get("page", "1"), 1))
        page_size = max(10, min(_safe_int(request.query.get("page_size", "50"), 50), 250))
        device_filter = request.query.get("filter", "all")
        search = request.query.get("search")
        sort_column = request.query.get("sort", "last_seen")
        sort_direction = request.query.get("direction", "desc")

        devices, total = await db.get_devices_page(
            page=page,
            page_size=page_size,
            include_ignored=True,
            device_filter=device_filter,
            search=search,
            sort_column=sort_column,
            sort_direction=sort_direction,
            exclude_randomized=True,
        )
        stats = await db.get_dashboard_stats(include_ignored=True)
        groups = await db.get_groups()
        group_lookup = {g.id: g for g in groups}

        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        if total > 0 and page > total_pages:
            page = total_pages
            devices, total = await db.get_devices_page(
                page=page,
                page_size=page_size,
                include_ignored=True,
                device_filter=device_filter,
                search=search,
                sort_column=sort_column,
                sort_direction=sort_direction,
                exclude_randomized=True,
            )

        device_list = []
        for d in devices:
            device_type = d.device_type or classify_device(
                d.vendor,
                d.friendly_name,
                d.service_uuids,
                d.device_class,
            )
            group = group_lookup.get(d.group_id) if d.group_id else None

            device_list.append({
                "mac": d.mac,
                "vendor": d.vendor,
                "friendly_name": d.friendly_name,
                "device_type": device_type,
                "type_icon": get_type_icon(device_type),
                "type_label": get_type_label(device_type),
                "ignored": d.ignored,
                "watched": d.watched,
                "randomized_mac": False,
                "first_seen": (d.first_seen.isoformat() + "Z") if d.first_seen else None,
                "last_seen": (d.last_seen.isoformat() + "Z") if d.last_seen else None,
                "total_sightings": d.total_sightings,
                "service_uuids": d.service_uuids,
                "uuid_names": get_uuid_names(d.service_uuids),
                "group_id": d.group_id,
                "group_name": group.name if group else None,
                "group_color": group.color if group else None,
            })

        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        return web.json_response({
            "devices": device_list,
            "total": stats["total"],
            "randomized_count": stats["randomized_count"],
            "active_today": stats["active_today"],
            "new_past_hour": stats["new_past_hour"],
            "filter_counts": stats["filter_counts"],
            "page": page,
            "page_size": page_size,
            "page_count": len(device_list),
            "total_pages": total_pages,
            "total_matching": total,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        })

    async def api_export_devices(self, request: web.Request) -> web.Response:
        """Stream a CSV export (one row per sighting) for the matching devices.

        The CSV is generated and streamed server-side so the browser downloads
        straight to disk. Building it client-side meant pulling every sighting
        into one giant JSON response (hundreds of MB on a busy sensor) and then
        concatenating an even larger string in the page — which simply never
        finished. Sightings are read in MAC batches so memory stays bounded
        regardless of history size.

        Accepts either GET query params or POST form fields. ``macs`` (a
        comma-separated allow-list) pins the export to a specific selection or
        date-filtered set; ``screenshot=1`` mirrors the dashboard's privacy
        obfuscation. POST is used for large selections that would overflow a URL.
        """
        if request.method == "POST":
            params = await request.post()
        else:
            params = request.query

        device_filter = params.get("filter", "all")
        search = params.get("search") or None
        sort_column = params.get("sort", "last_seen")
        sort_direction = params.get("direction", "desc")
        screenshot = str(params.get("screenshot", "")).lower() in ("1", "true", "yes")
        macs_param = params.get("macs")
        explicit_macs = (
            [m for m in macs_param.split(",") if m] if macs_param else None
        )

        # Export everything that matches the query, including randomized-MAC and
        # ignored devices that the dashboard hides by default.
        devices = await db.get_devices_export(
            include_ignored=True,
            device_filter=device_filter,
            search=search,
            sort_column=sort_column,
            sort_direction=sort_direction,
            exclude_randomized=False,
        )

        # A selection or date filter scopes the export to specific MACs, kept in
        # the order the client supplied them.
        if explicit_macs is not None:
            order = {m: i for i, m in enumerate(explicit_macs)}
            wanted = set(explicit_macs)
            devices = [d for d in devices if d.mac in wanted]
            devices.sort(key=lambda d: order.get(d.mac, len(order)))

        groups = await db.get_groups()
        group_lookup = {g.id: g for g in groups}

        export_format = "json" if str(params.get("format", "csv")).lower() == "json" else "csv"

        def _obfuscate_mac(mac: str) -> str:
            if not screenshot or not mac:
                return mac
            if is_macos_uuid(mac):
                return mac[:8] + "-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
            parts = mac.split(":")
            if len(parts) == 6:
                return parts[0] + ":" + parts[1] + ":XX:XX:XX:XX"
            return mac[:5] + ":XX:XX:XX:XX"

        def _obfuscate_name(name: str) -> str:
            if not screenshot or not name:
                return name
            if len(name) <= 2:
                return "**"
            return name[:2] + "*" * min(len(name) - 2, 8)

        filename = (
            "bluehood-recon-" + datetime.now().strftime("%Y-%m-%d") + "." + export_format
        )
        content_type = (
            "application/json; charset=utf-8"
            if export_format == "json"
            else "text/csv; charset=utf-8"
        )
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
        await response.prepare(request)

        if export_format == "json":
            await self._stream_devices_json(
                response, devices, group_lookup, _obfuscate_mac, _obfuscate_name
            )
        else:
            await self._stream_devices_csv(
                response, devices, group_lookup, _obfuscate_mac, _obfuscate_name
            )

        await response.write_eof()
        return response

    async def _stream_devices_csv(
        self, response, devices, group_lookup, obfuscate_mac, obfuscate_name
    ) -> None:
        """Write the device export as CSV (one row per sighting) to the stream."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")

        def _flush() -> bytes:
            data = buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)
            return data

        writer.writerow([
            "MAC", "Vendor", "Identifier", "Type", "BT_Type", "Device_Class",
            "Watched", "Ignored", "First_Seen", "Last_Seen", "Total_Sightings",
            "Group", "Service_UUIDs", "UUID_Names", "Notes",
            "Sighting_Time", "RSSI", "Proximity_Zone",
        ])
        await response.write(_flush())

        # Walk the devices in MAC batches, pulling each batch's raw sightings as
        # we go so the full history never has to live in memory at once.
        chunk = 400
        for start in range(0, len(devices), chunk):
            subset = devices[start:start + chunk]
            sightings = await db.get_sightings_for_export([d.mac for d in subset])
            sightings_by_mac: dict[str, list[dict]] = {}
            for s in sightings:
                sightings_by_mac.setdefault(s["mac"], []).append(s)

            for d in subset:
                device_type = d.device_type or classify_device(
                    d.vendor, d.friendly_name, d.service_uuids, d.device_class,
                )
                group = group_lookup.get(d.group_id) if d.group_id else None
                uuids = "; ".join(d.service_uuids) if d.service_uuids else ""
                uuid_names = "; ".join(get_uuid_names(d.service_uuids) or [])
                base = [
                    obfuscate_mac(d.mac),
                    d.vendor or "",
                    obfuscate_name(d.friendly_name) if d.friendly_name else "",
                    get_type_label(device_type) or device_type or "",
                    d.bt_type or "",
                    d.device_class if d.device_class is not None else "",
                    "Yes" if d.watched else "No",
                    "Yes" if d.ignored else "No",
                    (d.first_seen.isoformat() + "Z") if d.first_seen else "",
                    (d.last_seen.isoformat() + "Z") if d.last_seen else "",
                    d.total_sightings if d.total_sightings is not None else "",
                    group.name if group else "",
                    uuids,
                    uuid_names,
                    d.notes or "",
                ]
                device_sightings = sightings_by_mac.get(d.mac)
                if not device_sightings:
                    # Keep the device even if it has no stored sightings.
                    writer.writerow(base + ["", "", ""])
                    continue
                for s in device_sightings:
                    rssi = s.get("rssi")
                    writer.writerow(base + [
                        s.get("timestamp") or "",
                        rssi if rssi is not None else "",
                        db.rssi_to_proximity_zone(rssi),
                    ])
            await response.write(_flush())

    async def _stream_devices_json(
        self, response, devices, group_lookup, obfuscate_mac, obfuscate_name
    ) -> None:
        """Write the device export as a JSON array (sightings nested per device).

        Streamed device-by-device behind a single top-level array so the whole
        history never has to be assembled in memory, mirroring the CSV path.
        """
        await response.write(b"[")
        first = True
        chunk = 400
        for start in range(0, len(devices), chunk):
            subset = devices[start:start + chunk]
            sightings = await db.get_sightings_for_export([d.mac for d in subset])
            sightings_by_mac: dict[str, list[dict]] = {}
            for s in sightings:
                sightings_by_mac.setdefault(s["mac"], []).append(s)

            for d in subset:
                device_type = d.device_type or classify_device(
                    d.vendor, d.friendly_name, d.service_uuids, d.device_class,
                )
                group = group_lookup.get(d.group_id) if d.group_id else None
                record = {
                    "mac": obfuscate_mac(d.mac),
                    "vendor": d.vendor,
                    "identifier": obfuscate_name(d.friendly_name) if d.friendly_name else None,
                    "type": get_type_label(device_type) or device_type,
                    "device_type": device_type,
                    "bt_type": d.bt_type,
                    "device_class": d.device_class,
                    "watched": bool(d.watched),
                    "ignored": bool(d.ignored),
                    "first_seen": (d.first_seen.isoformat() + "Z") if d.first_seen else None,
                    "last_seen": (d.last_seen.isoformat() + "Z") if d.last_seen else None,
                    "total_sightings": d.total_sightings,
                    "group": group.name if group else None,
                    "service_uuids": d.service_uuids or [],
                    "uuid_names": get_uuid_names(d.service_uuids) or [],
                    "notes": d.notes or None,
                    "sightings": [
                        {
                            "timestamp": s.get("timestamp"),
                            "rssi": s.get("rssi"),
                            "proximity_zone": db.rssi_to_proximity_zone(s.get("rssi")),
                        }
                        for s in sightings_by_mac.get(d.mac, [])
                    ],
                }
                prefix = b"" if first else b","
                first = False
                await response.write(prefix + json.dumps(record).encode("utf-8"))

        await response.write(b"]")

    async def api_device(self, request: web.Request) -> web.Response:
        """Get detailed info for a single device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        hourly = await db.get_hourly_distribution(mac, 30)
        daily = await db.get_daily_distribution(mac, 30)
        sightings = await db.get_sightings(mac, 30)
        daily_timeline = await db.get_daily_sightings(mac, 30)
        device_type = device.device_type or classify_device(device.vendor, device.friendly_name, device.service_uuids, device.device_class)

        # Calculate pattern summary
        pattern = self._analyze_pattern(hourly, daily, len(sightings))

        # Calculate average RSSI from recent sightings
        rssi_values = [s.rssi for s in sightings if s.rssi is not None]
        avg_rssi = round(sum(rssi_values) / len(rssi_values)) if rssi_values else None

        # Get proximity zone from latest RSSI
        latest_rssi = rssi_values[0] if rssi_values else None
        proximity_zone = db.rssi_to_proximity_zone(latest_rssi) if latest_rssi else "unknown"

        return web.json_response({
            "device": {
                "mac": device.mac,
                "vendor": device.vendor,
                "friendly_name": device.friendly_name,
                "device_type": device_type,
                "ignored": device.ignored,
                "watched": device.watched,
                "first_seen": (device.first_seen.isoformat() + "Z") if device.first_seen else None,
                "last_seen": (device.last_seen.isoformat() + "Z") if device.last_seen else None,
                "total_sightings": device.total_sightings,
                "service_uuids": device.service_uuids,
                "notes": device.notes,
                "group_id": device.group_id,
            },
            "type_label": get_type_label(device_type),
            "uuid_names": get_uuid_names(device.service_uuids),
            "pattern": pattern,
            "avg_rssi": avg_rssi,
            "proximity_zone": proximity_zone,
            "hourly_heatmap": generate_hourly_heatmap(hourly),
            "daily_heatmap": generate_daily_heatmap(daily),
            "hourly_data": {str(k): v for k, v in hourly.items()},
            "daily_data": {str(k): v for k, v in daily.items()},
            "timeline": daily_timeline,
        })

    async def api_toggle_watch(self, request: web.Request) -> web.Response:
        """Toggle watched status for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        # Toggle the watched status
        new_status = not device.watched
        await db.set_watched(mac, new_status)

        # Update notifications manager state
        if self._notifications:
            self._notifications.update_watched_state(mac, new_status)

        return web.json_response({
            "mac": mac,
            "watched": new_status,
        })

    async def api_set_device_group(self, request: web.Request) -> web.Response:
        """Set the group for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        try:
            data = await request.json()
            group_id = data.get("group_id")  # Can be None to remove from group
            await db.set_device_group(mac, group_id)
            return web.json_response({"mac": mac, "group_id": group_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_set_device_name(self, request: web.Request) -> web.Response:
        """Set the friendly name for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        try:
            data = await request.json()
            name = data.get("name", "")
            await db.set_friendly_name(mac, name)
            return web.json_response({"mac": mac, "friendly_name": name})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_device_rssi(self, request: web.Request) -> web.Response:
        """Get RSSI history for a device."""
        mac = request.match_info["mac"]
        days = int(request.query.get("days", "7"))

        rssi_history = await db.get_rssi_history(mac, days)
        return web.json_response({"mac": mac, "rssi_history": rssi_history})

    async def api_device_dwell(self, request: web.Request) -> web.Response:
        """Get dwell time analysis for a device."""
        mac = request.match_info["mac"]
        days = int(request.query.get("days", "30"))
        gap_minutes = int(request.query.get("gap", "15"))

        dwell_data = await db.get_dwell_time(mac, days, gap_minutes)
        return web.json_response({"mac": mac, **dwell_data})

    async def api_device_correlation(self, request: web.Request) -> web.Response:
        """Get correlated devices for a device."""
        mac = request.match_info["mac"]
        days = int(request.query.get("days", "30"))
        window_minutes = int(request.query.get("window", "5"))
        gap_minutes = int(request.query.get("gap", "15"))
        edge_raw = request.query.get("edge")
        edge_minutes = int(edge_raw) if edge_raw not in (None, "") else None

        correlated = await db.get_correlated_devices(
            mac, days, window_minutes, gap_minutes, edge_minutes
        )
        return web.json_response({"mac": mac, "correlated_devices": correlated})

    async def api_device_rotation(self, request: web.Request) -> web.Response:
        """Find devices likely to be the same physical device (MAC rotation)."""
        mac = request.match_info["mac"]
        days = int(request.query.get("days", "7"))
        tolerance = int(request.query.get("tolerance", "6"))

        rotation = await db.get_rotation_candidates(mac, days, rssi_tolerance=tolerance)
        return web.json_response({"mac": mac, **rotation})

    async def api_device_proximity(self, request: web.Request) -> web.Response:
        """Get proximity zone statistics for a device."""
        mac = request.match_info["mac"]
        days = int(request.query.get("days", "7"))

        proximity = await db.get_proximity_stats(mac, days)
        return web.json_response({"mac": mac, **proximity})

    async def api_set_device_notes(self, request: web.Request) -> web.Response:
        """Set notes for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        try:
            data = await request.json()
            notes = data.get("notes", "")
            await db.set_device_notes(mac, notes if notes else None)
            return web.json_response({"mac": mac, "notes": notes})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    def _analyze_pattern(self, hourly: dict, daily: dict, sighting_count: int) -> str:
        """Simple pattern analysis from hourly/daily data."""
        if sighting_count < 5:
            return "Insufficient data"

        parts = []

        # Frequency
        avg_per_day = sighting_count / 30
        if avg_per_day >= 5:
            parts.append("Constant")
        elif avg_per_day >= 2:
            parts.append("Very frequent")
        elif avg_per_day >= 1:
            parts.append("Daily")
        elif avg_per_day >= 0.5:
            parts.append("Regular")
        elif avg_per_day >= 0.15:
            parts.append("Occasional")
        else:
            parts.append("Rare")

        # Time pattern
        if hourly:
            total = sum(hourly.values())
            morning = sum(hourly.get(h, 0) for h in range(6, 12))
            afternoon = sum(hourly.get(h, 0) for h in range(12, 18))
            evening = sum(hourly.get(h, 0) for h in range(18, 24))
            night = sum(hourly.get(h, 0) for h in range(0, 6))

            if total > 0:
                dominant = max([(morning, "mornings"), (afternoon, "afternoons"),
                               (evening, "evenings"), (night, "nights")], key=lambda x: x[0])
                if dominant[0] / total > 0.5:
                    parts.append(dominant[1])

        # Day pattern
        if daily:
            total = sum(daily.values())
            weekday = sum(daily.get(d, 0) for d in range(5))
            weekend = sum(daily.get(d, 0) for d in range(5, 7))

            if total > 0:
                if weekday / total > 0.85:
                    parts.append("weekdays only")
                elif weekend / total > 0.7:
                    parts.append("weekends only")

        return ", ".join(parts) if parts else "No clear pattern"

    async def api_name_groups(self, request: web.Request) -> web.Response:
        """List names shared by more than one MAC (MAC-randomization duplicates)."""
        include_ignored = str(request.query.get("include_ignored", "")).lower() in ("1", "true", "yes")
        groups = await db.get_name_groups(min_devices=2, include_ignored=include_ignored)
        for g in groups:
            device_type = g.get("device_type") or classify_device(g.get("vendor"), g.get("name"))
            g["device_type"] = device_type
            g["type_icon"] = get_type_icon(device_type)
            g["type_label"] = get_type_label(device_type)
        return web.json_response({"groups": groups, "total": len(groups)})

    async def api_search(self, request: web.Request) -> web.Response:
        """Search for devices seen within a datetime range."""
        start_str = request.query.get("start")
        end_str = request.query.get("end")

        start_dt = None
        end_dt = None

        try:
            if start_str:
                start_dt = datetime.fromisoformat(start_str.replace("T", " "))
            if end_str:
                end_dt = datetime.fromisoformat(end_str.replace("T", " "))
        except ValueError:
            return web.json_response({"error": "Invalid datetime format"}, status=400)

        # Search for devices with sightings in the range
        results = await db.search_devices(None, start_dt, end_dt)

        device_list = []
        for r in results:
            device_type = r.get("device_type") or classify_device(r.get("vendor"), r.get("friendly_name"), device_class=r.get("device_class"))
            device_list.append({
                "mac": r["mac"],
                "vendor": r.get("vendor"),
                "friendly_name": r.get("friendly_name"),
                "device_type": device_type,
                "type_icon": get_type_icon(device_type),
                "type_label": get_type_label(device_type),
                "ignored": r.get("ignored", False),
                "first_seen": r.get("range_first"),
                "last_seen": r.get("range_last"),
                "total_sightings": r.get("range_sightings", 0),
            })

        return web.json_response({
            "devices": device_list,
            "total": len(device_list),
            "query": {
                "start": start_str,
                "end": end_str,
            }
        })

    async def api_stats(self, request: web.Request) -> web.Response:
        """Get overall stats."""
        global_stats = await db.get_global_stats(include_ignored=True)

        return web.json_response({
            "total_devices": global_stats["total_devices"],
            "active_today": global_stats["active_today"],
            "total_sightings": global_stats["total_sightings"],
        })

    # ========================================================================
    # Settings API
    # ========================================================================

    async def api_get_settings(self, request: web.Request) -> web.Response:
        """Get all settings."""
        settings = await db.get_settings()
        return web.json_response({
            "ntfy_topic": settings.ntfy_topic or "",
            "ntfy_enabled": settings.ntfy_enabled,
            "notify_new_device": settings.notify_new_device,
            "new_device_threshold_minutes": settings.new_device_threshold_minutes,
            "notify_watched_return": settings.notify_watched_return,
            "notify_watched_leave": settings.notify_watched_leave,
            "watched_absence_minutes": settings.watched_absence_minutes,
            "watched_return_minutes": settings.watched_return_minutes,
            "heartbeat_url": settings.heartbeat_url or "",
            "heartbeat_interval": settings.heartbeat_interval,
            "prune_days": settings.prune_days,
            "prune_min_sightings": settings.prune_min_sightings,
        })

    async def api_update_settings(self, request: web.Request) -> web.Response:
        """Update settings."""
        try:
            data = await request.json()
            heartbeat_url = data.get("heartbeat_url", "").strip() or None
            settings = db.Settings(
                ntfy_topic=data.get("ntfy_topic"),
                ntfy_enabled=data.get("ntfy_enabled", False),
                notify_new_device=data.get("notify_new_device", False),
                new_device_threshold_minutes=int(data.get("new_device_threshold_minutes", 0)),
                notify_watched_return=data.get("notify_watched_return", True),
                notify_watched_leave=data.get("notify_watched_leave", True),
                watched_absence_minutes=int(data.get("watched_absence_minutes", 30)),
                watched_return_minutes=int(data.get("watched_return_minutes", 5)),
                heartbeat_url=heartbeat_url,
                heartbeat_interval=int(data.get("heartbeat_interval", 300)),
                prune_days=int(data.get("prune_days", 0)),
                prune_min_sightings=int(data.get("prune_min_sightings", 0)),
            )
            await db.update_settings(settings)

            # Reload settings in notification manager
            if self._notifications:
                await self._notifications.reload_settings()

            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ========================================================================
    # Groups API
    # ========================================================================

    async def api_get_groups(self, request: web.Request) -> web.Response:
        """Get all device groups."""
        groups = await db.get_groups()
        return web.json_response({
            "groups": [
                {"id": g.id, "name": g.name, "color": g.color, "icon": g.icon}
                for g in groups
            ]
        })

    async def api_create_group(self, request: web.Request) -> web.Response:
        """Create a new device group."""
        try:
            data = await request.json()
            name = data.get("name")
            if not name:
                return web.json_response({"error": "Name is required"}, status=400)

            group = await db.create_group(
                name=name,
                color=data.get("color", "#3b82f6"),
                icon=data.get("icon", "📁"),
            )
            return web.json_response({
                "id": group.id,
                "name": group.name,
                "color": group.color,
                "icon": group.icon,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_update_group(self, request: web.Request) -> web.Response:
        """Update a device group."""
        try:
            group_id = int(request.match_info["group_id"])
            data = await request.json()

            await db.update_group(
                group_id=group_id,
                name=data.get("name", ""),
                color=data.get("color", "#3b82f6"),
                icon=data.get("icon", "📁"),
            )
            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_delete_group(self, request: web.Request) -> web.Response:
        """Delete a device group."""
        try:
            group_id = int(request.match_info["group_id"])
            await db.delete_group(group_id)
            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ========================================================================
    # Authentication API
    # ========================================================================

    async def api_login(self, request: web.Request) -> web.Response:
        """Handle login request."""
        try:
            data = await request.json()
            username = data.get("username", "")
            password = data.get("password", "")

            settings = await db.get_settings()

            # Check if auth is enabled and credentials match
            if not settings.auth_enabled:
                return web.json_response({"error": "Auth not enabled"}, status=400)

            if (username == settings.auth_username and
                verify_password(password, settings.auth_password_hash)):
                # Create session
                token = self._create_session()
                response = web.json_response({"status": "ok"})
                response.set_cookie(
                    "session", token,
                    max_age=int(self._session_duration.total_seconds()),
                    httponly=True,
                    samesite="Lax"
                )
                return response
            else:
                return web.json_response({"error": "Invalid credentials"}, status=401)

        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_logout(self, request: web.Request) -> web.Response:
        """Handle logout request."""
        token = request.cookies.get("session")
        if token and token in self._sessions:
            del self._sessions[token]

        response = web.json_response({"status": "ok"})
        response.del_cookie("session")
        return response

    async def api_auth_status(self, request: web.Request) -> web.Response:
        """Get authentication status."""
        settings = await db.get_settings()
        authenticated = await self._check_auth(request)

        return web.json_response({
            "auth_enabled": settings.auth_enabled,
            "authenticated": authenticated,
            "username": settings.auth_username if authenticated else None,
        })

    async def api_auth_setup(self, request: web.Request) -> web.Response:
        """Setup or update authentication credentials."""
        # Only allow if already authenticated or auth is disabled
        settings = await db.get_settings()
        if settings.auth_enabled and not await self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            data = await request.json()
            enabled = data.get("enabled", False)
            username = data.get("username", "")
            password = data.get("password", "")

            if enabled:
                if not username or not password:
                    return web.json_response(
                        {"error": "Username and password required"},
                        status=400
                    )
                password_hash = hash_password(password)
            else:
                password_hash = None

            await db.update_auth_settings(
                enabled=enabled,
                username=username if enabled else None,
                password_hash=password_hash
            )

            return web.json_response({"status": "ok"})

        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def start(self) -> web.AppRunner:
        """Start the web server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"Web dashboard available at http://{self.host}:{self.port}")
        return self._runner

    async def stop(self) -> None:
        """Stop the web server."""
        if hasattr(self, '_runner') and self._runner:
            await self._runner.cleanup()
            logger.info("Web server stopped")
