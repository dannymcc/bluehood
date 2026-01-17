"""Bluetooth scanning module using bleak."""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

try:
    from mac_vendor_lookup import AsyncMacLookup, MacLookup
    HAS_MAC_LOOKUP = True
except ImportError:
    HAS_MAC_LOOKUP = False

from .config import SCAN_DURATION, BLUETOOTH_ADAPTER

logger = logging.getLogger(__name__)


@dataclass
class BluetoothAdapter:
    """Represents a Bluetooth adapter."""
    name: str  # e.g., "hci0"
    address: str  # MAC address
    alias: str  # Friendly name


@dataclass
class ScannedDevice:
    """A device found during a scan."""
    mac: str
    name: Optional[str]
    rssi: int
    vendor: Optional[str] = None


def list_adapters() -> list[BluetoothAdapter]:
    """List available Bluetooth adapters."""
    adapters = []
    try:
        # Use bluetoothctl to list adapters
        result = subprocess.run(
            ["bluetoothctl", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        idx = 0
        for line in result.stdout.strip().split("\n"):
            if line.startswith("Controller"):
                parts = line.split()
                if len(parts) >= 3:
                    address = parts[1]
                    alias = " ".join(parts[2:])
                    # Assume hci naming convention
                    hci_name = f"hci{idx}"
                    idx += 1
                    adapters.append(BluetoothAdapter(
                        name=hci_name,
                        address=address,
                        alias=alias
                    ))
    except FileNotFoundError:
        logger.warning("bluetoothctl not found - install bluez-utils")
    except Exception as e:
        logger.warning(f"Could not list adapters: {e}")
    return adapters


class BluetoothScanner:
    """Bluetooth LE scanner."""

    def __init__(self, adapter: Optional[str] = None):
        self.adapter = adapter or BLUETOOTH_ADAPTER
        self._mac_lookup: Optional[AsyncMacLookup] = None
        self._vendor_cache: dict[str, Optional[str]] = {}
        self._vendors_updated = False

    async def _ensure_vendor_db(self) -> None:
        """Ensure vendor database is up to date."""
        if self._vendors_updated or not HAS_MAC_LOOKUP:
            return

        try:
            # Update vendors synchronously on first use
            logger.info("Updating MAC vendor database...")
            mac_lookup = MacLookup()
            mac_lookup.update_vendors()
            self._vendors_updated = True
            logger.info("MAC vendor database updated")
        except Exception as e:
            logger.warning(f"Could not update vendor database: {e}")
            self._vendors_updated = True  # Don't retry

    async def _get_vendor(self, mac: str) -> Optional[str]:
        """Look up vendor from MAC address OUI."""
        # Check cache first - only return if we have a successful lookup
        if mac in self._vendor_cache and self._vendor_cache[mac] is not None:
            return self._vendor_cache[mac]

        if not HAS_MAC_LOOKUP:
            return None

        try:
            if self._mac_lookup is None:
                await self._ensure_vendor_db()
                self._mac_lookup = AsyncMacLookup()

            vendor = await self._mac_lookup.lookup(mac)
            self._vendor_cache[mac] = vendor
            return vendor
        except Exception:
            # Vendor not found - don't cache so we can retry later
            # (vendor database may be updated)
            return None

    async def scan(self, duration: float = SCAN_DURATION) -> list[ScannedDevice]:
        """Perform a Bluetooth scan and return discovered devices."""
        devices: list[ScannedDevice] = []

        try:
            # Build scanner kwargs
            kwargs = {
                "timeout": duration,
                "return_adv": True,
            }
            if self.adapter:
                kwargs["adapter"] = self.adapter

            discovered = await BleakScanner.discover(**kwargs)

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
