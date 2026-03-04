"""Bluetooth scanning module using bleak (BLE) and hcitool (classic)."""

import asyncio
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
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
from .config import (
    SCAN_DURATION, BLUETOOTH_ADAPTER, CLASSIC_BLUETOOTH_ADAPTER,
    BLUETOOTH_ADAPTER_MAC, CLASSIC_BLUETOOTH_ADAPTER_MAC,
    STALE_SCAN_THRESHOLD, HEALTH_MAX_SCAN_AGE, DATA_DIR,
)

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
    """List available Bluetooth adapters via sysfs.

    Reads /sys/class/bluetooth/hciX/address for each adapter.
    Falls back to bluetoothctl if sysfs is not available.
    """
    adapters = []
    bt_class = Path("/sys/class/bluetooth")

    if bt_class.is_dir():
        for entry in sorted(bt_class.iterdir()):
            if not entry.name.startswith("hci"):
                continue
            hci_name = entry.name
            address = ""
            addr_file = entry / "address"
            if addr_file.is_file():
                try:
                    address = addr_file.read_text().strip()
                except OSError:
                    pass
            adapters.append(BluetoothAdapter(
                name=hci_name,
                address=address,
                alias=hci_name,
            ))
        if adapters:
            return adapters

    # Fallback: bluetoothctl (when sysfs is unavailable)
    try:
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
                    adapters.append(BluetoothAdapter(
                        name="",  # cannot reliably infer hci name
                        address=address,
                        alias=alias
                    ))
    except FileNotFoundError:
        logger.warning("bluetoothctl not found - install bluez-utils")
    except Exception as e:
        logger.warning(f"Could not list adapters: {e}")
    return adapters


def resolve_adapter_by_mac(mac: str) -> Optional[str]:
    """Find the hciX name for a Bluetooth adapter with the given MAC address.

    Args:
        mac: Bluetooth MAC address (e.g., "AA:BB:CC:DD:EE:FF"), case-insensitive.

    Returns:
        The hci name (e.g., "hci2") or None if no adapter matches.
    """
    mac_upper = mac.upper()
    for adapter in list_adapters():
        if adapter.address.upper() == mac_upper:
            logger.info(f"Resolved adapter MAC {mac} -> {adapter.name}")
            return adapter.name
    return None


def find_any_bluetooth_adapter() -> Optional[str]:
    """Find any available Bluetooth adapter as a last resort.

    Returns the hci name of the first adapter found, or None.
    """
    adapters = list_adapters()
    if adapters and adapters[0].name:
        logger.warning(f"Failover: using first available adapter {adapters[0].name}")
        return adapters[0].name
    return None


def find_rfkill_for_adapter(adapter: str) -> Optional[str]:
    """Find the rfkill sysfs state path for a given Bluetooth adapter.

    Walks /sys/class/rfkill/rfkillN/ entries and matches by device symlink
    or falls back to first bluetooth-type rfkill.

    Args:
        adapter: hci name like "hci0".

    Returns:
        Path like "/sys/class/rfkill/rfkill2/state", or None.
    """
    rfkill_base = Path("/sys/class/rfkill")
    if not rfkill_base.is_dir():
        return None

    # Get the real device path for our adapter
    try:
        adapter_device = os.path.realpath(f"/sys/class/bluetooth/{adapter}/device")
    except OSError:
        adapter_device = None

    bluetooth_rfkills = []

    for entry in sorted(rfkill_base.iterdir()):
        if not entry.name.startswith("rfkill"):
            continue

        type_file = entry / "type"
        if not type_file.is_file():
            continue

        try:
            rfkill_type = type_file.read_text().strip()
        except OSError:
            continue

        if rfkill_type != "bluetooth":
            continue

        state_path = str(entry / "state")

        # Check if this rfkill's device matches our adapter's device
        if adapter_device:
            try:
                rfkill_device = os.path.realpath(str(entry / "device"))
                if rfkill_device == adapter_device:
                    return state_path
            except OSError:
                pass

        bluetooth_rfkills.append(state_path)

    # Fallback: return first bluetooth rfkill
    if bluetooth_rfkills:
        return bluetooth_rfkills[0]

    return None


VENDOR_DB_MAX_AGE_DAYS = 7
VENDOR_DB_UPDATE_TIMEOUT = 30

_PROCESS_START = time.monotonic()
_MIN_UPTIME_FOR_EXIT = 180  # 3 min — prevents crash loops after failed recovery
_BACKOFF_SLEEP = 300  # 5 min sleep if restart didn't help

_RFKILL_FALLBACK = "/sys/class/rfkill/rfkill0/state"

# Maximum consecutive USB resets before giving up and exiting
_MAX_USB_RESETS = 3
_USB_RESET_COOLDOWN = 30  # seconds between reset attempts


class BluetoothScanner:
    """Bluetooth LE and classic scanner."""

    def __init__(
        self,
        adapter: Optional[str] = None,
        classic_adapter: Optional[str] = None,
        adapter_mac: Optional[str] = None,
        classic_adapter_mac: Optional[str] = None,
    ):
        # Store MAC identifiers for re-resolution after recovery
        self._adapter_mac = adapter_mac or BLUETOOTH_ADAPTER_MAC
        self._classic_adapter_mac = classic_adapter_mac or CLASSIC_BLUETOOTH_ADAPTER_MAC

        # Resolve adapter: MAC takes precedence over hci name
        self.adapter = self._resolve_adapter(
            adapter or BLUETOOTH_ADAPTER,
            self._adapter_mac,
        )
        self.classic_adapter = self._resolve_adapter(
            classic_adapter or CLASSIC_BLUETOOTH_ADAPTER,
            self._classic_adapter_mac,
        ) or self.adapter

        self._use_dual_adapter = (
            self.classic_adapter is not None
            and self.adapter is not None
            and self.classic_adapter != self.adapter
        )
        self._mac_lookup: Optional[AsyncMacLookup] = None
        self._vendor_cache: dict[str, Optional[str]] = {}
        self._vendors_updated = False
        self._vendor_update_task: Optional[asyncio.Task] = None
        self._ble_stuck = False
        self._usb_reset_count = 0
        self._last_usb_reset = 0.0
        self._adapter_usb_path: Optional[str] = None  # cached sysfs USB path

        # Stale scan detection
        self._consecutive_empty_scans = 0
        self._last_successful_scan_time: Optional[float] = None
        self._last_scan_device_count = 0

        # Dynamic rfkill path (resolved lazily, invalidated on recovery)
        self._rfkill_path: Optional[str] = None

    def _resolve_adapter(
        self,
        hci_name: Optional[str],
        mac: Optional[str],
    ) -> Optional[str]:
        """Resolve an adapter, preferring MAC-based lookup over hci name.

        Resolution order:
        1. If MAC is set, find the hci name matching that MAC.
        2. If MAC lookup fails, try the hci name (if provided and exists in sysfs).
        3. If hci name doesn't exist, try find_any_bluetooth_adapter().
        4. Return None if nothing works (bleak will auto-select).
        """
        # Strategy 1: MAC-based resolution
        if mac:
            resolved = resolve_adapter_by_mac(mac)
            if resolved:
                return resolved
            logger.warning(f"Adapter MAC {mac} not found among available adapters")

        # Strategy 2: Check if the hci name is still valid
        if hci_name:
            if Path(f"/sys/class/bluetooth/{hci_name}").exists():
                return hci_name
            logger.warning(f"Adapter {hci_name} not found in sysfs")

        # Strategy 3: Failover to any available adapter
        fallback = find_any_bluetooth_adapter()
        if fallback:
            return fallback

        # Strategy 4: Return None and let bleak auto-select
        logger.warning("No Bluetooth adapter found, relying on bleak auto-selection")
        return None

    def _re_resolve_adapter(self) -> bool:
        """Re-resolve the BLE adapter after a crash/renumbering event.

        Invalidates cached USB path and rfkill path since hci index may
        have changed. Returns True if an adapter was found.
        """
        self._adapter_usb_path = None
        self._rfkill_path = None

        old_adapter = self.adapter
        self.adapter = self._resolve_adapter(old_adapter, self._adapter_mac)

        if self.adapter and self.adapter != old_adapter:
            logger.info(f"Adapter re-resolved: {old_adapter} -> {self.adapter}")

        # Also re-resolve classic adapter
        if self._classic_adapter_mac or self.classic_adapter:
            old_classic = self.classic_adapter
            self.classic_adapter = self._resolve_adapter(
                old_classic,
                self._classic_adapter_mac,
            ) or self.adapter
            if self.classic_adapter != old_classic:
                logger.info(f"Classic adapter re-resolved: {old_classic} -> {self.classic_adapter}")
            self._use_dual_adapter = (
                self.classic_adapter is not None
                and self.adapter is not None
                and self.classic_adapter != self.adapter
            )

        return self.adapter is not None

    def get_scan_health(self) -> dict:
        """Return scan health status for the /api/health endpoint."""
        now = time.monotonic()
        scan_age = None
        if self._last_successful_scan_time is not None:
            scan_age = now - self._last_successful_scan_time

        healthy = (
            not self._ble_stuck
            and (scan_age is None or scan_age < HEALTH_MAX_SCAN_AGE)
        )

        return {
            "healthy": healthy,
            "adapter": self.adapter,
            "adapter_mac": self._adapter_mac,
            "last_successful_scan_age": round(scan_age, 1) if scan_age is not None else None,
            "consecutive_empty_scans": self._consecutive_empty_scans,
            "ble_stuck": self._ble_stuck,
            "last_scan_devices": self._last_scan_device_count,
        }

    def _is_vendor_db_fresh(self) -> bool:
        """Check if the cached vendor DB exists and is less than 7 days old."""
        cache_path = BaseMacLookup.cache_path if HAS_MAC_LOOKUP else None
        if not cache_path or not os.path.exists(cache_path):
            return False
        age_days = (time.time() - os.path.getmtime(cache_path)) / 86400
        return age_days < VENDOR_DB_MAX_AGE_DAYS

    def _start_vendor_db_update(self) -> None:
        """Kick off a background vendor DB update (never blocks scanning)."""
        if self._vendors_updated or not HAS_MAC_LOOKUP:
            return
        if self._vendor_update_task and not self._vendor_update_task.done():
            return

        if self._is_vendor_db_fresh():
            logger.info("MAC vendor database is up to date (cached)")
            self._vendors_updated = True
            return

        self._vendor_update_task = asyncio.create_task(self._update_vendor_db())

    async def _update_vendor_db(self) -> None:
        """Download vendor database in the background with a timeout."""
        try:
            logger.info("Updating MAC vendor database...")

            def update_sync():
                mac_lookup = MacLookup()
                mac_lookup.update_vendors()

            await asyncio.wait_for(
                asyncio.to_thread(update_sync),
                timeout=VENDOR_DB_UPDATE_TIMEOUT,
            )
            self._vendors_updated = True
            logger.info("MAC vendor database updated")
        except asyncio.TimeoutError:
            logger.warning(
                f"MAC vendor database update timed out ({VENDOR_DB_UPDATE_TIMEOUT}s), "
                "using cached/bundled data"
            )
            self._vendors_updated = True
        except Exception as e:
            logger.warning(f"Could not update vendor database: {e}")
            self._vendors_updated = True

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

        # Check cache first - only return if we have a successful lookup
        if mac in self._vendor_cache and self._vendor_cache[mac] is not None:
            return self._vendor_cache[mac]

        vendor = None

        # Try local database first
        if HAS_MAC_LOOKUP:
            try:
                if self._mac_lookup is None:
                    self._start_vendor_db_update()
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
        """Look up vendor using MACVendors.com API.

        Only sends the OUI (first 3 bytes) to protect privacy.
        """
        # Extract OUI (first 3 bytes / 6 hex chars) for privacy
        oui = mac[:8]  # e.g., "AA:BB:CC"

        # Rate limit: 1 request per second
        if hasattr(self, '_last_api_call'):
            elapsed = asyncio.get_event_loop().time() - self._last_api_call
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{MACVENDORS_API_URL}{oui}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    self._last_api_call = asyncio.get_event_loop().time()
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

    def _find_usb_device_path(self, adapter: str) -> Optional[str]:
        """Find the sysfs USB device path for a given HCI adapter.

        Maps e.g. 'hci1' -> '1-1.5' by reading the symlink at
        /sys/class/bluetooth/hci1/device -> ../../usb1/1-1/1-1.5/1-1.5:1.0
        and extracting the USB device portion.

        Returns None for non-USB adapters (e.g. UART/SDIO).
        """
        if self._adapter_usb_path is not None:
            return self._adapter_usb_path

        try:
            device_link = os.path.realpath(f"/sys/class/bluetooth/{adapter}/device")
            # USB device paths look like /sys/devices/.../1-1.5:1.0
            # We want the parent: 1-1.5
            base = os.path.basename(device_link)
            if ":" in base:
                # Strip interface suffix (e.g. "1-1.5:1.0" -> "1-1.5")
                usb_path = base.split(":")[0]
                # Verify it's actually a USB device by checking the driver path
                driver_path = f"/sys/bus/usb/drivers/usb/{usb_path}"
                if os.path.exists(driver_path):
                    self._adapter_usb_path = usb_path
                    return usb_path
        except (OSError, IndexError):
            pass

        return None

    def _usb_reset_adapter(self, adapter: str) -> bool:
        """Reset a USB Bluetooth adapter by unbinding and rebinding it.

        This is the correct recovery for USB adapters that go DOWN
        (org.bluez.Error.NotReady). Unlike rfkill (which soft-blocks
        the radio), USB unbind/bind power-cycles the device at the
        USB stack level, forcing the kernel driver to re-initialize.
        """
        usb_path = self._find_usb_device_path(adapter)
        if not usb_path:
            logger.warning(f"Cannot find USB device path for {adapter} — not a USB adapter?")
            return False

        try:
            logger.info(f"Resetting USB device {usb_path} for adapter {adapter}")

            # Unbind
            with open("/sys/bus/usb/drivers/usb/unbind", "w") as f:
                f.write(usb_path)
            time.sleep(2)

            # Rebind
            with open("/sys/bus/usb/drivers/usb/bind", "w") as f:
                f.write(usb_path)
            time.sleep(3)

            # Verify adapter came back UP
            try:
                result = subprocess.run(
                    ["hciconfig", adapter],
                    capture_output=True, text=True, timeout=5,
                )
                if "UP RUNNING" in result.stdout:
                    logger.info(f"USB adapter {adapter} recovered successfully")
                    self._usb_reset_count = 0
                    self._adapter_usb_path = None  # re-discover next time
                    return True

                # Adapter exists but not UP — try bringing it up
                subprocess.run(
                    ["hciconfig", adapter, "up"],
                    capture_output=True, timeout=5,
                )
                time.sleep(1)
                result = subprocess.run(
                    ["hciconfig", adapter],
                    capture_output=True, text=True, timeout=5,
                )
                if "UP RUNNING" in result.stdout:
                    logger.info(f"USB adapter {adapter} recovered after hciconfig up")
                    self._usb_reset_count = 0
                    self._adapter_usb_path = None
                    return True

            except Exception as e:
                logger.warning(f"Post-reset verification failed: {e}")

            logger.error(f"USB adapter {adapter} did not recover after reset")
            return False

        except PermissionError:
            logger.error(
                f"Permission denied writing to USB sysfs for {usb_path}. "
                "Container must run with --privileged or appropriate capabilities."
            )
            return False
        except Exception as e:
            logger.error(f"USB reset failed for {adapter}: {e}")
            return False

    async def _recover_adapter(self, adapter: str, error_type: str) -> bool:
        """Attempt to recover a failed Bluetooth adapter.

        Chooses the right recovery strategy based on adapter type:
        - USB adapters: unbind/bind cycle (for NotReady/DOWN errors)
        - UART/internal adapters: rfkill toggle (for soft-block errors)

        After recovery, re-resolves the adapter name in case the kernel
        renumbered hciX indices during USB rebind.

        Returns True if recovery succeeded without needing a process exit.
        """
        now = time.monotonic()

        # Rate-limit resets
        if now - self._last_usb_reset < _USB_RESET_COOLDOWN:
            logger.debug("Skipping adapter reset — cooldown period")
            return False

        self._last_usb_reset = now
        self._usb_reset_count += 1

        if self._usb_reset_count > _MAX_USB_RESETS:
            logger.error(
                f"Adapter {adapter} failed {self._usb_reset_count} times. "
                "Falling back to process exit for clean D-Bus state."
            )
            return False

        # Try USB reset first (works for USB dongles)
        usb_path = self._find_usb_device_path(adapter)
        if usb_path:
            logger.warning(
                f"BLE adapter {adapter} error ({error_type}), "
                f"attempting USB reset (attempt {self._usb_reset_count}/{_MAX_USB_RESETS})"
            )
            success = await asyncio.to_thread(self._usb_reset_adapter, adapter)
        else:
            # Fall back to rfkill for non-USB adapters
            logger.warning(
                f"BLE adapter {adapter} error ({error_type}), "
                f"attempting rfkill toggle"
            )
            success = await asyncio.to_thread(self._rfkill_toggle)

        # After any recovery attempt, re-resolve the adapter name.
        # The kernel may have renumbered hciX after USB unbind/rebind.
        if success or self._adapter_mac:
            await asyncio.sleep(2)  # wait for kernel enumeration
            self._re_resolve_adapter()

        return success

    def _rfkill_toggle(self) -> bool:
        """Toggle Bluetooth via sysfs rfkill (no binary/fork needed).

        Writing to sysfs is a simple file write — works even when FDs
        are nearly exhausted, unlike subprocess.run which needs to fork.
        """
        # Resolve rfkill path dynamically
        adapter = self.adapter or "hci0"
        rfkill_path = self._rfkill_path
        if not rfkill_path:
            rfkill_path = find_rfkill_for_adapter(adapter)
            if rfkill_path:
                self._rfkill_path = rfkill_path
            else:
                rfkill_path = _RFKILL_FALLBACK
                logger.warning(f"Could not find rfkill for {adapter}, using fallback {rfkill_path}")

        try:
            logger.info(f"Toggling rfkill via {rfkill_path}")
            with open(rfkill_path, "w") as f:
                f.write("1")  # soft-block
            time.sleep(2)
            with open(rfkill_path, "w") as f:
                f.write("0")  # unblock
            time.sleep(3)
            logger.info("Bluetooth adapter reset via sysfs rfkill")
            return True
        except Exception as e:
            logger.error(f"sysfs rfkill toggle failed ({rfkill_path}): {e}")
            return False

    async def _recover_and_exit(self) -> None:
        """Reset Bluetooth adapter and exit for a clean restart.

        First attempts in-process recovery (USB reset for USB adapters,
        rfkill for internal adapters). Only exits if in-process recovery
        fails, since each failed BleakScanner.discover() leaks D-Bus file
        descriptors that can't be reclaimed without a new process.

        Crash-loop prevention: if uptime < 3 min, the previous restart
        didn't help — sleep 5 min instead of exiting again.

        All blocking I/O and sleeps use asyncio.to_thread / asyncio.sleep
        so the event loop (and web server) stays responsive during recovery.
        """
        adapter = self.adapter or "hci0"

        # Try in-process recovery first (USB reset or rfkill)
        if await self._recover_adapter(adapter, "InProgress"):
            logger.info("Adapter recovered in-process, continuing scan loop")
            self._ble_stuck = False
            self._consecutive_empty_scans = 0
            return

        # In-process recovery failed — fall back to exit
        uptime = time.monotonic() - _PROCESS_START

        if uptime < _MIN_UPTIME_FOR_EXIT:
            logger.warning(
                f"BLE stuck right after start (uptime {uptime:.0f}s). "
                f"Sleeping {_BACKOFF_SLEEP}s before retrying."
            )
            self._ble_stuck = False
            self._consecutive_empty_scans = 0
            await asyncio.sleep(_BACKOFF_SLEEP)
            # After long sleep, adapter might have recovered — re-resolve
            self._re_resolve_adapter()
            return

        logger.critical(
            "BLE adapter stuck and in-process recovery failed. "
            "Toggling rfkill and exiting for fresh D-Bus connections."
        )
        await asyncio.to_thread(self._rfkill_toggle)
        os._exit(0)

    async def scan_ble(self, duration: float = SCAN_DURATION) -> list[ScannedDevice]:
        """Perform a Bluetooth LE scan."""
        devices: list[ScannedDevice] = []

        if self._ble_stuck:
            await self._recover_and_exit()

        try:
            kwargs = {
                "timeout": duration,
                "return_adv": True,
            }
            if self.adapter:
                kwargs["adapter"] = self.adapter

            # Wrap in wait_for as a hard deadline — bleak's timeout parameter
            # only controls the scan window duration, not the underlying D-Bus
            # call which can block indefinitely if the adapter is busy.
            discovered = await asyncio.wait_for(
                BleakScanner.discover(**kwargs),
                timeout=duration + 10,
            )

            for device, adv_data in discovered.values():
                mac = device.address
                vendor = await self._get_vendor(mac)

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

        except asyncio.TimeoutError:
            logger.warning("BLE scan timed out (adapter may be busy)")
            adapter = self.adapter or "hci0"
            logger.warning(f"Adapter {adapter} timed out — attempting recovery")
            if not await self._recover_adapter(adapter, "Timeout"):
                self._ble_stuck = True

        except Exception as e:
            error_str = str(e)
            logger.error(f"BLE scan error: {e}")

            if "InProgress" in error_str:
                self._ble_stuck = True
            else:
                # ALL other exceptions trigger recovery (adapter gone, D-Bus
                # failures, NotReady, etc.) — not just specific error strings.
                adapter = self.adapter or "hci0"
                logger.warning(f"Adapter {adapter} error — attempting recovery")
                if not await self._recover_adapter(adapter, error_str[:50]):
                    self._ble_stuck = True

        # Stale scan detection: if 0 devices for too many consecutive scans,
        # the adapter may have silently died without raising an error.
        if devices:
            self._consecutive_empty_scans = 0
            self._last_successful_scan_time = time.monotonic()
            self._last_scan_device_count = len(devices)
        else:
            self._consecutive_empty_scans += 1
            self._last_scan_device_count = 0
            if (
                STALE_SCAN_THRESHOLD > 0
                and self._consecutive_empty_scans >= STALE_SCAN_THRESHOLD
                and not self._ble_stuck
            ):
                logger.warning(
                    f"Stale scan: {self._consecutive_empty_scans} consecutive scans "
                    f"with 0 BLE devices — triggering recovery"
                )
                adapter = self.adapter or "hci0"
                if await self._recover_adapter(adapter, "StaleScan"):
                    self._consecutive_empty_scans = 0
                else:
                    self._ble_stuck = True

        return devices

    async def scan_classic(self, duration: int = 8) -> list[ScannedDevice]:
        """Perform a classic Bluetooth inquiry scan using hcitool.

        Duration is in 1.28 second units (8 = ~10 seconds).
        """
        devices: list[ScannedDevice] = []

        try:
            # Use hcitool for classic Bluetooth inquiry
            adapter_arg = ["-i", self.classic_adapter] if self.classic_adapter else []

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
        """Perform both BLE and classic Bluetooth scans.

        When a dedicated classic adapter is configured, scans run concurrently
        since they use separate hardware with no contention. Otherwise, scans
        run sequentially (BLE first, then classic) to avoid locking the shared
        adapter in INQUIRY mode which blocks BLE discovery via D-Bus.

        See: https://github.com/dannymcc/bluehood/issues/30
        """
        ble_devices: list[ScannedDevice] = []
        classic_devices: list[ScannedDevice] = []

        if self._use_dual_adapter:
            # Separate adapters — safe to run concurrently
            ble_task = asyncio.create_task(self.scan_ble(duration))
            classic_task = asyncio.create_task(self.scan_classic())

            results = await asyncio.gather(
                ble_task, classic_task, return_exceptions=True
            )

            if isinstance(results[0], Exception):
                logger.error(f"BLE scan failed: {results[0]}")
            else:
                ble_devices = results[0]

            if isinstance(results[1], Exception):
                logger.debug(f"Classic scan failed: {results[1]}")
            else:
                classic_devices = results[1]
        else:
            # Same adapter — run sequentially to avoid contention
            try:
                ble_devices = await self.scan_ble(duration)
            except Exception as e:
                logger.error(f"BLE scan failed: {e}")

            try:
                classic_devices = await self.scan_classic()
            except Exception as e:
                logger.debug(f"Classic scan failed: {e}")

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
