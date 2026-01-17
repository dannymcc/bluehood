"""Bluehood TUI - Textual-based interface for monitoring Bluetooth devices."""

import asyncio
import json
from datetime import datetime
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from .config import SOCKET_PATH
from .patterns import (
    analyze_device_pattern,
    generate_daily_heatmap,
    generate_hourly_heatmap,
)


class DaemonClient:
    """Client for communicating with the bluehood daemon."""

    def __init__(self):
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

    async def connect(self) -> bool:
        """Connect to the daemon."""
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(
                str(SOCKET_PATH)
            )
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the daemon."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False

    async def send_command(self, cmd: dict) -> dict:
        """Send a command and receive response."""
        if not self.connected:
            return {"status": "error", "message": "Not connected"}

        try:
            self.writer.write(json.dumps(cmd).encode() + b"\n")
            await self.writer.drain()

            data = await self.reader.readline()
            return json.loads(data.decode())
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_devices(self, include_ignored: bool = True) -> list[dict]:
        """Get list of devices from daemon."""
        response = await self.send_command({
            "cmd": "list",
            "include_ignored": include_ignored,
        })
        return response.get("devices", [])

    async def set_name(self, mac: str, name: str) -> bool:
        """Set friendly name for a device."""
        response = await self.send_command({
            "cmd": "set_name",
            "mac": mac,
            "name": name,
        })
        return response.get("status") == "ok"

    async def set_ignored(self, mac: str, ignored: bool) -> bool:
        """Set ignored status for a device."""
        response = await self.send_command({
            "cmd": "set_ignored",
            "mac": mac,
            "ignored": ignored,
        })
        return response.get("status") == "ok"

    async def get_hourly(self, mac: str, days: int = 30) -> dict[int, int]:
        """Get hourly distribution for a device."""
        response = await self.send_command({
            "cmd": "get_hourly",
            "mac": mac,
            "days": days,
        })
        # Convert string keys back to int
        hourly = response.get("hourly", {})
        return {int(k): v for k, v in hourly.items()}

    async def get_daily(self, mac: str, days: int = 30) -> dict[int, int]:
        """Get daily distribution for a device."""
        response = await self.send_command({
            "cmd": "get_daily",
            "mac": mac,
            "days": days,
        })
        daily = response.get("daily", {})
        return {int(k): v for k, v in daily.items()}


class NameInputScreen(ModalScreen[str]):
    """Modal screen for entering a device name."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, mac: str, current_name: str = ""):
        super().__init__()
        self.mac = mac
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        with Container(id="name-dialog"):
            yield Label(f"Set name for {self.mac}")
            yield Input(
                value=self.current_name,
                placeholder="Enter friendly name...",
                id="name-input",
            )
            yield Label("Press Enter to save, Escape to cancel", classes="hint")

    def on_mount(self) -> None:
        self.query_one("#name-input", Input).focus()

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss("")


class DetailScreen(ModalScreen):
    """Modal screen showing device details."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, device: dict, hourly: dict, daily: dict):
        super().__init__()
        self.device = device
        self.hourly = hourly
        self.daily = daily

    def compose(self) -> ComposeResult:
        d = self.device

        # Format timestamps
        first_seen = d.get("first_seen", "Unknown")
        last_seen = d.get("last_seen", "Unknown")
        if first_seen and first_seen != "Unknown":
            first_seen = datetime.fromisoformat(first_seen).strftime("%Y-%m-%d %H:%M")
        if last_seen and last_seen != "Unknown":
            last_seen = datetime.fromisoformat(last_seen).strftime("%Y-%m-%d %H:%M")

        with Container(id="detail-dialog"):
            yield Label(f"Device Details", classes="title")
            yield Static(f"MAC: {d.get('mac', 'Unknown')}")
            yield Static(f"Vendor: {d.get('vendor') or 'Unknown'}")
            yield Static(f"Name: {d.get('friendly_name') or 'Not set'}")
            yield Static(f"Status: {'Ignored' if d.get('ignored') else 'Active'}")
            yield Static(f"First seen: {first_seen}")
            yield Static(f"Last seen: {last_seen}")
            yield Static(f"Total sightings: {d.get('total_sightings', 0)}")

            yield Label("Hourly Activity (24h)", classes="subtitle")
            yield Static(f"     0  3  6  9 12 15 18 21 24")
            yield Static(f"     {generate_hourly_heatmap(self.hourly)}")

            yield Label("Daily Activity (week)", classes="subtitle")
            yield Static(f"     M  T  W  T  F  S  S")
            yield Static(f"     {generate_daily_heatmap(self.daily)}")

            yield Label("Press Escape or Q to close", classes="hint")

    def action_close(self) -> None:
        self.dismiss()


class BluehoodApp(App):
    """Main Bluehood TUI application."""

    CSS = """
    #device-table {
        height: 100%;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    #name-dialog {
        align: center middle;
        width: 60;
        height: 10;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #name-dialog Label {
        margin-bottom: 1;
    }

    #name-dialog .hint {
        margin-top: 1;
        color: $text-muted;
    }

    #detail-dialog {
        align: center middle;
        width: 70;
        height: 25;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }

    #detail-dialog .title {
        text-style: bold;
        margin-bottom: 1;
    }

    #detail-dialog .subtitle {
        margin-top: 1;
        text-style: bold;
    }

    #detail-dialog .hint {
        margin-top: 1;
        color: $text-muted;
    }

    .ignored {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("i", "toggle_ignore", "Toggle Ignore"),
        Binding("n", "set_name", "Set Name"),
        Binding("d", "show_detail", "Details"),
        Binding("f", "toggle_filter", "Filter"),
    ]

    def __init__(self):
        super().__init__()
        self.client = DaemonClient()
        self.devices: list[dict] = []
        self.show_ignored = True
        self.selected_mac: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="device-table")
        yield Static("Connecting...", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the app."""
        table = self.query_one("#device-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("MAC", "Vendor", "Name", "Sightings", "Last Seen", "Pattern")

        # Connect to daemon
        if await self.client.connect():
            self.update_status("Connected to daemon")
            await self.refresh_devices()
            # Start background refresh
            self.set_interval(10, self.refresh_devices)
        else:
            self.update_status("Failed to connect - is bluehood-daemon running?")

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        await self.client.disconnect()

    def update_status(self, message: str) -> None:
        """Update the status bar."""
        status = self.query_one("#status-bar", Static)
        filter_text = "All" if self.show_ignored else "Active only"
        status.update(f"{message} | Filter: {filter_text} | {len(self.devices)} devices")

    async def refresh_devices(self) -> None:
        """Refresh the device list from daemon."""
        if not self.client.connected:
            return

        self.devices = await self.client.list_devices(self.show_ignored)

        table = self.query_one("#device-table", DataTable)
        table.clear()

        for device in self.devices:
            mac = device.get("mac", "")
            vendor = device.get("vendor") or "Unknown"
            name = device.get("friendly_name") or ""
            sightings = str(device.get("total_sightings", 0))
            ignored = device.get("ignored", False)

            last_seen = device.get("last_seen")
            if last_seen:
                dt = datetime.fromisoformat(last_seen)
                last_seen = dt.strftime("%m-%d %H:%M")
            else:
                last_seen = "Never"

            # Get pattern (simplified for table view)
            hourly = await self.client.get_hourly(mac, 30)
            from .patterns import _analyze_time_pattern
            pattern = _analyze_time_pattern(hourly)

            # Truncate long values
            vendor = vendor[:20] if len(vendor) > 20 else vendor
            name = name[:15] if len(name) > 15 else name

            row_style = "ignored" if ignored else ""
            table.add_row(mac, vendor, name, sightings, last_seen, pattern, key=mac)

        self.update_status("Refreshed")

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Track selected row."""
        self.selected_mac = str(event.row_key.value) if event.row_key else None

    def _get_selected_device(self) -> Optional[dict]:
        """Get the currently selected device."""
        if not self.selected_mac:
            return None
        for d in self.devices:
            if d.get("mac") == self.selected_mac:
                return d
        return None

    def action_refresh(self) -> None:
        """Refresh device list."""
        self.run_worker(self.refresh_devices())

    async def action_toggle_ignore(self) -> None:
        """Toggle ignore status for selected device."""
        device = self._get_selected_device()
        if device:
            mac = device.get("mac")
            current = device.get("ignored", False)
            if await self.client.set_ignored(mac, not current):
                await self.refresh_devices()
                self.update_status(f"{'Ignored' if not current else 'Unignored'} {mac}")

    async def action_set_name(self) -> None:
        """Set friendly name for selected device."""
        device = self._get_selected_device()
        if device:
            mac = device.get("mac")
            current_name = device.get("friendly_name") or ""

            def on_name_set(name: str) -> None:
                if name:
                    async def do_set():
                        if await self.client.set_name(mac, name):
                            await self.refresh_devices()
                            self.update_status(f"Named {mac} as '{name}'")
                    self.run_worker(do_set())

            self.push_screen(NameInputScreen(mac, current_name), on_name_set)

    async def action_show_detail(self) -> None:
        """Show detail screen for selected device."""
        device = self._get_selected_device()
        if device:
            mac = device.get("mac")
            hourly = await self.client.get_hourly(mac, 30)
            daily = await self.client.get_daily(mac, 30)
            self.push_screen(DetailScreen(device, hourly, daily))

    def action_toggle_filter(self) -> None:
        """Toggle between showing all devices and only active."""
        self.show_ignored = not self.show_ignored
        self.run_worker(self.refresh_devices())


def main() -> None:
    """Entry point for bluehood TUI."""
    app = BluehoodApp()
    app.run()


if __name__ == "__main__":
    main()
