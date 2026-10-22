"""Receive BLE advertisements from ESPHome Bluetooth proxies.

An ESPHome device with the ``bluetooth_proxy`` component forwards every BLE
advertisement it hears over the ESPHome native API (port 6053). Bluehood keeps
a connection open to each configured proxy, buffers what it hears, and hands
the buffered devices to the scan loop once per cycle — so a proxy behaves like
an extra (remote) Bluetooth adapter.

See: https://esphome.io/components/bluetooth_proxy/

Requires the optional ``aioesphomeapi`` dependency: ``pip install bluehood[esphome]``.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_PORT = 6053

# Reconnect backoff after a proxy drops or can't be reached (seconds)
_RECONNECT_MIN = 5
_RECONNECT_MAX = 60

# Warn if a connected proxy has forwarded nothing for this long (seconds) —
# usually another client (e.g. Home Assistant) holds its advertisement stream
_SILENT_WARNING_AFTER = 120

# Bluetooth SIG base UUID, used to expand 16/32-bit UUIDs to the 128-bit
# string form bleak reports (and the classifier matches against)
_BASE_UUID_SUFFIX = "-0000-1000-8000-00805f9b34fb"

# Advertising data (AD) types — Bluetooth Core Spec Supplement, Part A
_AD_UUID16 = (0x02, 0x03)
_AD_UUID32 = (0x04, 0x05)
_AD_UUID128 = (0x06, 0x07)
_AD_SHORT_NAME = 0x08
_AD_COMPLETE_NAME = 0x09
_AD_SERVICE_DATA_UUID16 = 0x16
_AD_SERVICE_DATA_UUID32 = 0x20
_AD_SERVICE_DATA_UUID128 = 0x21


@dataclass
class ProxyConfig:
    """Connection details for one ESPHome Bluetooth proxy."""
    host: str
    port: int = DEFAULT_PORT
    noise_psk: Optional[str] = None  # API encryption key (base64)
    password: Optional[str] = None  # Legacy API password

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class ProxyAdvertisement:
    """Aggregated advertisement data for one device since the last drain."""
    mac: str
    rssi: int
    name: Optional[str] = None
    service_uuids: list[str] = field(default_factory=list)
    proxies: set[str] = field(default_factory=set)


def parse_proxy_list(
    spec: Optional[str],
    noise_psk: Optional[str] = None,
    password: Optional[str] = None,
) -> list[ProxyConfig]:
    """Parse a comma-separated list of proxies.

    Each entry is ``host[:port][@encryption_key]``; IPv6 hosts go in brackets
    (``[fd00::1]:6053``). An entry without its own key uses ``noise_psk``.
    Base64 keys never contain ``,`` or ``@`` so the separators are unambiguous.
    """
    configs: list[ProxyConfig] = []
    if not spec:
        return configs

    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue

        key = noise_psk
        if "@" in entry:
            entry, _, entry_key = entry.partition("@")
            key = entry_key.strip() or noise_psk

        host, port = entry, DEFAULT_PORT
        if entry.startswith("["):
            # [ipv6]:port
            close = entry.find("]")
            if close == -1:
                raise ValueError(f"Invalid ESPHome proxy address: {entry!r}")
            host = entry[1:close]
            rest = entry[close + 1:]
            port_str = rest[1:] if rest.startswith(":") else rest
        elif entry.count(":") == 1:
            host, _, port_str = entry.partition(":")
        else:
            port_str = ""  # hostname, or bare IPv6 without a port

        if port_str:
            if not port_str.isdigit() or not 0 < int(port_str) < 65536:
                raise ValueError(f"Invalid ESPHome proxy port: {entry!r}")
            port = int(port_str)

        host = host.strip()
        if not host:
            raise ValueError(f"Invalid ESPHome proxy address: {entry!r}")

        configs.append(ProxyConfig(host=host, port=port, noise_psk=key or None, password=password or None))

    return configs


def format_mac(address: int) -> str:
    """Format a 48-bit integer address as ``AA:BB:CC:DD:EE:FF``."""
    raw = f"{address:012X}"
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def _uuid16(value: int) -> str:
    return f"0000{value:04x}{_BASE_UUID_SUFFIX}"


def _uuid32(value: int) -> str:
    return f"{value:08x}{_BASE_UUID_SUFFIX}"


def _uuid128(data: bytes) -> str:
    # Transmitted little-endian
    h = data[::-1].hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def parse_advertisement(data: bytes) -> tuple[Optional[str], list[str]]:
    """Extract the local name and service UUIDs from raw advertising data.

    Service UUIDs come from both the service UUID lists and service data
    fields, normalized to lowercase 128-bit strings like bleak reports them.
    Malformed trailing structures are ignored.
    """
    name: Optional[str] = None
    short_name: Optional[str] = None
    uuids: list[str] = []

    def add(uuid: str) -> None:
        if uuid not in uuids:
            uuids.append(uuid)

    i = 0
    length = len(data)
    while i < length:
        field_len = data[i]
        if field_len == 0 or i + 1 + field_len > length:
            break
        ad_type = data[i + 1]
        value = data[i + 2:i + 1 + field_len]
        i += 1 + field_len

        if ad_type in _AD_UUID16:
            for j in range(0, len(value) - 1, 2):
                add(_uuid16(int.from_bytes(value[j:j + 2], "little")))
        elif ad_type in _AD_UUID32:
            for j in range(0, len(value) - 3, 4):
                add(_uuid32(int.from_bytes(value[j:j + 4], "little")))
        elif ad_type in _AD_UUID128:
            for j in range(0, len(value) - 15, 16):
                add(_uuid128(value[j:j + 16]))
        elif ad_type == _AD_SERVICE_DATA_UUID16 and len(value) >= 2:
            add(_uuid16(int.from_bytes(value[:2], "little")))
        elif ad_type == _AD_SERVICE_DATA_UUID32 and len(value) >= 4:
            add(_uuid32(int.from_bytes(value[:4], "little")))
        elif ad_type == _AD_SERVICE_DATA_UUID128 and len(value) >= 16:
            add(_uuid128(value[:16]))
        elif ad_type in (_AD_COMPLETE_NAME, _AD_SHORT_NAME):
            decoded = value.decode("utf-8", errors="replace").rstrip("\x00").strip()
            if decoded:
                if ad_type == _AD_COMPLETE_NAME:
                    name = decoded
                else:
                    short_name = decoded

    return name or short_name, uuids


class ESPHomeProxyManager:
    """Maintains connections to ESPHome Bluetooth proxies and buffers advertisements."""

    def __init__(self, proxies: list[ProxyConfig]):
        self.proxies = proxies
        self._buffer: dict[str, ProxyAdvertisement] = {}
        self._tasks: list[asyncio.Task] = []
        self._connected: set[str] = set()
        self._adv_counts: dict[str, int] = {}
        self._running = False

    @property
    def enabled(self) -> bool:
        return bool(self.proxies)

    @property
    def connected_count(self) -> int:
        return len(self._connected)

    def start(self) -> bool:
        """Start a connection task per proxy. Returns False if unavailable."""
        if not self.proxies or self._running:
            return self._running
        try:
            import aioesphomeapi  # noqa: F401
        except ImportError:
            logger.error(
                "ESPHome proxies configured but aioesphomeapi is not installed. "
                "Install with: pip install bluehood[esphome]"
            )
            return False

        self._running = True
        for proxy in self.proxies:
            self._tasks.append(asyncio.create_task(self._run_proxy(proxy)))
        logger.info(
            f"ESPHome Bluetooth proxies: {', '.join(p.label for p in self.proxies)}"
        )
        return True

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._connected.clear()

    def drain(self) -> list[ProxyAdvertisement]:
        """Return devices heard since the last drain and reset the buffer."""
        devices = list(self._buffer.values())
        self._buffer = {}
        return devices

    def _record(self, proxy_label: str, address: int, rssi: int, data: bytes) -> None:
        mac = format_mac(address)
        name, uuids = parse_advertisement(data)

        entry = self._buffer.get(mac)
        if entry is None:
            entry = ProxyAdvertisement(mac=mac, rssi=rssi)
            self._buffer[mac] = entry
        else:
            # Strongest signal across proxies/packets in this window
            entry.rssi = max(entry.rssi, rssi)
        # Scan responses carry the name separately from the advertisement,
        # so merge fields across packets rather than overwriting.
        if name:
            entry.name = name
        for uuid in uuids:
            if uuid not in entry.service_uuids:
                entry.service_uuids.append(uuid)
        entry.proxies.add(proxy_label)
        self._adv_counts[proxy_label] = self._adv_counts.get(proxy_label, 0) + 1

    async def _run_proxy(self, proxy: ProxyConfig) -> None:
        """Connect to one proxy, subscribe to advertisements, reconnect on loss."""
        from aioesphomeapi import APIClient

        backoff = _RECONNECT_MIN
        label = proxy.label

        while self._running:
            client = APIClient(
                proxy.host,
                proxy.port,
                proxy.password,
                client_info="bluehood",
                noise_psk=proxy.noise_psk,
            )
            disconnected = asyncio.Event()

            async def on_stop(expected_disconnect: bool) -> None:
                disconnected.set()

            def on_advertisements(response, _label=label) -> None:
                for adv in response.advertisements:
                    self._record(_label, adv.address, adv.rssi, adv.data)

            try:
                await asyncio.wait_for(client.connect(on_stop=on_stop, login=True, log_errors=False), timeout=30)
                info = await client.device_info()
                if not getattr(info, "bluetooth_proxy_feature_flags", 0):
                    logger.warning(
                        f"ESPHome device {info.name or label} does not report the "
                        "bluetooth_proxy component; no advertisements will be received"
                    )
                client.subscribe_bluetooth_le_raw_advertisements(on_advertisements)
                self._connected.add(label)
                backoff = _RECONNECT_MIN
                logger.info(f"Connected to ESPHome Bluetooth proxy {info.name or label} ({label})")

                await self._wait_disconnected(label, disconnected)
                logger.warning(f"ESPHome proxy {label} disconnected")
            except asyncio.CancelledError:
                await self._disconnect(client)
                raise
            except Exception as e:
                logger.warning(f"ESPHome proxy {label} connection failed: {e}")
            finally:
                self._connected.discard(label)

            await self._disconnect(client)
            if not self._running:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_MAX)

    async def _wait_disconnected(self, label: str, disconnected: asyncio.Event) -> None:
        """Wait for the connection to drop, warning once if no advertisements arrive."""
        start_count = self._adv_counts.get(label, 0)
        try:
            await asyncio.wait_for(disconnected.wait(), timeout=_SILENT_WARNING_AFTER)
            return
        except asyncio.TimeoutError:
            pass
        if self._adv_counts.get(label, 0) == start_count:
            logger.warning(
                f"ESPHome proxy {label} is connected but has sent no advertisements "
                f"in {_SILENT_WARNING_AFTER}s. A proxy streams advertisements to one "
                "API client at a time — is Home Assistant already subscribed to it?"
            )
        await disconnected.wait()

    @staticmethod
    async def _disconnect(client) -> None:
        try:
            await client.disconnect()
        except Exception:
            pass
