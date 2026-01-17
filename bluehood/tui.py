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

            # Read response, skipping any notifications (event messages)
            while True:
                data = await self.reader.readline()
                if not data:
                    return {"status": "error", "message": "Connection closed"}
                response = json.loads(data.decode())
                # Skip notification events, wait for actual command response
                if "event" not in response:
                    return response
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

    async def get_sightings(self, mac: str, days: int = 7) -> list[dict]:
        """Get recent sightings for a device."""
        response = await self.send_command({
            "cmd": "get_sightings",
            "mac": mac,
            "days": days,
        })
        return response.get("sightings", [])

    async def search(
        self,
        mac: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict]:
        """Search devices by MAC and/or time range."""
        cmd = {"cmd": "search"}
        if mac:
            cmd["mac"] = mac
        if start_time:
            cmd["start_time"] = start_time
        if end_time:
            cmd["end_time"] = end_time
        response = await self.send_command(cmd)
        return response.get("results", [])


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

    def __init__(self, device: dict, hourly: dict, daily: dict, sightings: list, pattern: str):
        super().__init__()
        self.device = device
        self.hourly = hourly
        self.daily = daily
        self.sightings = sightings
        self.pattern = pattern

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

            yield Label("Pattern Analysis", classes="subtitle")
            yield Static(f"  {self.pattern}")

            yield Label("Hourly Activity (30 days)", classes="subtitle")
            yield Static(f"     0  3  6  9 12 15 18 21 24")
            yield Static(f"     {generate_hourly_heatmap(self.hourly)}")

            yield Label("Daily Activity (30 days)", classes="subtitle")
            yield Static(f"     M  T  W  T  F  S  S")
            yield Static(f"     {generate_daily_heatmap(self.daily)}")

            yield Label("Recent Sightings", classes="subtitle")
            if self.sightings:
                for s in self.sightings[:10]:  # Show last 10
                    ts = datetime.fromisoformat(s["timestamp"]).strftime("%m-%d %H:%M")
                    rssi = s.get("rssi", "?")
                    yield Static(f"  {ts}  RSSI: {rssi} dBm")
            else:
                yield Static("  No recent sightings")

            yield Label("Press Escape or Q to close", classes="hint")

    def action_close(self) -> None:
        self.dismiss()


class SearchScreen(ModalScreen):
    """Modal screen for searching devices."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="search-dialog"):
            yield Label("Search Devices", classes="title")
            yield Label("MAC/Name/Vendor:")
            yield Input(placeholder="Search text (leave empty for all)", id="search-mac")
            yield Label("Start Time (YYYY-MM-DD HH:MM):")
            yield Input(placeholder="e.g. 2026-01-17 09:00", id="search-start")
            yield Label("End Time (YYYY-MM-DD HH:MM):")
            yield Input(placeholder="e.g. 2026-01-17 18:00", id="search-end")
            yield Label("Press Enter to search, Escape to cancel", classes="hint")

    def on_mount(self) -> None:
        self.query_one("#search-mac", Input).focus()

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        mac = self.query_one("#search-mac", Input).value.strip()
        start = self.query_one("#search-start", Input).value.strip()
        end = self.query_one("#search-end", Input).value.strip()
        self.dismiss({"mac": mac or None, "start": start or None, "end": end or None})

    def action_cancel(self) -> None:
        self.dismiss(None)


class SearchResultsScreen(ModalScreen):
    """Modal screen showing search results."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, results: list[dict], query_desc: str):
        super().__init__()
        self.results = results
        self.query_desc = query_desc

    def compose(self) -> ComposeResult:
        with Container(id="results-dialog"):
            yield Label(f"Search Results: {self.query_desc}", classes="title")
            yield Label(f"Found {len(self.results)} devices", classes="subtitle")

            if self.results:
                # Create a simple table view
                yield Static("MAC               Vendor          Name         Sightings")
                yield Static("-" * 65)
                for r in self.results[:20]:  # Show top 20
                    mac = r.get("mac", "")[:17]
                    vendor = (r.get("vendor") or "Unknown")[:15]
                    name = (r.get("friendly_name") or "")[:12]
                    sightings = r.get("range_sightings", 0)
                    yield Static(f"{mac:<17} {vendor:<15} {name:<12} {sightings:>5}")

                if len(self.results) > 20:
                    yield Static(f"... and {len(self.results) - 20} more")
            else:
                yield Static("No devices found matching your search.")

            yield Label("Press Escape or Q to close", classes="hint")

    def action_close(self) -> None:
        self.dismiss()


class BluehoodApp(App):
    """Main Bluehood TUI application."""

    TITLE = "BLUEHOOD"
    SUB_TITLE = "Bluetooth Neighborhood Monitor"

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: #1a1a2e;
        color: #00d4ff;
    }

    HeaderTitle {
        color: #00d4ff;
        text-style: bold;
    }

    Footer {
        background: #1a1a2e;
    }

    FooterKey {
        background: #16213e;
        color: #00d4ff;
    }

    #device-table {
        height: 100%;
        background: #0f0f1a;
    }

    DataTable > .datatable--header {
        background: #16213e;
        color: #00d4ff;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #1a1a4e;
        color: #00ff88;
    }

    DataTable > .datatable--hover {
        background: #1a1a3e;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #16213e;
        color: #00d4ff;
        padding: 0 1;
    }

    #name-dialog {
        align: center middle;
        width: 60;
        height: 10;
        border: solid #00d4ff;
        background: #1a1a2e;
        padding: 1 2;
    }

    #name-dialog Label {
        margin-bottom: 1;
        color: #00d4ff;
    }

    #name-dialog .hint {
        margin-top: 1;
        color: #666688;
    }

    #name-dialog Input {
        background: #0f0f1a;
        border: solid #00d4ff;
    }

    #detail-dialog {
        align: center middle;
        width: 78;
        height: 38;
        border: solid #00d4ff;
        background: #1a1a2e;
        padding: 1 2;
        overflow-y: auto;
    }

    #detail-dialog .title {
        text-style: bold;
        color: #00d4ff;
        margin-bottom: 1;
    }

    #detail-dialog .subtitle {
        margin-top: 1;
        text-style: bold;
        color: #00ff88;
    }

    #detail-dialog .hint {
        margin-top: 1;
        color: #666688;
    }

    #detail-dialog Static {
        color: #ccccdd;
    }

    .ignored {
        color: #666688;
    }

    #search-dialog {
        align: center middle;
        width: 65;
        height: 16;
        border: solid #00d4ff;
        background: #1a1a2e;
        padding: 1 2;
    }

    #search-dialog Label {
        color: #00d4ff;
    }

    #search-dialog .title {
        text-style: bold;
        color: #00d4ff;
        margin-bottom: 1;
    }

    #search-dialog .hint {
        margin-top: 1;
        color: #666688;
    }

    #search-dialog Input {
        margin-bottom: 1;
        background: #0f0f1a;
        border: solid #00d4ff;
    }

    #results-dialog {
        align: center middle;
        width: 85;
        height: 32;
        border: solid #00d4ff;
        background: #1a1a2e;
        padding: 1 2;
        overflow-y: auto;
    }

    #results-dialog .title {
        text-style: bold;
        color: #00d4ff;
        margin-bottom: 1;
    }

    #results-dialog .subtitle {
        color: #00ff88;
        margin-bottom: 1;
    }

    #results-dialog .hint {
        margin-top: 1;
        color: #666688;
    }

    #results-dialog Static {
        color: #ccccdd;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "search", "Search"),
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

        new_devices = await self.client.list_devices(self.show_ignored)
        table = self.query_one("#device-table", DataTable)

        # Track existing MACs
        existing_macs = {d.get("mac") for d in self.devices}
        new_macs = {d.get("mac") for d in new_devices}

        # Remove rows that no longer exist
        for mac in existing_macs - new_macs:
            try:
                table.remove_row(mac)
            except Exception:
                pass

        # Update or add rows
        for device in new_devices:
            mac = device.get("mac", "")
            vendor = device.get("vendor") or "Unknown"
            name = device.get("friendly_name") or ""
            sightings = str(device.get("total_sightings", 0))

            last_seen = device.get("last_seen")
            if last_seen:
                dt = datetime.fromisoformat(last_seen)
                last_seen = dt.strftime("%m-%d %H:%M")
            else:
                last_seen = "Never"

            # Get pattern (simplified for table view) - skip on updates to avoid slowdown
            if mac not in existing_macs:
                hourly = await self.client.get_hourly(mac, 30)
                from .patterns import _analyze_time_pattern
                pattern = _analyze_time_pattern(hourly)
            else:
                pattern = ""  # Keep existing pattern on updates

            # Truncate long values for display
            vendor = vendor[:18] if len(vendor) > 18 else vendor
            name = name[:25] if len(name) > 25 else name

            if mac in existing_macs:
                # Update existing row
                try:
                    row_idx = table.get_row_index(mac)
                    table.update_cell_at((row_idx, 0), mac)
                    table.update_cell_at((row_idx, 1), vendor)
                    table.update_cell_at((row_idx, 2), name)
                    table.update_cell_at((row_idx, 3), sightings)
                    table.update_cell_at((row_idx, 4), last_seen)
                except Exception:
                    pass
            else:
                # Add new row
                table.add_row(mac, vendor, name, sightings, last_seen, pattern, key=mac)

        self.devices = new_devices
        self.update_status("Refreshed")

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track highlighted row (cursor position)."""
        self.selected_mac = str(event.row_key.value) if event.row_key else None

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open detail view when row is selected (Enter pressed)."""
        self.selected_mac = str(event.row_key.value) if event.row_key else None
        if self.selected_mac:
            self.run_worker(self.action_show_detail())

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
            sightings = await self.client.get_sightings(mac, 7)
            pattern = analyze_device_pattern(hourly, daily)
            self.push_screen(DetailScreen(device, hourly, daily, sightings, pattern))

    def action_toggle_filter(self) -> None:
        """Toggle between showing all devices and only active."""
        self.show_ignored = not self.show_ignored
        self.run_worker(self.refresh_devices())

    def action_search(self) -> None:
        """Open search dialog."""
        def on_search(params: Optional[dict]) -> None:
            if params is None:
                return  # Cancelled

            async def do_search():
                mac = params.get("mac")
                start = params.get("start")
                end = params.get("end")

                # Parse datetime strings
                start_iso = None
                end_iso = None
                if start:
                    try:
                        # Support both "YYYY-MM-DD HH:MM" and "YYYY-MM-DD"
                        if len(start) == 10:
                            start += " 00:00"
                        dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
                        start_iso = dt.isoformat()
                    except ValueError:
                        self.update_status("Invalid start time format")
                        return
                if end:
                    try:
                        if len(end) == 10:
                            end += " 23:59"
                        dt = datetime.strptime(end, "%Y-%m-%d %H:%M")
                        end_iso = dt.isoformat()
                    except ValueError:
                        self.update_status("Invalid end time format")
                        return

                results = await self.client.search(mac, start_iso, end_iso)

                # Build query description
                parts = []
                if mac:
                    parts.append(f"'{mac}'")
                if start:
                    parts.append(f"from {start}")
                if end:
                    parts.append(f"to {end}")
                query_desc = " ".join(parts) if parts else "all devices"

                self.push_screen(SearchResultsScreen(results, query_desc))

            self.run_worker(do_search())

        self.push_screen(SearchScreen(), on_search)


def main() -> None:
    """Entry point for bluehood TUI."""
    app = BluehoodApp()
    app.run()


if __name__ == "__main__":
    main()
