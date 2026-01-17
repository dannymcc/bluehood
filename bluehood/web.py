"""Bluehood Web GUI - Modern dashboard interface."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from aiohttp import web

from . import db
from .classifier import classify_device, get_type_icon, get_type_label, get_all_types, is_randomized_mac
from .patterns import generate_hourly_heatmap, generate_daily_heatmap

logger = logging.getLogger(__name__)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bluehood - Bluetooth Intelligence</title>
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
        </div>
    </header>

    <main class="main">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Devices</div>
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
                <div class="stat-label">Total Sightings</div>
                <div class="stat-value yellow" id="stat-sightings">--</div>
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
        <p>Bluehood v0.1.0 - Bluetooth Neighborhood Monitor</p>
        <p>Open source on <a href="https://github.com/dannymcc/bluehood">GitHub</a></p>
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
            document.getElementById('stat-sightings').textContent = data.total_sightings || 0;
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
                if (currentFilter !== 'all' && d.device_type !== currentFilter) return false;

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

                return `
                    <tr onclick="showDevice('${d.mac}')" style="cursor: pointer;">
                        <td><span class="device-type ${typeClass}">${d.type_icon} ${d.type_label}</span></td>
                        <td class="mac-address">${d.mac}</td>
                        <td class="device-vendor">${d.vendor || (d.randomized_mac ? '<span style="color: var(--text-muted); font-style: italic;">Randomized</span>' : 'Unknown')}</td>
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

            content.innerHTML = `
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
            `;
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


class WebServer:
    """Web server for Bluehood dashboard."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/api/devices", self.api_devices)
        self.app.router.add_get("/api/device/{mac}", self.api_device)
        self.app.router.add_get("/api/search", self.api_search)
        self.app.router.add_get("/api/stats", self.api_stats)

    async def index(self, request: web.Request) -> web.Response:
        """Serve the main dashboard."""
        return web.Response(text=HTML_TEMPLATE, content_type="text/html")

    async def api_devices(self, request: web.Request) -> web.Response:
        """Get all devices with stats."""
        devices = await db.get_all_devices(include_ignored=True)

        now = datetime.now()
        today = now.date()
        one_hour_ago = now - timedelta(hours=1)

        active_today = 0
        new_past_hour = 0
        total_sightings = 0
        type_set = set()

        device_list = []
        for d in devices:
            device_type = d.device_type or classify_device(d.vendor, d.friendly_name)
            type_set.add(device_type)
            total_sightings += d.total_sightings

            if d.last_seen and d.last_seen.date() == today:
                active_today += 1

            # Count devices first seen in the past hour
            if d.first_seen and d.first_seen >= one_hour_ago:
                new_past_hour += 1

            # Check if MAC is randomized (privacy feature)
            randomized = is_randomized_mac(d.mac)
            vendor_display = d.vendor if d.vendor else ("Randomized MAC" if randomized else None)

            device_list.append({
                "mac": d.mac,
                "vendor": vendor_display,
                "friendly_name": d.friendly_name,
                "device_type": device_type,
                "type_icon": get_type_icon(device_type),
                "type_label": get_type_label(device_type),
                "ignored": d.ignored,
                "randomized_mac": randomized,
                "first_seen": d.first_seen.isoformat() if d.first_seen else None,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "total_sightings": d.total_sightings,
            })

        return web.json_response({
            "devices": device_list,
            "total": len(devices),
            "active_today": active_today,
            "new_past_hour": new_past_hour,
            "total_sightings": total_sightings,
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
        device_type = device.device_type or classify_device(device.vendor, device.friendly_name)

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
                "first_seen": device.first_seen.isoformat() if device.first_seen else None,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "total_sightings": device.total_sightings,
            },
            "type_label": get_type_label(device_type),
            "pattern": pattern,
            "avg_rssi": avg_rssi,
            "hourly_heatmap": generate_hourly_heatmap(hourly),
            "daily_heatmap": generate_daily_heatmap(daily),
        })

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
