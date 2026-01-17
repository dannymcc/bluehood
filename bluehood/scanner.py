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
    from mac_vendor_lookup import AsyncMacLookup
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
        for line in result.stdout.strip().split("\n"):
            if line.startswith("Controller"):
                parts = line.split()
                if len(parts) >= 3:
                    address = parts[1]
                    alias = " ".join(parts[2:])
                    # Try to get hci name
                    hci_result = subprocess.run(
                        ["hcitool", "dev"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    hci_name = "hci0"  # default
                    for hci_line in hci_result.stdout.strip().split("\n"):
                        if address in hci_line:
                            hci_name = hci_line.split()[0]
                            break
                    adapters.append(BluetoothAdapter(
                        name=hci_name,
                        address=address,
                        alias=alias
                    ))
    except Exception as e:
        logger.warning(f"Could not list adapters: {e}")
    return adapters


class BluetoothScanner:
    """Bluetooth LE scanner."""

    def __init__(self, adapter: Optional[str] = None):
        self.adapter = adapter or BLUETOOTH_ADAPTER
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
