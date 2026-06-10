"""Web server for the Bluehood dashboard."""

import hashlib
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
        self.app.router.add_get("/api/device/{mac}", self.api_device)
        self.app.router.add_post("/api/device/{mac}/watch", self.api_toggle_watch)
        self.app.router.add_post("/api/device/{mac}/group", self.api_set_device_group)
        self.app.router.add_post("/api/device/{mac}/name", self.api_set_device_name)
        self.app.router.add_get("/api/device/{mac}/rssi", self.api_device_rssi)
        self.app.router.add_get("/api/device/{mac}/dwell", self.api_device_dwell)
        self.app.router.add_get("/api/device/{mac}/correlation", self.api_device_correlation)
        self.app.router.add_get("/api/device/{mac}/proximity", self.api_device_proximity)
        self.app.router.add_post("/api/device/{mac}/notes", self.api_set_device_notes)
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

        correlated = await db.get_correlated_devices(mac, days, window_minutes)
        return web.json_response({"mac": mac, "correlated_devices": correlated})

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
