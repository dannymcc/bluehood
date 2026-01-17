"""Bluetooth scanning module using bleak."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

try:
    from mac_vendor_lookup import AsyncMacLookup
    HAS_MAC_LOOKUP = True
except ImportError:
    HAS_MAC_LOOKUP = False

from .config import SCAN_DURATION

logger = logging.getLogger(__name__)


@dataclass
class ScannedDevice:
    """A device found during a scan."""
    mac: str
    name: Optional[str]
    rssi: int
    vendor: Optional[str] = None


class BluetoothScanner:
    """Bluetooth LE scanner."""

    def __init__(self):
        self._mac_lookup: Optional[AsyncMacLookup] = None
        self._vendor_cache: dict[str, Optional[str]] = {}

    async def _get_vendor(self, mac: str) -> Optional[str]:
        """Look up vendor from MAC address OUI."""
        # Check cache first
        if mac in self._vendor_cache:
            return self._vendor_cache[mac]

        if not HAS_MAC_LOOKUP:
            return None

        try:
            if self._mac_lookup is None:
                self._mac_lookup = AsyncMacLookup()

            vendor = await self._mac_lookup.lookup(mac)
            self._vendor_cache[mac] = vendor
            return vendor
        except Exception:
            # Vendor not found or lookup failed
            self._vendor_cache[mac] = None
            return None

    async def scan(self, duration: float = SCAN_DURATION) -> list[ScannedDevice]:
        """Perform a Bluetooth scan and return discovered devices."""
        devices: list[ScannedDevice] = []

        try:
            discovered = await BleakScanner.discover(
                timeout=duration,
                return_adv=True
            )

            for device, adv_data in discovered.values():
                mac = device.address
                vendor = await self._get_vendor(mac)

                devices.append(ScannedDevice(
                    mac=mac,
                    name=device.name or adv_data.local_name,
                    rssi=adv_data.rssi,
                    vendor=vendor,
                ))

            logger.info(f"Scan complete: found {len(devices)} devices")

        except Exception as e:
            logger.error(f"Scan error: {e}")

        return devices

    async def scan_continuous(
        self,
        callback: Callable[[ScannedDevice], None],
        interval: float = 10.0
    ) -> None:
        """Continuously scan and call callback for each device found."""
        while True:
            devices = await self.scan()
            for device in devices:
                callback(device)
            await asyncio.sleep(interval)
