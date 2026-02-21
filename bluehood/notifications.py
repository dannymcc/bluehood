"""Notification system using ntfy.sh for push notifications."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

from . import db
from .db import Device, Settings

logger = logging.getLogger(__name__)

# ntfy.sh base URL
NTFY_BASE_URL = "https://ntfy.sh"


class NotificationManager:
    """Manages push notifications via ntfy.sh."""

    def __init__(self):
        self._settings: Optional[Settings] = None
        self._watched_last_seen: dict[str, datetime] = {}  # MAC -> last seen time
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Initialize the notification manager."""
        self._settings = await db.get_settings()
        self._session = aiohttp.ClientSession()

        # Load current state of watched devices
        watched = await db.get_watched_devices()
        for device in watched:
            if device.last_seen:
                self._watched_last_seen[device.mac] = device.last_seen

        logger.info(f"Notification manager started (enabled={self._settings.ntfy_enabled})")

    async def stop(self) -> None:
        """Cleanup the notification manager."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("Notification manager stopped")

    async def reload_settings(self) -> None:
        """Reload settings from database."""
        self._settings = await db.get_settings()
        logger.info(f"Notification settings reloaded (enabled={self._settings.ntfy_enabled})")

    async def _send_notification(
        self,
        title: str,
        message: str,
        priority: int = 3,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Send a notification via ntfy.sh.

        Priority levels: 1=min, 2=low, 3=default, 4=high, 5=urgent
        """
        if not self._settings or not self._settings.ntfy_enabled:
            return False

        if not self._settings.ntfy_topic:
            logger.warning("Notifications enabled but no topic configured")
            return False

        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{NTFY_BASE_URL}/{self._settings.ntfy_topic}"

        headers = {
            "Title": title,
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = ",".join(tags)

        try:
            async with self._session.post(
                url,
                data=message,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    logger.info(f"Notification sent: {title}")
                    return True
                else:
                    logger.warning(f"Notification failed: {response.status}")
                    return False
        except asyncio.TimeoutError:
            logger.warning("Notification timeout")
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return False

    async def on_device_seen(self, device: Device, is_new: bool) -> None:
        """Handle a device being seen during a scan.

        This is called after every device sighting to check for notification triggers.
        """
        if not self._settings or not self._settings.ntfy_enabled:
            return

        now = datetime.now(tz=timezone.utc)

        # Check for new device notification
        if is_new and self._settings.notify_new_device:
            name = device.friendly_name or device.vendor or device.mac
            await self._send_notification(
                title="New Device Detected",
                message=f"{name} ({device.mac})\nType: {device.device_type or 'Unknown'}",
                priority=3,
                tags=["new", "bluetooth"],
            )
            return

        # Check for watched device notifications
        if device.watched:
            prev_seen = self._watched_last_seen.get(device.mac)

            if prev_seen:
                minutes_absent = (now - prev_seen).total_seconds() / 60

                # Device returning after absence
                if (self._settings.notify_watched_return and
                        minutes_absent >= self._settings.watched_return_minutes):
                    name = device.friendly_name or device.vendor or device.mac
                    absence_str = self._format_duration(minutes_absent)
                    await self._send_notification(
                        title="Watched Device Returned",
                        message=f"{name} is back\nWas absent for {absence_str}",
                        priority=4,
                        tags=["loudspeaker", "bluetooth"],
                    )

            # Update last seen time
            self._watched_last_seen[device.mac] = now

    async def check_absent_devices(self) -> None:
        """Check for watched devices that have been absent too long.

        This should be called periodically (e.g., every minute).
        """
        if not self._settings or not self._settings.ntfy_enabled:
            return

        if not self._settings.notify_watched_leave:
            return

        now = datetime.now(tz=timezone.utc)
        threshold = timedelta(minutes=self._settings.watched_absence_minutes)

        # Get all watched devices
        watched = await db.get_watched_devices()

        for device in watched:
            if not device.last_seen:
                continue

            # Check if device has been absent longer than threshold
            if now - device.last_seen >= threshold:
                # Only notify once per absence (check if we already notified)
                notified_key = f"notified_absent_{device.mac}"
                last_notified = self._watched_last_seen.get(notified_key)

                if last_notified and (now - last_notified).total_seconds() < 3600:
                    # Already notified within the last hour
                    continue

                name = device.friendly_name or device.vendor or device.mac
                absence_str = self._format_duration(
                    (now - device.last_seen).total_seconds() / 60
                )
                await self._send_notification(
                    title="Watched Device Left",
                    message=f"{name} hasn't been seen for {absence_str}",
                    priority=3,
                    tags=["wave", "bluetooth"],
                )

                # Mark as notified
                self._watched_last_seen[notified_key] = now

    def _format_duration(self, minutes: float) -> str:
        """Format a duration in minutes to a human-readable string."""
        if minutes < 60:
            m = int(minutes)
            return f"{m} minute{'s' if m != 1 else ''}"
        elif minutes < 1440:
            hours = minutes / 60
            return f"{hours:.1f} hours"
        else:
            days = minutes / 1440
            return f"{days:.1f} days"

    def update_watched_state(self, mac: str, watched: bool) -> None:
        """Update internal state when a device's watched status changes."""
        if watched:
            self._watched_last_seen[mac] = datetime.now(tz=timezone.utc)
        else:
            self._watched_last_seen.pop(mac, None)
            self._watched_last_seen.pop(f"notified_absent_{mac}", None)
