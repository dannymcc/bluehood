"""Prometheus metrics exporter for Bluehood."""

import logging
from threading import Thread
from typing import Optional

import aiosqlite
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    start_http_server,
)

from .config import DB_PATH

logger = logging.getLogger(__name__)

# Buckets tuned for typical BLE RSSI range (-100 to -30 dBm)
RSSI_BUCKETS = (-100, -95, -90, -85, -80, -75, -70, -65, -60, -55, -50, -45, -40)


class MetricsExporter:
    """Prometheus metrics exporter that runs an HTTP server on a dedicated thread."""

    def __init__(self, port: int, version: str = "unknown"):
        self.port = port

        # -- Info --
        self.build_info = Info("bluehood", "Bluehood build information")
        self.build_info.info({"version": version})

        # -- Counters --
        self.scans_total = Counter(
            "bluehood_scans_total",
            "Total Bluetooth scan cycles completed",
        )
        self.scan_errors_total = Counter(
            "bluehood_scan_errors_total",
            "Total scan errors",
            ["scan_type"],
        )
        self.sightings_total = Counter(
            "bluehood_sightings_total",
            "Total device sightings recorded",
        )
        self.new_devices_total = Counter(
            "bluehood_new_devices_total",
            "Total new unique devices discovered",
        )

        # -- Gauges --
        self.last_scan_devices = Gauge(
            "bluehood_last_scan_devices",
            "Number of devices found in the last scan cycle",
            ["scan_type"],
        )
        self.devices_total = Gauge(
            "bluehood_devices_total",
            "Total unique devices tracked in the database",
            ["bt_type"],
        )
        self.devices_active = Gauge(
            "bluehood_devices_active",
            "Devices seen in the last 5 minutes",
        )
        self.devices_watched = Gauge(
            "bluehood_devices_watched",
            "Number of watched (devices of interest) devices",
        )
        self.devices_ignored = Gauge(
            "bluehood_devices_ignored",
            "Number of ignored devices",
        )

        # -- Histograms --
        self.scan_duration = Histogram(
            "bluehood_scan_duration_seconds",
            "Wall-clock duration of a scan cycle",
            buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60),
        )
        self.device_rssi = Histogram(
            "bluehood_device_rssi_dbm",
            "RSSI distribution of scanned BLE devices",
            buckets=RSSI_BUCKETS,
        )

    def start(self) -> None:
        """Start the Prometheus HTTP server in a daemon thread."""
        start_http_server(self.port)
        logger.info(f"Prometheus metrics available at http://0.0.0.0:{self.port}/metrics")

    def on_scan_complete(
        self,
        devices: list,
        ble_count: int,
        classic_count: int,
        duration_seconds: float,
        new_count: int,
    ) -> None:
        """Called by the daemon after each scan cycle."""
        self.scans_total.inc()
        self.scan_duration.observe(duration_seconds)

        total = ble_count + classic_count
        self.last_scan_devices.labels(scan_type="ble").set(ble_count)
        self.last_scan_devices.labels(scan_type="classic").set(classic_count)
        self.last_scan_devices.labels(scan_type="total").set(total)

        self.sightings_total.inc(total)
        self.new_devices_total.inc(new_count)

        for device in devices:
            if device.rssi is not None and device.rssi != -60:
                self.device_rssi.observe(device.rssi)

    def on_scan_error(self, scan_type: str) -> None:
        """Record a scan error."""
        self.scan_errors_total.labels(scan_type=scan_type).inc()

    async def update_db_metrics(self) -> None:
        """Query the database for aggregate device counts."""
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                # Devices by bt_type
                async with conn.execute(
                    "SELECT bt_type, COUNT(*) FROM devices WHERE ignored = 0 GROUP BY bt_type"
                ) as cursor:
                    rows = await cursor.fetchall()
                for bt_type in ("ble", "classic", "both"):
                    self.devices_total.labels(bt_type=bt_type).set(0)
                for row in rows:
                    bt = row[0] or "ble"
                    self.devices_total.labels(bt_type=bt).set(row[1])

                # Active devices (seen in last 5 minutes)
                async with conn.execute(
                    "SELECT COUNT(*) FROM devices WHERE last_seen > datetime('now', '-5 minutes')"
                ) as cursor:
                    row = await cursor.fetchone()
                self.devices_active.set(row[0] if row else 0)

                # Watched devices
                async with conn.execute(
                    "SELECT COUNT(*) FROM devices WHERE watched = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                self.devices_watched.set(row[0] if row else 0)

                # Ignored devices
                async with conn.execute(
                    "SELECT COUNT(*) FROM devices WHERE ignored = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                self.devices_ignored.set(row[0] if row else 0)

        except Exception as e:
            logger.warning(f"Failed to update DB metrics: {e}")
