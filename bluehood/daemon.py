"""Bluehood daemon - continuous Bluetooth scanning service."""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from . import db
from .config import SCAN_INTERVAL, SOCKET_PATH
from .scanner import BluetoothScanner, ScannedDevice, list_adapters
from .web import WebServer
from .notifications import NotificationManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class BluehoodDaemon:
    """Main daemon process for Bluetooth scanning."""

    def __init__(self, adapter: Optional[str] = None, web_port: Optional[int] = None):
        self.scanner = BluetoothScanner(adapter=adapter)
        self.running = False
        self.clients: list[asyncio.StreamWriter] = []
        self._server: asyncio.Server | None = None
        self._web_port = web_port
        self._web_server: WebServer | None = None
        self._notifications = NotificationManager()

    async def start(self) -> None:
        """Start the daemon."""
        logger.info("Starting bluehood daemon...")

        # Initialize database
        await db.init_db()
        logger.info(f"Database initialized at {db.DB_PATH}")

        # Initialize notifications
        await self._notifications.start()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Start socket server for TUI communication
        await self._start_socket_server()

        # Start web server if port specified
        if self._web_port:
            self._web_server = WebServer(port=self._web_port, notifications=self._notifications)
            await self._web_server.start()
            logger.info(f"Web dashboard available at http://0.0.0.0:{self._web_port}")

        # Start scanning and absence checking
        self.running = True
        asyncio.create_task(self._absence_check_loop())
        await self._scan_loop()

    async def stop(self) -> None:
        """Stop the daemon."""
        logger.info("Stopping bluehood daemon...")
        self.running = False

        # Close all client connections
        for writer in self.clients:
            writer.close()
            await writer.wait_closed()

        # Close socket server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Stop web server
        if self._web_server:
            await self._web_server.stop()

        # Stop notifications
        await self._notifications.stop()

        # Remove socket file
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        logger.info("Daemon stopped")

    async def _start_socket_server(self) -> None:
        """Start Unix socket server for TUI clients."""
        # Remove stale socket
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(SOCKET_PATH)
        )
        # Make socket accessible
        os.chmod(SOCKET_PATH, 0o666)
        logger.info(f"Socket server listening at {SOCKET_PATH}")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle a TUI client connection."""
        self.clients.append(writer)
        logger.info("TUI client connected")

        try:
            while self.running:
                data = await reader.readline()
                if not data:
                    break

                try:
                    request = json.loads(data.decode())
                    response = await self._handle_request(request)
                    writer.write(json.dumps(response).encode() + b"\n")
                    await writer.drain()
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from client")
                except Exception as e:
                    logger.error(f"Error handling request: {e}")

        except asyncio.CancelledError:
            pass
        finally:
            self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()
            logger.info("TUI client disconnected")

    async def _handle_request(self, request: dict) -> dict:
        """Handle a request from a TUI client."""
        cmd = request.get("cmd")

        if cmd == "list":
            include_ignored = request.get("include_ignored", True)
            devices = await db.get_all_devices(include_ignored)

            # Auto-classify devices that don't have a type
            from .classifier import classify_device
            device_list = []
            for d in devices:
                device_type = d.device_type
                if not device_type:
                    device_type = classify_device(d.vendor, d.friendly_name, d.service_uuids, d.device_class)
                    # Store the auto-classified type
                    if device_type != "unknown":
                        await db.set_device_type(d.mac, device_type)

                device_list.append({
                    "mac": d.mac,
                    "vendor": d.vendor,
                    "friendly_name": d.friendly_name,
                    "device_type": device_type,
                    "ignored": d.ignored,
                    "first_seen": (d.first_seen.isoformat() + "Z") if d.first_seen else None,
                    "last_seen": (d.last_seen.isoformat() + "Z") if d.last_seen else None,
                    "total_sightings": d.total_sightings,
                })

            return {"status": "ok", "devices": device_list}

        elif cmd == "set_name":
            mac = request.get("mac")
            name = request.get("name")
            if mac and name is not None:
                await db.set_friendly_name(mac, name)
                return {"status": "ok"}
            return {"status": "error", "message": "Missing mac or name"}

        elif cmd == "set_ignored":
            mac = request.get("mac")
            ignored = request.get("ignored", False)
            if mac:
                await db.set_ignored(mac, ignored)
                return {"status": "ok"}
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "set_device_type":
            mac = request.get("mac")
            device_type = request.get("device_type")
            if mac and device_type:
                await db.set_device_type(mac, device_type)
                return {"status": "ok"}
            return {"status": "error", "message": "Missing mac or device_type"}

        elif cmd == "get_device_types":
            from .classifier import get_all_types
            types = get_all_types()
            return {
                "status": "ok",
                "types": [{"id": t[0], "icon": t[1], "label": t[2]} for t in types]
            }

        elif cmd == "get_sightings":
            mac = request.get("mac")
            days = request.get("days", 30)
            if mac:
                sightings = await db.get_sightings(mac, days)
                return {
                    "status": "ok",
                    "sightings": [
                        {
                            "timestamp": s.timestamp.isoformat() + "Z",
                            "rssi": s.rssi,
                        }
                        for s in sightings
                    ]
                }
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "get_hourly":
            mac = request.get("mac")
            days = request.get("days", 30)
            if mac:
                hourly = await db.get_hourly_distribution(mac, days)
                return {"status": "ok", "hourly": hourly}
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "get_daily":
            mac = request.get("mac")
            days = request.get("days", 30)
            if mac:
                daily = await db.get_daily_distribution(mac, days)
                return {"status": "ok", "daily": daily}
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "search":
            mac_filter = request.get("mac")
            start_time = request.get("start_time")
            end_time = request.get("end_time")

            # Parse datetime strings if provided
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_time) if start_time else None
            end_dt = datetime.fromisoformat(end_time) if end_time else None

            results = await db.search_devices(mac_filter, start_dt, end_dt)
            return {
                "status": "ok",
                "results": results,
            }

        elif cmd == "status":
            return {
                "status": "ok",
                "running": self.running,
                "clients": len(self.clients),
            }

        elif cmd == "set_notes":
            mac = request.get("mac")
            notes = request.get("notes")
            if mac:
                await db.set_device_notes(mac, notes)
                return {"status": "ok"}
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "get_dwell_time":
            mac = request.get("mac")
            days = request.get("days", 30)
            gap_minutes = request.get("gap_minutes", 15)
            if mac:
                dwell = await db.get_dwell_time(mac, days, gap_minutes)
                return {"status": "ok", "dwell_time": dwell}
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "get_correlated_devices":
            mac = request.get("mac")
            days = request.get("days", 30)
            window_minutes = request.get("window_minutes", 5)
            if mac:
                correlated = await db.get_correlated_devices(mac, days, window_minutes)
                return {"status": "ok", "correlated_devices": correlated}
            return {"status": "error", "message": "Missing mac"}

        elif cmd == "get_proximity_stats":
            mac = request.get("mac")
            days = request.get("days", 7)
            if mac:
                stats = await db.get_proximity_stats(mac, days)
                return {"status": "ok", "proximity_stats": stats}
            return {"status": "error", "message": "Missing mac"}

        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        logger.info(f"Starting scan loop (interval: {SCAN_INTERVAL}s)")

        while self.running:
            try:
                devices = await self.scanner.scan()

                for device in devices:
                    db_device, is_new = await db.upsert_device(
                        mac=device.mac,
                        vendor=device.vendor,
                        friendly_name=device.name,
                        rssi=device.rssi,
                        service_uuids=device.service_uuids,
                        bt_type=device.bt_type,
                        device_class=device.device_class,
                    )

                    # Trigger notification checks
                    await self._notifications.on_device_seen(db_device, is_new)

                # Notify connected clients
                await self._notify_clients({
                    "event": "scan_complete",
                    "count": len(devices),
                })

            except Exception as e:
                logger.error(f"Scan error: {e}")

            await asyncio.sleep(SCAN_INTERVAL)

    async def _absence_check_loop(self) -> None:
        """Periodically check for absent watched devices."""
        while self.running:
            try:
                await self._notifications.check_absent_devices()
            except Exception as e:
                logger.error(f"Absence check error: {e}")
            await asyncio.sleep(60)  # Check every minute

    async def _notify_clients(self, event: dict) -> None:
        """Send an event to all connected clients."""
        data = json.dumps(event).encode() + b"\n"
        for writer in self.clients:
            try:
                writer.write(data)
                await writer.drain()
            except Exception:
                pass  # Client might have disconnected


def main() -> None:
    """Entry point for bluehood-daemon."""
    parser = argparse.ArgumentParser(
        description="Bluehood Bluetooth neighborhood monitor daemon"
    )
    parser.add_argument(
        "-a", "--adapter",
        help="Bluetooth adapter to use (e.g., hci0)"
    )
    parser.add_argument(
        "-l", "--list-adapters",
        action="store_true",
        help="List available Bluetooth adapters and exit"
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable web dashboard"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Web dashboard port (default: 8080)"
    )
    args = parser.parse_args()

    if args.list_adapters:
        adapters = list_adapters()
        if adapters:
            print("Available Bluetooth adapters:")
            for adapter in adapters:
                print(f"  {adapter.name}: {adapter.address} ({adapter.alias})")
        else:
            print("No Bluetooth adapters found")
        return

    web_port = None if args.no_web else args.port
    daemon = BluehoodDaemon(adapter=args.adapter, web_port=web_port)
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
