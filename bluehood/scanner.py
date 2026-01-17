"""Bluetooth scanning module using bleak."""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

import aiohttp
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

try:
    from mac_vendor_lookup import AsyncMacLookup, MacLookup
    HAS_MAC_LOOKUP = True
except ImportError:
    HAS_MAC_LOOKUP = False

# Online API for vendor lookup fallback
MACVENDORS_API_URL = "https://api.macvendors.com/"

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

    def _is_randomized_mac(self, mac: str) -> bool:
        """Check if MAC address is locally administered (randomized).

        The second-least-significant bit of the first byte indicates
        locally administered addresses (randomized for privacy).
        """
        try:
            first_byte = int(mac.split(":")[0], 16)
            return bool(first_byte & 0x02)  # Check bit 1
        except (ValueError, IndexError):
            return False

    async def _get_vendor(self, mac: str) -> Optional[str]:
        """Look up vendor from MAC address OUI."""
        # Skip randomized MACs - they won't have vendors
        if self._is_randomized_mac(mac):
            return None

        # Check cache first - only return if we have a successful lookup
        if mac in self._vendor_cache and self._vendor_cache[mac] is not None:
            return self._vendor_cache[mac]

        vendor = None

        # Try local database first
        if HAS_MAC_LOOKUP:
            try:
                if self._mac_lookup is None:
                    await self._ensure_vendor_db()
                    self._mac_lookup = AsyncMacLookup()

                vendor = await self._mac_lookup.lookup(mac)
            except Exception:
                pass  # Fall through to online API

        # Fallback to online API if local lookup failed
        if vendor is None:
            vendor = await self._get_vendor_online(mac)

        if vendor:
            self._vendor_cache[mac] = vendor

        return vendor

    async def _get_vendor_online(self, mac: str) -> Optional[str]:
        """Look up vendor using MACVendors.com API."""
        # Rate limit: 1 request per second
        if hasattr(self, '_last_api_call'):
            elapsed = asyncio.get_event_loop().time() - self._last_api_call
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{MACVENDORS_API_URL}{mac}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    self._last_api_call = asyncio.get_event_loop().time()
                    if response.status == 200:
                        vendor = await response.text()
                        return vendor.strip() if vendor else None
                    elif response.status == 404:
                        return None  # MAC not found in database
                    elif response.status == 429:
                        logger.debug("Vendor API rate limited")
                        return None
                    else:
                        return None
        except asyncio.TimeoutError:
            logger.debug(f"Vendor API timeout for {mac}")
            return None
        except Exception as e:
            logger.debug(f"Vendor API error for {mac}: {e}")
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
