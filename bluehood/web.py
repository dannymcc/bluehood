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
    <title>Bluehood - Bluetooth Neighborhood</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a25;
            --bg-hover: #22222f;
            --text-primary: #e4e4e7;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-green: #22c55e;
            --accent-yellow: #eab308;
            --accent-red: #ef4444;
            --accent-purple: #a855f7;
            --border-color: #27272a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: var(--font-sans);
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        /* Header */
        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .logo-text span {
            color: var(--accent-cyan);
        }

        .header-subtitle {
            color: var(--text-muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .header-status {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .header-link {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.875rem;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            transition: all 0.15s ease;
        }

        .header-link:hover {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        /* Main Content */
        .main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            font-family: var(--font-mono);
        }

        .stat-value.blue { color: var(--accent-blue); }
        .stat-value.cyan { color: var(--accent-cyan); }
        .stat-value.green { color: var(--accent-green); }
        .stat-value.yellow { color: var(--accent-yellow); }
        .stat-value.purple { color: var(--accent-purple); }

        /* Section */
        .section {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
        }

        .section-title {
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
        }

        .section-actions {
            display: flex;
            gap: 0.5rem;
        }

        .btn {
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            border: 1px solid var(--border-color);
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }

        .btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .btn-primary {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: white;
        }

        .btn-primary:hover {
            background: #2563eb;
        }

        /* Device Table */
        .device-table {
            width: 100%;
            border-collapse: collapse;
        }

        .device-table th {
            text-align: left;
            padding: 0.75rem 1rem;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            background: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-color);
        }

        .device-table td {
            padding: 0.875rem 1rem;
            font-size: 0.875rem;
            border-bottom: 1px solid var(--border-color);
            vertical-align: middle;
        }

        .device-table tr:hover {
            background: var(--bg-hover);
        }

        .device-table tr:last-child td {
            border-bottom: none;
        }

        .device-type {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
            font-family: var(--font-mono);
        }

        .type-phone { background: #1e3a5f; color: #60a5fa; }
        .type-laptop { background: #1e3a3a; color: #5eead4; }
        .type-smart { background: #3a2e1e; color: #fbbf24; }
        .type-audio { background: #2e1e3a; color: #c084fc; }
        .type-watch { background: #1e3a2e; color: #4ade80; }
        .type-tv { background: #3a1e2e; color: #f472b6; }
        .type-vehicle { background: #3a3a1e; color: #facc15; }
        .type-unknown { background: #2a2a2a; color: #a1a1aa; }

        .mac-address {
            font-family: var(--font-mono);
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        .device-name {
            font-weight: 500;
        }

        .device-vendor {
            color: var(--text-muted);
            font-size: 0.8rem;
        }

        .sightings-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background: var(--bg-tertiary);
            border-radius: 4px;
            font-family: var(--font-mono);
            font-size: 0.75rem;
        }

        .last-seen {
            color: var(--text-muted);
            font-size: 0.8rem;
        }

        .last-seen.recent {
            color: var(--accent-green);
        }

        /* Search */
        .search-box {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }

        .search-input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-tertiary);
            color: var(--text-primary);
            font-size: 0.875rem;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-blue);
        }

        .search-input::placeholder {
            color: var(--text-muted);
        }

        /* Filter tabs */
        .filter-tabs {
            display: flex;
            gap: 0.25rem;
            padding: 0.25rem;
            background: var(--bg-tertiary);
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .filter-tab {
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            color: var(--text-muted);
            background: transparent;
            border: none;
        }

        .filter-tab:hover {
            color: var(--text-secondary);
        }

        .filter-tab.active {
            background: var(--bg-secondary);
            color: var(--text-primary);
        }

        /* Device Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
        }

        .modal-overlay.active {
            opacity: 1;
            pointer-events: all;
        }

        .modal {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }

        .modal-header {
            padding: 1.25rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-title {
            font-size: 1.125rem;
            font-weight: 600;
        }

        .modal-close {
            width: 32px;
            height: 32px;
            border-radius: 6px;
            border: none;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1.25rem;
        }

        .modal-close:hover {
            background: var(--bg-hover);
        }

        .modal-body {
            padding: 1.25rem;
        }

        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--border-color);
        }

        .detail-row:last-child {
            border-bottom: none;
        }

        .detail-label {
            color: var(--text-muted);
            font-size: 0.875rem;
        }

        .detail-value {
            font-weight: 500;
            font-family: var(--font-mono);
        }

        /* Heatmap */
        .heatmap-section {
            margin-top: 1.5rem;
        }

        .heatmap-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
        }

        .heatmap {
            font-family: var(--font-mono);
            font-size: 0.875rem;
            padding: 1rem;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }

        .heatmap-labels {
            color: var(--text-muted);
            font-size: 0.7rem;
        }

        /* Timeline chart */
        .timeline-chart {
            display: flex;
            align-items: flex-end;
            gap: 2px;
            height: 60px;
            padding: 0.5rem 0;
        }

        .timeline-bar {
            flex: 1;
            min-width: 4px;
            background: var(--accent-cyan);
            border-radius: 2px 2px 0 0;
            transition: background 0.15s;
            cursor: pointer;
        }

        .timeline-bar:hover {
            background: var(--accent-blue);
        }

        .timeline-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.65rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        /* RSSI Chart */
        .rssi-chart {
            position: relative;
            height: 80px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            padding: 0.5rem;
            overflow: hidden;
        }

        .rssi-chart svg {
            width: 100%;
            height: 100%;
        }

        .rssi-line {
            fill: none;
            stroke: var(--accent-cyan);
            stroke-width: 2;
        }

        .rssi-area {
            fill: url(#rssiGradient);
        }

        .rssi-label {
            font-size: 0.65rem;
            fill: var(--text-muted);
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.75rem;
        }

        .footer a {
            color: var(--accent-cyan);
            text-decoration: none;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }

            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .device-table {
                font-size: 0.8rem;
            }

            .device-table th,
            .device-table td {
                padding: 0.5rem;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <div class="logo-icon">B</div>
            <div>
                <div class="logo-text">Blue<span>hood</span></div>
                <div class="header-subtitle">Bluetooth Intelligence Dashboard</div>
            </div>
        </div>
        <div class="header-status">
            <div class="status-item">
                <div class="status-dot"></div>
                <span>Scanning</span>
            </div>
            <div class="status-item" id="last-update">
                Last update: --
            </div>
            <a href="/settings" class="header-link">Settings</a>
            <a href="/about" class="header-link">About</a>
        </div>
    </header>

    <main class="main">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Identified Devices</div>
                <div class="stat-value blue" id="stat-total">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Active Today</div>
                <div class="stat-value green" id="stat-today">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">New (Past Hour)</div>
                <div class="stat-value purple" id="stat-new-hour">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Randomized (Hidden)</div>
                <div class="stat-value" style="color: var(--text-muted);" id="stat-randomized">--</div>
            </div>
        </div>

        <div class="search-box">
            <input type="text" class="search-input" id="search" placeholder="Search by MAC, vendor, or name..." style="flex: 2;">
            <input type="datetime-local" class="search-input" id="search-start" title="Start datetime">
            <input type="datetime-local" class="search-input" id="search-end" title="End datetime">
            <button class="btn" onclick="clearDateFilters()">Clear Dates</button>
            <button class="btn btn-primary" onclick="searchByDateRange()">Search</button>
        </div>

        <div class="filter-tabs">
            <button class="filter-tab active" data-filter="all">All Devices</button>
            <button class="filter-tab" data-filter="watched" style="color: var(--accent-yellow);">★ Watching</button>
            <button class="filter-tab" data-filter="phone">Phones</button>
            <button class="filter-tab" data-filter="laptop">Laptops</button>
            <button class="filter-tab" data-filter="smart">IoT</button>
            <button class="filter-tab" data-filter="audio">Audio</button>
            <button class="filter-tab" data-filter="unknown">Unknown</button>
        </div>

        <div class="section">
            <div class="section-header">
                <div class="section-title">Detected Devices</div>
                <div class="section-actions">
                    <button class="btn" onclick="exportData()">Export CSV</button>
                </div>
            </div>
            <table class="device-table">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>MAC Address</th>
                        <th>Vendor</th>
                        <th>Name</th>
                        <th>Sightings</th>
                        <th>Last Seen</th>
                    </tr>
                </thead>
                <tbody id="device-list">
                    <tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">Loading devices...</td></tr>
                </tbody>
            </table>
        </div>
    </main>

    <footer class="footer">
        <p>Bluehood v0.3.0 - Bluetooth Neighborhood | <a href="https://github.com/dannymcc/bluehood">GitHub</a></p>
    </footer>

    <!-- Device Detail Modal -->
    <div class="modal-overlay" id="device-modal">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-title">Device Details</div>
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
        let dateFilteredDevices = null;  // null means no date filter active

        // Fetch and display devices
        async function refreshDevices() {
            try {
                const response = await fetch('/api/devices');
                const data = await response.json();
                allDevices = data.devices || [];
                updateStats(data);
                if (!dateFilteredDevices) {
                    renderDevices();
                }
                document.getElementById('last-update').textContent = 'Last update: ' + new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error fetching devices:', error);
            }
        }

        function updateStats(data) {
            document.getElementById('stat-total').textContent = data.total || 0;
            document.getElementById('stat-today').textContent = data.active_today || 0;
            document.getElementById('stat-new-hour').textContent = data.new_past_hour || 0;
            document.getElementById('stat-randomized').textContent = data.randomized_count || 0;
        }

        async function searchByDateRange() {
            const startInput = document.getElementById('search-start').value;
            const endInput = document.getElementById('search-end').value;

            if (!startInput && !endInput) {
                clearDateFilters();
                return;
            }

            try {
                let url = '/api/search?';
                if (startInput) url += 'start=' + encodeURIComponent(startInput) + '&';
                if (endInput) url += 'end=' + encodeURIComponent(endInput);

                const response = await fetch(url);
                const data = await response.json();
                dateFilteredDevices = data.devices || [];
                renderDevices();
            } catch (error) {
                console.error('Error searching:', error);
            }
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

            // Use date-filtered devices if active, otherwise use all devices
            const sourceDevices = dateFilteredDevices !== null ? dateFilteredDevices : allDevices;

            let filtered = sourceDevices.filter(d => {
                // Apply type filter
                if (currentFilter === 'watched') {
                    if (!d.watched) return false;
                } else if (currentFilter !== 'all' && d.device_type !== currentFilter) {
                    return false;
                }

                // Apply search
                if (searchTerm) {
                    const searchable = [d.mac, d.vendor, d.friendly_name].join(' ').toLowerCase();
                    if (!searchable.includes(searchTerm)) return false;
                }
                return true;
            });

            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">No devices found</td></tr>';
                return;
            }

            tbody.innerHTML = filtered.map(d => {
                const typeClass = getTypeClass(d.device_type);
                const lastSeen = formatLastSeen(d.last_seen);
                const isRecent = isRecentlySeen(d.last_seen);
                const watchedStar = d.watched ? '<span style="color: var(--accent-yellow); margin-right: 0.25rem;">★</span>' : '';

                return `
                    <tr onclick="showDevice('${d.mac}')" style="cursor: pointer;">
                        <td><span class="device-type ${typeClass}">${watchedStar}${d.type_icon} ${d.type_label}</span></td>
                        <td class="mac-address">${d.mac}</td>
                        <td class="device-vendor">${d.vendor || 'Unknown'}</td>
                        <td class="device-name">${d.friendly_name || '-'}</td>
                        <td><span class="sightings-badge">${d.total_sightings}</span></td>
                        <td class="last-seen ${isRecent ? 'recent' : ''}">${lastSeen}</td>
                    </tr>
                `;
            }).join('');
        }

        function getTypeClass(type) {
            const classes = {
                'phone': 'type-phone',
                'laptop': 'type-laptop',
                'computer': 'type-laptop',
                'tablet': 'type-phone',
                'smart': 'type-smart',
                'audio': 'type-audio',
                'speaker': 'type-audio',
                'watch': 'type-watch',
                'wearable': 'type-watch',
                'tv': 'type-tv',
                'vehicle': 'type-vehicle',
            };
            return classes[type] || 'type-unknown';
        }

        function formatLastSeen(isoString) {
            if (!isoString) return 'Never';
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return diffMins + 'm ago';
            if (diffMins < 1440) return Math.floor(diffMins / 60) + 'h ago';
            return date.toLocaleDateString();
        }

        function isRecentlySeen(isoString) {
            if (!isoString) return false;
            const date = new Date(isoString);
            const now = new Date();
            return (now - date) < 600000; // 10 minutes
        }

        async function showDevice(mac) {
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac));
                const data = await response.json();
                renderModal(data);
                document.getElementById('device-modal').classList.add('active');
            } catch (error) {
                console.error('Error fetching device:', error);
            }
        }

        function renderModal(data) {
            const d = data.device;
            const content = document.getElementById('modal-content');

            // Format RSSI with signal indicator
            let rssiDisplay = 'No data';
            if (data.avg_rssi !== null && data.avg_rssi !== undefined) {
                const rssi = data.avg_rssi;
                let strength = 'Weak';
                let color = 'var(--accent-red)';
                if (rssi > -50) { strength = 'Excellent'; color = 'var(--accent-green)'; }
                else if (rssi > -60) { strength = 'Good'; color = 'var(--accent-cyan)'; }
                else if (rssi > -70) { strength = 'Fair'; color = 'var(--accent-yellow)'; }
                rssiDisplay = `<span style="color: ${color}">${rssi} dBm (${strength})</span>`;
            }

            // Watch button
            const watchBtnText = d.watched ? '★ Watching' : '☆ Watch';
            const watchBtnStyle = d.watched
                ? 'background: var(--accent-yellow); color: #000; border-color: var(--accent-yellow);'
                : '';

            content.innerHTML = `
                <div class="detail-row" style="justify-content: flex-start; gap: 1rem;">
                    <button class="btn" id="watch-btn" style="${watchBtnStyle}" onclick="toggleWatch('${d.mac}')">${watchBtnText}</button>
                    <span style="color: var(--text-muted); font-size: 0.8rem;">Mark as Device of Interest</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">MAC Address</span>
                    <span class="detail-value">${d.mac}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Device Type</span>
                    <span class="detail-value">${data.type_label}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Vendor</span>
                    <span class="detail-value">${d.vendor || 'Unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Name</span>
                    <span class="detail-value">${d.friendly_name || 'Not set'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">First Seen</span>
                    <span class="detail-value">${d.first_seen ? new Date(d.first_seen).toLocaleString() : 'Unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Last Seen</span>
                    <span class="detail-value">${d.last_seen ? new Date(d.last_seen).toLocaleString() : 'Unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Total Sightings</span>
                    <span class="detail-value">${d.total_sightings}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Avg Signal Strength</span>
                    <span class="detail-value">${rssiDisplay}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Pattern</span>
                    <span class="detail-value">${data.pattern || 'Insufficient data'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">BLE Services</span>
                    <span class="detail-value">${data.uuid_names && data.uuid_names.length > 0 ? data.uuid_names.join(', ') : 'None detected'}</span>
                </div>

                <div class="heatmap-section">
                    <div class="heatmap-title">Hourly Activity (30 days)</div>
                    <div class="heatmap">
                        <div class="heatmap-labels">0  3  6  9 12 15 18 21 24</div>
                        <div>${data.hourly_heatmap || '------------------------'}</div>
                    </div>
                </div>

                <div class="heatmap-section">
                    <div class="heatmap-title">Daily Activity</div>
                    <div class="heatmap">
                        <div class="heatmap-labels">M  T  W  T  F  S  S</div>
                        <div>${data.daily_heatmap || '-------'}</div>
                    </div>
                </div>

                <div class="heatmap-section">
                    <div class="heatmap-title">Presence Timeline (30 days)</div>
                    ${renderTimeline(data.timeline)}
                </div>

                <div class="heatmap-section" id="rssi-section">
                    <div class="heatmap-title">Signal Strength History (7 days)</div>
                    <div class="rssi-chart" id="rssi-chart">
                        <div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding-top: 1.5rem;">Loading...</div>
                    </div>
                </div>
            `;

            // Load RSSI history after rendering
            loadRssiChart(d.mac);
        }

        function renderTimeline(timeline) {
            if (!timeline || timeline.length === 0) {
                return '<div style="color: var(--text-muted); font-size: 0.8rem;">No data available</div>';
            }

            const maxCount = Math.max(...timeline.map(d => d.count));
            const bars = timeline.map(d => {
                const height = maxCount > 0 ? (d.count / maxCount * 100) : 0;
                const date = new Date(d.date);
                const tooltip = date.toLocaleDateString() + ': ' + d.count + ' sightings';
                return '<div class="timeline-bar" style="height: ' + height + '%" title="' + tooltip + '"></div>';
            }).join('');

            // Get first and last dates for labels
            const firstDate = new Date(timeline[0].date);
            const lastDate = new Date(timeline[timeline.length - 1].date);
            const formatDate = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

            return '<div class="timeline-chart">' + bars + '</div>' +
                   '<div class="timeline-labels">' +
                   '<span>' + formatDate(firstDate) + '</span>' +
                   '<span>' + formatDate(lastDate) + '</span>' +
                   '</div>';
        }

        async function loadRssiChart(mac) {
            const container = document.getElementById('rssi-chart');
            if (!container) return;

            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac) + '/rssi?days=7');
                const data = await response.json();

                if (!data.rssi_history || data.rssi_history.length < 2) {
                    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding-top: 1.5rem;">Insufficient data</div>';
                    return;
                }

                renderRssiChart(container, data.rssi_history);
            } catch (error) {
                console.error('Error loading RSSI history:', error);
                container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding-top: 1.5rem;">Error loading data</div>';
            }
        }

        function renderRssiChart(container, rssiData) {
            const width = container.clientWidth - 20;
            const height = 60;
            const padding = { left: 30, right: 10, top: 5, bottom: 15 };

            // Get min/max RSSI values
            const rssiValues = rssiData.map(d => d.rssi);
            const minRssi = Math.min(...rssiValues);
            const maxRssi = Math.max(...rssiValues);

            // Scale functions
            const xScale = (i) => padding.left + (i / (rssiData.length - 1)) * (width - padding.left - padding.right);
            const yScale = (rssi) => {
                const range = maxRssi - minRssi || 1;
                return padding.top + (1 - (rssi - minRssi) / range) * (height - padding.top - padding.bottom);
            };

            // Build SVG path
            const linePath = rssiData.map((d, i) => {
                const x = xScale(i);
                const y = yScale(d.rssi);
                return (i === 0 ? 'M' : 'L') + x + ',' + y;
            }).join(' ');

            // Area path (for gradient fill)
            const areaPath = linePath +
                ' L' + xScale(rssiData.length - 1) + ',' + (height - padding.bottom) +
                ' L' + padding.left + ',' + (height - padding.bottom) + ' Z';

            // Time labels
            const firstTime = new Date(rssiData[0].timestamp);
            const lastTime = new Date(rssiData[rssiData.length - 1].timestamp);
            const formatTime = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

            container.innerHTML = '<svg viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none">' +
                '<defs>' +
                '<linearGradient id="rssiGradient" x1="0%" y1="0%" x2="0%" y2="100%">' +
                '<stop offset="0%" style="stop-color: var(--accent-cyan); stop-opacity: 0.3"/>' +
                '<stop offset="100%" style="stop-color: var(--accent-cyan); stop-opacity: 0.05"/>' +
                '</linearGradient>' +
                '</defs>' +
                '<path class="rssi-area" d="' + areaPath + '"/>' +
                '<path class="rssi-line" d="' + linePath + '"/>' +
                '<text class="rssi-label" x="' + padding.left + '" y="' + (height - 2) + '">' + formatTime(firstTime) + '</text>' +
                '<text class="rssi-label" x="' + (width - padding.right) + '" y="' + (height - 2) + '" text-anchor="end">' + formatTime(lastTime) + '</text>' +
                '<text class="rssi-label" x="2" y="' + (padding.top + 8) + '">' + maxRssi + 'dBm</text>' +
                '<text class="rssi-label" x="2" y="' + (height - padding.bottom - 2) + '">' + minRssi + 'dBm</text>' +
                '</svg>';
        }

        async function toggleWatch(mac) {
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac) + '/watch', {
                    method: 'POST'
                });
                const data = await response.json();

                // Update button appearance
                const btn = document.getElementById('watch-btn');
                if (data.watched) {
                    btn.textContent = '★ Watching';
                    btn.style.background = 'var(--accent-yellow)';
                    btn.style.color = '#000';
                    btn.style.borderColor = 'var(--accent-yellow)';
                } else {
                    btn.textContent = '☆ Watch';
                    btn.style.background = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }

                // Refresh the device list to update watched status
                refreshDevices();
            } catch (error) {
                console.error('Error toggling watch:', error);
            }
        }

        function closeModal() {
            document.getElementById('device-modal').classList.remove('active');
        }

        function exportData() {
            const csv = ['MAC,Vendor,Name,Type,Sightings,Last Seen'];
            allDevices.forEach(d => {
                csv.push([d.mac, d.vendor || '', d.friendly_name || '', d.device_type || '', d.total_sightings, d.last_seen || ''].join(','));
            });

            const blob = new Blob([csv.join('\\n')], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'bluehood-devices-' + new Date().toISOString().split('T')[0] + '.csv';
            a.click();
        }

        // Filter tabs
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentFilter = tab.dataset.filter;
                renderDevices();
            });
        });

        // Search
        document.getElementById('search').addEventListener('input', renderDevices);

        // Close modal on overlay click
        document.getElementById('device-modal').addEventListener('click', (e) => {
            if (e.target.id === 'device-modal') closeModal();
        });

        // Initial load and auto-refresh
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
    <title>Settings - Bluehood</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a25;
            --bg-hover: #22222f;
            --text-primary: #e4e4e7;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-green: #22c55e;
            --accent-yellow: #eab308;
            --accent-red: #ef4444;
            --border-color: #27272a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: var(--font-sans);
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            text-decoration: none;
            color: inherit;
        }

        .logo-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .logo-text span { color: var(--accent-cyan); }

        .header-nav {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .header-link {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.875rem;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            transition: all 0.15s ease;
        }

        .header-link:hover, .header-link.active {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .main {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }

        .page-title {
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .page-desc {
            color: var(--text-muted);
            margin-bottom: 2rem;
        }

        .section {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .section-title {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-primary);
        }

        .form-group {
            margin-bottom: 1.25rem;
        }

        .form-label {
            display: block;
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }

        .form-input {
            width: 100%;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-tertiary);
            color: var(--text-primary);
            font-size: 0.875rem;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--accent-blue);
        }

        .form-checkbox {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem;
            background: var(--bg-tertiary);
            border-radius: 8px;
            cursor: pointer;
            margin-bottom: 0.5rem;
        }

        .form-checkbox input {
            width: 18px;
            height: 18px;
            accent-color: var(--accent-blue);
        }

        .form-checkbox-label {
            font-size: 0.875rem;
        }

        .form-checkbox-desc {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        .btn {
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            border: 1px solid var(--border-color);
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            transition: all 0.15s ease;
        }

        .btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .btn-primary {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: white;
        }

        .btn-primary:hover {
            background: #2563eb;
        }

        .btn-row {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
        }

        .status-msg {
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-size: 0.875rem;
            margin-bottom: 1rem;
            display: none;
        }

        .status-msg.success {
            background: rgba(34, 197, 94, 0.1);
            color: var(--accent-green);
            display: block;
        }

        .status-msg.error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--accent-red);
            display: block;
        }

        .footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.75rem;
        }

        .footer a {
            color: var(--accent-cyan);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <header class="header">
        <a href="/" class="logo">
            <div class="logo-icon">B</div>
            <div class="logo-text">Blue<span>hood</span></div>
        </a>
        <nav class="header-nav">
            <a href="/" class="header-link">Dashboard</a>
            <a href="/settings" class="header-link active">Settings</a>
            <a href="/about" class="header-link">About</a>
        </nav>
    </header>

    <main class="main">
        <h1 class="page-title">Settings</h1>
        <p class="page-desc">Configure notifications and preferences.</p>

        <div id="status-msg" class="status-msg"></div>

        <form id="settings-form">
            <div class="section">
                <h2 class="section-title">Push Notifications (ntfy.sh)</h2>

                <div class="form-group">
                    <label class="form-label">ntfy Topic Name</label>
                    <input type="text" class="form-input" id="ntfy_topic" placeholder="e.g., bluehood-myname-alerts">
                </div>

                <label class="form-checkbox">
                    <input type="checkbox" id="ntfy_enabled">
                    <div>
                        <div class="form-checkbox-label">Enable Notifications</div>
                        <div class="form-checkbox-desc">Send push notifications via ntfy.sh</div>
                    </div>
                </label>
            </div>

            <div class="section">
                <h2 class="section-title">Notification Triggers</h2>

                <label class="form-checkbox">
                    <input type="checkbox" id="notify_new_device">
                    <div>
                        <div class="form-checkbox-label">New Device Detected</div>
                        <div class="form-checkbox-desc">Notify when a new device is first seen</div>
                    </div>
                </label>

                <label class="form-checkbox">
                    <input type="checkbox" id="notify_watched_return">
                    <div>
                        <div class="form-checkbox-label">Watched Device Returns</div>
                        <div class="form-checkbox-desc">Notify when a watched device comes back</div>
                    </div>
                </label>

                <label class="form-checkbox">
                    <input type="checkbox" id="notify_watched_leave">
                    <div>
                        <div class="form-checkbox-label">Watched Device Leaves</div>
                        <div class="form-checkbox-desc">Notify when a watched device is no longer detected</div>
                    </div>
                </label>
            </div>

            <div class="section">
                <h2 class="section-title">Timing Thresholds</h2>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Absence Threshold (minutes)</label>
                        <input type="number" class="form-input" id="watched_absence_minutes" value="30" min="1" max="1440">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Return Threshold (minutes)</label>
                        <input type="number" class="form-input" id="watched_return_minutes" value="5" min="1" max="60">
                    </div>
                </div>
            </div>

            <div class="btn-row">
                <button type="submit" class="btn btn-primary">Save Settings</button>
                <a href="/" class="btn">Cancel</a>
            </div>
        </form>
    </main>

    <footer class="footer">
        <p>Bluehood v0.3.0 | <a href="https://github.com/dannymcc/bluehood">GitHub</a></p>
    </footer>

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
            } catch (error) {
                console.error('Error loading settings:', error);
                showStatus('Error loading settings', 'error');
            }
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
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });

                if (response.ok) {
                    showStatus('Settings saved successfully!', 'success');
                } else {
                    showStatus('Error saving settings', 'error');
                }
            } catch (error) {
                console.error('Error saving settings:', error);
                showStatus('Error saving settings', 'error');
            }
        }

        function showStatus(message, type) {
            const el = document.getElementById('status-msg');
            el.textContent = message;
            el.className = 'status-msg ' + type;

            if (type === 'success') {
                setTimeout(() => { el.className = 'status-msg'; }, 3000);
            }
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
    <title>About - Bluehood</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a25;
            --text-primary: #e4e4e7;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --border-color: #27272a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: var(--font-sans);
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            text-decoration: none;
            color: inherit;
        }

        .logo-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .logo-text span { color: var(--accent-cyan); }

        .header-nav {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .header-link {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.875rem;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            transition: all 0.15s ease;
        }

        .header-link:hover, .header-link.active {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .main {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }

        .hero {
            text-align: center;
            margin-bottom: 3rem;
        }

        .hero-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
            margin-bottom: 1.5rem;
        }

        .hero-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .hero-title span { color: var(--accent-cyan); }

        .hero-tagline {
            font-size: 1.25rem;
            color: var(--text-secondary);
        }

        .section {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .section-title {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--accent-cyan);
        }

        .section p {
            color: var(--text-secondary);
            line-height: 1.7;
            margin-bottom: 1rem;
        }

        .section p:last-child { margin-bottom: 0; }

        .section a {
            color: var(--accent-cyan);
            text-decoration: none;
        }

        .section a:hover { text-decoration: underline; }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .feature {
            background: var(--bg-tertiary);
            border-radius: 8px;
            padding: 1rem;
        }

        .feature-icon {
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
        }

        .feature-name {
            font-weight: 600;
            font-size: 0.875rem;
            margin-bottom: 0.25rem;
        }

        .feature-desc {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .version {
            text-align: center;
            padding: 1.5rem;
            color: var(--text-muted);
            font-family: var(--font-mono);
            font-size: 0.875rem;
        }

        .footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.75rem;
        }

        .footer a {
            color: var(--accent-cyan);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <header class="header">
        <a href="/" class="logo">
            <div class="logo-icon">B</div>
            <div class="logo-text">Blue<span>hood</span></div>
        </a>
        <nav class="header-nav">
            <a href="/" class="header-link">Dashboard</a>
            <a href="/settings" class="header-link">Settings</a>
            <a href="/about" class="header-link active">About</a>
        </nav>
    </header>

    <main class="main">
        <div class="hero">
            <div class="hero-icon">B</div>
            <h1 class="hero-title">Blue<span>hood</span></h1>
            <p class="hero-tagline">Bluetooth Neighborhood Monitor</p>
        </div>

        <div class="section">
            <h2 class="section-title">What is Bluehood?</h2>
            <p>Bluehood is an educational tool that passively scans for Bluetooth devices in your area. It demonstrates how easily Bluetooth metadata can be collected and analyzed to reveal patterns in device presence.</p>
            <p>Inspired by the <a href="https://whisperpair.eu/">WhisperPair vulnerability</a> (CVE-2025-36911), Bluehood aims to raise awareness about Bluetooth privacy.</p>
        </div>

        <div class="section">
            <h2 class="section-title">Features</h2>
            <div class="feature-grid">
                <div class="feature">
                    <div class="feature-icon">📡</div>
                    <div class="feature-name">Dual-Mode Scanning</div>
                    <div class="feature-desc">Scans both BLE and Classic Bluetooth</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">🏭</div>
                    <div class="feature-name">Vendor Detection</div>
                    <div class="feature-desc">Identifies device manufacturers</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">📊</div>
                    <div class="feature-name">Pattern Analysis</div>
                    <div class="feature-desc">Hourly and daily activity heatmaps</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">🔔</div>
                    <div class="feature-name">Push Notifications</div>
                    <div class="feature-desc">Alerts via ntfy.sh</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">⭐</div>
                    <div class="feature-name">Watch List</div>
                    <div class="feature-desc">Track specific devices</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">🔒</div>
                    <div class="feature-name">Privacy Filter</div>
                    <div class="feature-desc">Hides randomized MACs</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Disclaimer</h2>
            <p>This tool is for educational purposes only. Be mindful of privacy laws in your jurisdiction when monitoring Bluetooth devices. The author is not responsible for any misuse of this software.</p>
        </div>

        <div class="version">v0.3.0</div>
    </main>

    <footer class="footer">
        <p>Created by <a href="https://github.com/dannymcc">Danny McClelland</a> | <a href="https://github.com/dannymcc/bluehood">GitHub</a></p>
    </footer>
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
