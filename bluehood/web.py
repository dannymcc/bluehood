"""Bluehood Web GUI - Modern dashboard interface."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from aiohttp import web

from . import db
from .classifier import classify_device, get_type_icon, get_type_label, get_all_types, is_randomized_mac, get_uuid_names
from .patterns import generate_hourly_heatmap, generate_daily_heatmap

logger = logging.getLogger(__name__)

# Import for type hints (will be None at runtime if not used)
try:
    from .notifications import NotificationManager
except ImportError:
    NotificationManager = None

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BLUEHOOD // BT Reconnaissance Framework</title>
    <style>
        :root {
            --bg-primary: #0d0d0d;
            --bg-secondary: #141414;
            --bg-tertiary: #1a1a1a;
            --bg-hover: #242424;
            --bg-panel: #111111;
            --text-primary: #e0e0e0;
            --text-secondary: #888888;
            --text-muted: #555555;
            --accent-red: #dc2626;
            --accent-orange: #ea580c;
            --accent-amber: #d97706;
            --accent-green: #16a34a;
            --accent-blue: #2563eb;
            --accent-cyan: #0891b2;
            --border-color: #2a2a2a;
            --border-active: #404040;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', 'Cascadia Code', Consolas, monospace;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: var(--font-mono);
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            font-size: 13px;
            line-height: 1.5;
        }

        /* Top Bar */
        .topbar {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .topbar-left {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            color: inherit;
        }

        .brand-icon {
            color: var(--accent-red);
            font-size: 1.1rem;
        }

        .brand-text {
            font-weight: 700;
            font-size: 0.9rem;
            letter-spacing: 0.05em;
        }

        .brand-text span {
            color: var(--accent-red);
        }

        .nav {
            display: flex;
            gap: 0.25rem;
        }

        .nav-link {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.75rem;
            padding: 0.4rem 0.75rem;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.1s;
        }

        .nav-link:hover, .nav-link.active {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .topbar-right {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--accent-green);
            box-shadow: 0 0 6px var(--accent-green);
            animation: pulse 2s infinite;
        }

        .status-dot.scanning { background: var(--accent-amber); box-shadow: 0 0 6px var(--accent-amber); }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .timestamp {
            font-size: 0.7rem;
            color: var(--text-muted);
        }

        /* Main Layout */
        .main {
            display: grid;
            grid-template-columns: 280px 1fr;
            min-height: calc(100vh - 45px);
        }

        /* Sidebar */
        .sidebar {
            background: var(--bg-panel);
            border-right: 1px solid var(--border-color);
            padding: 1rem;
            overflow-y: auto;
        }

        .panel {
            margin-bottom: 1.5rem;
        }

        .panel-header {
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }

        .stat-grid {
            display: grid;
            gap: 0.5rem;
        }

        .stat-item {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .stat-label {
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-value {
            font-size: 1.25rem;
            font-weight: 700;
        }

        .stat-value.red { color: var(--accent-red); }
        .stat-value.amber { color: var(--accent-amber); }
        .stat-value.green { color: var(--accent-green); }
        .stat-value.blue { color: var(--accent-blue); }

        /* Filters */
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .filter-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 0.75rem;
            padding: 0.5rem 0.75rem;
            text-align: left;
            cursor: pointer;
            border-radius: 3px;
            transition: all 0.1s;
            display: flex;
            justify-content: space-between;
        }

        .filter-btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .filter-btn.active {
            background: var(--bg-tertiary);
            border-color: var(--accent-red);
            color: var(--text-primary);
        }

        .filter-count {
            color: var(--text-muted);
            font-size: 0.7rem;
        }

        /* Content Area */
        .content {
            padding: 1rem;
            overflow-y: auto;
        }

        /* Search Bar */
        .search-bar {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }

        .search-input {
            flex: 1;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 3px;
            padding: 0.6rem 0.75rem;
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 0.8rem;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-red);
        }

        .search-input::placeholder { color: var(--text-muted); }

        .btn {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 0.7rem;
            padding: 0.6rem 1rem;
            cursor: pointer;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.1s;
        }

        .btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
            border-color: var(--border-active);
        }

        .btn-primary {
            background: var(--accent-red);
            border-color: var(--accent-red);
            color: white;
        }

        .btn-primary:hover {
            background: #b91c1c;
        }

        /* Device Table */
        .table-container {
            background: var(--bg-panel);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            overflow: hidden;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 1rem;
            background: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-color);
        }

        .table-title {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-secondary);
        }

        .table-actions {
            display: flex;
            gap: 0.5rem;
        }

        .device-table {
            width: 100%;
            border-collapse: collapse;
        }

        .device-table th {
            text-align: left;
            padding: 0.6rem 0.75rem;
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
        }

        .device-table td {
            padding: 0.6rem 0.75rem;
            font-size: 0.8rem;
            border-bottom: 1px solid var(--border-color);
            vertical-align: middle;
        }

        .device-table tr:hover {
            background: var(--bg-hover);
        }

        .device-table tr:last-child td { border-bottom: none; }

        .device-table tr { cursor: pointer; }

        /* Device Type Badge */
        .type-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.2rem 0.5rem;
            border-radius: 2px;
            font-size: 0.7rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .type-phone { background: #1e3a5f; color: #60a5fa; }
        .type-laptop { background: #1a3a3a; color: #5eead4; }
        .type-audio { background: #3a1e3a; color: #c084fc; }
        .type-watch { background: #1e3a2e; color: #4ade80; }
        .type-smart { background: #3a2e1e; color: #fbbf24; }
        .type-tv { background: #3a1e2e; color: #f472b6; }
        .type-vehicle { background: #3a3a1e; color: #facc15; }
        .type-unknown { background: #2a2a2a; color: #888; }

        .mac-addr {
            font-size: 0.75rem;
            color: var(--text-secondary);
            letter-spacing: 0.02em;
        }

        .vendor-name {
            color: var(--text-muted);
            font-size: 0.75rem;
        }

        .device-name {
            color: var(--text-primary);
        }

        .sighting-count {
            font-size: 0.8rem;
            color: var(--accent-amber);
        }

        .last-seen {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .last-seen.recent {
            color: var(--accent-green);
        }

        .watched-star {
            color: var(--accent-amber);
            margin-right: 0.25rem;
        }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.15s;
        }

        .modal-overlay.active {
            opacity: 1;
            pointer-events: all;
        }

        .modal {
            background: var(--bg-panel);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            width: 90%;
            max-width: 700px;
            max-height: 85vh;
            overflow-y: auto;
        }

        .modal-header {
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-tertiary);
        }

        .modal-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .modal-close {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1.25rem;
            line-height: 1;
        }

        .modal-close:hover { color: var(--text-primary); }

        .modal-body {
            padding: 1rem;
        }

        .detail-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }

        .detail-item {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 3px;
            padding: 0.75rem;
        }

        .detail-item.full { grid-column: 1 / -1; }

        .detail-label {
            font-size: 0.6rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 0.35rem;
        }

        .detail-value {
            font-size: 0.85rem;
            color: var(--text-primary);
            word-break: break-all;
        }

        .detail-value.mono { font-family: var(--font-mono); }
        .detail-value.highlight { color: var(--accent-amber); }

        /* Heatmaps */
        .heatmap-section {
            margin-top: 1.5rem;
        }

        .heatmap-title {
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }

        .heatmap {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 3px;
            padding: 0.75rem;
            font-size: 0.8rem;
        }

        .heatmap-labels {
            color: var(--text-muted);
            font-size: 0.65rem;
            margin-bottom: 0.25rem;
        }

        /* Timeline Chart */
        .timeline-chart {
            display: flex;
            align-items: flex-end;
            gap: 2px;
            height: 50px;
            padding: 0.5rem 0;
        }

        .timeline-bar {
            flex: 1;
            min-width: 3px;
            background: var(--accent-red);
            border-radius: 1px 1px 0 0;
            transition: background 0.1s;
            cursor: pointer;
            opacity: 0.7;
        }

        .timeline-bar:hover {
            opacity: 1;
            background: var(--accent-orange);
        }

        .timeline-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.6rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        /* RSSI Chart */
        .rssi-chart {
            position: relative;
            height: 70px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 3px;
            padding: 0.5rem;
            overflow: hidden;
        }

        .rssi-chart svg { width: 100%; height: 100%; }
        .rssi-line { fill: none; stroke: var(--accent-red); stroke-width: 1.5; }
        .rssi-area { fill: url(#rssiGradient); }
        .rssi-label { font-size: 0.55rem; fill: var(--text-muted); }

        /* Action Buttons in Modal */
        .action-row {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }

        .btn-watch {
            background: transparent;
            border: 1px solid var(--accent-amber);
            color: var(--accent-amber);
        }

        .btn-watch.active {
            background: var(--accent-amber);
            color: #000;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 0.75rem;
            font-size: 0.65rem;
            color: var(--text-muted);
            border-top: 1px solid var(--border-color);
            background: var(--bg-secondary);
        }

        .footer a { color: var(--accent-red); text-decoration: none; }
        .footer a:hover { text-decoration: underline; }

        /* Responsive */
        @media (max-width: 900px) {
            .main { grid-template-columns: 1fr; }
            .sidebar { display: none; }
        }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="topbar-left">
            <a href="/" class="brand">
                <span class="brand-icon">◉</span>
                <span class="brand-text">BLUE<span>HOOD</span></span>
            </a>
            <nav class="nav">
                <a href="/" class="nav-link active">Recon</a>
                <a href="/settings" class="nav-link">Config</a>
                <a href="/about" class="nav-link">Intel</a>
            </nav>
        </div>
        <div class="topbar-right">
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span>Scanning</span>
            </div>
            <div class="timestamp" id="last-update">--:--:--</div>
        </div>
    </header>

    <div class="main">
        <aside class="sidebar">
            <div class="panel">
                <div class="panel-header">Target Statistics</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <span class="stat-label">Identified</span>
                        <span class="stat-value red" id="stat-total">--</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Active</span>
                        <span class="stat-value green" id="stat-today">--</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">New Targets</span>
                        <span class="stat-value amber" id="stat-new-hour">--</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Randomized</span>
                        <span class="stat-value blue" id="stat-randomized">--</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">Filter by Class</div>
                <div class="filter-group" id="filter-group">
                    <button class="filter-btn active" data-filter="all">All Targets <span class="filter-count" id="count-all">--</span></button>
                    <button class="filter-btn" data-filter="watched">★ Watching <span class="filter-count" id="count-watched">--</span></button>
                    <button class="filter-btn" data-filter="phone">Phones <span class="filter-count" id="count-phone">--</span></button>
                    <button class="filter-btn" data-filter="laptop">Computers <span class="filter-count" id="count-laptop">--</span></button>
                    <button class="filter-btn" data-filter="audio">Audio <span class="filter-count" id="count-audio">--</span></button>
                    <button class="filter-btn" data-filter="smart">IoT <span class="filter-count" id="count-smart">--</span></button>
                    <button class="filter-btn" data-filter="unknown">Unclassified <span class="filter-count" id="count-unknown">--</span></button>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">Date Range Query</div>
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    <input type="datetime-local" class="search-input" id="search-start" style="font-size: 0.7rem;">
                    <input type="datetime-local" class="search-input" id="search-end" style="font-size: 0.7rem;">
                    <div style="display: flex; gap: 0.5rem;">
                        <button class="btn" style="flex:1;" onclick="clearDateFilters()">Clear</button>
                        <button class="btn btn-primary" style="flex:1;" onclick="searchByDateRange()">Query</button>
                    </div>
                </div>
            </div>
        </aside>

        <main class="content">
            <div class="search-bar">
                <input type="text" class="search-input" id="search" placeholder="Search MAC, vendor, or identifier...">
                <button class="btn" onclick="exportData()">Export CSV</button>
            </div>

            <div class="table-container">
                <div class="table-header">
                    <span class="table-title">Identified Targets</span>
                    <div class="table-actions">
                        <span style="font-size: 0.7rem; color: var(--text-muted);">
                            <span id="visible-count">--</span> targets
                        </span>
                    </div>
                </div>
                <table class="device-table">
                    <thead>
                        <tr>
                            <th>Class</th>
                            <th>MAC Address</th>
                            <th>Vendor</th>
                            <th>Identifier</th>
                            <th>Sightings</th>
                            <th>Last Contact</th>
                        </tr>
                    </thead>
                    <tbody id="device-list">
                        <tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">Initializing scanner...</td></tr>
                    </tbody>
                </table>
            </div>
        </main>
    </div>

    <footer class="footer">
        BLUEHOOD v0.4.0 // Bluetooth Reconnaissance Framework // <a href="https://github.com/dannymcc/bluehood">Source</a>
    </footer>

    <!-- Target Detail Modal -->
    <div class="modal-overlay" id="device-modal">
        <div class="modal">
            <div class="modal-header">
                <span class="modal-title">Target Intelligence</span>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-content">
                <!-- Dynamic content -->
            </div>
        </div>
    </div>

    <script>
        let allDevices = [];
        let currentFilter = 'all';
        let dateFilteredDevices = null;

        async function refreshDevices() {
            try {
                const response = await fetch('/api/devices');
                const data = await response.json();
                allDevices = data.devices || [];
                updateStats(data);
                updateFilterCounts();
                if (!dateFilteredDevices) renderDevices();
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Scan error:', error);
            }
        }

        function updateStats(data) {
            document.getElementById('stat-total').textContent = data.total || 0;
            document.getElementById('stat-today').textContent = data.active_today || 0;
            document.getElementById('stat-new-hour').textContent = data.new_past_hour || 0;
            document.getElementById('stat-randomized').textContent = data.randomized_count || 0;
        }

        function updateFilterCounts() {
            const counts = { all: 0, watched: 0, phone: 0, laptop: 0, audio: 0, smart: 0, unknown: 0 };
            allDevices.forEach(d => {
                counts.all++;
                if (d.watched) counts.watched++;
                if (d.device_type === 'phone') counts.phone++;
                else if (d.device_type === 'laptop' || d.device_type === 'computer') counts.laptop++;
                else if (d.device_type === 'audio' || d.device_type === 'speaker') counts.audio++;
                else if (d.device_type === 'smart') counts.smart++;
                else if (d.device_type === 'unknown') counts.unknown++;
            });
            Object.keys(counts).forEach(k => {
                const el = document.getElementById('count-' + k);
                if (el) el.textContent = counts[k];
            });
        }

        async function searchByDateRange() {
            const startInput = document.getElementById('search-start').value;
            const endInput = document.getElementById('search-end').value;
            if (!startInput && !endInput) { clearDateFilters(); return; }
            try {
                let url = '/api/search?';
                if (startInput) url += 'start=' + encodeURIComponent(startInput) + '&';
                if (endInput) url += 'end=' + encodeURIComponent(endInput);
                const response = await fetch(url);
                const data = await response.json();
                dateFilteredDevices = data.devices || [];
                renderDevices();
            } catch (error) { console.error('Query error:', error); }
        }

        function clearDateFilters() {
            document.getElementById('search-start').value = '';
            document.getElementById('search-end').value = '';
            dateFilteredDevices = null;
            renderDevices();
        }

        function renderDevices() {
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const tbody = document.getElementById('device-list');
            const sourceDevices = dateFilteredDevices !== null ? dateFilteredDevices : allDevices;

            let filtered = sourceDevices.filter(d => {
                if (currentFilter === 'watched') { if (!d.watched) return false; }
                else if (currentFilter === 'laptop') { if (d.device_type !== 'laptop' && d.device_type !== 'computer') return false; }
                else if (currentFilter !== 'all' && d.device_type !== currentFilter) return false;
                if (searchTerm) {
                    const searchable = [d.mac, d.vendor, d.friendly_name].join(' ').toLowerCase();
                    if (!searchable.includes(searchTerm)) return false;
                }
                return true;
            });

            document.getElementById('visible-count').textContent = filtered.length;

            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">No targets match criteria</td></tr>';
                return;
            }

            tbody.innerHTML = filtered.map(d => {
                const typeClass = getTypeClass(d.device_type);
                const lastSeen = formatLastSeen(d.last_seen);
                const isRecent = isRecentlySeen(d.last_seen);
                const watchedStar = d.watched ? '<span class="watched-star">★</span>' : '';

                return '<tr onclick="showDevice(\\'' + d.mac + '\\')">' +
                    '<td><span class="type-badge ' + typeClass + '">' + watchedStar + d.type_icon + ' ' + d.type_label + '</span></td>' +
                    '<td class="mac-addr">' + d.mac + '</td>' +
                    '<td class="vendor-name">' + (d.vendor || '—') + '</td>' +
                    '<td class="device-name">' + (d.friendly_name || '—') + '</td>' +
                    '<td class="sighting-count">' + d.total_sightings + '</td>' +
                    '<td class="last-seen ' + (isRecent ? 'recent' : '') + '">' + lastSeen + '</td>' +
                    '</tr>';
            }).join('');
        }

        function getTypeClass(type) {
            const classes = { phone: 'type-phone', laptop: 'type-laptop', computer: 'type-laptop', tablet: 'type-phone', smart: 'type-smart', audio: 'type-audio', speaker: 'type-audio', watch: 'type-watch', wearable: 'type-watch', tv: 'type-tv', vehicle: 'type-vehicle' };
            return classes[type] || 'type-unknown';
        }

        function formatLastSeen(isoString) {
            if (!isoString) return '—';
            const date = new Date(isoString);
            const now = new Date();
            const diffMins = Math.floor((now - date) / 60000);
            if (diffMins < 1) return 'NOW';
            if (diffMins < 60) return diffMins + 'm';
            if (diffMins < 1440) return Math.floor(diffMins / 60) + 'h';
            return date.toLocaleDateString();
        }

        function isRecentlySeen(isoString) {
            if (!isoString) return false;
            return (new Date() - new Date(isoString)) < 600000;
        }

        async function showDevice(mac) {
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac));
                const data = await response.json();
                renderModal(data);
                document.getElementById('device-modal').classList.add('active');
            } catch (error) { console.error('Error:', error); }
        }

        function renderModal(data) {
            const d = data.device;
            const content = document.getElementById('modal-content');

            let rssiDisplay = '—';
            if (data.avg_rssi !== null && data.avg_rssi !== undefined) {
                const rssi = data.avg_rssi;
                let strength = 'WEAK';
                if (rssi > -50) strength = 'STRONG';
                else if (rssi > -60) strength = 'GOOD';
                else if (rssi > -70) strength = 'FAIR';
                rssiDisplay = rssi + ' dBm (' + strength + ')';
            }

            const watchBtnText = d.watched ? '★ WATCHING' : '☆ WATCH TARGET';
            const watchBtnClass = d.watched ? 'btn btn-watch active' : 'btn btn-watch';

            content.innerHTML = '<div class="action-row">' +
                '<button class="' + watchBtnClass + '" id="watch-btn" onclick="toggleWatch(\\'' + d.mac + '\\')">' + watchBtnText + '</button>' +
                '</div>' +
                '<div class="detail-grid">' +
                '<div class="detail-item"><div class="detail-label">MAC Address</div><div class="detail-value mono">' + d.mac + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Classification</div><div class="detail-value">' + data.type_label + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Vendor OUI</div><div class="detail-value">' + (d.vendor || '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Identifier</div><div class="detail-value">' + (d.friendly_name || '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">First Contact</div><div class="detail-value mono">' + (d.first_seen ? new Date(d.first_seen).toLocaleString() : '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Last Contact</div><div class="detail-value mono">' + (d.last_seen ? new Date(d.last_seen).toLocaleString() : '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Total Sightings</div><div class="detail-value highlight">' + d.total_sightings + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Signal Strength</div><div class="detail-value">' + rssiDisplay + '</div></div>' +
                '<div class="detail-item full"><div class="detail-label">Behavioral Pattern</div><div class="detail-value">' + (data.pattern || 'Insufficient data') + '</div></div>' +
                '<div class="detail-item full"><div class="detail-label">BLE Service Fingerprint</div><div class="detail-value mono" style="font-size:0.75rem;">' + (data.uuid_names && data.uuid_names.length > 0 ? data.uuid_names.join(', ') : '—') + '</div></div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Hourly Activity Matrix (30d)</div>' +
                '<div class="heatmap"><div class="heatmap-labels">00  03  06  09  12  15  18  21</div><div>' + (data.hourly_heatmap || '------------------------') + '</div></div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Daily Activity Matrix</div>' +
                '<div class="heatmap"><div class="heatmap-labels">M   T   W   T   F   S   S</div><div>' + (data.daily_heatmap || '-------') + '</div></div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Presence Timeline (30d)</div>' +
                renderTimeline(data.timeline) +
                '</div>' +
                '<div class="heatmap-section" id="rssi-section">' +
                '<div class="heatmap-title">Signal History (7d)</div>' +
                '<div class="rssi-chart" id="rssi-chart"><div style="color: var(--text-muted); font-size: 0.75rem; text-align: center; padding-top: 1.5rem;">Loading...</div></div>' +
                '</div>';

            loadRssiChart(d.mac);
        }

        function renderTimeline(timeline) {
            if (!timeline || timeline.length === 0) return '<div style="color: var(--text-muted); font-size: 0.75rem;">No data</div>';
            const maxCount = Math.max(...timeline.map(d => d.count));
            const bars = timeline.map(d => {
                const height = maxCount > 0 ? (d.count / maxCount * 100) : 0;
                const date = new Date(d.date);
                const tooltip = date.toLocaleDateString() + ': ' + d.count + ' sightings';
                return '<div class="timeline-bar" style="height: ' + height + '%" title="' + tooltip + '"></div>';
            }).join('');
            const firstDate = new Date(timeline[0].date);
            const lastDate = new Date(timeline[timeline.length - 1].date);
            const formatDate = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            return '<div class="timeline-chart">' + bars + '</div><div class="timeline-labels"><span>' + formatDate(firstDate) + '</span><span>' + formatDate(lastDate) + '</span></div>';
        }

        async function loadRssiChart(mac) {
            const container = document.getElementById('rssi-chart');
            if (!container) return;
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac) + '/rssi?days=7');
                const data = await response.json();
                if (!data.rssi_history || data.rssi_history.length < 2) {
                    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.75rem; text-align: center; padding-top: 1.5rem;">Insufficient data</div>';
                    return;
                }
                renderRssiChart(container, data.rssi_history);
            } catch (error) {
                container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.75rem; text-align: center; padding-top: 1.5rem;">Error</div>';
            }
        }

        function renderRssiChart(container, rssiData) {
            const width = container.clientWidth - 20;
            const height = 50;
            const padding = { left: 30, right: 10, top: 5, bottom: 15 };
            const rssiValues = rssiData.map(d => d.rssi);
            const minRssi = Math.min(...rssiValues);
            const maxRssi = Math.max(...rssiValues);
            const xScale = (i) => padding.left + (i / (rssiData.length - 1)) * (width - padding.left - padding.right);
            const yScale = (rssi) => {
                const range = maxRssi - minRssi || 1;
                return padding.top + (1 - (rssi - minRssi) / range) * (height - padding.top - padding.bottom);
            };
            const linePath = rssiData.map((d, i) => (i === 0 ? 'M' : 'L') + xScale(i) + ',' + yScale(d.rssi)).join(' ');
            const areaPath = linePath + ' L' + xScale(rssiData.length - 1) + ',' + (height - padding.bottom) + ' L' + padding.left + ',' + (height - padding.bottom) + ' Z';
            const firstTime = new Date(rssiData[0].timestamp);
            const lastTime = new Date(rssiData[rssiData.length - 1].timestamp);
            const formatTime = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

            container.innerHTML = '<svg viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none">' +
                '<defs><linearGradient id="rssiGradient" x1="0%" y1="0%" x2="0%" y2="100%">' +
                '<stop offset="0%" style="stop-color: #dc2626; stop-opacity: 0.3"/>' +
                '<stop offset="100%" style="stop-color: #dc2626; stop-opacity: 0.05"/>' +
                '</linearGradient></defs>' +
                '<path class="rssi-area" d="' + areaPath + '"/>' +
                '<path class="rssi-line" d="' + linePath + '"/>' +
                '<text class="rssi-label" x="' + padding.left + '" y="' + (height - 2) + '">' + formatTime(firstTime) + '</text>' +
                '<text class="rssi-label" x="' + (width - padding.right) + '" y="' + (height - 2) + '" text-anchor="end">' + formatTime(lastTime) + '</text>' +
                '<text class="rssi-label" x="2" y="' + (padding.top + 6) + '">' + maxRssi + '</text>' +
                '<text class="rssi-label" x="2" y="' + (height - padding.bottom - 2) + '">' + minRssi + '</text>' +
                '</svg>';
        }

        async function toggleWatch(mac) {
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac) + '/watch', { method: 'POST' });
                const data = await response.json();
                const btn = document.getElementById('watch-btn');
                if (data.watched) {
                    btn.textContent = '★ WATCHING';
                    btn.className = 'btn btn-watch active';
                } else {
                    btn.textContent = '☆ WATCH TARGET';
                    btn.className = 'btn btn-watch';
                }
                refreshDevices();
            } catch (error) { console.error('Error:', error); }
        }

        function closeModal() { document.getElementById('device-modal').classList.remove('active'); }

        function exportData() {
            const csv = ['MAC,Vendor,Identifier,Class,Sightings,Last_Contact'];
            allDevices.forEach(d => {
                csv.push([d.mac, d.vendor || '', d.friendly_name || '', d.device_type || '', d.total_sightings, d.last_seen || ''].join(','));
            });
            const blob = new Blob([csv.join('\\n')], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'bluehood-recon-' + new Date().toISOString().split('T')[0] + '.csv';
            a.click();
        }

        // Filter handlers
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                renderDevices();
            });
        });

        document.getElementById('search').addEventListener('input', renderDevices);
        document.getElementById('device-modal').addEventListener('click', (e) => { if (e.target.id === 'device-modal') closeModal(); });

        refreshDevices();
        setInterval(refreshDevices, 10000);
    </script>
</body>
</html>
"""

SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BLUEHOOD // Configuration</title>
    <style>
        :root {
            --bg-primary: #0d0d0d;
            --bg-secondary: #141414;
            --bg-tertiary: #1a1a1a;
            --bg-hover: #242424;
            --text-primary: #e0e0e0;
            --text-secondary: #888888;
            --text-muted: #555555;
            --accent-red: #dc2626;
            --accent-green: #16a34a;
            --border-color: #2a2a2a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: var(--font-mono); background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; font-size: 13px; }

        .topbar { background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); padding: 0.5rem 1rem; display: flex; justify-content: space-between; align-items: center; }
        .topbar-left { display: flex; align-items: center; gap: 1.5rem; }
        .brand { display: flex; align-items: center; gap: 0.5rem; text-decoration: none; color: inherit; }
        .brand-icon { color: var(--accent-red); font-size: 1.1rem; }
        .brand-text { font-weight: 700; font-size: 0.9rem; letter-spacing: 0.05em; }
        .brand-text span { color: var(--accent-red); }
        .nav { display: flex; gap: 0.25rem; }
        .nav-link { color: var(--text-secondary); text-decoration: none; font-size: 0.75rem; padding: 0.4rem 0.75rem; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.05em; transition: all 0.1s; }
        .nav-link:hover, .nav-link.active { color: var(--text-primary); background: var(--bg-tertiary); }

        .main { max-width: 700px; margin: 0 auto; padding: 2rem 1rem; }
        .page-header { margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border-color); }
        .page-title { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.15em; color: var(--text-muted); margin-bottom: 0.5rem; }
        .page-heading { font-size: 1.25rem; font-weight: 700; }

        .panel { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 4px; margin-bottom: 1.5rem; }
        .panel-header { padding: 0.75rem 1rem; background: var(--bg-tertiary); border-bottom: 1px solid var(--border-color); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-secondary); }
        .panel-body { padding: 1rem; }

        .form-group { margin-bottom: 1rem; }
        .form-label { display: block; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 0.5rem; }
        .form-input { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid var(--border-color); border-radius: 3px; background: var(--bg-tertiary); color: var(--text-primary); font-family: var(--font-mono); font-size: 0.8rem; }
        .form-input:focus { outline: none; border-color: var(--accent-red); }

        .form-check { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.75rem; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 3px; margin-bottom: 0.5rem; cursor: pointer; }
        .form-check:hover { border-color: var(--accent-red); }
        .form-check input { width: 16px; height: 16px; accent-color: var(--accent-red); margin-top: 2px; }
        .form-check-label { font-size: 0.8rem; }
        .form-check-desc { font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem; }

        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

        .btn { padding: 0.6rem 1.25rem; border-radius: 3px; font-family: var(--font-mono); font-size: 0.7rem; font-weight: 500; cursor: pointer; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; text-decoration: none; display: inline-block; transition: all 0.1s; }
        .btn:hover { background: var(--bg-hover); color: var(--text-primary); }
        .btn-primary { background: var(--accent-red); border-color: var(--accent-red); color: white; }
        .btn-primary:hover { background: #b91c1c; }

        .btn-row { display: flex; gap: 0.75rem; margin-top: 1.5rem; }

        .status-msg { padding: 0.75rem 1rem; border-radius: 3px; font-size: 0.8rem; margin-bottom: 1rem; display: none; border: 1px solid; }
        .status-msg.success { background: rgba(22, 163, 74, 0.1); color: var(--accent-green); border-color: var(--accent-green); display: block; }
        .status-msg.error { background: rgba(220, 38, 38, 0.1); color: var(--accent-red); border-color: var(--accent-red); display: block; }

        .footer { text-align: center; padding: 1.5rem; font-size: 0.65rem; color: var(--text-muted); border-top: 1px solid var(--border-color); }
        .footer a { color: var(--accent-red); text-decoration: none; }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="topbar-left">
            <a href="/" class="brand"><span class="brand-icon">◉</span><span class="brand-text">BLUE<span>HOOD</span></span></a>
            <nav class="nav">
                <a href="/" class="nav-link">Recon</a>
                <a href="/settings" class="nav-link active">Config</a>
                <a href="/about" class="nav-link">Intel</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="page-header">
            <div class="page-title">System Configuration</div>
            <h1 class="page-heading">Alert Configuration</h1>
        </div>

        <div id="status-msg" class="status-msg"></div>

        <form id="settings-form">
            <div class="panel">
                <div class="panel-header">Push Notification Channel (ntfy.sh)</div>
                <div class="panel-body">
                    <div class="form-group">
                        <label class="form-label">Topic Identifier</label>
                        <input type="text" class="form-input" id="ntfy_topic" placeholder="e.g., bluehood-ops-alerts">
                    </div>
                    <label class="form-check">
                        <input type="checkbox" id="ntfy_enabled">
                        <div>
                            <div class="form-check-label">Enable Push Notifications</div>
                            <div class="form-check-desc">Route alerts through ntfy.sh service</div>
                        </div>
                    </label>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">Alert Triggers</div>
                <div class="panel-body">
                    <label class="form-check">
                        <input type="checkbox" id="notify_new_device">
                        <div>
                            <div class="form-check-label">New Target Acquired</div>
                            <div class="form-check-desc">Alert on first contact with unknown device</div>
                        </div>
                    </label>
                    <label class="form-check">
                        <input type="checkbox" id="notify_watched_return">
                        <div>
                            <div class="form-check-label">Watched Target Returns</div>
                            <div class="form-check-desc">Alert when monitored target re-enters range</div>
                        </div>
                    </label>
                    <label class="form-check">
                        <input type="checkbox" id="notify_watched_leave">
                        <div>
                            <div class="form-check-label">Watched Target Departs</div>
                            <div class="form-check-desc">Alert when monitored target exits range</div>
                        </div>
                    </label>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">Detection Thresholds</div>
                <div class="panel-body">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Absence Threshold (min)</label>
                            <input type="number" class="form-input" id="watched_absence_minutes" value="30" min="1" max="1440">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Return Threshold (min)</label>
                            <input type="number" class="form-input" id="watched_return_minutes" value="5" min="1" max="60">
                        </div>
                    </div>
                </div>
            </div>

            <div class="btn-row">
                <button type="submit" class="btn btn-primary">Save Configuration</button>
                <a href="/" class="btn">Cancel</a>
            </div>
        </form>
    </main>

    <footer class="footer">BLUEHOOD v0.4.0 // <a href="https://github.com/dannymcc/bluehood">Source</a></footer>

    <script>
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const data = await response.json();
                document.getElementById('ntfy_topic').value = data.ntfy_topic || '';
                document.getElementById('ntfy_enabled').checked = data.ntfy_enabled;
                document.getElementById('notify_new_device').checked = data.notify_new_device;
                document.getElementById('notify_watched_return').checked = data.notify_watched_return;
                document.getElementById('notify_watched_leave').checked = data.notify_watched_leave;
                document.getElementById('watched_absence_minutes').value = data.watched_absence_minutes;
                document.getElementById('watched_return_minutes').value = data.watched_return_minutes;
            } catch (error) { showStatus('Error loading configuration', 'error'); }
        }

        async function saveSettings(e) {
            e.preventDefault();
            const settings = {
                ntfy_topic: document.getElementById('ntfy_topic').value,
                ntfy_enabled: document.getElementById('ntfy_enabled').checked,
                notify_new_device: document.getElementById('notify_new_device').checked,
                notify_watched_return: document.getElementById('notify_watched_return').checked,
                notify_watched_leave: document.getElementById('notify_watched_leave').checked,
                watched_absence_minutes: parseInt(document.getElementById('watched_absence_minutes').value),
                watched_return_minutes: parseInt(document.getElementById('watched_return_minutes').value),
            };
            try {
                const response = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) });
                if (response.ok) showStatus('Configuration saved', 'success');
                else showStatus('Error saving configuration', 'error');
            } catch (error) { showStatus('Error saving configuration', 'error'); }
        }

        function showStatus(message, type) {
            const el = document.getElementById('status-msg');
            el.textContent = message;
            el.className = 'status-msg ' + type;
            if (type === 'success') setTimeout(() => { el.className = 'status-msg'; }, 3000);
        }

        document.getElementById('settings-form').addEventListener('submit', saveSettings);
        loadSettings();
    </script>
</body>
</html>
"""

ABOUT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BLUEHOOD // Intel</title>
    <style>
        :root {
            --bg-primary: #0d0d0d;
            --bg-secondary: #141414;
            --bg-tertiary: #1a1a1a;
            --text-primary: #e0e0e0;
            --text-secondary: #888888;
            --text-muted: #555555;
            --accent-red: #dc2626;
            --accent-amber: #d97706;
            --border-color: #2a2a2a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: var(--font-mono); background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; font-size: 13px; }

        .topbar { background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); padding: 0.5rem 1rem; display: flex; justify-content: space-between; align-items: center; }
        .topbar-left { display: flex; align-items: center; gap: 1.5rem; }
        .brand { display: flex; align-items: center; gap: 0.5rem; text-decoration: none; color: inherit; }
        .brand-icon { color: var(--accent-red); font-size: 1.1rem; }
        .brand-text { font-weight: 700; font-size: 0.9rem; letter-spacing: 0.05em; }
        .brand-text span { color: var(--accent-red); }
        .nav { display: flex; gap: 0.25rem; }
        .nav-link { color: var(--text-secondary); text-decoration: none; font-size: 0.75rem; padding: 0.4rem 0.75rem; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.05em; transition: all 0.1s; }
        .nav-link:hover, .nav-link.active { color: var(--text-primary); background: var(--bg-tertiary); }

        .main { max-width: 800px; margin: 0 auto; padding: 2rem 1rem; }

        .hero { text-align: center; margin-bottom: 2.5rem; padding: 2rem; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 4px; }
        .hero-icon { color: var(--accent-red); font-size: 2.5rem; margin-bottom: 1rem; }
        .hero-title { font-size: 1.5rem; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 0.5rem; }
        .hero-title span { color: var(--accent-red); }
        .hero-tagline { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.15em; }

        .panel { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 4px; margin-bottom: 1.5rem; }
        .panel-header { padding: 0.75rem 1rem; background: var(--bg-tertiary); border-bottom: 1px solid var(--border-color); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent-red); }
        .panel-body { padding: 1rem; }
        .panel-body p { color: var(--text-secondary); line-height: 1.8; margin-bottom: 0.75rem; font-size: 0.85rem; }
        .panel-body p:last-child { margin-bottom: 0; }
        .panel-body a { color: var(--accent-red); text-decoration: none; }
        .panel-body a:hover { text-decoration: underline; }

        .capability-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
        .capability { background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 3px; padding: 1rem; text-align: center; }
        .capability-icon { font-size: 1.25rem; margin-bottom: 0.5rem; }
        .capability-name { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
        .capability-desc { font-size: 0.65rem; color: var(--text-muted); }

        .warning { background: rgba(220, 38, 38, 0.1); border: 1px solid var(--accent-red); border-radius: 3px; padding: 1rem; margin-top: 1rem; }
        .warning-title { color: var(--accent-red); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem; }
        .warning p { color: var(--text-secondary); font-size: 0.8rem; line-height: 1.6; }

        .version { text-align: center; padding: 1.5rem; color: var(--text-muted); font-size: 0.75rem; letter-spacing: 0.1em; }

        .footer { text-align: center; padding: 1.5rem; font-size: 0.65rem; color: var(--text-muted); border-top: 1px solid var(--border-color); }
        .footer a { color: var(--accent-red); text-decoration: none; }

        @media (max-width: 600px) { .capability-grid { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="topbar-left">
            <a href="/" class="brand"><span class="brand-icon">◉</span><span class="brand-text">BLUE<span>HOOD</span></span></a>
            <nav class="nav">
                <a href="/" class="nav-link">Recon</a>
                <a href="/settings" class="nav-link">Config</a>
                <a href="/about" class="nav-link active">Intel</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="hero">
            <div class="hero-icon">◉</div>
            <h1 class="hero-title">BLUE<span>HOOD</span></h1>
            <p class="hero-tagline">Bluetooth Reconnaissance Framework</p>
        </div>

        <div class="panel">
            <div class="panel-header">Mission Brief</div>
            <div class="panel-body">
                <p>Bluehood is a passive Bluetooth reconnaissance tool designed for authorized security assessments and research. It enables operators to identify, classify, and track Bluetooth-enabled devices within radio range.</p>
                <p>Developed in response to the <a href="https://whisperpair.eu/">WhisperPair vulnerability</a> (CVE-2025-36911), this framework demonstrates the surveillance potential of Bluetooth metadata collection.</p>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Capabilities</div>
            <div class="panel-body">
                <div class="capability-grid">
                    <div class="capability">
                        <div class="capability-icon">📡</div>
                        <div class="capability-name">Dual-Mode Scan</div>
                        <div class="capability-desc">BLE + Classic BT</div>
                    </div>
                    <div class="capability">
                        <div class="capability-icon">🔍</div>
                        <div class="capability-name">OUI Lookup</div>
                        <div class="capability-desc">Vendor identification</div>
                    </div>
                    <div class="capability">
                        <div class="capability-icon">📊</div>
                        <div class="capability-name">Pattern Intel</div>
                        <div class="capability-desc">Behavioral analysis</div>
                    </div>
                    <div class="capability">
                        <div class="capability-icon">🔔</div>
                        <div class="capability-name">Alert System</div>
                        <div class="capability-desc">Push notifications</div>
                    </div>
                    <div class="capability">
                        <div class="capability-icon">⭐</div>
                        <div class="capability-name">Target Watch</div>
                        <div class="capability-desc">Priority tracking</div>
                    </div>
                    <div class="capability">
                        <div class="capability-icon">🔐</div>
                        <div class="capability-name">MAC Filter</div>
                        <div class="capability-desc">Randomized detection</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Legal Notice</div>
            <div class="panel-body">
                <div class="warning">
                    <div class="warning-title">⚠ Authorization Required</div>
                    <p>This tool is intended for authorized security testing, research, and educational purposes only. Operators must ensure compliance with applicable laws and obtain proper authorization before deployment. Unauthorized surveillance of Bluetooth devices may violate privacy laws in your jurisdiction.</p>
                </div>
            </div>
        </div>

        <div class="version">v0.4.0 // BUILD 2026.01</div>
    </main>

    <footer class="footer">BLUEHOOD // <a href="https://github.com/dannymcc/bluehood">Source Repository</a></footer>
</body>
</html>
"""


class WebServer:
    """Web server for Bluehood dashboard."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, notifications=None):
        self.host = host
        self.port = port
        self.app = web.Application()
        self._notifications = notifications
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/settings", self.settings_page)
        self.app.router.add_get("/about", self.about_page)
        self.app.router.add_get("/api/devices", self.api_devices)
        self.app.router.add_get("/api/device/{mac}", self.api_device)
        self.app.router.add_post("/api/device/{mac}/watch", self.api_toggle_watch)
        self.app.router.add_post("/api/device/{mac}/group", self.api_set_device_group)
        self.app.router.add_post("/api/device/{mac}/name", self.api_set_device_name)
        self.app.router.add_get("/api/device/{mac}/rssi", self.api_device_rssi)
        self.app.router.add_get("/api/search", self.api_search)
        self.app.router.add_get("/api/stats", self.api_stats)
        # Settings
        self.app.router.add_get("/api/settings", self.api_get_settings)
        self.app.router.add_post("/api/settings", self.api_update_settings)
        # Groups
        self.app.router.add_get("/api/groups", self.api_get_groups)
        self.app.router.add_post("/api/groups", self.api_create_group)
        self.app.router.add_put("/api/groups/{group_id}", self.api_update_group)
        self.app.router.add_delete("/api/groups/{group_id}", self.api_delete_group)

    async def index(self, request: web.Request) -> web.Response:
        """Serve the main dashboard."""
        return web.Response(text=HTML_TEMPLATE, content_type="text/html")

    async def settings_page(self, request: web.Request) -> web.Response:
        """Serve the settings page."""
        return web.Response(text=SETTINGS_TEMPLATE, content_type="text/html")

    async def about_page(self, request: web.Request) -> web.Response:
        """Serve the about page."""
        return web.Response(text=ABOUT_TEMPLATE, content_type="text/html")

    async def api_devices(self, request: web.Request) -> web.Response:
        """Get all devices with stats."""
        devices = await db.get_all_devices(include_ignored=True)

        now = datetime.now()
        today = now.date()
        one_hour_ago = now - timedelta(hours=1)

        active_today = 0
        new_past_hour = 0
        total_sightings = 0
        randomized_count = 0
        identified_count = 0
        type_set = set()

        device_list = []
        for d in devices:
            # Use service UUIDs for better classification
            device_type = d.device_type or classify_device(d.vendor, d.friendly_name, d.service_uuids)
            type_set.add(device_type)
            total_sightings += d.total_sightings

            # Check if MAC is randomized (privacy feature)
            randomized = is_randomized_mac(d.mac)

            if randomized:
                randomized_count += 1
                continue  # Skip randomized MACs from the main list

            identified_count += 1

            if d.last_seen and d.last_seen.date() == today:
                active_today += 1

            # Count devices first seen in the past hour
            if d.first_seen and d.first_seen >= one_hour_ago:
                new_past_hour += 1

            vendor_display = d.vendor

            device_list.append({
                "mac": d.mac,
                "vendor": vendor_display,
                "friendly_name": d.friendly_name,
                "device_type": device_type,
                "type_icon": get_type_icon(device_type),
                "type_label": get_type_label(device_type),
                "ignored": d.ignored,
                "watched": d.watched,
                "randomized_mac": False,
                "first_seen": d.first_seen.isoformat() if d.first_seen else None,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "total_sightings": d.total_sightings,
                "service_uuids": d.service_uuids,
                "uuid_names": get_uuid_names(d.service_uuids),
            })

        return web.json_response({
            "devices": device_list,
            "total": identified_count,
            "randomized_count": randomized_count,
            "active_today": active_today,
            "new_past_hour": new_past_hour,
        })

    async def api_device(self, request: web.Request) -> web.Response:
        """Get detailed info for a single device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        hourly = await db.get_hourly_distribution(mac, 30)
        daily = await db.get_daily_distribution(mac, 30)
        sightings = await db.get_sightings(mac, 30)
        daily_timeline = await db.get_daily_sightings(mac, 30)
        device_type = device.device_type or classify_device(device.vendor, device.friendly_name, device.service_uuids)

        # Calculate pattern summary
        pattern = self._analyze_pattern(hourly, daily, len(sightings))

        # Calculate average RSSI from recent sightings
        rssi_values = [s.rssi for s in sightings if s.rssi is not None]
        avg_rssi = round(sum(rssi_values) / len(rssi_values)) if rssi_values else None

        return web.json_response({
            "device": {
                "mac": device.mac,
                "vendor": device.vendor,
                "friendly_name": device.friendly_name,
                "device_type": device_type,
                "ignored": device.ignored,
                "watched": device.watched,
                "first_seen": device.first_seen.isoformat() if device.first_seen else None,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "total_sightings": device.total_sightings,
                "service_uuids": device.service_uuids,
            },
            "type_label": get_type_label(device_type),
            "uuid_names": get_uuid_names(device.service_uuids),
            "pattern": pattern,
            "avg_rssi": avg_rssi,
            "hourly_heatmap": generate_hourly_heatmap(hourly),
            "daily_heatmap": generate_daily_heatmap(daily),
            "timeline": daily_timeline,
        })

    async def api_toggle_watch(self, request: web.Request) -> web.Response:
        """Toggle watched status for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        # Toggle the watched status
        new_status = not device.watched
        await db.set_watched(mac, new_status)

        # Update notifications manager state
        if self._notifications:
            self._notifications.update_watched_state(mac, new_status)

        return web.json_response({
            "mac": mac,
            "watched": new_status,
        })

    async def api_set_device_group(self, request: web.Request) -> web.Response:
        """Set the group for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        try:
            data = await request.json()
            group_id = data.get("group_id")  # Can be None to remove from group
            await db.set_device_group(mac, group_id)
            return web.json_response({"mac": mac, "group_id": group_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_set_device_name(self, request: web.Request) -> web.Response:
        """Set the friendly name for a device."""
        mac = request.match_info["mac"]
        device = await db.get_device(mac)

        if not device:
            return web.json_response({"error": "Device not found"}, status=404)

        try:
            data = await request.json()
            name = data.get("name", "")
            await db.set_friendly_name(mac, name)
            return web.json_response({"mac": mac, "friendly_name": name})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_device_rssi(self, request: web.Request) -> web.Response:
        """Get RSSI history for a device."""
        mac = request.match_info["mac"]
        days = int(request.query.get("days", "7"))

        rssi_history = await db.get_rssi_history(mac, days)
        return web.json_response({"mac": mac, "rssi_history": rssi_history})

    def _analyze_pattern(self, hourly: dict, daily: dict, sighting_count: int) -> str:
        """Simple pattern analysis from hourly/daily data."""
        if sighting_count < 5:
            return "Insufficient data"

        parts = []

        # Frequency
        avg_per_day = sighting_count / 30
        if avg_per_day >= 5:
            parts.append("Constant")
        elif avg_per_day >= 2:
            parts.append("Very frequent")
        elif avg_per_day >= 1:
            parts.append("Daily")
        elif avg_per_day >= 0.5:
            parts.append("Regular")
        elif avg_per_day >= 0.15:
            parts.append("Occasional")
        else:
            parts.append("Rare")

        # Time pattern
        if hourly:
            total = sum(hourly.values())
            morning = sum(hourly.get(h, 0) for h in range(6, 12))
            afternoon = sum(hourly.get(h, 0) for h in range(12, 18))
            evening = sum(hourly.get(h, 0) for h in range(18, 24))
            night = sum(hourly.get(h, 0) for h in range(0, 6))

            if total > 0:
                dominant = max([(morning, "mornings"), (afternoon, "afternoons"),
                               (evening, "evenings"), (night, "nights")], key=lambda x: x[0])
                if dominant[0] / total > 0.5:
                    parts.append(dominant[1])

        # Day pattern
        if daily:
            total = sum(daily.values())
            weekday = sum(daily.get(d, 0) for d in range(5))
            weekend = sum(daily.get(d, 0) for d in range(5, 7))

            if total > 0:
                if weekday / total > 0.85:
                    parts.append("weekdays only")
                elif weekend / total > 0.7:
                    parts.append("weekends only")

        return ", ".join(parts) if parts else "No clear pattern"

    async def api_search(self, request: web.Request) -> web.Response:
        """Search for devices seen within a datetime range."""
        start_str = request.query.get("start")
        end_str = request.query.get("end")

        start_dt = None
        end_dt = None

        try:
            if start_str:
                start_dt = datetime.fromisoformat(start_str.replace("T", " "))
            if end_str:
                end_dt = datetime.fromisoformat(end_str.replace("T", " "))
        except ValueError:
            return web.json_response({"error": "Invalid datetime format"}, status=400)

        # Search for devices with sightings in the range
        results = await db.search_devices(None, start_dt, end_dt)

        device_list = []
        for r in results:
            device_type = r.get("device_type") or classify_device(r.get("vendor"), r.get("friendly_name"))
            device_list.append({
                "mac": r["mac"],
                "vendor": r.get("vendor"),
                "friendly_name": r.get("friendly_name"),
                "device_type": device_type,
                "type_icon": get_type_icon(device_type),
                "type_label": get_type_label(device_type),
                "ignored": r.get("ignored", False),
                "first_seen": r.get("range_first"),
                "last_seen": r.get("range_last"),
                "total_sightings": r.get("range_sightings", 0),
            })

        return web.json_response({
            "devices": device_list,
            "total": len(device_list),
            "query": {
                "start": start_str,
                "end": end_str,
            }
        })

    async def api_stats(self, request: web.Request) -> web.Response:
        """Get overall stats."""
        devices = await db.get_all_devices(include_ignored=True)
        today = datetime.now().date()

        return web.json_response({
            "total_devices": len(devices),
            "active_today": sum(1 for d in devices if d.last_seen and d.last_seen.date() == today),
            "total_sightings": sum(d.total_sightings for d in devices),
        })

    # ========================================================================
    # Settings API
    # ========================================================================

    async def api_get_settings(self, request: web.Request) -> web.Response:
        """Get all settings."""
        settings = await db.get_settings()
        return web.json_response({
            "ntfy_topic": settings.ntfy_topic or "",
            "ntfy_enabled": settings.ntfy_enabled,
            "notify_new_device": settings.notify_new_device,
            "notify_watched_return": settings.notify_watched_return,
            "notify_watched_leave": settings.notify_watched_leave,
            "watched_absence_minutes": settings.watched_absence_minutes,
            "watched_return_minutes": settings.watched_return_minutes,
        })

    async def api_update_settings(self, request: web.Request) -> web.Response:
        """Update settings."""
        try:
            data = await request.json()
            settings = db.Settings(
                ntfy_topic=data.get("ntfy_topic"),
                ntfy_enabled=data.get("ntfy_enabled", False),
                notify_new_device=data.get("notify_new_device", False),
                notify_watched_return=data.get("notify_watched_return", True),
                notify_watched_leave=data.get("notify_watched_leave", True),
                watched_absence_minutes=int(data.get("watched_absence_minutes", 30)),
                watched_return_minutes=int(data.get("watched_return_minutes", 5)),
            )
            await db.update_settings(settings)

            # Reload settings in notification manager
            if self._notifications:
                await self._notifications.reload_settings()

            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ========================================================================
    # Groups API
    # ========================================================================

    async def api_get_groups(self, request: web.Request) -> web.Response:
        """Get all device groups."""
        groups = await db.get_groups()
        return web.json_response({
            "groups": [
                {"id": g.id, "name": g.name, "color": g.color, "icon": g.icon}
                for g in groups
            ]
        })

    async def api_create_group(self, request: web.Request) -> web.Response:
        """Create a new device group."""
        try:
            data = await request.json()
            name = data.get("name")
            if not name:
                return web.json_response({"error": "Name is required"}, status=400)

            group = await db.create_group(
                name=name,
                color=data.get("color", "#3b82f6"),
                icon=data.get("icon", "📁"),
            )
            return web.json_response({
                "id": group.id,
                "name": group.name,
                "color": group.color,
                "icon": group.icon,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_update_group(self, request: web.Request) -> web.Response:
        """Update a device group."""
        try:
            group_id = int(request.match_info["group_id"])
            data = await request.json()

            await db.update_group(
                group_id=group_id,
                name=data.get("name", ""),
                color=data.get("color", "#3b82f6"),
                icon=data.get("icon", "📁"),
            )
            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def api_delete_group(self, request: web.Request) -> web.Response:
        """Delete a device group."""
        try:
            group_id = int(request.match_info["group_id"])
            await db.delete_group(group_id)
            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def start(self) -> web.AppRunner:
        """Start the web server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"Web dashboard available at http://{self.host}:{self.port}")
        return self._runner

    async def stop(self) -> None:
        """Stop the web server."""
        if hasattr(self, '_runner') and self._runner:
            await self._runner.cleanup()
            logger.info("Web server stopped")
