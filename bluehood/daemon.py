"""Bluehood daemon - continuous Bluetooth scanning service."""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path

from . import db
from .config import SCAN_INTERVAL, SOCKET_PATH
from .scanner import BluetoothScanner, ScannedDevice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class BluehoodDaemon:
    """Main daemon process for Bluetooth scanning."""

    def __init__(self):
        self.scanner = BluetoothScanner()
        self.running = False
        self.clients: list[asyncio.StreamWriter] = []
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the daemon."""
        logger.info("Starting bluehood daemon...")

        # Initialize database
        await db.init_db()
        logger.info(f"Database initialized at {db.DB_PATH}")

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Start socket server for TUI communication
        await self._start_socket_server()

        # Start scanning
        self.running = True
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
            return {
                "status": "ok",
                "devices": [
                    {
                        "mac": d.mac,
                        "vendor": d.vendor,
                        "friendly_name": d.friendly_name,
                        "ignored": d.ignored,
                        "first_seen": d.first_seen.isoformat() if d.first_seen else None,
                        "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                        "total_sightings": d.total_sightings,
                    }
                    for d in devices
                ]
            }

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

        elif cmd == "get_sightings":
            mac = request.get("mac")
            days = request.get("days", 30)
            if mac:
                sightings = await db.get_sightings(mac, days)
                return {
                    "status": "ok",
                    "sightings": [
                        {
                            "timestamp": s.timestamp.isoformat(),
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

        elif cmd == "status":
            return {
                "status": "ok",
                "running": self.running,
                "clients": len(self.clients),
            }

        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        logger.info(f"Starting scan loop (interval: {SCAN_INTERVAL}s)")

        while self.running:
            try:
                devices = await self.scanner.scan()

                for device in devices:
                    await db.upsert_device(
                        mac=device.mac,
                        vendor=device.vendor,
                        rssi=device.rssi
                    )

                # Notify connected clients
                await self._notify_clients({
                    "event": "scan_complete",
                    "count": len(devices),
                })

            except Exception as e:
                logger.error(f"Scan error: {e}")

            await asyncio.sleep(SCAN_INTERVAL)

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
    daemon = BluehoodDaemon()
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
