"""Bluetooth scanning module using bleak (BLE) and hcitool (classic)."""

import asyncio
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

import aiohttp
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

try:
    from mac_vendor_lookup import AsyncMacLookup, MacLookup, BaseMacLookup
    HAS_MAC_LOOKUP = True
except ImportError:
    HAS_MAC_LOOKUP = False

# Online API for vendor lookup fallback
MACVENDORS_API_URL = "https://api.macvendors.com/"

from .classifier import is_macos_uuid
from .config import SCAN_DURATION, BLUETOOTH_ADAPTER, DATA_DIR

logger = logging.getLogger(__name__)

# Configure mac-vendor-lookup to use BLUEHOOD_DATA_DIR for caching
if HAS_MAC_LOOKUP:
    BaseMacLookup.cache_path = str(DATA_DIR / "mac-vendors.txt")


# Bluetooth device class codes for classification
# See: https://www.bluetooth.com/specifications/assigned-numbers/baseband/
BT_CLASS_MAJOR = {
    0x01: "computer",
    0x02: "phone",
    0x03: "network",  # LAN/Network Access Point
    0x04: "audio",    # Audio/Video
    0x05: "peripheral",  # Keyboard, mouse, etc.
    0x06: "imaging",  # Printer, scanner, camera
    0x07: "wearable",
    0x08: "toy",
    0x09: "health",
}

BT_CLASS_MINOR_AUDIO = {
    0x01: "headset",
    0x02: "handsfree",
    0x04: "microphone",
    0x05: "speaker",
    0x06: "headphones",
    0x07: "portable_audio",
    0x08: "car_audio",
}

BT_CLASS_MINOR_PHONE = {
    0x01: "cellular",
    0x02: "cordless",
    0x03: "smartphone",
}


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
    service_uuids: list[str] = None  # BLE service UUIDs for fingerprinting
    bt_type: str = "ble"  # "ble" or "classic"
    device_class: Optional[int] = None  # Classic Bluetooth device class

    def __post_init__(self):
        if self.service_uuids is None:
            self.service_uuids = []


def parse_device_class(device_class: int) -> tuple[str, Optional[str]]:
    """Parse Bluetooth device class into major and minor categories."""
    if device_class is None:
        return "unknown", None

    # Major device class is bits 8-12
    major = (device_class >> 8) & 0x1F
    # Minor device class is bits 2-7
    minor = (device_class >> 2) & 0x3F

    major_type = BT_CLASS_MAJOR.get(major, "unknown")

    minor_type = None
    if major == 0x04:  # Audio
        minor_type = BT_CLASS_MINOR_AUDIO.get(minor)
    elif major == 0x02:  # Phone
        minor_type = BT_CLASS_MINOR_PHONE.get(minor)

    return major_type, minor_type


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
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _ensure_vendor_db(self) -> None:
        """Ensure vendor database is up to date."""
        if self._vendors_updated or not HAS_MAC_LOOKUP:
            return

        try:
            # Run the sync update in a thread pool to avoid event loop conflict
            logger.info("Updating MAC vendor database...")

            def update_sync():
                mac_lookup = MacLookup()
                mac_lookup.update_vendors()

            await asyncio.to_thread(update_sync)
            self._vendors_updated = True
            logger.info("MAC vendor database updated")
        except Exception as e:
            logger.warning(f"Could not update vendor database: {e}")
            self._vendors_updated = True  # Don't retry

    def _is_randomized_mac(self, mac: str) -> bool:
        """Check if MAC address is locally administered (randomized).

        The second-least-significant bit of the first byte indicates
        locally administered addresses (randomized for privacy).

        Returns False for macOS UUID-format addresses since the
        bit-checking logic is not applicable to UUIDs.
        """
        if is_macos_uuid(mac):
            return False
        try:
            first_byte = int(mac.split(":")[0], 16)
            return bool(first_byte & 0x02)  # Check bit 1
        except (ValueError, IndexError):
            return False

    async def _get_vendor(self, mac: str) -> Optional[str]:
        """Look up vendor from MAC address OUI."""
        # macOS UUIDs have no OUI - skip vendor lookup
        if is_macos_uuid(mac):
            return None

        # Skip randomized MACs - they won't have vendors
        if self._is_randomized_mac(mac):
            return None

        # Check cache first (includes negative results)
        if mac in self._vendor_cache:
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

        # Cache both positive and negative results to avoid repeated lookups
        self._vendor_cache[mac] = vendor

        return vendor

    async def _get_vendor_online(self, mac: str) -> Optional[str]:
        """Look up vendor using MACVendors.com API.

        Only sends the OUI (first 3 bytes) to protect privacy.
        """
        # Extract OUI (first 3 bytes / 6 hex chars) for privacy
        oui = mac[:8]  # e.g., "AA:BB:CC"

        # Rate limit: 1 request per second
        if hasattr(self, '_last_api_call'):
            elapsed = asyncio.get_running_loop().time() - self._last_api_call
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

        try:
            if self._http_session is None or self._http_session.closed:
                self._http_session = aiohttp.ClientSession()
            async with self._http_session.get(
                f"{MACVENDORS_API_URL}{oui}",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                self._last_api_call = asyncio.get_running_loop().time()
                if response.status == 200:
                    vendor = await response.text()
                    return vendor.strip() if vendor else None
                elif response.status == 404:
                    return None  # OUI not found in database
                elif response.status == 429:
                    logger.debug("Vendor API rate limited")
                    return None
                else:
                    return None
        except asyncio.TimeoutError:
            logger.debug(f"Vendor API timeout for {oui}")
            return None
        except Exception as e:
            logger.debug(f"Vendor API error for {oui}: {e}")
            return None

    async def scan_ble(self, duration: float = SCAN_DURATION) -> list[ScannedDevice]:
        """Perform a Bluetooth LE scan."""
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

                # Capture service UUIDs for device fingerprinting
                service_uuids = list(adv_data.service_uuids) if adv_data.service_uuids else []

                devices.append(ScannedDevice(
                    mac=mac,
                    name=device.name or adv_data.local_name,
                    rssi=adv_data.rssi,
                    vendor=vendor,
                    service_uuids=service_uuids,
                    bt_type="ble",
                ))

            logger.debug(f"BLE scan: found {len(devices)} devices")

        except Exception as e:
            logger.error(f"BLE scan error: {e}")

        return devices

    async def scan_classic(self, duration: int = 8) -> list[ScannedDevice]:
        """Perform a classic Bluetooth inquiry scan using hcitool.

        Duration is in 1.28 second units (8 = ~10 seconds).
        """
        devices: list[ScannedDevice] = []

        try:
            # Use hcitool for classic Bluetooth inquiry
            adapter_arg = ["-i", self.adapter] if self.adapter else []

            # Run inquiry scan
            proc = await asyncio.create_subprocess_exec(
                "hcitool", *adapter_arg, "inq", "--length", str(duration),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=duration * 1.28 + 5  # Wait for scan + buffer
            )

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                # Don't log error if it's just "Device not configured" - adapter might not support inquiry
                if "not configured" not in error_msg.lower():
                    logger.debug(f"Classic scan unavailable: {error_msg}")
                return devices

            # Parse hcitool output
            # Format: "	XX:XX:XX:XX:XX:XX	clock offset: 0x1234	class: 0x123456"
            output = stdout.decode()
            for line in output.strip().split("\n"):
                if not line.strip() or line.startswith("Inquiring"):
                    continue

                # Parse MAC address and device class
                match = re.search(
                    r'([0-9A-Fa-f:]{17})\s+clock offset:.*class:\s*0x([0-9A-Fa-f]+)',
                    line
                )
                if match:
                    mac = match.group(1).upper()
                    device_class = int(match.group(2), 16)

                    # Try to get device name (separate call)
                    name = await self._get_classic_device_name(mac, adapter_arg)
                    vendor = await self._get_vendor(mac)

                    devices.append(ScannedDevice(
                        mac=mac,
                        name=name,
                        rssi=-60,  # hcitool doesn't provide RSSI, use placeholder
                        vendor=vendor,
                        service_uuids=[],
                        bt_type="classic",
                        device_class=device_class,
                    ))

            logger.debug(f"Classic scan: found {len(devices)} devices")

        except asyncio.TimeoutError:
            logger.debug("Classic scan timed out")
        except FileNotFoundError:
            logger.debug("hcitool not found - classic Bluetooth scanning unavailable")
        except Exception as e:
            logger.debug(f"Classic scan error: {e}")

        return devices

    async def _get_classic_device_name(
        self, mac: str, adapter_arg: list[str]
    ) -> Optional[str]:
        """Get the friendly name of a classic Bluetooth device."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "hcitool", *adapter_arg, "name", mac,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            name = stdout.decode().strip()
            return name if name else None
        except Exception:
            return None

    async def scan(self, duration: float = SCAN_DURATION) -> list[ScannedDevice]:
        """Perform both BLE and classic Bluetooth scans."""
        # Run both scans concurrently
        ble_task = asyncio.create_task(self.scan_ble(duration))
        classic_task = asyncio.create_task(self.scan_classic())

        ble_devices, classic_devices = await asyncio.gather(
            ble_task, classic_task, return_exceptions=True
        )

        # Handle any exceptions
        if isinstance(ble_devices, Exception):
            logger.error(f"BLE scan failed: {ble_devices}")
            ble_devices = []
        if isinstance(classic_devices, Exception):
            logger.debug(f"Classic scan failed: {classic_devices}")
            classic_devices = []

        # Merge results, preferring BLE data if device seen in both
        seen_macs = set()
        devices = []

        for device in ble_devices:
            seen_macs.add(device.mac.upper())
            devices.append(device)

        for device in classic_devices:
            if device.mac.upper() not in seen_macs:
                devices.append(device)

        logger.info(f"Scan complete: {len(ble_devices)} BLE + {len(classic_devices)} classic = {len(devices)} unique devices")

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
