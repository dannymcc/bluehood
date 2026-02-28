"""HTML templates for the Bluehood web dashboard."""

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

        [data-theme="light"] {
            --bg-primary: #f5f5f5;
            --bg-secondary: #e8e8e8;
            --bg-tertiary: #ffffff;
            --bg-hover: #d8d8d8;
            --bg-panel: #efefef;
            --text-primary: #1a1a1a;
            --text-secondary: #555555;
            --text-muted: #888888;
            --border-color: #cccccc;
            --border-active: #999999;
        }

        [data-theme="light"] .type-phone { background: #dbeafe; color: #1d4ed8; }
        [data-theme="light"] .type-laptop { background: #ccfbf1; color: #0f766e; }
        [data-theme="light"] .type-audio { background: #f3e8ff; color: #7c3aed; }
        [data-theme="light"] .type-watch { background: #dcfce7; color: #15803d; }
        [data-theme="light"] .type-smart { background: #fef3c7; color: #b45309; }
        [data-theme="light"] .type-tv { background: #fce7f3; color: #be185d; }
        [data-theme="light"] .type-vehicle { background: #fef9c3; color: #a16207; }
        [data-theme="light"] .type-unknown { background: #e5e5e5; color: #555; }
        [data-theme="light"] .modal-overlay.active { background: rgba(0, 0, 0, 0.5); }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        /* Thin, subtle scrollbars */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--border-active); }
        * { scrollbar-width: thin; scrollbar-color: var(--border-color) transparent; }

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

        .form-input {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 3px;
            padding: 0.6rem 0.75rem;
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 0.8rem;
            width: 100%;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--accent-red);
        }

        .kbd {
            display: inline-block;
            padding: 0.15rem 0.4rem;
            font-size: 0.65rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 2px;
            color: var(--text-muted);
        }

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
            flex-wrap: wrap;
            align-items: center;
        }

        .selected-summary {
            color: var(--accent-amber);
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

        .device-table th.select-col,
        .device-table td.select-col {
            width: 34px;
            padding: 0.4rem 0.5rem;
            text-align: center;
        }

        .row-select-checkbox {
            accent-color: var(--accent-red);
            cursor: pointer;
        }

        .device-table th.sortable {
            cursor: pointer;
            user-select: none;
            transition: color 0.1s ease, background 0.1s ease;
        }

        .device-table th.sortable:hover {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .device-table th.sortable.active {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .sort-indicator {
            margin-left: 0.35rem;
            font-size: 0.6rem;
            opacity: 0.7;
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

        .device-table tr.selected {
            background: rgba(220, 38, 38, 0.15);
        }

        .device-table tr.selected:hover {
            background: rgba(220, 38, 38, 0.22);
        }

        .device-table tr:last-child td { border-bottom: none; }

        .device-table tr { cursor: pointer; user-select: none; }

        .bulk-select {
            min-width: 140px;
            font-size: 0.7rem;
            padding: 0.4rem 0.5rem;
        }

        .pagination-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            padding: 0.65rem 0.9rem;
            border-top: 1px solid var(--border-color);
            background: var(--bg-tertiary);
            flex-wrap: wrap;
        }

        .pagination-left,
        .pagination-right {
            display: flex;
            align-items: center;
            gap: 0.45rem;
        }

        .pagination-center {
            display: flex;
            align-items: center;
            gap: 0.35rem;
            flex-wrap: wrap;
            justify-content: center;
        }

        .page-numbers {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            flex-wrap: wrap;
        }

        .page-number-btn {
            min-width: 2rem;
            padding: 0.35rem 0.45rem;
            font-size: 0.7rem;
            line-height: 1;
        }

        .page-number-btn.active {
            background: var(--accent-red);
            border-color: var(--accent-red);
            color: #fff;
        }

        .page-ellipsis {
            color: var(--text-muted);
            font-size: 0.75rem;
            padding: 0 0.1rem;
        }

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

        .activity-grid {
            display: grid;
            gap: 3px;
        }

        .activity-grid.hourly {
            grid-template-columns: repeat(24, 1fr);
        }

        .activity-grid.daily {
            grid-template-columns: repeat(7, 1fr);
        }

        .activity-cell {
            aspect-ratio: 1;
            border-radius: 2px;
            background: var(--bg-hover);
            cursor: pointer;
            transition: opacity 0.1s;
        }

        .activity-cell:hover { opacity: 0.8; }
        .activity-cell.l1 { background: rgba(220, 38, 38, 0.25); }
        .activity-cell.l2 { background: rgba(220, 38, 38, 0.5); }
        .activity-cell.l3 { background: rgba(220, 38, 38, 0.75); }
        .activity-cell.l4 { background: var(--accent-red); }

        .activity-labels {
            display: grid;
            gap: 3px;
            margin-top: 2px;
            font-size: 0.55rem;
            color: var(--text-muted);
            text-align: center;
        }

        .activity-labels.hourly { grid-template-columns: repeat(24, 1fr); }
        .activity-labels.daily { grid-template-columns: repeat(7, 1fr); }

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

        .theme-toggle {
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 0.75rem;
            padding: 0.3rem 0.5rem;
            cursor: pointer;
            border-radius: 3px;
            transition: all 0.1s;
        }

        .theme-toggle:hover {
            color: var(--text-primary);
            border-color: var(--border-active);
        }

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
            <button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">☀</button>
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

            <div class="panel">
                <div class="panel-header">Display</div>
                <button class="filter-btn" id="view-toggle" onclick="toggleViewMode()" style="width: 100%; justify-content: center;">
                    ☰ Compact View
                </button>
                <button class="filter-btn" id="screenshot-toggle" onclick="toggleScreenshotMode()" style="width: 100%; justify-content: center; margin-top: 0.5rem;">
                    📷 Screenshot Mode
                </button>
                <button class="filter-btn" id="click-to-open-toggle" onclick="toggleClickToOpen()" style="width: 100%; justify-content: center; margin-top: 0.5rem;">
                    👆 Click to Open
                </button>
            </div>
        </aside>

        <main class="content">
            <div class="search-bar">
                <input type="text" class="search-input" id="search" placeholder="Search MAC, vendor, or identifier...">
                <button class="btn" id="export-btn" onclick="exportData()">Export CSV</button>
            </div>

            <div class="table-container">
                <div class="table-header">
                    <span class="table-title">Identified Targets <span id="selected-count" class="selected-summary" style="display: none;">· 0 selected</span></span>
                    <div class="table-actions">
                        <span style="font-size: 0.7rem; color: var(--text-muted);">
                            <span id="visible-count">--</span> targets
                        </span>
                        <select class="form-input bulk-select" id="bulk-group-select">
                            <option value="">Assign group...</option>
                        </select>
                        <button class="btn" id="bulk-group-apply" onclick="applyBulkGroup()">Assign Group</button>
                        <select class="form-input bulk-select" id="bulk-watch-select">
                            <option value="">Watch...</option>
                            <option value="on">Watch ON</option>
                            <option value="off">Watch OFF</option>
                        </select>
                        <button class="btn" id="bulk-watch-apply" onclick="applyBulkWatch()">Apply Watch</button>
                        <button class="btn" id="clear-selection-btn" onclick="clearSelection()">Clear Selection</button>
                        <button class="btn" onclick="resetSort()">Reset Sort</button>
                    </div>
                </div>
                <table class="device-table">
                    <thead>
                        <tr>
                            <th class="select-col"><input type="checkbox" id="select-all-checkbox" class="row-select-checkbox" aria-label="Select all rows"></th>
                            <th class="sortable" data-sort="class">Class<span class="sort-indicator"></span></th>
                            <th class="sortable" data-sort="mac">Address<span class="sort-indicator"></span></th>
                            <th class="sortable" data-sort="vendor">Vendor<span class="sort-indicator"></span></th>
                            <th class="sortable" data-sort="identifier">Identifier<span class="sort-indicator"></span></th>
                            <th class="sortable" data-sort="sightings">Sightings<span class="sort-indicator"></span></th>
                            <th class="sortable" data-sort="last_seen">Last Contact<span class="sort-indicator"></span></th>
                            <th class="sortable" data-sort="group">Group<span class="sort-indicator"></span></th>
                        </tr>
                    </thead>
                    <tbody id="device-list">
                        <tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-muted);">Initializing scanner...</td></tr>
                    </tbody>
                </table>
                <div class="pagination-bar">
                    <div class="pagination-left">
                        <span id="page-info" style="font-size: 0.7rem; color: var(--text-muted);">Page --/--</span>
                    </div>
                    <div class="pagination-center">
                        <button class="btn" id="prev-page-btn" onclick="changePage(-1)">Prev</button>
                        <div class="page-numbers" id="page-numbers"></div>
                        <button class="btn" id="next-page-btn" onclick="changePage(1)">Next</button>
                    </div>
                    <div class="pagination-right">
                        <span style="font-size: 0.7rem; color: var(--text-muted);">Rows/page</span>
                        <select class="form-input bulk-select" id="page-size-select" onchange="changePageSize(this.value)">
                            <option value="25">25</option>
                            <option value="50" selected>50</option>
                            <option value="100">100</option>
                            <option value="150">150</option>
                            <option value="250">250</option>
                        </select>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <footer class="footer">
        BLUEHOOD v0.5.0 // Bluetooth Reconnaissance Framework // <a href="https://github.com/dannymcc/bluehood">Source</a> // <span class="kbd">?</span> Shortcuts
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

    <!-- Shortcuts Modal -->
    <div class="modal-overlay" id="shortcuts-modal">
        <div class="modal" style="max-width: 400px;">
            <div class="modal-header">
                <span class="modal-title">Keyboard Shortcuts</span>
                <button class="modal-close" onclick="closeShortcutsModal()">&times;</button>
            </div>
            <div class="modal-body" style="padding: 1rem;">
                <div style="display: grid; gap: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">/</span><span style="color: var(--text-secondary);">Focus search</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">r</span><span style="color: var(--text-secondary);">Refresh devices</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">Esc</span><span style="color: var(--text-secondary);">Close modal</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">w</span><span style="color: var(--text-secondary);">Toggle watch (in modal)</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">1</span><span style="color: var(--text-secondary);">Show all devices</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">2</span><span style="color: var(--text-secondary);">Show watched only</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">3</span><span style="color: var(--text-secondary);">Filter phones</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);"><span class="kbd">4</span><span style="color: var(--text-secondary);">Filter laptops</span></div>
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0;"><span class="kbd">5</span><span style="color: var(--text-secondary);">Filter audio</span></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function applyTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            const btn = document.getElementById('theme-toggle');
            if (btn) btn.textContent = theme === 'light' ? '☽' : '☀';
        }

        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem('bluehood_theme', next);
            applyTheme(next);
        }

        applyTheme(localStorage.getItem('bluehood_theme') || 'dark');

        const PAGE_SIZE_OPTIONS = [25, 50, 100, 150, 250];
        const PAGE_SIZE_STORAGE_KEY = 'bluehood_page_size_v2';

        function normalizePageSize(value) {
            const parsed = Number.parseInt(value, 10);
            if (!Number.isFinite(parsed)) return 50;
            if (PAGE_SIZE_OPTIONS.includes(parsed)) return parsed;
            return 50;
        }

        let allDevices = [];
        let currentFilter = 'all';
        let dateFilteredDevices = null;
        let compactView = localStorage.getItem('bluehood_compact_view') === 'true';
        let screenshotMode = localStorage.getItem('bluehood_screenshot_mode') === 'true';
        let clickToOpen = localStorage.getItem('bluehood_click_to_open') === 'true';
        const defaultSortState = { column: 'last_seen', direction: 'asc' };
        let sortState = { ...defaultSortState };
        let selectedMacs = new Set();
        let lastSelectedIndex = null;
        let currentVisibleDevices = [];
        let rowClickTimer = null;
        let searchDebounceTimer = null;
        let pagination = {
            page: 1,
            pageSize: normalizePageSize(localStorage.getItem(PAGE_SIZE_STORAGE_KEY)),
            totalPages: 1,
            totalMatching: 0,
            hasPrev: false,
            hasNext: false,
        };

        function getServerSortDirection() {
            if (sortState.column === 'last_seen') {
                return sortState.direction === 'asc' ? 'desc' : 'asc';
            }
            return sortState.direction;
        }

        function buildDevicesUrl() {
            const params = new URLSearchParams();
            params.set('page', pagination.page);
            params.set('page_size', pagination.pageSize);
            params.set('filter', currentFilter);
            params.set('sort', sortState.column);
            params.set('direction', getServerSortDirection());

            const searchInput = document.getElementById('search');
            const searchTerm = searchInput ? searchInput.value.trim() : '';
            if (searchTerm) params.set('search', searchTerm);

            return '/api/devices?' + params.toString();
        }

        function queueDeviceRefresh(resetPage = false) {
            if (resetPage) pagination.page = 1;
            if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                searchDebounceTimer = null;
                refreshDevices();
            }, 250);
        }

        function toggleViewMode() {
            compactView = !compactView;
            localStorage.setItem('bluehood_compact_view', compactView);
            updateViewToggle();
            renderDevices();
        }

        function updateViewToggle() {
            const btn = document.getElementById('view-toggle');
            if (btn) {
                btn.innerHTML = compactView ? '◫ Detailed View' : '☰ Compact View';
            }
        }

        function toggleScreenshotMode() {
            screenshotMode = !screenshotMode;
            localStorage.setItem('bluehood_screenshot_mode', screenshotMode);
            updateScreenshotToggle();
            renderDevices();
        }

        function updateScreenshotToggle() {
            const btn = document.getElementById('screenshot-toggle');
            if (btn) {
                btn.innerHTML = screenshotMode ? '📷 Screenshot Mode ON' : '📷 Screenshot Mode';
                btn.style.background = screenshotMode ? 'var(--accent-red)' : '';
                btn.style.color = screenshotMode ? 'white' : '';
            }
        }

        function toggleClickToOpen() {
            clickToOpen = !clickToOpen;
            localStorage.setItem('bluehood_click_to_open', clickToOpen);
            updateClickToOpenToggle();
        }

        function updateClickToOpenToggle() {
            const btn = document.getElementById('click-to-open-toggle');
            if (btn) {
                btn.innerHTML = clickToOpen ? '👆 Click to Open ON' : '👆 Click to Open';
                btn.style.background = clickToOpen ? 'var(--accent-blue)' : '';
                btn.style.color = clickToOpen ? 'white' : '';
            }
        }

        function isMacOSUUID(addr) {
            return /^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$/.test(addr);
        }

        function obfuscateMAC(mac) {
            if (!screenshotMode || !mac) return mac;
            // Handle macOS UUID-format addresses
            if (isMacOSUUID(mac)) {
                return mac.substring(0, 8) + '-XXXX-XXXX-XXXX-XXXXXXXXXXXX';
            }
            // Show first 2 octets, hide the rest: AA:BB:XX:XX:XX:XX
            const parts = mac.split(':');
            if (parts.length === 6) {
                return parts[0] + ':' + parts[1] + ':XX:XX:XX:XX';
            }
            return mac.substring(0, 5) + ':XX:XX:XX:XX';
        }

        function obfuscateName(name) {
            if (!screenshotMode || !name) return name;
            // Show first 2 chars, then asterisks
            if (name.length <= 2) return '**';
            return name.substring(0, 2) + '*'.repeat(Math.min(name.length - 2, 8));
        }

        function showShortcutsModal() {
            document.getElementById('shortcuts-modal').classList.add('active');
        }

        function closeShortcutsModal() {
            document.getElementById('shortcuts-modal').classList.remove('active');
        }

        async function refreshDevices() {
            try {
                const response = await fetch(buildDevicesUrl());
                const data = await response.json();
                allDevices = data.devices || [];
                const knownMacs = new Set(allDevices.map(d => d.mac));
                selectedMacs = new Set([...selectedMacs].filter(mac => knownMacs.has(mac)));
                pagination.page = data.page || pagination.page;
                pagination.pageSize = data.page_size || pagination.pageSize;
                pagination.totalPages = data.total_pages || 1;
                pagination.totalMatching = data.total_matching || 0;
                pagination.hasPrev = !!data.has_prev;
                pagination.hasNext = !!data.has_next;
                localStorage.setItem(PAGE_SIZE_STORAGE_KEY, String(pagination.pageSize));
                updateStats(data);
                updateFilterCounts(data.filter_counts);
                updatePaginationUI();
                if (!dateFilteredDevices) renderDevices();
                updateSelectionUI();
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

        function updateFilterCounts(serverCounts = null) {
            const counts = serverCounts || { all: 0, watched: 0, phone: 0, laptop: 0, audio: 0, smart: 0, unknown: 0 };
            if (!serverCounts) {
                allDevices.forEach(d => {
                    counts.all++;
                    if (d.watched) counts.watched++;
                    if (d.device_type === 'phone') counts.phone++;
                    else if (d.device_type === 'laptop' || d.device_type === 'computer') counts.laptop++;
                    else if (d.device_type === 'audio' || d.device_type === 'speaker') counts.audio++;
                    else if (d.device_type === 'smart') counts.smart++;
                    else if (d.device_type === 'unknown') counts.unknown++;
                });
            }
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
                selectedMacs.clear();
                lastSelectedIndex = null;
                updatePaginationUI();
                renderDevices();
            } catch (error) { console.error('Query error:', error); }
        }

        function clearDateFilters() {
            document.getElementById('search-start').value = '';
            document.getElementById('search-end').value = '';
            dateFilteredDevices = null;
            updatePaginationUI();
            refreshDevices();
        }

        function resetSort() {
            sortState = { ...defaultSortState };
            updateSortIndicators();
            if (dateFilteredDevices !== null) {
                renderDevices();
                return;
            }
            pagination.page = 1;
            refreshDevices();
        }

        function setSort(column) {
            if (sortState.column === column) {
                sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
            } else {
                sortState.column = column;
                sortState.direction = 'asc';
            }
            updateSortIndicators();
            if (dateFilteredDevices !== null) {
                renderDevices();
                return;
            }
            pagination.page = 1;
            refreshDevices();
        }

        function updatePaginationUI() {
            const pageInfo = document.getElementById('page-info');
            const prevBtn = document.getElementById('prev-page-btn');
            const nextBtn = document.getElementById('next-page-btn');
            const pageNumbers = document.getElementById('page-numbers');
            const pageSizeSelect = document.getElementById('page-size-select');
            if (!pageInfo || !prevBtn || !nextBtn || !pageNumbers) return;
            if (pageSizeSelect) {
                pageSizeSelect.value = String(pagination.pageSize);
            }

            if (dateFilteredDevices !== null) {
                pageInfo.textContent = 'Date query mode';
                prevBtn.disabled = true;
                nextBtn.disabled = true;
                pageNumbers.innerHTML = '';
                if (pageSizeSelect) pageSizeSelect.disabled = true;
                return;
            }

            pageInfo.textContent = 'Page ' + pagination.page + '/' + Math.max(1, pagination.totalPages);
            prevBtn.disabled = !pagination.hasPrev;
            nextBtn.disabled = !pagination.hasNext;
            if (pageSizeSelect) pageSizeSelect.disabled = false;
            renderPageNumbers(pageNumbers);
        }

        function getPageTokens(totalPages, currentPage) {
            if (totalPages <= 7) {
                return Array.from({ length: totalPages }, (_, i) => i + 1);
            }

            const tokens = [1];
            let start = Math.max(2, currentPage - 1);
            let end = Math.min(totalPages - 1, currentPage + 1);

            if (currentPage <= 3) {
                start = 2;
                end = 4;
            } else if (currentPage >= totalPages - 2) {
                start = totalPages - 3;
                end = totalPages - 1;
            }

            if (start > 2) tokens.push('…');
            for (let page = start; page <= end; page++) tokens.push(page);
            if (end < totalPages - 1) tokens.push('…');
            tokens.push(totalPages);

            return tokens;
        }

        function renderPageNumbers(container) {
            const totalPages = Math.max(1, pagination.totalPages);
            const currentPage = Math.min(Math.max(1, pagination.page), totalPages);
            const tokens = getPageTokens(totalPages, currentPage);

            container.innerHTML = tokens.map(token => {
                if (typeof token !== 'number') {
                    return '<span class="page-ellipsis">' + token + '</span>';
                }

                const activeClass = token === currentPage ? ' active' : '';
                return (
                    '<button class="btn page-number-btn' + activeClass + '"' +
                    ' onclick="goToPage(' + token + ')">' +
                    token +
                    '</button>'
                );
            }).join('');
        }

        function goToPage(page) {
            if (dateFilteredDevices !== null) return;
            const targetPage = Math.max(1, Math.min(page, pagination.totalPages));
            if (targetPage === pagination.page) return;
            pagination.page = targetPage;
            selectedMacs.clear();
            lastSelectedIndex = null;
            refreshDevices();
        }

        function changePage(delta) {
            if (dateFilteredDevices !== null) return;
            const nextPage = pagination.page + delta;
            goToPage(nextPage);
        }

        function changePageSize(value) {
            const nextPageSize = normalizePageSize(value);
            if (nextPageSize === pagination.pageSize) return;
            pagination.pageSize = nextPageSize;
            localStorage.setItem(PAGE_SIZE_STORAGE_KEY, String(nextPageSize));
            pagination.page = 1;
            selectedMacs.clear();
            lastSelectedIndex = null;

            if (dateFilteredDevices !== null) {
                updatePaginationUI();
                return;
            }
            refreshDevices();
        }

        function updateSortIndicators() {
            document.querySelectorAll('.device-table th.sortable').forEach(th => {
                const indicator = th.querySelector('.sort-indicator');
                if (!indicator) return;
                const isActive = th.dataset.sort === sortState.column;
                th.classList.toggle('active', isActive);
                if (!isActive) {
                    indicator.textContent = '';
                } else {
                    indicator.textContent = sortState.direction === 'asc' ? '▲' : '▼';
                }
            });
        }

        function getSortValue(device, column) {
            switch (column) {
                case 'class':
                    return (device.type_label || device.device_type || '').toLowerCase();
                case 'mac':
                    return (device.mac || '').toLowerCase();
                case 'vendor':
                    return (device.vendor || '').toLowerCase();
                case 'identifier':
                    return (device.friendly_name || '').toLowerCase();
                case 'sightings':
                    return Number.isFinite(device.total_sightings) ? device.total_sightings : -1;
                case 'last_seen': {
                    if (!device.last_seen) return Number.POSITIVE_INFINITY;
                    const last = new Date(device.last_seen);
                    const now = new Date();
                    return Math.max(0, now - last);
                }
                case 'group':
                    return (device.group_name || '').toLowerCase();
                default:
                    return '';
            }
        }

        function applySort(devices) {
            const sorted = [...devices];
            const direction = sortState.direction === 'asc' ? 1 : -1;
            sorted.sort((a, b) => {
                const aVal = getSortValue(a, sortState.column);
                const bVal = getSortValue(b, sortState.column);
                if (aVal < bVal) return -1 * direction;
                if (aVal > bVal) return 1 * direction;
                return 0;
            });
            return sorted;
        }

        function updateSelectionUI() {
            const selectedCount = selectedMacs.size;
            const summary = document.getElementById('selected-count');
            if (summary) {
                if (selectedCount > 0) {
                    summary.style.display = 'inline';
                    summary.textContent = '· ' + selectedCount + ' selected';
                } else {
                    summary.style.display = 'none';
                    summary.textContent = '';
                }
            }

            const exportBtn = document.getElementById('export-btn');
            if (exportBtn) {
                exportBtn.textContent = selectedCount > 0 ? 'EXPORT CSV (sel)' : 'Export CSV';
            }

            updateSelectAllCheckbox();
            updateBulkActionState();
        }

        function updateSelectAllCheckbox() {
            const checkbox = document.getElementById('select-all-checkbox');
            if (!checkbox) return;
            if (!currentVisibleDevices || currentVisibleDevices.length === 0) {
                checkbox.checked = false;
                checkbox.indeterminate = false;
                checkbox.disabled = true;
                return;
            }
            checkbox.disabled = false;
            const selectedVisibleCount = currentVisibleDevices.filter(d => selectedMacs.has(d.mac)).length;
            checkbox.checked = selectedVisibleCount > 0 && selectedVisibleCount === currentVisibleDevices.length;
            checkbox.indeterminate = selectedVisibleCount > 0 && selectedVisibleCount < currentVisibleDevices.length;
        }

        function updateBulkActionState() {
            const hasSelection = selectedMacs.size > 0;
            const bulkGroupSelect = document.getElementById('bulk-group-select');
            const bulkGroupApply = document.getElementById('bulk-group-apply');
            const bulkWatchSelect = document.getElementById('bulk-watch-select');
            const bulkWatchApply = document.getElementById('bulk-watch-apply');
            const clearBtn = document.getElementById('clear-selection-btn');

            if (bulkGroupSelect) bulkGroupSelect.disabled = !hasSelection;
            if (bulkGroupApply) bulkGroupApply.disabled = !hasSelection;
            if (bulkWatchSelect) bulkWatchSelect.disabled = !hasSelection;
            if (bulkWatchApply) bulkWatchApply.disabled = !hasSelection;
            if (clearBtn) clearBtn.disabled = !hasSelection;
        }

        function clearSelection() {
            selectedMacs.clear();
            lastSelectedIndex = null;
            renderDevices();
        }

        function toggleSelectAllVisible() {
            if (!currentVisibleDevices || currentVisibleDevices.length === 0) return;
            const allSelected = currentVisibleDevices.every(d => selectedMacs.has(d.mac));
            if (allSelected) {
                currentVisibleDevices.forEach(d => selectedMacs.delete(d.mac));
            } else {
                currentVisibleDevices.forEach(d => selectedMacs.add(d.mac));
            }
            renderDevices();
        }

        function toggleRowCheckbox(event, mac, index) {
            event.stopPropagation();
            if (event.target.checked) {
                selectedMacs.add(mac);
            } else {
                selectedMacs.delete(mac);
            }
            lastSelectedIndex = index;
            renderDevices();
        }

        function handleRowClick(event, mac, index) {
            if (event.target && event.target.closest('input.row-select-checkbox')) return;
            const isCtrl = event.ctrlKey || event.metaKey;
            const isShift = event.shiftKey;

            if (clickToOpen && !isCtrl && !isShift) {
                showDevice(mac);
                return;
            }

            if (isShift && lastSelectedIndex !== null && currentVisibleDevices.length > 0) {
                const start = Math.max(0, Math.min(lastSelectedIndex, index));
                const end = Math.min(currentVisibleDevices.length - 1, Math.max(lastSelectedIndex, index));
                if (!isCtrl) selectedMacs.clear();
                for (let i = start; i <= end; i++) {
                    selectedMacs.add(currentVisibleDevices[i].mac);
                }
            } else if (isCtrl) {
                if (selectedMacs.has(mac)) {
                    selectedMacs.delete(mac);
                } else {
                    selectedMacs.add(mac);
                }
            } else {
                if (selectedMacs.has(mac)) {
                    selectedMacs.delete(mac);
                } else {
                    selectedMacs.clear();
                    selectedMacs.add(mac);
                }
            }

            lastSelectedIndex = index;
            // Delay renderDevices so the dblclick event can fire on the original
            // <tr> element before innerHTML replaces it. Without this delay,
            // the first click destroys the row and dblclick never fires.
            if (rowClickTimer) clearTimeout(rowClickTimer);
            rowClickTimer = setTimeout(() => { rowClickTimer = null; renderDevices(); }, 250);
        }

        function getContrastColor(hexColor) {
            if (!hexColor) return 'var(--text-primary)';
            // Remove # if present
            const hex = hexColor.replace('#', '');
            // Parse RGB values
            const r = parseInt(hex.substr(0, 2), 16);
            const g = parseInt(hex.substr(2, 2), 16);
            const b = parseInt(hex.substr(4, 2), 16);
            // Calculate relative luminance
            const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
            // Return black for light backgrounds, white for dark
            return luminance > 0.5 ? '#000000' : '#ffffff';
        }

        function renderDevices() {
            const tbody = document.getElementById('device-list');
            const sourceDevices = dateFilteredDevices !== null ? dateFilteredDevices : allDevices;
            let visibleDevices = sourceDevices;

            if (dateFilteredDevices !== null) {
                const searchTerm = document.getElementById('search').value.toLowerCase();
                visibleDevices = sourceDevices.filter(d => {
                    if (currentFilter === 'watched') {
                        if (!d.watched) return false;
                    } else if (currentFilter === 'laptop') {
                        if (d.device_type !== 'laptop' && d.device_type !== 'computer') return false;
                    } else if (currentFilter !== 'all' && d.device_type !== currentFilter) {
                        return false;
                    }
                    if (searchTerm) {
                        const searchable = [d.mac, d.vendor, d.friendly_name].join(' ').toLowerCase();
                        if (!searchable.includes(searchTerm)) return false;
                    }
                    return true;
                });
                visibleDevices = applySort(visibleDevices);
                document.getElementById('visible-count').textContent = visibleDevices.length;
            } else {
                document.getElementById('visible-count').textContent = pagination.totalMatching || visibleDevices.length;
            }

            currentVisibleDevices = visibleDevices;

            if (visibleDevices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-muted);">No targets match criteria</td></tr>';
                updateSelectionUI();
                return;
            }

            tbody.innerHTML = visibleDevices.map((d, index) => {
                const typeClass = getTypeClass(d.device_type);
                const { text: lastSeen, tooltip: lastSeenTooltip } = formatLastSeen(d.last_seen);
                const isRecent = isRecentlySeen(d.last_seen);
                const watchedStar = d.watched ? '<span class="watched-star">★</span>' : '';
                const isSelected = selectedMacs.has(d.mac);
                const rowClass = isSelected ? 'selected' : '';
                const checkedAttr = isSelected ? 'checked' : '';

                // Build group pill HTML
                let groupHtml = '—';
                if (d.group_name && d.group_color) {
                    const textColor = getContrastColor(d.group_color);
                    groupHtml = '<span style="background: ' + d.group_color + '; color: ' + textColor + '; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.7rem; font-weight: 500;">' + d.group_name + '</span>';
                } else if (d.group_name) {
                    groupHtml = '<span style="background: var(--bg-tertiary); color: var(--text-secondary); padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.7rem;">' + d.group_name + '</span>';
                }

                if (compactView) {
                    // Compact: Type, Name/MAC, Sightings, Last Seen, Group
                    const rawDisplayName = d.friendly_name || d.vendor || d.mac;
                    let displayName = d.friendly_name ? obfuscateName(rawDisplayName) : (d.vendor ? rawDisplayName : obfuscateMAC(rawDisplayName));
                    // Truncate long macOS UUID addresses in compact view
                    if (!d.friendly_name && !d.vendor && isMacOSUUID(d.mac)) {
                        displayName = displayName.substring(0, 13) + '...';
                    }
                    return '<tr class="' + rowClass + '" onclick="handleRowClick(event, \\'' + d.mac + '\\', ' + index + ')" ondblclick="showDevice(\\'' + d.mac + '\\')" style="height: auto;">' +
                        '<td class="select-col"><input type="checkbox" class="row-select-checkbox" ' + checkedAttr + ' onclick="toggleRowCheckbox(event, \\'' + d.mac + '\\', ' + index + ')"></td>' +
                        '<td style="padding: 0.4rem 0.5rem;"><span class="type-badge ' + typeClass + '" style="font-size: 0.65rem; padding: 0.15rem 0.4rem;">' + watchedStar + d.type_icon + '</span></td>' +
                        '<td colspan="3" style="padding: 0.4rem 0.5rem; font-size: 0.75rem;">' + displayName + '</td>' +
                        '<td style="padding: 0.4rem 0.5rem; font-size: 0.7rem;">' + d.total_sightings + '</td>' +
                        '<td style="padding: 0.4rem 0.5rem; font-size: 0.7rem;" class="' + (isRecent ? 'recent' : '') + '" title="' + lastSeenTooltip + '">' + lastSeen + '</td>' +
                        '<td style="padding: 0.4rem 0.5rem; font-size: 0.7rem;">' + groupHtml + '</td>' +
                        '</tr>';
                }

                return '<tr class="' + rowClass + '" onclick="handleRowClick(event, \\'' + d.mac + '\\', ' + index + ')" ondblclick="showDevice(\\'' + d.mac + '\\')">' +
                    '<td class="select-col"><input type="checkbox" class="row-select-checkbox" ' + checkedAttr + ' onclick="toggleRowCheckbox(event, \\'' + d.mac + '\\', ' + index + ')"></td>' +
                    '<td><span class="type-badge ' + typeClass + '">' + watchedStar + d.type_icon + ' ' + d.type_label + '</span></td>' +
                    '<td class="mac-addr" title="' + d.mac + '">' + (isMacOSUUID(d.mac) ? obfuscateMAC(d.mac).substring(0, 13) + '...' : obfuscateMAC(d.mac)) + '</td>' +
                    '<td class="vendor-name">' + (d.vendor || '—') + '</td>' +
                    '<td class="device-name">' + (d.friendly_name ? obfuscateName(d.friendly_name) : '—') + '</td>' +
                    '<td class="sighting-count">' + d.total_sightings + '</td>' +
                    '<td class="last-seen ' + (isRecent ? 'recent' : '') + '" title="' + lastSeenTooltip + '">' + lastSeen + '</td>' +
                    '<td class="group-name">' + groupHtml + '</td>' +
                    '</tr>';
            }).join('');
            updateSelectionUI();
        }

        function getTypeClass(type) {
            const classes = { phone: 'type-phone', laptop: 'type-laptop', computer: 'type-laptop', tablet: 'type-phone', smart: 'type-smart', audio: 'type-audio', speaker: 'type-audio', watch: 'type-watch', wearable: 'type-watch', tv: 'type-tv', vehicle: 'type-vehicle' };
            return classes[type] || 'type-unknown';
        }

        function formatLastSeen(isoString) {
            if (!isoString) return { text: '—', tooltip: '' };
            const date = new Date(isoString);
            const now = new Date();
            const tooltip = date.toLocaleString();
            const diffMins = Math.floor((now - date) / 60000);
            let text;
            if (diffMins < 1) text = 'NOW';
            else if (diffMins < 60) text = diffMins + 'm ago';
            else if (diffMins < 1440) {
                const h = Math.floor(diffMins / 60);
                const m = diffMins % 60;
                text = m > 0 ? h + 'h ' + m + 'm ago' : h + 'h ago';
            } else {
                const diffDays = Math.floor(diffMins / 1440);
                if (diffDays === 1) text = 'Yesterday ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                else if (diffDays < 7) text = diffDays + 'd ago';
                else text = date.toLocaleDateString();
            }
            return { text, tooltip };
        }

        function isRecentlySeen(isoString) {
            if (!isoString) return false;
            return (new Date() - new Date(isoString)) < 600000;
        }

        async function showDevice(mac) {
            // Cancel any pending single-click re-render so it doesn't
            // disrupt the modal that the double-click is about to open.
            if (rowClickTimer) { clearTimeout(rowClickTimer); rowClickTimer = null; }
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac));
                const data = await response.json();
                renderModal(data);
                document.getElementById('device-modal').classList.add('active');
            } catch (error) { console.error('Error:', error); }
        }

        let currentDeviceMac = null;

        function renderModal(data) {
            const d = data.device;
            currentDeviceMac = d.mac;
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

            const proximityColors = { immediate: '#16a34a', near: '#d97706', far: '#ea580c', remote: '#dc2626', unknown: '#555' };
            const proximityZone = data.proximity_zone || 'unknown';
            const proximityColor = proximityColors[proximityZone] || '#555';

            const watchBtnText = d.watched ? '★ WATCHING' : '☆ WATCH TARGET';
            const watchBtnClass = d.watched ? 'btn btn-watch active' : 'btn btn-watch';

            content.innerHTML = '<div class="action-row">' +
                '<button class="' + watchBtnClass + '" id="watch-btn" onclick="toggleWatch(\\'' + d.mac + '\\')">' + watchBtnText + '</button>' +
                '</div>' +
                '<div class="detail-grid">' +
                '<div class="detail-item"><div class="detail-label">Address</div><div class="detail-value mono" style="font-size:' + (isMacOSUUID(d.mac) ? '0.65rem' : '0.85rem') + '; word-break: break-all;">' + obfuscateMAC(d.mac) + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Classification</div><div class="detail-value">' + data.type_label + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Vendor OUI</div><div class="detail-value">' + (d.vendor || '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Proximity Zone</div><div class="detail-value" style="color: ' + proximityColor + '; text-transform: uppercase;">' + proximityZone + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">First Contact</div><div class="detail-value mono">' + (d.first_seen ? new Date(d.first_seen).toLocaleString() : '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Last Contact</div><div class="detail-value mono">' + (d.last_seen ? new Date(d.last_seen).toLocaleString() : '—') + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Total Sightings</div><div class="detail-value highlight">' + d.total_sightings + '</div></div>' +
                '<div class="detail-item"><div class="detail-label">Signal Strength</div><div class="detail-value">' + rssiDisplay + '</div></div>' +
                '<div class="detail-item full"><div class="detail-label">Behavioral Pattern</div><div class="detail-value">' + (data.pattern || 'Insufficient data') + '</div></div>' +
                '<div class="detail-item full"><div class="detail-label">BLE Service Fingerprint</div><div class="detail-value mono" style="font-size:0.75rem;">' + (data.uuid_names && data.uuid_names.length > 0 ? data.uuid_names.join(', ') : '—') + '</div></div>' +
                '<div class="detail-item full"><div class="detail-label">Operator Notes</div><textarea class="form-input" id="device-notes" rows="2" style="font-size: 0.8rem; resize: vertical;" placeholder="Add notes...">' + (d.notes || '') + '</textarea><button class="btn" style="margin-top: 0.5rem;" onclick="saveNotes(\\'' + d.mac + '\\')">Save Notes</button></div>' +
                '<div class="detail-item full"><div class="detail-label">Assign to Group</div><select class="form-input" id="device-group" onchange="setDeviceGroup(\\'' + d.mac + '\\', this.value)" style="font-size: 0.8rem;"><option value="">No group</option></select></div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Dwell Time Analysis (30d)</div>' +
                '<div id="dwell-stats" class="heatmap" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; text-align: center;"><div style="color: var(--text-muted);">Loading...</div></div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Hourly Activity (30d)</div>' +
                '<div class="heatmap">' + renderHourlyHeatmap(data.hourly_data) + '</div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Daily Activity</div>' +
                '<div class="heatmap">' + renderDailyHeatmap(data.daily_data) + '</div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Presence Timeline (30d)</div>' +
                renderTimeline(data.timeline) +
                '</div>' +
                '<div class="heatmap-section" id="rssi-section">' +
                '<div class="heatmap-title">Signal History (7d)</div>' +
                '<div class="rssi-chart" id="rssi-chart"><div style="color: var(--text-muted); font-size: 0.75rem; text-align: center; padding-top: 1.5rem;">Loading...</div></div>' +
                '</div>' +
                '<div class="heatmap-section">' +
                '<div class="heatmap-title">Correlated Devices</div>' +
                '<div id="correlated-devices" class="heatmap"><div style="color: var(--text-muted);">Loading...</div></div>' +
                '</div>';

            loadRssiChart(d.mac);
            loadDwellStats(d.mac);
            loadCorrelatedDevices(d.mac);
            loadGroupsForDevice(d.group_id);
        }

        let cachedGroups = [];

        async function loadGroupsForDevice(currentGroupId) {
            const select = document.getElementById('device-group');
            if (!select) return;

            // Use cached groups if available
            if (cachedGroups.length === 0) {
                try {
                    const response = await fetch('/api/groups');
                    const data = await response.json();
                    cachedGroups = data.groups || [];
                } catch (error) { return; }
            }

            select.innerHTML = '<option value="">No group</option>' +
                cachedGroups.map(g => '<option value="' + g.id + '"' + (g.id === currentGroupId ? ' selected' : '') + '>' + g.name + '</option>').join('');
        }

        async function loadGroupsForBulkSelect() {
            const select = document.getElementById('bulk-group-select');
            if (!select) return;

            if (cachedGroups.length === 0) {
                try {
                    const response = await fetch('/api/groups');
                    const data = await response.json();
                    cachedGroups = data.groups || [];
                } catch (error) {
                    return;
                }
            }

            select.innerHTML = '<option value="">Assign group...</option>' +
                '<option value="__none__">No group</option>' +
                cachedGroups.map(g => '<option value="' + g.id + '">' + g.name + '</option>').join('');
        }

        async function setDeviceGroup(mac, groupId) {
            try {
                await fetch('/api/device/' + encodeURIComponent(mac) + '/group', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ group_id: groupId ? parseInt(groupId) : null })
                });
                refreshDevices();
            } catch (error) { console.error('Error setting group:', error); }
        }

        async function applyBulkGroup() {
            const select = document.getElementById('bulk-group-select');
            if (!select || !select.value) return;
            if (selectedMacs.size === 0) return;

            const groupValue = select.value;
            const groupId = groupValue === '__none__' ? null : parseInt(groupValue);
            const macs = Array.from(selectedMacs);

            try {
                await Promise.all(macs.map(mac =>
                    fetch('/api/device/' + encodeURIComponent(mac) + '/group', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ group_id: groupId })
                    })
                ));
                refreshDevices();
            } catch (error) {
                console.error('Error applying bulk group:', error);
            }
        }

        async function applyBulkWatch() {
            const select = document.getElementById('bulk-watch-select');
            if (!select || !select.value) return;
            if (selectedMacs.size === 0) return;

            const desired = select.value;
            const deviceMap = new Map(allDevices.map(d => [d.mac, d]));
            const macs = Array.from(selectedMacs);
            const requests = [];

            macs.forEach(mac => {
                const device = deviceMap.get(mac);
                if (!device) return;
                if (desired === 'on' && !device.watched) {
                    requests.push(fetch('/api/device/' + encodeURIComponent(mac) + '/watch', { method: 'POST' }));
                }
                if (desired === 'off' && device.watched) {
                    requests.push(fetch('/api/device/' + encodeURIComponent(mac) + '/watch', { method: 'POST' }));
                }
            });

            try {
                await Promise.all(requests);
                refreshDevices();
            } catch (error) {
                console.error('Error applying bulk watch:', error);
            }
        }

        async function loadDwellStats(mac) {
            const container = document.getElementById('dwell-stats');
            if (!container) return;
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac) + '/dwell?days=30');
                const data = await response.json();
                container.innerHTML = '<div><div style="font-size: 1.25rem; color: var(--accent-amber);">' + Math.round(data.total_minutes) + '</div><div style="font-size: 0.65rem; color: var(--text-muted);">TOTAL MIN</div></div>' +
                    '<div><div style="font-size: 1.25rem; color: var(--accent-green);">' + data.session_count + '</div><div style="font-size: 0.65rem; color: var(--text-muted);">SESSIONS</div></div>' +
                    '<div><div style="font-size: 1.25rem; color: var(--accent-blue);">' + Math.round(data.avg_session_minutes) + '</div><div style="font-size: 0.65rem; color: var(--text-muted);">AVG MIN</div></div>' +
                    '<div><div style="font-size: 1.25rem; color: var(--accent-red);">' + Math.round(data.longest_session_minutes) + '</div><div style="font-size: 0.65rem; color: var(--text-muted);">LONGEST</div></div>';
            } catch (error) {
                container.innerHTML = '<div style="color: var(--text-muted);">Error loading data</div>';
            }
        }

        async function loadCorrelatedDevices(mac) {
            const container = document.getElementById('correlated-devices');
            if (!container) return;
            try {
                const response = await fetch('/api/device/' + encodeURIComponent(mac) + '/correlation?days=30');
                const data = await response.json();
                if (!data.correlated_devices || data.correlated_devices.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.75rem;">No correlated devices found</div>';
                    return;
                }
                container.innerHTML = data.correlated_devices.slice(0, 5).map(c => {
                    const rawPrimaryName = c.friendly_name || c.vendor || 'Unknown';
                    const primaryName = c.friendly_name ? obfuscateName(rawPrimaryName) : rawPrimaryName;
                    const rawSecondaryInfo = c.friendly_name ? (c.vendor || c.mac) : c.mac;
                    const secondaryInfo = (c.friendly_name && c.vendor) ? rawSecondaryInfo : obfuscateMAC(rawSecondaryInfo);
                    const corrBar = '<div style="background: var(--accent-red); height: 4px; width: ' + c.correlation_score + '%; border-radius: 2px;"></div>';
                    return '<div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); cursor: pointer;" onclick="openDeviceModal(\\'' + c.mac + '\\')">' +
                        '<div style="flex: 1; min-width: 0;">' +
                        '<div style="font-size: 0.8rem; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' + primaryName + '</div>' +
                        '<div style="font-size: 0.65rem; color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' + secondaryInfo + '</div>' +
                        '</div>' +
                        '<div style="display: flex; align-items: center; gap: 0.5rem; margin-left: 0.5rem;">' +
                        '<div style="width: 50px;">' + corrBar + '</div>' +
                        '<span style="font-size: 0.7rem; color: var(--accent-amber); min-width: 32px; text-align: right;">' + c.correlation_score + '%</span>' +
                        '</div></div>';
                }).join('');
            } catch (error) {
                container.innerHTML = '<div style="color: var(--text-muted);">Error loading data</div>';
            }
        }

        async function saveNotes(mac) {
            const notes = document.getElementById('device-notes').value;
            try {
                await fetch('/api/device/' + encodeURIComponent(mac) + '/notes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ notes: notes })
                });
            } catch (error) { console.error('Error:', error); }
        }

        function renderHourlyHeatmap(hourlyData) {
            if (!hourlyData || Object.keys(hourlyData).length === 0) return '<div style="color: var(--text-muted); font-size: 0.75rem; text-align: center; padding: 1rem 0;">No data</div>';
            var offset = -(new Date().getTimezoneOffset() / 60);
            var shifted = {};
            for (var h in hourlyData) {
                var localHour = ((parseInt(h) + offset) % 24 + 24) % 24;
                shifted[localHour] = (shifted[localHour] || 0) + hourlyData[h];
            }
            var max = Math.max(...Object.values(shifted), 1);
            var cells = '';
            var labels = '';
            for (var i = 0; i < 24; i++) {
                var count = shifted[i] || 0;
                var level = count === 0 ? 0 : Math.ceil((count / max) * 4);
                var label = i < 10 ? '0' + i : '' + i;
                cells += '<div class="activity-cell l' + level + '" title="' + label + ':00 — ' + count + ' sightings"></div>';
                labels += '<span>' + (i % 6 === 0 ? label : '') + '</span>';
            }
            return '<div class="activity-grid hourly">' + cells + '</div><div class="activity-labels hourly">' + labels + '</div>';
        }

        function renderDailyHeatmap(dailyData) {
            if (!dailyData || Object.keys(dailyData).length === 0) return '<div style="color: var(--text-muted); font-size: 0.75rem; text-align: center; padding: 1rem 0;">No data</div>';
            var days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            var max = Math.max(...Object.values(dailyData), 1);
            var cells = '';
            var labels = '';
            for (var d = 0; d < 7; d++) {
                var count = dailyData[d] || dailyData[String(d)] || 0;
                var level = count === 0 ? 0 : Math.ceil((count / max) * 4);
                cells += '<div class="activity-cell l' + level + '" title="' + days[d] + ' — ' + count + ' sightings"></div>';
                labels += '<span>' + days[d] + '</span>';
            }
            return '<div class="activity-grid daily">' + cells + '</div><div class="activity-labels daily">' + labels + '</div>';
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

        function csvField(val) {
            const s = String(val);
            if (s.includes(',') || s.includes('"') || s.includes('\\n')) {
                return '"' + s.replace(/"/g, '""') + '"';
            }
            return s;
        }

        function exportData() {
            const csv = ['MAC,Vendor,Identifier,Class,Sightings,Last_Contact,Group'];
            const exportDevices = selectedMacs.size > 0
                ? allDevices.filter(d => selectedMacs.has(d.mac))
                : allDevices;
            exportDevices.forEach(d => {
                const mac = obfuscateMAC(d.mac);
                const name = d.friendly_name ? obfuscateName(d.friendly_name) : '';
                csv.push([mac, d.vendor || '', name, d.device_type || '', d.total_sightings, d.last_seen || '', d.group_name || ''].map(csvField).join(','));
            });
            const blob = new Blob([csv.join('\\n')], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'bluehood-recon-' + new Date().toISOString().split('T')[0] + '.csv';
            a.click();
        }

        // Filter handlers
        document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                selectedMacs.clear();
                lastSelectedIndex = null;
                if (dateFilteredDevices !== null) {
                    renderDevices();
                    return;
                }
                pagination.page = 1;
                refreshDevices();
            });
        });

        document.querySelectorAll('.device-table th.sortable').forEach(th => {
            th.addEventListener('click', () => setSort(th.dataset.sort));
        });

        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', toggleSelectAllVisible);
        }

        document.getElementById('search').addEventListener('input', () => {
            if (dateFilteredDevices !== null) {
                renderDevices();
                return;
            }
            selectedMacs.clear();
            lastSelectedIndex = null;
            queueDeviceRefresh(true);
        });
        document.getElementById('device-modal').addEventListener('click', (e) => { if (e.target.id === 'device-modal') closeModal(); });
        document.getElementById('shortcuts-modal').addEventListener('click', (e) => { if (e.target.id === 'shortcuts-modal') closeShortcutsModal(); });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input/textarea
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            const modalActive = document.getElementById('device-modal').classList.contains('active');

            if (e.key === 'Escape') {
                closeModal();
                closeShortcutsModal();
            } else if (e.key === 'r' || e.key === 'R') {
                // Refresh
                refreshDevices();
            } else if (e.key === '/') {
                // Focus search
                e.preventDefault();
                document.getElementById('search').focus();
            } else if (e.key === 'w' && modalActive && currentDeviceMac) {
                // Toggle watch on current device
                toggleWatch(currentDeviceMac);
            } else if (e.key === '1') {
                document.querySelector('[data-filter="all"]').click();
            } else if (e.key === '2') {
                document.querySelector('[data-filter="watched"]').click();
            } else if (e.key === '3') {
                document.querySelector('[data-filter="phone"]').click();
            } else if (e.key === '4') {
                document.querySelector('[data-filter="laptop"]').click();
            } else if (e.key === '5') {
                document.querySelector('[data-filter="audio"]').click();
            } else if (e.key === '?') {
                showShortcutsModal();
            }
        });

        updateViewToggle();
        updateScreenshotToggle();
        updateClickToOpenToggle();
        updateSortIndicators();
        loadGroupsForBulkSelect();
        updateSelectionUI();
        updatePaginationUI();
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

        [data-theme="light"] { --bg-primary: #f5f5f5; --bg-secondary: #e8e8e8; --bg-tertiary: #ffffff; --bg-hover: #d8d8d8; --text-primary: #1a1a1a; --text-secondary: #555555; --text-muted: #888888; --accent-red: #dc2626; --accent-green: #16a34a; --border-color: #cccccc; }

        .theme-toggle { background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.75rem; padding: 0.3rem 0.5rem; cursor: pointer; border-radius: 3px; transition: all 0.1s; }
        .theme-toggle:hover { color: var(--text-primary); border-color: var(--border-active, #999); }

        .config-nav { background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); display: flex; justify-content: center; gap: 0; }
        .config-nav a { color: var(--text-muted); text-decoration: none; font-size: 0.7rem; padding: 0.75rem 1.25rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 2px solid transparent; transition: all 0.15s; }
        .config-nav a:hover { color: var(--text-secondary); }
        .config-nav a.active { color: var(--text-primary); border-bottom-color: var(--accent-red); }

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
        .form-hint { font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem; }

        .btn { padding: 0.6rem 1.25rem; border-radius: 3px; font-family: var(--font-mono); font-size: 0.7rem; font-weight: 500; cursor: pointer; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; text-decoration: none; display: inline-block; transition: all 0.1s; }
        .btn:hover { background: var(--bg-hover); color: var(--text-primary); }
        .btn-primary { background: var(--accent-red); border-color: var(--accent-red); color: white; }
        .btn-primary:hover { background: #b91c1c; }

        .btn-row { display: flex; gap: 0.75rem; margin-top: 1.5rem; }

        .status-msg { padding: 0.75rem 1rem; border-radius: 3px; font-size: 0.8rem; margin-bottom: 1rem; display: none; border: 1px solid; }
        .status-msg.success { background: rgba(22, 163, 74, 0.1); color: var(--accent-green); border-color: var(--accent-green); display: block; }
        .status-msg.error { background: rgba(220, 38, 38, 0.1); color: var(--accent-red); border-color: var(--accent-red); display: block; }

        .config-tab { display: none; }

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
        <div><button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">☀</button></div>
    </header>

    <nav class="config-nav">
        <a href="#alerts" data-tab="alerts" class="active" onclick="switchTab('alerts')">Alerts</a>
        <a href="#operations" data-tab="operations" onclick="switchTab('operations')">Operations</a>
        <a href="#groups" data-tab="groups" onclick="switchTab('groups')">Groups</a>
        <a href="#security" data-tab="security" onclick="switchTab('security')">Security</a>
    </nav>

    <main class="main">
        <div id="status-msg" class="status-msg"></div>

        <!-- Alerts Tab -->
        <div class="config-tab" id="tab-alerts">
            <div class="page-header">
                <div class="page-title">System Configuration</div>
                <h1 class="page-heading">Alert Configuration</h1>
            </div>

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
                        <div id="new-device-threshold-field" style="display: none; margin: 0.5rem 0 0.5rem 2rem;">
                            <label class="form-label">Persistence Threshold (min)</label>
                            <input type="number" class="form-input" id="new_device_threshold_minutes" value="0" min="0" max="1440" style="width: 120px;">
                            <div class="form-hint">0 = immediate alert, &gt;0 = alert after device persists this long</div>
                        </div>
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
        </div>

        <!-- Operations Tab -->
        <div class="config-tab" id="tab-operations">
            <div class="page-header">
                <div class="page-title">System Configuration</div>
                <h1 class="page-heading">Operations</h1>
            </div>

            <form id="operations-form">
                <div class="panel">
                    <div class="panel-header">Heartbeat Check-In</div>
                    <div class="panel-body">
                        <div class="form-group">
                            <label class="form-label">Heartbeat URL</label>
                            <input type="url" class="form-input" id="heartbeat_url" placeholder="e.g., https://uptime.example.com/api/push/abc123">
                            <div class="form-hint">POST JSON payload with hostname, uptime, device count. Leave empty to disable.</div>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Interval (seconds)</label>
                            <input type="number" class="form-input" id="heartbeat_interval" value="300" min="30" max="86400" style="width: 160px;">
                            <div class="form-hint">How often to send heartbeat pings (default: 300s / 5 min)</div>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">Storage Rotation</div>
                    <div class="panel-body">
                        <div class="form-group">
                            <label class="form-label">Prune Sightings Older Than (days)</label>
                            <input type="number" class="form-input" id="prune_days" value="0" min="0" max="3650" style="width: 160px;">
                            <div class="form-hint">Automatically delete sighting records older than this many days. 0 = keep forever.</div>
                        </div>
                    </div>
                </div>

                <div class="btn-row">
                    <button type="submit" class="btn btn-primary">Save Configuration</button>
                    <a href="/" class="btn">Cancel</a>
                </div>
            </form>
        </div>

        <!-- Groups Tab -->
        <div class="config-tab" id="tab-groups">
            <div class="page-header">
                <div class="page-title">System Configuration</div>
                <h1 class="page-heading">Device Groups</h1>
            </div>

            <div class="panel">
                <div class="panel-header">Device Groups</div>
                <div class="panel-body">
                    <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 1rem;">Organize targets into custom groups for easier tracking</p>
                    <div id="groups-list" style="margin-bottom: 1rem;"></div>
                    <div style="display: flex; gap: 0.5rem;">
                        <input type="text" class="form-input" id="new-group-name" placeholder="New group name" style="flex: 1;">
                        <input type="color" id="new-group-color" value="#3b82f6" style="width: 40px; height: 38px; border: 1px solid var(--border-color); background: var(--bg-tertiary); cursor: pointer;">
                        <button type="button" class="btn btn-primary" onclick="createGroup()">Add Group</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Security Tab -->
        <div class="config-tab" id="tab-security">
            <div class="page-header">
                <div class="page-title">System Configuration</div>
                <h1 class="page-heading">Access Control</h1>
            </div>

            <div class="panel">
                <div class="panel-header">Access Control</div>
                <div class="panel-body">
                    <label class="form-check">
                        <input type="checkbox" id="auth_enabled">
                        <div>
                            <div class="form-check-label">Enable Authentication</div>
                            <div class="form-check-desc">Require login to access the dashboard</div>
                        </div>
                    </label>
                    <div id="auth-fields" style="display: none; margin-top: 1rem;">
                        <div class="form-group">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-input" id="auth_username" autocomplete="username">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-input" id="auth_password" autocomplete="new-password" placeholder="Enter new password">
                        </div>
                    </div>
                    <div class="btn-row" style="margin-top: 1rem;">
                        <button type="button" class="btn btn-primary" onclick="saveAuthSettings()">Update Access Control</button>
                        <button type="button" class="btn" onclick="logout()" id="logout-btn" style="display: none;">Logout</button>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer class="footer">BLUEHOOD v0.5.0 // <a href="https://github.com/dannymcc/bluehood">Source</a></footer>

    <script>
        function applyTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            const btn = document.getElementById('theme-toggle');
            if (btn) btn.textContent = theme === 'light' ? '☽' : '☀';
        }
        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem('bluehood_theme', next);
            applyTheme(next);
        }
        applyTheme(localStorage.getItem('bluehood_theme') || 'dark');

        function switchTab(tab) {
            document.querySelectorAll('.config-tab').forEach(function(t) { t.style.display = 'none'; });
            document.querySelectorAll('.config-nav a').forEach(function(a) { a.classList.remove('active'); });
            var tabEl = document.getElementById('tab-' + tab);
            if (tabEl) tabEl.style.display = 'block';
            var navEl = document.querySelector('[data-tab="' + tab + '"]');
            if (navEl) navEl.classList.add('active');
            history.replaceState(null, '', '#' + tab);
        }

        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const data = await response.json();
                document.getElementById('ntfy_topic').value = data.ntfy_topic || '';
                document.getElementById('ntfy_enabled').checked = data.ntfy_enabled;
                document.getElementById('notify_new_device').checked = data.notify_new_device;
                document.getElementById('new_device_threshold_minutes').value = data.new_device_threshold_minutes || 0;
                document.getElementById('new-device-threshold-field').style.display = data.notify_new_device ? 'block' : 'none';
                document.getElementById('notify_watched_return').checked = data.notify_watched_return;
                document.getElementById('notify_watched_leave').checked = data.notify_watched_leave;
                document.getElementById('watched_absence_minutes').value = data.watched_absence_minutes;
                document.getElementById('watched_return_minutes').value = data.watched_return_minutes;
                document.getElementById('heartbeat_url').value = data.heartbeat_url || '';
                document.getElementById('heartbeat_interval').value = data.heartbeat_interval || 300;
                document.getElementById('prune_days').value = data.prune_days || 0;
            } catch (error) { showStatus('Error loading configuration', 'error'); }
        }

        function gatherAllSettings() {
            return {
                ntfy_topic: document.getElementById('ntfy_topic').value,
                ntfy_enabled: document.getElementById('ntfy_enabled').checked,
                notify_new_device: document.getElementById('notify_new_device').checked,
                new_device_threshold_minutes: parseInt(document.getElementById('new_device_threshold_minutes').value) || 0,
                notify_watched_return: document.getElementById('notify_watched_return').checked,
                notify_watched_leave: document.getElementById('notify_watched_leave').checked,
                watched_absence_minutes: parseInt(document.getElementById('watched_absence_minutes').value),
                watched_return_minutes: parseInt(document.getElementById('watched_return_minutes').value),
                heartbeat_url: document.getElementById('heartbeat_url').value,
                heartbeat_interval: parseInt(document.getElementById('heartbeat_interval').value) || 300,
                prune_days: parseInt(document.getElementById('prune_days').value) || 0,
            };
        }

        async function saveSettings(e) {
            e.preventDefault();
            try {
                const response = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(gatherAllSettings()) });
                if (response.ok) showStatus('Configuration saved', 'success');
                else showStatus('Error saving configuration', 'error');
            } catch (error) { showStatus('Error saving configuration', 'error'); }
        }

        async function saveOperations(e) {
            e.preventDefault();
            try {
                const response = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(gatherAllSettings()) });
                if (response.ok) showStatus('Configuration saved', 'success');
                else showStatus('Error saving configuration', 'error');
            } catch (error) { showStatus('Error saving configuration', 'error'); }
        }

        function showStatus(message, type) {
            const el = document.getElementById('status-msg');
            el.textContent = message;
            el.className = 'status-msg ' + type;
            if (type === 'success') setTimeout(function() { el.className = 'status-msg'; }, 3000);
        }

        async function loadAuthStatus() {
            try {
                const response = await fetch('/api/auth/status');
                const data = await response.json();
                document.getElementById('auth_enabled').checked = data.auth_enabled;
                document.getElementById('auth_username').value = data.username || '';
                document.getElementById('auth-fields').style.display = data.auth_enabled ? 'block' : 'none';
                document.getElementById('logout-btn').style.display = data.authenticated && data.auth_enabled ? 'inline-block' : 'none';
            } catch (error) { console.error('Error loading auth status'); }
        }

        document.getElementById('notify_new_device').addEventListener('change', function(e) {
            document.getElementById('new-device-threshold-field').style.display = e.target.checked ? 'block' : 'none';
        });

        document.getElementById('auth_enabled').addEventListener('change', function(e) {
            document.getElementById('auth-fields').style.display = e.target.checked ? 'block' : 'none';
        });

        async function saveAuthSettings() {
            const enabled = document.getElementById('auth_enabled').checked;
            const username = document.getElementById('auth_username').value;
            const password = document.getElementById('auth_password').value;

            if (enabled && (!username || !password)) {
                showStatus('Username and password required', 'error');
                return;
            }

            try {
                const response = await fetch('/api/auth/setup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: enabled, username: username, password: password })
                });
                if (response.ok) {
                    showStatus('Access control updated', 'success');
                    document.getElementById('auth_password').value = '';
                    loadAuthStatus();
                } else {
                    const data = await response.json();
                    showStatus(data.error || 'Error updating access control', 'error');
                }
            } catch (error) { showStatus('Error updating access control', 'error'); }
        }

        async function logout() {
            try {
                await fetch('/api/auth/logout', { method: 'POST' });
                window.location.href = '/login';
            } catch (error) { console.error('Logout error'); }
        }

        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();
                const container = document.getElementById('groups-list');
                if (!data.groups || data.groups.length === 0) {
                    container.textContent = '';
                    var empty = document.createElement('div');
                    empty.style.cssText = 'color: var(--text-muted); font-size: 0.75rem; text-align: center; padding: 1rem;';
                    empty.textContent = 'No groups created yet';
                    container.appendChild(empty);
                    return;
                }
                container.textContent = '';
                data.groups.forEach(function(g) {
                    var row = document.createElement('div');
                    row.style.cssText = 'display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem; background: var(--bg-tertiary); border-radius: 3px; margin-bottom: 0.5rem;';
                    var swatch = document.createElement('div');
                    swatch.style.cssText = 'width: 12px; height: 12px; border-radius: 2px; background: ' + g.color + ';';
                    var name = document.createElement('span');
                    name.style.cssText = 'flex: 1; font-size: 0.85rem;';
                    name.textContent = g.name;
                    var btn = document.createElement('button');
                    btn.className = 'btn';
                    btn.style.cssText = 'padding: 0.25rem 0.5rem; font-size: 0.7rem;';
                    btn.textContent = 'Delete';
                    btn.addEventListener('click', function() { deleteGroup(g.id); });
                    row.appendChild(swatch);
                    row.appendChild(name);
                    row.appendChild(btn);
                    container.appendChild(row);
                });
            } catch (error) { console.error('Error loading groups'); }
        }

        async function createGroup() {
            const name = document.getElementById('new-group-name').value.trim();
            const color = document.getElementById('new-group-color').value;
            if (!name) { showStatus('Group name required', 'error'); return; }

            try {
                const response = await fetch('/api/groups', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, color: color, icon: String.fromCodePoint(128193) })
                });
                if (response.ok) {
                    document.getElementById('new-group-name').value = '';
                    loadGroups();
                    showStatus('Group created', 'success');
                } else {
                    showStatus('Error creating group', 'error');
                }
            } catch (error) { showStatus('Error creating group', 'error'); }
        }

        async function deleteGroup(id) {
            if (!confirm('Delete this group?')) return;
            try {
                const response = await fetch('/api/groups/' + id, { method: 'DELETE' });
                if (response.ok) { loadGroups(); showStatus('Group deleted', 'success'); }
                else { showStatus('Error deleting group', 'error'); }
            } catch (error) { showStatus('Error deleting group', 'error'); }
        }

        document.getElementById('settings-form').addEventListener('submit', saveSettings);
        document.getElementById('operations-form').addEventListener('submit', saveOperations);

        // Tab routing: read hash on load, default to alerts
        var hash = window.location.hash.replace('#', '') || 'alerts';
        switchTab(['alerts', 'operations', 'groups', 'security'].indexOf(hash) !== -1 ? hash : 'alerts');

        loadSettings();
        loadAuthStatus();
        loadGroups();
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

        [data-theme="light"] { --bg-primary: #f5f5f5; --bg-secondary: #e8e8e8; --bg-tertiary: #ffffff; --bg-hover: #d8d8d8; --text-primary: #1a1a1a; --text-secondary: #555555; --text-muted: #888888; --accent-red: #dc2626; --accent-amber: #d97706; --border-color: #cccccc; }

        .theme-toggle { background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.75rem; padding: 0.3rem 0.5rem; cursor: pointer; border-radius: 3px; transition: all 0.1s; }
        .theme-toggle:hover { color: var(--text-primary); border-color: var(--border-active, #999); }

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
        <div><button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">☀</button></div>
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

        <div class="version">v0.5.0 // BUILD 2026.01</div>
    </main>

    <footer class="footer">BLUEHOOD // <a href="https://github.com/dannymcc/bluehood">Source Repository</a></footer>

    <script>
        function applyTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            const btn = document.getElementById('theme-toggle');
            if (btn) btn.textContent = theme === 'light' ? '☽' : '☀';
        }
        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem('bluehood_theme', next);
            applyTheme(next);
        }
        applyTheme(localStorage.getItem('bluehood_theme') || 'dark');
    </script>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BLUEHOOD // Authentication Required</title>
    <style>
        :root {
            --bg-primary: #0d0d0d;
            --bg-secondary: #141414;
            --bg-tertiary: #1a1a1a;
            --text-primary: #e0e0e0;
            --text-secondary: #888888;
            --text-muted: #555555;
            --accent-red: #dc2626;
            --border-color: #2a2a2a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: var(--font-mono); background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; display: flex; align-items: center; justify-content: center; }

        .login-container { width: 100%; max-width: 380px; padding: 1rem; }

        .login-box { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 4px; padding: 2rem; }

        .login-header { text-align: center; margin-bottom: 2rem; }
        .login-icon { color: var(--accent-red); font-size: 2rem; margin-bottom: 0.75rem; }
        .login-title { font-size: 1.25rem; font-weight: 700; letter-spacing: 0.1em; }
        .login-title span { color: var(--accent-red); }
        .login-subtitle { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.15em; margin-top: 0.5rem; }

        .form-group { margin-bottom: 1rem; }
        .form-label { display: block; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 0.5rem; }
        .form-input { width: 100%; padding: 0.75rem; border: 1px solid var(--border-color); border-radius: 3px; background: var(--bg-tertiary); color: var(--text-primary); font-family: var(--font-mono); font-size: 0.9rem; }
        .form-input:focus { outline: none; border-color: var(--accent-red); }

        .btn { width: 100%; padding: 0.75rem; border: none; border-radius: 3px; background: var(--accent-red); color: white; font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; cursor: pointer; transition: background 0.1s; }
        .btn:hover { background: #b91c1c; }

        .error-msg { background: rgba(220, 38, 38, 0.1); border: 1px solid var(--accent-red); border-radius: 3px; padding: 0.75rem; margin-bottom: 1rem; color: var(--accent-red); font-size: 0.8rem; text-align: center; display: none; }
        .error-msg.show { display: block; }

        [data-theme="light"] { --bg-primary: #f5f5f5; --bg-secondary: #e8e8e8; --bg-tertiary: #ffffff; --text-primary: #1a1a1a; --text-secondary: #555555; --text-muted: #888888; --accent-red: #dc2626; --border-color: #cccccc; }

        .theme-toggle { position: fixed; top: 1rem; right: 1rem; background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.75rem; padding: 0.3rem 0.5rem; cursor: pointer; border-radius: 3px; transition: all 0.1s; }
        .theme-toggle:hover { color: var(--text-primary); border-color: var(--border-active, #999); }
    </style>
</head>
<body>
    <button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">☀</button>
    <div class="login-container">
        <div class="login-box">
            <div class="login-header">
                <div class="login-icon">◉</div>
                <h1 class="login-title">BLUE<span>HOOD</span></h1>
                <p class="login-subtitle">Authentication Required</p>
            </div>

            <div class="error-msg" id="error-msg">Invalid credentials</div>

            <form id="login-form">
                <div class="form-group">
                    <label class="form-label">Username</label>
                    <input type="text" class="form-input" id="username" name="username" autocomplete="username" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Password</label>
                    <input type="password" class="form-input" id="password" name="password" autocomplete="current-password" required>
                </div>
                <button type="submit" class="btn">Authenticate</button>
            </form>
        </div>
    </div>

    <script>
        function applyTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            const btn = document.getElementById('theme-toggle');
            if (btn) btn.textContent = theme === 'light' ? '☽' : '☀';
        }
        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem('bluehood_theme', next);
            applyTheme(next);
        }
        applyTheme(localStorage.getItem('bluehood_theme') || 'dark');

        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                if (response.ok) {
                    window.location.href = '/';
                } else {
                    document.getElementById('error-msg').classList.add('show');
                }
            } catch (error) {
                document.getElementById('error-msg').classList.add('show');
            }
        });
    </script>
</body>
</html>
"""
