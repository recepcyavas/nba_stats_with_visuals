"""
================================================================================
GENERATE PLAYER STATS HTML
================================================================================

PURPOSE:
    Generates standalone HTML dashboard for player statistics analysis.
    Shows sortable, filterable tables with custom metrics (IPM, Ethical Hoops).

INPUT:
    player_computed_stats.json (from compute_player_stats.py)

OUTPUT:
    player_stats_dashboard.html

================================================================================
"""

import json

INPUT_PATH = "player_computed_stats.json"
OUTPUT_PATH = "player_stats_dashboard.html"


def generate_html():
    print("=" * 60)
    print("GENERATE PLAYER STATS HTML")
    print("=" * 60)
    
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    players = list(data.get("players", {}).values())
    meta = data.get("meta", {})
    
    print(f"Loaded {len(players)} players")
    print(f"IPM weights: {meta.get('ipm_weights', {})}")
    print(f"Ethical weights: {meta.get('ethical_weights', {})}")
    
    # Escape for safe JavaScript embedding
    def js_escape(obj):
        s = json.dumps(obj, ensure_ascii=False)
        s = s.replace('</script>', '<\\/script>')
        return s
    
    players_json = js_escape(players)
    meta_json = js_escape(meta)
    
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>NBA Player Stats 2025-26</title>
    <meta charset="UTF-8">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%); 
            color: white; 
            min-height: 100vh;
            padding: 20px;
        }
        
        /* Header */
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5rem;
            background: linear-gradient(90deg, #007AC1, #4ade80);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        .header .subtitle {
            color: #888;
            font-size: 1rem;
        }
        
        /* Main Layout */
        .main-container {
            max-width: 1800px;
            margin: 0 auto;
        }
        
        /* Control Panel */
        .control-panel {
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .control-row {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: flex-end;
            margin-bottom: 15px;
        }
        .control-row:last-child { margin-bottom: 0; }
        
        .control-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .control-group label {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .control-group input, .control-group select {
            background: #0a1628;
            border: 2px solid #333;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }
        .control-group input:focus, .control-group select:focus {
            border-color: #007AC1;
        }
        .control-group input::placeholder {
            color: #555;
        }
        .control-group.name-search input {
            width: 200px;
        }
        
        /* Filter Pills */
        .filter-pills {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .filter-pill {
            background: #0f3460;
            color: #4ade80;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .filter-pill .remove {
            cursor: pointer;
            color: #f87171;
            font-weight: bold;
        }
        .filter-pill .remove:hover {
            color: #ff0000;
        }
        
        /* Quick Actions */
        .quick-actions {
            display: flex;
            gap: 10px;
            margin-left: auto;
        }
        .action-btn {
            background: linear-gradient(135deg, #166534, #4ade80);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.2s;
        }
        .action-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(74, 222, 128, 0.3);
        }
        .action-btn.secondary {
            background: #333;
        }
        .action-btn.secondary:hover {
            background: #444;
            box-shadow: none;
        }
        
        /* Stats Summary */
        .stats-summary {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .summary-card {
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 10px;
            padding: 15px 25px;
            text-align: center;
            min-width: 120px;
        }
        .summary-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #4ade80;
        }
        .summary-label {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            margin-top: 3px;
        }
        
        /* Table Container */
        .table-container {
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            overflow: hidden;
        }
        
        /* Table */
        .stats-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            table-layout: fixed;
        }
        .stats-table thead {
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .stats-table th {
            background: #0a1628;
            padding: 12px 6px;
            text-align: right;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.5px;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
            border-bottom: 2px solid #333;
            transition: all 0.2s;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .stats-table th:hover {
            color: #007AC1;
            background: #0d1d35;
        }
        .stats-table th.sorted {
            color: #4ade80;
        }
        .stats-table th.sorted::after {
            content: ' ▼';
            font-size: 0.6rem;
        }
        .stats-table th.sorted.asc::after {
            content: ' ▲';
        }
        
        .stats-table td {
            padding: 10px 6px;
            border-bottom: 1px solid #2a3a5a;
            vertical-align: middle;
            text-align: right;
            font-variant-numeric: tabular-nums;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .stats-table tbody tr {
            transition: background 0.2s;
        }
        .stats-table tbody tr:hover {
            background: rgba(0, 122, 193, 0.15);
        }
        
        /* Column Groups - fixed widths */
        .col-rank, th.col-rank, td.col-rank { width: 40px; min-width: 40px; text-align: center !important; color: #007AC1; font-weight: 700; }
        .col-player, th.col-player, td.col-player { width: 180px; min-width: 180px; text-align: left !important; }
        .col-team, th.col-team, td.col-team { width: 50px; min-width: 50px; text-align: center !important; }
        .col-gp, th.col-gp, td.col-gp { width: 40px; min-width: 40px; text-align: center !important; }
        .col-stat, th.col-stat, td.col-stat { width: 55px; min-width: 55px; text-align: right !important; }
        .col-pct, th.col-pct, td.col-pct { width: 50px; min-width: 50px; text-align: right !important; }
        
        /* Player Cell */
        .player-cell {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .player-headshot {
            width: 40px;
            height: 30px;
            border-radius: 4px;
            overflow: hidden;
            background: #0a1628;
            flex-shrink: 0;
        }
        .player-headshot img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .player-name {
            font-weight: 600;
            color: #fff;
        }
        
        /* Team Badge */
        .team-badge {
            background: #0f3460;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #4ade80;
        }
        
        /* Stat Values */
        .stat-positive { color: #4ade80; }
        .stat-negative { color: #f87171; }
        .stat-neutral { color: #888; }
        .stat-highlight { 
            color: #fbbf24; 
            font-weight: 700;
        }
        .foul-penalty {
            color: #f87171 !important;
            position: relative;
        }
        .foul-penalty::after {
            content: '⚠';
            font-size: 0.7em;
            margin-left: 2px;
            vertical-align: super;
        }
        
        /* Rank Styling */
        .rank-1 { color: #fbbf24; font-weight: 700; }
        .rank-2 { color: #c0c0c0; font-weight: 600; }
        .rank-3 { color: #cd7f32; font-weight: 600; }
        .rank-top10 { color: #4ade80; }
        
        /* Pagination */
        .pagination {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            background: #0a1628;
            border-top: 1px solid #333;
        }
        .pagination-info {
            color: #888;
            font-size: 0.85rem;
        }
        .pagination-controls {
            display: flex;
            gap: 5px;
        }
        .page-btn {
            background: #0f3460;
            color: #aaa;
            border: none;
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .page-btn:hover:not(:disabled) {
            background: #007AC1;
            color: #fff;
        }
        .page-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        .page-btn.active {
            background: #007AC1;
            color: #fff;
        }
        
        /* Tabs */
        .tab-nav {
            display: flex;
            gap: 0;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
        }
        .tab-btn {
            background: transparent;
            color: #888;
            border: none;
            padding: 12px 24px;
            font-size: 1rem;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }
        .tab-btn:hover { color: #fff; }
        .tab-btn.active {
            color: #007AC1;
            border-bottom-color: #007AC1;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Scrollable table wrapper */
        .table-scroll {
            max-height: 70vh;
            overflow-y: auto;
        }
        .table-scroll::-webkit-scrollbar {
            width: 8px;
        }
        .table-scroll::-webkit-scrollbar-track {
            background: #0a1628;
        }
        .table-scroll::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 4px;
        }
        .table-scroll::-webkit-scrollbar-thumb:hover {
            background: #007AC1;
        }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 60px;
            color: #888;
        }
        
        /* Responsive */
        @media (max-width: 1200px) {
            .control-row { flex-direction: column; align-items: stretch; }
            .quick-actions { margin-left: 0; margin-top: 10px; }
        }
        
        /* Presets */
        .preset-btn {
            background: #1e3a5f;
            color: #60a5fa;
            border: 1px solid #2a4a6f;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.2s;
        }
        .preset-btn:hover {
            background: #2a4a6f;
            color: #fff;
        }
        
        /* Toggle Label */
        .rank-toggle {
            display: flex;
            gap: 5px;
        }
        .toggle-label {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            color: #aaa;
            padding: 6px 10px;
            background: #0f3460;
            border-radius: 6px;
            border: 2px solid #333;
            transition: all 0.2s;
        }
        .toggle-label:hover {
            border-color: #007AC1;
            color: #fff;
        }
        .toggle-label input {
            accent-color: #4ade80;
            width: 14px;
            height: 14px;
        }
        .toggle-label input:checked + span {
            color: #4ade80;
        }
        
        /* Metrics Intro & Appendix */
        .metrics-intro {
            background: linear-gradient(135deg, #0f3460 0%, #1a1a3e 100%);
            border: 1px solid #2a4a6f;
            border-radius: 12px;
            padding: 20px 25px;
            margin-bottom: 20px;
        }
        .metrics-intro h3 {
            color: #4ade80;
            margin-bottom: 12px;
            font-size: 1.1rem;
        }
        .metrics-intro p {
            color: #ccc;
            line-height: 1.6;
            font-size: 0.9rem;
        }
        .metrics-intro .highlight {
            color: #fbbf24;
            font-weight: 600;
        }
        .metrics-intro .quote {
            border-left: 3px solid #4ade80;
            padding-left: 15px;
            margin: 15px 0;
            font-style: italic;
            color: #aaa;
        }
        .metrics-intro .quote .author {
            color: #888;
            font-style: normal;
            font-size: 0.85rem;
            margin-top: 5px;
        }
        
        .metrics-appendix {
            background: #0a1628;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 30px;
            margin-top: 30px;
        }
        .metrics-appendix h2 {
            color: #4ade80;
            margin-bottom: 25px;
            font-size: 1.4rem;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }
        .metrics-appendix h3 {
            color: #60a5fa;
            margin: 25px 0 15px 0;
            font-size: 1.1rem;
        }
        .metrics-appendix h4 {
            color: #fbbf24;
            margin: 20px 0 10px 0;
            font-size: 1rem;
        }
        .metrics-appendix p {
            color: #bbb;
            line-height: 1.7;
            margin-bottom: 12px;
            font-size: 0.9rem;
        }
        .metrics-appendix .formula-box {
            background: #0f1a2a;
            border: 1px solid #2a4a6f;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            overflow-x: auto;
        }
        .metrics-appendix .formula-box .MathJax {
            font-size: 1.1rem !important;
        }
        .metrics-appendix ul {
            margin: 10px 0 10px 25px;
            color: #aaa;
        }
        .metrics-appendix li {
            margin: 8px 0;
            line-height: 1.5;
        }
        .metrics-appendix .insight {
            background: linear-gradient(135deg, #1e3a5f 0%, #0f3460 100%);
            border-left: 4px solid #4ade80;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }
        .metrics-appendix .insight p {
            color: #ccc;
            margin: 0;
        }
        .metrics-appendix code {
            background: #1e3a5f;
            padding: 2px 6px;
            border-radius: 4px;
            color: #4ade80;
            font-family: monospace;
        }
        
        /* Visualize Tab Styles */
        .viz-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }
        .viz-container h3 {
            color: #4ade80;
            margin-bottom: 10px;
        }
        .viz-description {
            color: #aaa;
            margin-bottom: 20px;
            font-size: 0.95rem;
        }
        .viz-controls {
            display: flex;
            gap: 15px;
            align-items: center;
            margin-bottom: 15px;
        }
        .viz-search {
            position: relative;
            flex: 1;
            max-width: 300px;
        }
        .viz-search input {
            width: 100%;
            padding: 10px 15px;
            border: 1px solid #333;
            border-radius: 8px;
            background: #1a1a2e;
            color: white;
            font-size: 0.95rem;
        }
        .viz-search input:focus {
            outline: none;
            border-color: #4ade80;
        }
        .viz-search-dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 100;
            display: none;
        }
        .viz-search-dropdown.active {
            display: block;
        }
        .viz-search-item {
            padding: 10px 15px;
            cursor: pointer;
            border-bottom: 1px solid #333;
        }
        .viz-search-item:hover {
            background: #2a2a4e;
        }
        .viz-search-item:last-child {
            border-bottom: none;
        }
        .viz-reset-btn {
            padding: 10px 20px;
            background: #333;
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .viz-reset-btn:hover {
            background: #444;
        }
        .viz-added-players {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            margin-bottom: 20px;
            min-height: 40px;
        }
        .viz-added-label {
            color: #888;
            font-size: 0.9rem;
        }
        .viz-added-tag {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: #ff9800;
            color: #000;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .viz-added-tag .viz-remove {
            cursor: pointer;
            font-weight: bold;
            opacity: 0.7;
        }
        .viz-added-tag .viz-remove:hover {
            opacity: 1;
        }
        .viz-chart-container {
            background: #1a1a2e;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
        }
        .viz-legend {
            display: flex;
            gap: 25px;
            justify-content: center;
        }
        .viz-legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #aaa;
            font-size: 0.9rem;
        }
        .viz-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .viz-dot-fixed {
            background: #3b82f6;
        }
        .viz-dot-added {
            background: #ff9800;
        }
        
        /* Custom Tooltip */
        .viz-custom-tooltip {
            position: absolute;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 0;
            pointer-events: none;
            z-index: 1000;
            min-width: 180px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            opacity: 0;
            transition: opacity 0.15s;
        }
        .viz-tt-header {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 12px;
            border-bottom: 3px solid #4ade80;
            background: #0d0d1a;
            border-radius: 10px 10px 0 0;
        }
        .viz-tt-header img {
            width: 60px;
            height: 44px;
            object-fit: cover;
            border-radius: 6px;
            margin-bottom: 6px;
        }
        .viz-tt-name {
            font-weight: 700;
            color: #fff;
            font-size: 0.95rem;
        }
        .viz-tt-team {
            font-size: 0.8rem;
            font-weight: 600;
        }
        .viz-tt-stats {
            padding: 10px 12px;
        }
        .viz-tt-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            color: #ccc;
            font-size: 0.85rem;
        }
        .viz-tt-row strong {
            color: #fff;
            margin: 0 8px;
        }
        .viz-tt-rank {
            background: #333;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            color: #4ade80;
        }
        .viz-tt-sub {
            border-top: 1px solid #333;
            margin-top: 6px;
            padding-top: 8px;
            font-size: 0.8rem;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏀 NBA Player Statistics</h1>
        <div class="subtitle">2025-26 Season • Advanced Analytics Dashboard</div>
    </div>
    
    <div class="main-container">
        <!-- Tab Navigation -->
        <div class="tab-nav">
            <button class="tab-btn active" data-tab="stats">📊 Player Stats</button>
            <button class="tab-btn" data-tab="custom">⚡ Custom Metrics</button>
            <button class="tab-btn" data-tab="achievements">🏆 Achievements</button>
            <button class="tab-btn" data-tab="visualize">📈 Visualize</button>
        </div>
        
        <!-- STATS TAB -->
        <div id="tab-stats" class="tab-content active">
            <div class="control-panel">
                <div class="control-row">
                    <div class="control-group name-search">
                        <label>Search Player</label>
                        <input type="text" id="name-search" placeholder="Name (e.g., Jokic, Luka)">
                    </div>
                    <div class="control-group">
                        <label>Team</label>
                        <select id="team-filter">
                            <option value="">All Teams</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Min GP</label>
                        <input type="number" id="min-gp" value="10" min="1">
                    </div>
                    <div class="control-group">
                        <label>Show</label>
                        <select id="show-count">
                            <option value="25">25 players</option>
                            <option value="50" selected>50 players</option>
                            <option value="100">100 players</option>
                            <option value="200">200 players</option>
                            <option value="all">All players</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Sort By</label>
                        <select id="sort-by">
                            <option value="ppg">PPG</option>
                            <option value="rpg">RPG</option>
                            <option value="apg">APG</option>
                            <option value="spg">SPG</option>
                            <option value="bpg">BPG</option>
                            <option value="stocks_pg">Stocks</option>
                            <option value="mpg">MPG</option>
                            <option value="ts_pct">TS%</option>
                            <option value="net_ipm">Net IPM</option>
                            <option value="ethical_avg">Ethical Hoops</option>
                        </select>
                    </div>
                    <div class="quick-actions">
                        <div class="rank-toggle">
                            <label class="toggle-label">
                                <input type="radio" name="stats-rank-mode" value="none" checked onchange="applyFilters()">
                                <span>Values</span>
                            </label>
                            <label class="toggle-label">
                                <input type="radio" name="stats-rank-mode" value="list" onchange="applyFilters()">
                                <span>Rank (List)</span>
                            </label>
                            <label class="toggle-label">
                                <input type="radio" name="stats-rank-mode" value="league" onchange="applyFilters()">
                                <span>Rank (League)</span>
                            </label>
                        </div>
                        <button class="action-btn secondary" onclick="resetFilters()">Reset</button>
                        <button class="action-btn" onclick="applyFilters()">Apply Filters</button>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>Stat Filters (min-max)</label>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <span style="color: #888; font-size: 0.8rem;">PPG:</span>
                                <input type="number" id="ppg-min" placeholder="min" style="width: 75px;">
                                <span style="color: #555;">-</span>
                                <input type="number" id="ppg-max" placeholder="max" style="width: 75px;">
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <span style="color: #888; font-size: 0.8rem;">APG:</span>
                                <input type="number" id="apg-min" placeholder="min" style="width: 75px;">
                                <span style="color: #555;">-</span>
                                <input type="number" id="apg-max" placeholder="max" style="width: 75px;">
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <span style="color: #888; font-size: 0.8rem;">RPG:</span>
                                <input type="number" id="rpg-min" placeholder="min" style="width: 75px;">
                                <span style="color: #555;">-</span>
                                <input type="number" id="rpg-max" placeholder="max" style="width: 75px;">
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <span style="color: #888; font-size: 0.8rem;">BPG:</span>
                                <input type="number" id="bpg-min" placeholder="min" style="width: 75px;">
                                <span style="color: #555;">-</span>
                                <input type="number" id="bpg-max" placeholder="max" style="width: 75px;">
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <span style="color: #888; font-size: 0.8rem;">SPG:</span>
                                <input type="number" id="spg-min" placeholder="min" style="width: 75px;">
                                <span style="color: #555;">-</span>
                                <input type="number" id="spg-max" placeholder="max" style="width: 75px;">
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <span style="color: #888; font-size: 0.8rem;">Stocks:</span>
                                <input type="number" id="stocks-min" placeholder="min" style="width: 75px;">
                                <span style="color: #555;">-</span>
                                <input type="number" id="stocks-max" placeholder="max" style="width: 75px;">
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>Presets</label>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                            <button class="preset-btn" onclick="applyPreset('scorers')">🔥 Scorers (25+ PPG)</button>
                            <button class="preset-btn" onclick="applyPreset('playmakers')">🎯 Playmakers (7+ APG)</button>
                            <button class="preset-btn" onclick="applyPreset('defenders')">🛡️ Rim Protectors (2+ BPG)</button>
                            <button class="preset-btn" onclick="applyPreset('stocks')">🔒 Stocks Leaders (3+)</button>
                            <button class="preset-btn" onclick="applyPreset('efficient')">📈 Efficient (60+ TS%)</button>
                            <button class="preset-btn" onclick="applyPreset('allround')">⭐ All-Around (15/5/5)</button>
                        </div>
                    </div>
                </div>
                
                <div id="active-filters" class="filter-pills"></div>
            </div>
            
            <div class="stats-summary">
                <div class="summary-card">
                    <div class="summary-value" id="summary-shown">0</div>
                    <div class="summary-label">Players Shown</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value" id="summary-avg-ppg">0</div>
                    <div class="summary-label">Avg PPG</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value" id="summary-avg-ts">0%</div>
                    <div class="summary-label">Avg TS%</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value" id="summary-total-td">0</div>
                    <div class="summary-label">Triple-Doubles</div>
                </div>
            </div>
            
            <div class="table-container">
                <div class="table-scroll">
                    <table class="stats-table" id="stats-table">
                        <thead>
                            <tr>
                                <th class="col-rank" data-sort="rank">#</th>
                                <th class="col-player" data-sort="name">Player</th>
                                <th class="col-team" data-sort="team">Team</th>
                                <th class="col-gp" data-sort="gp">GP</th>
                                <th class="col-stat" data-sort="mpg">MPG</th>
                                <th class="col-stat" data-sort="ppg">PPG</th>
                                <th class="col-stat" data-sort="rpg">RPG</th>
                                <th class="col-stat" data-sort="apg">APG</th>
                                <th class="col-stat" data-sort="spg">SPG</th>
                                <th class="col-stat" data-sort="bpg">BPG</th>
                                <th class="col-stat" data-sort="stocks_pg" title="Steals + Blocks">STK</th>
                                <th class="col-pct" data-sort="fg_pct">FG%</th>
                                <th class="col-pct" data-sort="fg3_pct">3P%</th>
                                <th class="col-pct" data-sort="ft_pct">FT%</th>
                                <th class="col-pct" data-sort="ts_pct">TS%</th>
                                <th class="col-stat" data-sort="topg">TOV</th>
                                <th class="col-stat" data-sort="plus_minus_pg">+/-</th>
                            </tr>
                        </thead>
                        <tbody id="stats-tbody"></tbody>
                    </table>
                </div>
                <div class="pagination">
                    <div class="pagination-info" id="pagination-info">Showing 0 of 0 players</div>
                    <div class="pagination-controls" id="pagination-controls"></div>
                </div>
            </div>
        </div>
        
        <!-- CUSTOM METRICS TAB -->
        <div id="tab-custom" class="tab-content">
            <div class="metrics-intro">
                <h3>⚡ Beyond the Box Score: Novel Basketball Analytics</h3>
                <p>
                    Traditional stats tell you <span class="highlight">what</span> happened. These metrics try to tell you <span class="highlight">how</span> it happened 
                    and <span class="highlight">how reliably</span> it will happen again. We measure player involvement intensity, 
                    reward clean play over foul-hunting, and use Sortino-style risk adjustment to penalize only downside variance.
                </p>
                <div class="quote">
                    "We are playing ethical hoops. We are not flopping... We just want to play the right way."
                    <div class="author">— Jarrett Allen, Cleveland Cavaliers (2024)</div>
                </div>
                <p>
                    Inspired by Allen's philosophy, the <span class="highlight">Ethical Hoops</span> metric penalizes free throw attempts 
                    (proxy for foul-baiting) while rewarding blocks, steals, and offensive rebounds. Technical and flagrant fouls 
                    carry a <span class="highlight">per-game penalty</span> that dilutes with clean play — redemption is possible.
                    Scroll down to the <span class="highlight">Appendix</span> for full methodology and formulas.
                </p>
            </div>
            
            <div class="control-panel">
                <div class="control-row">
                    <div class="control-group name-search">
                        <label>Search Player</label>
                        <input type="text" id="custom-name-search" placeholder="Name">
                    </div>
                    <div class="control-group">
                        <label>Min GP</label>
                        <input type="number" id="custom-min-gp" value="10" min="1">
                    </div>
                    <div class="control-group">
                        <label>Min MPG</label>
                        <input type="number" id="custom-min-mpg" value="15" min="0" step="1">
                    </div>
                    <div class="control-group">
                        <label>Sort By</label>
                        <select id="custom-sort-by">
                            <option value="net_ipm">Net IPM</option>
                            <option value="any_ipm">Any IPM</option>
                            <option value="ethical_avg">Ethical Hoops</option>
                            <option value="ethical_per_min">Ethical/Min</option>
                            <option value="pts_risk_adj">Risk-Adj PTS</option>
                            <option value="reb_risk_adj">Risk-Adj REB</option>
                            <option value="ast_risk_adj">Risk-Adj AST</option>
                            <option value="mpg">MPG</option>
                            <option value="gp">GP</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Show</label>
                        <select id="custom-show-count">
                            <option value="25">25</option>
                            <option value="50" selected>50</option>
                            <option value="100">100</option>
                            <option value="all">All</option>
                        </select>
                    </div>
                    <div class="quick-actions">
                        <div class="rank-toggle">
                            <label class="toggle-label">
                                <input type="radio" name="custom-rank-mode" value="none" checked onchange="applyCustomFilters(false)">
                                <span>Values</span>
                            </label>
                            <label class="toggle-label">
                                <input type="radio" name="custom-rank-mode" value="list" onchange="applyCustomFilters(false)">
                                <span>Rank (List)</span>
                            </label>
                            <label class="toggle-label">
                                <input type="radio" name="custom-rank-mode" value="league" onchange="applyCustomFilters(false)">
                                <span>Rank (League)</span>
                            </label>
                        </div>
                        <button class="action-btn" onclick="applyCustomFilters(true)">Apply</button>
                    </div>
                </div>
            </div>
            
            <div class="table-container">
                <div class="table-scroll">
                    <table class="stats-table" id="custom-table">
                        <thead>
                            <tr>
                                <th class="col-rank">#</th>
                                <th class="col-player" data-sort="name">Player</th>
                                <th class="col-team" data-sort="team">Team</th>
                                <th class="col-gp" data-sort="gp">GP</th>
                                <th class="col-stat" data-sort="mpg">MPG</th>
                                <th class="col-stat" data-sort="net_ipm" title="Involvement Per Minute (Adjusted)">Net IPM</th>
                                <th class="col-stat" data-sort="any_ipm" title="Any IPM (Adjusted)">Any IPM</th>
                                <th class="col-stat" data-sort="ethical_avg" title="Ethical Hoops Score">Ethical</th>
                                <th class="col-stat" data-sort="ethical_per_min" title="Ethical per minute">Eth/Min</th>
                                <th class="col-stat" data-sort="pts_risk_adj" title="Risk-adjusted points">R-PTS</th>
                                <th class="col-stat" data-sort="reb_risk_adj" title="Risk-adjusted rebounds">R-REB</th>
                                <th class="col-stat" data-sort="ast_risk_adj" title="Risk-adjusted assists">R-AST</th>
                            </tr>
                        </thead>
                        <tbody id="custom-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <div class="metrics-appendix">
                <h2>📐 Appendix: Methodology & Formulas</h2>
                
                <h3>1. Involvement Per Minute (IPM)</h3>
                <p>
                    IPM measures how frequently a player directly impacts the game — every touch, every action, 
                    every mistake — normalized by playing time. It combines traditional box score stats with 
                    Second Spectrum tracking data (touches, deflections, screens, etc.) for a fuller picture.
                </p>
                
                <h4>Box Score Component</h4>
                <p>We track all involvements with different weights:</p>
                <div class="formula-box">
                    $$\\text{FG}_{\\text{miss}} = \\text{FGA} - \\text{FGM}$$
                    $$\\text{FT}_{\\text{miss}} = \\text{FTA} - \\text{FTM}$$
                </div>
                <div class="formula-box">
                    $$\\text{Any IPM}_{\\text{box}} = \\frac{0.5 \\cdot \\text{PTS} + 0.5 \\cdot \\text{FG}_{\\text{miss}} + 0.25 \\cdot \\text{FT}_{\\text{miss}} + \\text{REB} + \\text{AST} + \\text{STL} + \\text{BLK} + \\text{TOV} + 0.5 \\cdot \\text{PF}}{\\text{MIN}}$$
                </div>
                <div class="formula-box">
                    $$\\text{Net IPM}_{\\text{box}} = \\frac{0.5 \\cdot \\text{PTS} - 0.5 \\cdot \\text{FG}_{\\text{miss}} - 0.25 \\cdot \\text{FT}_{\\text{miss}} + \\text{REB} + \\text{AST} + \\text{STL} + \\text{BLK} - \\text{TOV} - 0.5 \\cdot \\text{PF}}{\\text{MIN}}$$
                </div>
                <p>
                    <strong>Any IPM</strong> counts everything — even mistakes like turnovers, fouls, and missed shots add to your 
                    "involvement" because you're still touching the ball and affecting the game. <strong>Net IPM</strong> 
                    flips all the bad stuff to negatives: missed shots, turnovers, and fouls all hurt you. It's a transparent 
                    alternative to black-box metrics like PER, LEBRON, or EPM — just add up the good, subtract the bad.
                </p>
                <ul>
                    <li><code>PTS × 0.5</code>: Points (halved to avoid double-counting with made shots)</li>
                    <li><code>FG_miss × ±0.5</code>: +0.5 for Any (still involvement), -0.5 for Net (wasted possession)</li>
                    <li><code>FT_miss × ±0.25</code>: +0.25 for Any, -0.25 for Net</li>
                    <li><code>REB, AST, STL, BLK × 1.0</code>: Full credit for these actions</li>
                    <li><code>TOV × ±1.0</code>: +1 for Any (still involvement), -1 for Net (costly mistake)</li>
                    <li><code>PF × ±0.5</code>: +0.5 for Any, -0.5 for Net</li>
                </ul>
                
                <h4>Tracking Component (Second Spectrum Data)</h4>
                <p>
                    The box score misses a lot. Screen assists, deflections, loose balls — these are invisible in 
                    traditional stats but crucial to winning basketball. We add tracking data to capture this:
                </p>
                <div class="formula-box">
                    $$\\text{IPM}_{\\text{tracking}} = \\frac{0.05 \\cdot \\text{TOUCHES} + 0.5 \\cdot \\text{DEFLECTIONS} + 0.1 \\cdot \\text{CONTESTED SHOTS}}{\\text{MPG}}$$
                    $$+ \\frac{0.5 \\cdot \\text{SCREEN AST} + 0.5 \\cdot \\text{LOOSE BALLS} + 0.5 \\cdot \\text{SECONDARY AST}}{\\text{MPG}}$$
                </div>
                <ul>
                    <li><code>TOUCHES × 0.05</code>: Every ball touch counts, but at low weight (~3 contribution for avg starter)</li>
                    <li><code>DEFLECTIONS × 0.5</code>: Active hands on defense</li>
                    <li><code>CONTESTED_SHOTS × 0.1</code>: Defensive effort</li>
                    <li><code>SCREEN_ASSISTS × 0.5</code>: Off-ball work that creates shots</li>
                    <li><code>LOOSE_BALLS × 0.5</code>: Hustle plays</li>
                    <li><code>SECONDARY_AST × 0.5</code>: Hockey assists (the pass before the assist)</li>
                </ul>
                <p>Calibrated so average top-100 player gets ~6 per game from tracking (~3 from touches, ~3 from hustle).</p>
                
                <h4>Final IPM</h4>
                <div class="formula-box">
                    $$\\text{IPM}_{\\text{final}} = (\\text{IPM}_{\\text{box}} + \\text{IPM}_{\\text{tracking}}) \\times \\text{scale}$$
                </div>
                
                <div class="insight">
                    <p><strong>The Gap Matters:</strong> A big gap between Any IPM and Net IPM reveals inefficiency. 
                    High Any + Low Net = ball-dominant but wasteful. High Any + High Net = true star.</p>
                </div>
                
                <h4>Minutes Adjustment (The Bench Player Problem)</h4>
                <p>
                    Raw IPM has a flaw: bench players with tiny sample sizes often top the leaderboards. 
                    A guy who plays 6 minutes and goes off looks like a god, while Jokić at 35 MPG with 
                    steady production looks pedestrian. We fix this with logarithmic scaling:
                </p>
                <div class="formula-box">
                    $$\\text{scale} = \\left( \\frac{\\ln(1 + \\text{MPG})}{\\ln(1 + \\text{MPG}_{\\max})} \\right)^p$$
                </div>
                <p>Where <code>p = 1.5</code> is the harshness parameter and <code>MPG_max</code> is the league leader in minutes per game. This creates a smooth penalty curve:</p>
                <ul>
                    <li>35 MPG player: scale ≈ 0.97 (nearly full credit)</li>
                    <li>20 MPG player: scale ≈ 0.75 (moderate penalty)</li>
                    <li>6 MPG player: scale ≈ 0.42 (heavy penalty)</li>
                </ul>
                <div class="insight">
                    <p><strong>Why logarithmic?</strong> Linear scaling would be too harsh on rotation players. 
                    Log scaling recognizes that the difference between 30 and 35 MPG is less meaningful than 
                    the difference between 5 and 10 MPG.</p>
                </div>
                
                <h3>2. Ethical Hoops Score</h3>
                <p>
                    Named after Jarrett Allen's philosophy, this metric rewards players who score efficiently 
                    through real basketball plays rather than hunting for fouls and free throws. It combines 
                    box score stats with tracking data to capture the full picture of "playing the right way."
                </p>
                
                <h4>Box Score Component</h4>
                <div class="formula-box">
                    $$\\text{Ethical}_{\\text{box}} = 1.0 \\cdot \\text{PTS} - 0.5 \\cdot \\text{FTM} - 1.5 \\cdot \\text{FTA}$$
                    $$+ 0.9 \\cdot \\text{AST} + 0.9 \\cdot \\text{OREB} + 0.7 \\cdot \\text{DREB}$$
                    $$+ 1.5 \\cdot \\text{BLK} + 1.5 \\cdot \\text{STL} - 1.2 \\cdot \\text{PF}$$
                </div>
                <p>Breakdown of box score weights:</p>
                <ul>
                    <li><code>PTS × 1.0</code>: Full credit for points scored</li>
                    <li><code>FTM × -0.5</code>: Made free throws still required a whistle</li>
                    <li><code>FTA × -1.5</code>: Attempting free throws = hunting fouls (harsh penalty)</li>
                    <li><code>AST × 0.9</code>: Team play bonus (moderated to prevent point guard dominance)</li>
                    <li><code>OREB × 0.9</code>: Hustle plays</li>
                    <li><code>DREB × 0.7</code>: Expected, less credit than offensive boards</li>
                    <li><code>BLK × 1.5</code>: Rim protection, clean defense</li>
                    <li><code>STL × 1.5</code>: Active hands, not flopping (same as blocks)</li>
                    <li><code>PF × -1.2</code>: Undisciplined play (harsher penalty)</li>
                </ul>
                
                <h4>Tracking Component (Hustle Stats)</h4>
                <p>
                    The box score misses the quintessential "ethical hoops" plays: setting screens, boxing out, 
                    contesting shots. We add tracking data to reward the dirty work:
                </p>
                <div class="formula-box">
                    $$\\text{Ethical}_{\\text{tracking}} = 0.4 \\cdot \\text{DEFLECTIONS} + 0.1 \\cdot \\text{CONTESTED SHOTS}$$
                    $$+ 0.5 \\cdot \\text{SCREEN AST} + 0.4 \\cdot \\text{BOX OUTS} + 1.5 \\cdot \\text{CHARGES DRAWN}$$
                </div>
                <ul>
                    <li><code>DEFLECTIONS × 0.4</code>: Active hands on defense</li>
                    <li><code>CONTESTED_SHOTS × 0.1</code>: Effort defense</li>
                    <li><code>SCREEN_ASSISTS × 0.5</code>: Selfless off-ball work that creates shots for others</li>
                    <li><code>BOX_OUTS × 0.4</code>: Doing the dirty work on the glass</li>
                    <li><code>CHARGES_DRAWN × 1.5</code>: Taking contact (capped at BLK weight — it's rare but valuable)</li>
                </ul>
                <p>Calibrated so average top-100 player gets ~2.2 per game from tracking.</p>
                
                <h4>Final Ethical Hoops</h4>
                <div class="formula-box">
                    $$\\text{Ethical}_{\\text{total}} = \\text{Ethical}_{\\text{box}} + \\text{Ethical}_{\\text{tracking}} - 4 \\times \\text{TECH} - 10 \\times \\text{FLAG}$$
                </div>
                
                <h4>Technical & Flagrant Foul Penalty</h4>
                <p>
                    Technicals and flagrants represent the <em>opposite</em> of ethical basketball — losing your cool, 
                    dangerous plays, disrespecting officials. The penalty is added to the season total, then divided 
                    like any other stat. Clean games dilute the impact, creating a redemption path.
                </p>
                <div class="formula-box">
                    $$\\text{Ethical}_{\\text{avg}} = \\frac{\\text{Ethical}_{\\text{total}}}{\\text{GP}}$$
                    $$\\text{Ethical}_{\\text{per min}} = \\frac{\\text{Ethical}_{\\text{total}}}{\\text{MIN}}$$
                </div>
                <ul>
                    <li><code>TECH × -4</code>: Technical foul penalty (≈ 3 personal fouls worth)</li>
                    <li><code>FLAG × -10</code>: Flagrant foul penalty (≈ 2.5× tech, causes ejections + opponent FTs)</li>
                </ul>
                <div class="insight">
                    <p><strong>Example penalties (25 GP):</strong> Jokić (0T 2F) = -0.80/game. 
                    Gobert (3T 4F) = -2.08/game. Stewart (5T 2F) = -1.82/game. 
                    Meaningful but don't dominate rankings — fouls act as a tiebreaker, not the headline.</p>
                </div>
                
                <p>
                    <strong>Ethical Per Minute (Eth/Min)</strong> = Ethical Total / Total Minutes, 
                    allowing comparison across different roles and playing times.
                </p>
                <div class="insight">
                    <p><strong>Who ranks high?</strong> Efficient mid-range assassins, post players who score without 
                    drawing fouls, rim protectors, and glue guys who set screens and box out. <strong>Who ranks low?</strong> 
                    Foul merchants who live at the line, players who rely on referee charity over skill.</p>
                </div>
                
                <h3>3. Risk-Adjusted Stats (Sortino-Style)</h3>
                <p>
                    A player averaging 25 PPG sounds great — but what if they score 40 one night and 10 the next? 
                    Consistency matters. Unlike standard deviation which penalizes ALL variance, we use 
                    <strong>downside deviation</strong> (Sortino-style) which only penalizes bad games.
                </p>
                <h4>Why Sortino over Sharpe?</h4>
                <p>
                    Standard deviation treats a 45-point explosion the same as a 5-point dud — both are "variance." 
                    But explosions are <em>good</em>! We only want to penalize the downside.
                </p>
                <div class="formula-box">
                    $$\\text{threshold} = \\bar{X} \\text{ (player's mean)}$$
                    $$\\text{Downside Deviation} = \\sqrt{\\frac{1}{n} \\sum_{i=1}^{n} \\left( \\min(X_i - \\text{threshold}, 0) \\right)^2}$$
                    $$\\text{Risk-Adjusted Stat} = \\bar{X} - \\text{Downside Deviation}$$
                </div>
                <p>Example with three players, all averaging 20 PPG:</p>
                <ul>
                    <li><strong>Player A</strong>: [20, 22, 18, 21, 19] → low variance → high R-PTS</li>
                    <li><strong>Player B</strong>: [10, 15, 20, 25, 30] → high downside games → lower R-PTS</li>
                    <li><strong>Player C</strong>: [20, 20, 20, 20, 70] → explosion helps, no downside → very high R-PTS</li>
                </ul>
                <ul>
                    <li><strong>R-PTS</strong>: Risk-adjusted points per game</li>
                    <li><strong>R-REB</strong>: Risk-adjusted rebounds per game</li>
                    <li><strong>R-AST</strong>: Risk-adjusted assists per game</li>
                </ul>
                <div class="insight">
                    <p><strong>Interpretation:</strong> R-PTS tells you what floor you can count on. A player with 
                    R-PTS of 17 means "even on a bad night, they'll probably give you around 17." It rewards 
                    consistency without punishing upside explosions.</p>
                </div>
                
                <h3>4. Stocks (STK)</h3>
                <p>
                    A simple but useful combination stat for defensive playmakers:
                </p>
                <div class="formula-box">
                    $$\\text{Stocks} = \\text{STL} + \\text{BLK}$$
                </div>
                <p>
                    Found on the Player Stats tab. Elite perimeter defenders rack up steals; elite rim protectors 
                    rack up blocks. The rare players who do both (like peak Hakeem, prime AD, or current Wemby) 
                    are defensive unicorns.
                </p>
                
                <h3>Philosophy</h3>
                <p>
                    These metrics share a common philosophy: <em>context matters more than counting</em>. 
                    Raw totals favor high-minute players on bad teams who chuck shots. Per-minute stats 
                    favor low-minute players with small samples. We try to thread the needle — rewarding 
                    genuine impact while adjusting for opportunity and reliability.
                </p>
                <p>
                    None of these are perfect. Basketball is too complex to reduce to a single number. 
                    But they offer a different lens than traditional stats, one that might surface players 
                    the box score undersells and expose players it oversells.
                </p>
            </div>
        </div>
        
        <!-- ACHIEVEMENTS TAB -->
        <div id="tab-achievements" class="tab-content">
            <div class="control-panel">
                <div class="control-row">
                    <div class="control-group name-search">
                        <label>Search Player</label>
                        <input type="text" id="ach-name-search" placeholder="Name">
                    </div>
                    <div class="control-group">
                        <label>Sort By</label>
                        <select id="ach-sort-by">
                            <option value="triple_doubles">Triple-Doubles</option>
                            <option value="double_doubles">Double-Doubles</option>
                            <option value="near_triple_doubles">Near Triple-Doubles</option>
                            <option value="games_30plus">30+ Point Games</option>
                            <option value="games_40plus">40+ Point Games</option>
                            <option value="games_50plus">50+ Point Games</option>
                            <option value="games_20_10">20/10 Games</option>
                            <option value="pts_max">Season High PTS</option>
                            <option value="reb_max">Season High REB</option>
                            <option value="ast_max">Season High AST</option>
                            <option value="blk_max">Season High BLK</option>
                            <option value="stl_max">Season High STL</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Show</label>
                        <select id="ach-show-count">
                            <option value="25">25</option>
                            <option value="50" selected>50</option>
                            <option value="100">100</option>
                        </select>
                    </div>
                    <div class="quick-actions">
                        <div class="rank-toggle">
                            <label class="toggle-label">
                                <input type="radio" name="ach-rank-mode" value="none" checked onchange="applyAchFilters(false)">
                                <span>Values</span>
                            </label>
                            <label class="toggle-label">
                                <input type="radio" name="ach-rank-mode" value="list" onchange="applyAchFilters(false)">
                                <span>Rank (List)</span>
                            </label>
                            <label class="toggle-label">
                                <input type="radio" name="ach-rank-mode" value="league" onchange="applyAchFilters(false)">
                                <span>Rank (League)</span>
                            </label>
                        </div>
                        <button class="action-btn" onclick="applyAchFilters(true)">Apply</button>
                    </div>
                </div>
            </div>
            
            <div class="table-container">
                <div class="table-scroll">
                    <table class="stats-table" id="ach-table">
                        <thead>
                            <tr>
                                <th class="col-rank">#</th>
                                <th class="col-player" data-sort="name">Player</th>
                                <th class="col-team" data-sort="team">Team</th>
                                <th class="col-gp" data-sort="gp">GP</th>
                                <th class="col-stat" data-sort="triple_doubles" title="Triple-Doubles">TD</th>
                                <th class="col-stat" data-sort="double_doubles" title="Double-Doubles">DD</th>
                                <th class="col-stat" data-sort="near_triple_doubles" title="Near Triple-Doubles">NTD</th>
                                <th class="col-stat" data-sort="games_30plus" title="30+ Point Games">30+</th>
                                <th class="col-stat" data-sort="games_40plus" title="40+ Point Games">40+</th>
                                <th class="col-stat" data-sort="games_50plus" title="50+ Point Games">50+</th>
                                <th class="col-stat" data-sort="games_20_10" title="20-10 Games">20/10</th>
                                <th class="col-stat" data-sort="pts_max" title="Season High Points">PTS↑</th>
                                <th class="col-stat" data-sort="reb_max" title="Season High Rebounds">REB↑</th>
                                <th class="col-stat" data-sort="ast_max" title="Season High Assists">AST↑</th>
                                <th class="col-stat" data-sort="blk_max" title="Season High Blocks">BLK↑</th>
                                <th class="col-stat" data-sort="stl_max" title="Season High Steals">STL↑</th>
                            </tr>
                        </thead>
                        <tbody id="ach-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- VISUALIZE TAB -->
        <div id="tab-visualize" class="tab-content">
            <div class="viz-container">
                <h3>📈 Any IPM vs Ethical Hoops</h3>
                <p class="viz-description">
                    Scatter plot showing player involvement intensity (Any IPM) against ethical play score.
                    Dot colors reflect team colors. Hover for detailed stats with rankings.
                </p>
                
                <div class="viz-controls">
                    <div class="viz-search">
                        <input type="text" id="viz-search-input" placeholder="Search player to add...">
                        <div id="viz-search-results" class="viz-search-dropdown"></div>
                    </div>
                    <button id="viz-reset-btn" class="viz-reset-btn">Reset Added</button>
                </div>
                
                <div class="viz-added-players" id="viz-added-container">
                    <span class="viz-added-label">Added players:</span>
                    <div id="viz-added-list"></div>
                </div>
                
                <div class="viz-chart-container">
                    <canvas id="viz-scatter-chart"></canvas>
                </div>
                
                <div class="viz-legend">
                    <span class="viz-legend-item">Dot color = Team color</span>
                    <span class="viz-legend-item">● Top 10 IPM ∪ Top 10 Ethical (fixed) + Your selections</span>
                </div>
            </div>
        </div>
    </div>
    
    <script>
// =============================================================================
// DATA
// =============================================================================

var allPlayers = ''' + players_json + ''';
var meta = ''' + meta_json + ''';

var filteredPlayers = [];
var currentSort = { key: 'ppg', asc: false };
var customSort = { key: 'net_ipm', asc: false };
var achSort = { key: 'triple_doubles', asc: false };
var currentPage = 1;
var perPage = 50;

// =============================================================================
// RANK COMPUTATION
// =============================================================================

// Rank keys for each tab
var statsRankKeys = ['mpg', 'ppg', 'rpg', 'apg', 'spg', 'bpg', 'stocks_pg', 'fg_pct', 'fg3_pct', 'ft_pct', 'ts_pct', 'topg', 'plus_minus_pg'];
var customRankKeys = ['mpg', 'net_ipm', 'any_ipm', 'ethical_avg', 'ethical_per_min', 'pts_risk_adj', 'reb_risk_adj', 'ast_risk_adj'];
var achRankKeys = ['triple_doubles', 'double_doubles', 'near_triple_doubles', 'games_30plus', 'games_40plus', 'games_50plus', 'games_20_10', 'pts_max', 'reb_max', 'ast_max', 'blk_max', 'stl_max'];

// League-wide ranks (computed once on init)
var leagueRanks = {};

function computeLeagueRanks() {
    var allKeys = statsRankKeys.concat(customRankKeys).concat(achRankKeys);
    leagueRanks = computeRanksForList(allPlayers, allKeys);
    console.log('Computed league ranks for', Object.keys(leagueRanks).length, 'players');
}

function computeRanksForList(players, keys) {
    // Reset ranks
    var ranks = {};
    
    keys.forEach(function(key) {
        // Sort players by this stat (descending, except topg which is better when lower)
        var desc = (key !== 'topg');
        var sorted = players.slice().sort(function(a, b) {
            var valA = a[key] || 0;
            var valB = b[key] || 0;
            return desc ? (valB - valA) : (valA - valB);
        });
        
        // Assign ranks (handle ties)
        var rank = 1;
        var prevVal = null;
        
        sorted.forEach(function(p, idx) {
            var val = p[key] || 0;
            if (prevVal !== null && val !== prevVal) {
                rank = idx + 1;
            }
            
            if (!ranks[p.player_id]) {
                ranks[p.player_id] = {};
            }
            ranks[p.player_id][key] = rank;
            prevVal = val;
        });
    });
    
    return ranks;
}

function getRankFromMap(ranks, playerId, key) {
    if (ranks[playerId] && ranks[playerId][key] !== undefined) {
        return ranks[playerId][key];
    }
    return '-';
}

function formatRank(rank) {
    if (rank === '-') return '-';
    var suffix = 'th';
    if (rank % 100 < 11 || rank % 100 > 13) {
        if (rank % 10 === 1) suffix = 'st';
        else if (rank % 10 === 2) suffix = 'nd';
        else if (rank % 10 === 3) suffix = 'rd';
    }
    if (rank === 1) return '<span class="rank-1">' + rank + suffix + '</span>';
    if (rank === 2) return '<span class="rank-2">' + rank + suffix + '</span>';
    if (rank === 3) return '<span class="rank-3">' + rank + suffix + '</span>';
    if (rank <= 10) return '<span class="rank-top10">' + rank + suffix + '</span>';
    return rank + suffix;
}

// =============================================================================
// INIT
// =============================================================================

function init() {
    console.log('Loaded', allPlayers.length, 'players');
    
    // Calculate stocks_pg for each player
    allPlayers.forEach(function(p) {
        p.stocks_pg = (p.spg || 0) + (p.bpg || 0);
    });
    
    // Compute league-wide ranks once
    computeLeagueRanks();
    
    initTeamFilter();
    applyFilters();
    applyCustomFilters(true);
    applyAchFilters(true);
    
    // Add dropdown change handlers
    document.getElementById('custom-sort-by').addEventListener('change', function() {
        applyCustomFilters(true);
    });
    document.getElementById('ach-sort-by').addEventListener('change', function() {
        applyAchFilters(true);
    });
}

function initTeamFilter() {
    var teams = [...new Set(allPlayers.map(function(p) { return p.team; }))].sort();
    var select = document.getElementById('team-filter');
    teams.forEach(function(team) {
        var opt = document.createElement('option');
        opt.value = team;
        opt.textContent = team;
        select.appendChild(opt);
    });
}

// =============================================================================
// FILTERING
// =============================================================================

function applyFilters() {
    var nameSearch = document.getElementById('name-search').value.toLowerCase().trim();
    var teamFilter = document.getElementById('team-filter').value;
    var minGP = parseInt(document.getElementById('min-gp').value) || 0;
    var showCount = document.getElementById('show-count').value;
    currentSort.key = document.getElementById('sort-by').value;
    
    var ppgMin = parseFloat(document.getElementById('ppg-min').value) || null;
    var ppgMax = parseFloat(document.getElementById('ppg-max').value) || null;
    var apgMin = parseFloat(document.getElementById('apg-min').value) || null;
    var apgMax = parseFloat(document.getElementById('apg-max').value) || null;
    var rpgMin = parseFloat(document.getElementById('rpg-min').value) || null;
    var rpgMax = parseFloat(document.getElementById('rpg-max').value) || null;
    var bpgMin = parseFloat(document.getElementById('bpg-min').value) || null;
    var bpgMax = parseFloat(document.getElementById('bpg-max').value) || null;
    var spgMin = parseFloat(document.getElementById('spg-min').value) || null;
    var spgMax = parseFloat(document.getElementById('spg-max').value) || null;
    var stocksMin = parseFloat(document.getElementById('stocks-min').value) || null;
    var stocksMax = parseFloat(document.getElementById('stocks-max').value) || null;
    
    filteredPlayers = allPlayers.filter(function(p) {
        if (nameSearch) {
            var nameLower = p.name.toLowerCase();
            var nameNorm = nameLower.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            var searchNorm = nameSearch.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            if (!nameNorm.includes(searchNorm) && !nameLower.includes(nameSearch)) return false;
        }
        if (teamFilter && p.team !== teamFilter) return false;
        if (p.gp < minGP) return false;
        if (ppgMin !== null && p.ppg < ppgMin) return false;
        if (ppgMax !== null && p.ppg > ppgMax) return false;
        if (apgMin !== null && p.apg < apgMin) return false;
        if (apgMax !== null && p.apg > apgMax) return false;
        if (rpgMin !== null && p.rpg < rpgMin) return false;
        if (rpgMax !== null && p.rpg > rpgMax) return false;
        if (bpgMin !== null && p.bpg < bpgMin) return false;
        if (bpgMax !== null && p.bpg > bpgMax) return false;
        if (spgMin !== null && p.spg < spgMin) return false;
        if (spgMax !== null && p.spg > spgMax) return false;
        if (stocksMin !== null && p.stocks_pg < stocksMin) return false;
        if (stocksMax !== null && p.stocks_pg > stocksMax) return false;
        return true;
    });
    
    sortPlayers(currentSort.key);
    perPage = showCount === 'all' ? filteredPlayers.length : parseInt(showCount);
    currentPage = 1;
    renderStatsTable();
    updateSummary();
    updateActiveFilters();
}

function sortPlayers(key) {
    filteredPlayers.sort(function(a, b) {
        var valA = a[key] || 0;
        var valB = b[key] || 0;
        if (typeof valA === 'string') {
            return currentSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return currentSort.asc ? valA - valB : valB - valA;
    });
}

function resetFilters() {
    document.getElementById('name-search').value = '';
    document.getElementById('team-filter').value = '';
    document.getElementById('min-gp').value = '10';
    document.getElementById('show-count').value = '50';
    document.getElementById('sort-by').value = 'ppg';
    document.getElementById('ppg-min').value = '';
    document.getElementById('ppg-max').value = '';
    document.getElementById('apg-min').value = '';
    document.getElementById('apg-max').value = '';
    document.getElementById('rpg-min').value = '';
    document.getElementById('rpg-max').value = '';
    document.getElementById('bpg-min').value = '';
    document.getElementById('bpg-max').value = '';
    document.getElementById('spg-min').value = '';
    document.getElementById('spg-max').value = '';
    document.getElementById('stocks-min').value = '';
    document.getElementById('stocks-max').value = '';
    currentSort = { key: 'ppg', asc: false };
    applyFilters();
}

function applyPreset(preset) {
    resetFilters();
    switch (preset) {
        case 'scorers':
            document.getElementById('ppg-min').value = '25';
            document.getElementById('sort-by').value = 'ppg';
            break;
        case 'playmakers':
            document.getElementById('apg-min').value = '7';
            document.getElementById('sort-by').value = 'apg';
            break;
        case 'defenders':
            document.getElementById('bpg-min').value = '2';
            document.getElementById('sort-by').value = 'bpg';
            break;
        case 'efficient':
            document.getElementById('min-gp').value = '15';
            document.getElementById('sort-by').value = 'ts_pct';
            break;
        case 'stocks':
            document.getElementById('stocks-min').value = '3';
            document.getElementById('sort-by').value = 'stocks_pg';
            break;
        case 'allround':
            document.getElementById('ppg-min').value = '15';
            document.getElementById('rpg-min').value = '5';
            document.getElementById('apg-min').value = '5';
            break;
    }
    applyFilters();
}

// =============================================================================
// RENDER STATS TABLE
// =============================================================================

function renderStatsTable() {
    var tbody = document.getElementById('stats-tbody');
    var start = (currentPage - 1) * perPage;
    var end = Math.min(start + perPage, filteredPlayers.length);
    var pageData = filteredPlayers.slice(start, end);
    var rankMode = document.querySelector('input[name="stats-rank-mode"]:checked').value;
    
    if (!pageData.length) {
        tbody.innerHTML = '<tr><td colspan="17" style="color:#888;text-align:center;padding:40px;">No players match filters</td></tr>';
        document.getElementById('pagination-info').textContent = 'Showing 0 of 0 players';
        return;
    }
    
    // Compute ranks based on mode
    var ranks = {};
    if (rankMode === 'list') {
        ranks = computeRanksForList(filteredPlayers, statsRankKeys);
    } else if (rankMode === 'league') {
        ranks = leagueRanks;
    }
    
    var html = '';
    pageData.forEach(function(p, idx) {
        var rank = start + idx + 1;
        html += '<tr>';
        html += '<td class="col-rank">' + rank + '</td>';
        html += '<td class="col-player"><div class="player-cell">';
        html += '<div class="player-headshot"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/' + p.player_id + '.png" onerror="this.src=\\'\\'"></div>';
        html += '<span class="player-name">' + p.name + '</span>';
        html += '</div></td>';
        html += '<td class="col-team"><span class="team-badge">' + p.team + '</span></td>';
        html += '<td class="col-gp">' + p.gp + '</td>';
        
        if (rankMode !== 'none') {
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'mpg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'ppg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'rpg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'apg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'spg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'bpg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'stocks_pg')) + '</td>';
            html += '<td class="col-pct">' + formatRank(getRankFromMap(ranks, p.player_id, 'fg_pct')) + '</td>';
            html += '<td class="col-pct">' + formatRank(getRankFromMap(ranks, p.player_id, 'fg3_pct')) + '</td>';
            html += '<td class="col-pct">' + formatRank(getRankFromMap(ranks, p.player_id, 'ft_pct')) + '</td>';
            html += '<td class="col-pct">' + formatRank(getRankFromMap(ranks, p.player_id, 'ts_pct')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'topg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'plus_minus_pg')) + '</td>';
        } else {
            html += '<td class="col-stat">' + p.mpg.toFixed(1) + '</td>';
            html += '<td class="col-stat stat-highlight">' + p.ppg.toFixed(1) + '</td>';
            html += '<td class="col-stat">' + p.rpg.toFixed(1) + '</td>';
            html += '<td class="col-stat">' + p.apg.toFixed(1) + '</td>';
            html += '<td class="col-stat">' + p.spg.toFixed(1) + '</td>';
            html += '<td class="col-stat">' + p.bpg.toFixed(1) + '</td>';
            html += '<td class="col-stat">' + p.stocks_pg.toFixed(1) + '</td>';
            html += '<td class="col-pct">' + p.fg_pct.toFixed(1) + '</td>';
            html += '<td class="col-pct">' + p.fg3_pct.toFixed(1) + '</td>';
            html += '<td class="col-pct">' + p.ft_pct.toFixed(1) + '</td>';
            html += '<td class="col-pct ' + (p.ts_pct >= 60 ? 'stat-positive' : '') + '">' + p.ts_pct.toFixed(1) + '</td>';
            html += '<td class="col-stat stat-neutral">' + p.topg.toFixed(1) + '</td>';
            html += '<td class="col-stat ' + (p.plus_minus_pg > 0 ? 'stat-positive' : p.plus_minus_pg < 0 ? 'stat-negative' : '') + '">' + (p.plus_minus_pg > 0 ? '+' : '') + p.plus_minus_pg.toFixed(1) + '</td>';
        }
        html += '</tr>';
    });
    
    tbody.innerHTML = html;
    document.getElementById('pagination-info').textContent = 'Showing ' + (start + 1) + '-' + end + ' of ' + filteredPlayers.length + ' players';
    renderPagination();
}

function renderPagination() {
    var totalPages = Math.ceil(filteredPlayers.length / perPage);
    var container = document.getElementById('pagination-controls');
    
    if (totalPages <= 1) { container.innerHTML = ''; return; }
    
    var html = '';
    html += '<button class="page-btn" onclick="goToPage(' + (currentPage - 1) + ')" ' + (currentPage === 1 ? 'disabled' : '') + '>‹</button>';
    for (var i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += '<button class="page-btn ' + (i === currentPage ? 'active' : '') + '" onclick="goToPage(' + i + ')">' + i + '</button>';
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<span style="color:#555;padding:0 5px;">...</span>';
        }
    }
    html += '<button class="page-btn" onclick="goToPage(' + (currentPage + 1) + ')" ' + (currentPage === totalPages ? 'disabled' : '') + '>›</button>';
    container.innerHTML = html;
}

function goToPage(page) {
    var totalPages = Math.ceil(filteredPlayers.length / perPage);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderStatsTable();
}

// =============================================================================
// SUMMARY & ACTIVE FILTERS
// =============================================================================

function updateSummary() {
    document.getElementById('summary-shown').textContent = filteredPlayers.length;
    if (filteredPlayers.length > 0) {
        var avgPPG = filteredPlayers.reduce(function(s, p) { return s + p.ppg; }, 0) / filteredPlayers.length;
        var avgTS = filteredPlayers.reduce(function(s, p) { return s + p.ts_pct; }, 0) / filteredPlayers.length;
        var totalTD = filteredPlayers.reduce(function(s, p) { return s + p.triple_doubles; }, 0);
        document.getElementById('summary-avg-ppg').textContent = avgPPG.toFixed(1);
        document.getElementById('summary-avg-ts').textContent = avgTS.toFixed(1) + '%';
        document.getElementById('summary-total-td').textContent = totalTD;
    }
}

function updateActiveFilters() {
    var pills = [];
    var ppgMin = document.getElementById('ppg-min').value;
    var ppgMax = document.getElementById('ppg-max').value;
    var apgMin = document.getElementById('apg-min').value;
    var apgMax = document.getElementById('apg-max').value;
    var rpgMin = document.getElementById('rpg-min').value;
    var rpgMax = document.getElementById('rpg-max').value;
    var bpgMin = document.getElementById('bpg-min').value;
    var bpgMax = document.getElementById('bpg-max').value;
    var spgMin = document.getElementById('spg-min').value;
    var spgMax = document.getElementById('spg-max').value;
    var stocksMin = document.getElementById('stocks-min').value;
    var stocksMax = document.getElementById('stocks-max').value;
    var team = document.getElementById('team-filter').value;
    var name = document.getElementById('name-search').value;
    
    if (name) pills.push({ label: 'Name: ' + name, id: 'name-search' });
    if (team) pills.push({ label: 'Team: ' + team, id: 'team-filter' });
    if (ppgMin) pills.push({ label: 'PPG ≥ ' + ppgMin, id: 'ppg-min' });
    if (ppgMax) pills.push({ label: 'PPG ≤ ' + ppgMax, id: 'ppg-max' });
    if (apgMin) pills.push({ label: 'APG ≥ ' + apgMin, id: 'apg-min' });
    if (apgMax) pills.push({ label: 'APG ≤ ' + apgMax, id: 'apg-max' });
    if (rpgMin) pills.push({ label: 'RPG ≥ ' + rpgMin, id: 'rpg-min' });
    if (rpgMax) pills.push({ label: 'RPG ≤ ' + rpgMax, id: 'rpg-max' });
    if (bpgMin) pills.push({ label: 'BPG ≥ ' + bpgMin, id: 'bpg-min' });
    if (bpgMax) pills.push({ label: 'BPG ≤ ' + bpgMax, id: 'bpg-max' });
    if (spgMin) pills.push({ label: 'SPG ≥ ' + spgMin, id: 'spg-min' });
    if (spgMax) pills.push({ label: 'SPG ≤ ' + spgMax, id: 'spg-max' });
    if (stocksMin) pills.push({ label: 'Stocks ≥ ' + stocksMin, id: 'stocks-min' });
    if (stocksMax) pills.push({ label: 'Stocks ≤ ' + stocksMax, id: 'stocks-max' });
    
    var container = document.getElementById('active-filters');
    if (!pills.length) { container.innerHTML = ''; return; }
    
    container.innerHTML = pills.map(function(pill) {
        return '<div class="filter-pill">' + pill.label + '<span class="remove" data-id="' + pill.id + '">×</span></div>';
    }).join('');
    
    container.querySelectorAll('.remove').forEach(function(el) {
        el.addEventListener('click', function() {
            var elem = document.getElementById(this.dataset.id);
            if (elem.tagName === 'SELECT') elem.value = '';
            else elem.value = '';
            applyFilters();
        });
    });
}

// =============================================================================
// CUSTOM METRICS TAB
// =============================================================================

function applyCustomFilters(fromDropdown) {
    var nameSearch = document.getElementById('custom-name-search').value.toLowerCase().trim();
    var minGP = parseInt(document.getElementById('custom-min-gp').value) || 0;
    var minMPG = parseFloat(document.getElementById('custom-min-mpg').value) || 0;
    var showCount = document.getElementById('custom-show-count').value;
    
    // Only update sort key from dropdown if called from dropdown change
    if (fromDropdown) {
        customSort.key = document.getElementById('custom-sort-by').value;
        customSort.asc = false;
    }
    
    var filtered = allPlayers.filter(function(p) {
        if (nameSearch) {
            var nameNorm = p.name.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            var searchNorm = nameSearch.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            if (!nameNorm.includes(searchNorm)) return false;
        }
        return p.gp >= minGP && p.mpg >= minMPG;
    });
    
    filtered.sort(function(a, b) {
        var valA = a[customSort.key] || 0;
        var valB = b[customSort.key] || 0;
        if (typeof valA === 'string') {
            return customSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return customSort.asc ? valA - valB : valB - valA;
    });
    
    var limit = showCount === 'all' ? filtered.length : parseInt(showCount);
    filtered = filtered.slice(0, limit);
    
    updateCustomHeaders();
    renderCustomTable(filtered);
}

function updateCustomHeaders() {
    document.querySelectorAll('#custom-table th').forEach(function(h) { h.classList.remove('sorted', 'asc'); });
    var th = document.querySelector('#custom-table th[data-sort="' + customSort.key + '"]');
    if (th) {
        th.classList.add('sorted');
        if (customSort.asc) th.classList.add('asc');
    }
}

function renderCustomTable(players) {
    var tbody = document.getElementById('custom-tbody');
    var rankMode = document.querySelector('input[name="custom-rank-mode"]:checked').value;
    
    if (!players.length) {
        tbody.innerHTML = '<tr><td colspan="12" style="color:#888;text-align:center;padding:40px;">No players</td></tr>';
        return;
    }
    
    // Compute ranks based on mode
    var ranks = {};
    if (rankMode === 'list') {
        ranks = computeRanksForList(players, customRankKeys);
    } else if (rankMode === 'league') {
        ranks = leagueRanks;
    }
    
    var html = '';
    players.forEach(function(p, idx) {
        html += '<tr>';
        html += '<td class="col-rank">' + (idx + 1) + '</td>';
        html += '<td class="col-player"><div class="player-cell">';
        html += '<div class="player-headshot"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/' + p.player_id + '.png" onerror="this.src=\\'\\'"></div>';
        html += '<span class="player-name">' + p.name + '</span></div></td>';
        html += '<td class="col-team"><span class="team-badge">' + p.team + '</span></td>';
        html += '<td class="col-gp">' + p.gp + '</td>';
        
        if (rankMode !== 'none') {
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'mpg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'net_ipm')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'any_ipm')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'ethical_avg')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'ethical_per_min')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'pts_risk_adj')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'reb_risk_adj')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'ast_risk_adj')) + '</td>';
        } else {
            html += '<td class="col-stat">' + p.mpg.toFixed(1) + '</td>';
            html += '<td class="col-stat stat-positive">' + (p.net_ipm || 0).toFixed(3) + '</td>';
            html += '<td class="col-stat">' + (p.any_ipm || 0).toFixed(3) + '</td>';
            // Ethical with foul penalty indicator
            var ethTitle = 'Ethical Hoops Score';
            var ethClass = 'col-stat stat-highlight';
            if ((p.technical_fouls || 0) > 0 || (p.flagrant_fouls || 0) > 0) {
                ethTitle = p.technical_fouls + 'T ' + p.flagrant_fouls + 'F = ' + (p.foul_penalty || 0).toFixed(1) + ' penalty';
                ethClass = 'col-stat stat-highlight foul-penalty';
            }
            html += '<td class="' + ethClass + '" title="' + ethTitle + '">' + (p.ethical_avg || 0).toFixed(1) + '</td>';
            html += '<td class="col-stat">' + (p.ethical_per_min || 0).toFixed(3) + '</td>';
            html += '<td class="col-stat">' + (p.pts_risk_adj || 0).toFixed(1) + '</td>';
            html += '<td class="col-stat">' + (p.reb_risk_adj || 0).toFixed(1) + '</td>';
            html += '<td class="col-stat">' + (p.ast_risk_adj || 0).toFixed(1) + '</td>';
        }
        html += '</tr>';
    });
    tbody.innerHTML = html;
}

// =============================================================================
// ACHIEVEMENTS TAB
// =============================================================================

function applyAchFilters(fromDropdown) {
    var nameSearch = document.getElementById('ach-name-search').value.toLowerCase().trim();
    var showCount = parseInt(document.getElementById('ach-show-count').value);
    
    // Only update sort key from dropdown if called from dropdown change
    if (fromDropdown) {
        achSort.key = document.getElementById('ach-sort-by').value;
        achSort.asc = false;
    }
    
    var filtered = allPlayers.filter(function(p) {
        if (nameSearch) {
            var nameNorm = p.name.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            if (!nameNorm.includes(nameSearch)) return false;
        }
        return p.triple_doubles > 0 || p.double_doubles > 0 || p.near_triple_doubles > 0 || p.games_30plus > 0;
    });
    
    filtered.sort(function(a, b) {
        var valA = a[achSort.key] || 0;
        var valB = b[achSort.key] || 0;
        if (typeof valA === 'string') {
            return achSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return achSort.asc ? valA - valB : valB - valA;
    });
    
    filtered = filtered.slice(0, showCount);
    
    updateAchHeaders();
    renderAchTable(filtered);
}

function updateAchHeaders() {
    document.querySelectorAll('#ach-table th').forEach(function(h) { h.classList.remove('sorted', 'asc'); });
    var th = document.querySelector('#ach-table th[data-sort="' + achSort.key + '"]');
    if (th) {
        th.classList.add('sorted');
        if (achSort.asc) th.classList.add('asc');
    }
}

function renderAchTable(players) {
    var tbody = document.getElementById('ach-tbody');
    var rankMode = document.querySelector('input[name="ach-rank-mode"]:checked').value;
    
    if (!players.length) {
        tbody.innerHTML = '<tr><td colspan="16" style="color:#888;text-align:center;padding:40px;">No players with achievements</td></tr>';
        return;
    }
    
    // Compute ranks based on mode
    var ranks = {};
    if (rankMode === 'list') {
        ranks = computeRanksForList(players, achRankKeys);
    } else if (rankMode === 'league') {
        ranks = leagueRanks;
    }
    
    var html = '';
    players.forEach(function(p, idx) {
        html += '<tr>';
        html += '<td class="col-rank">' + (idx + 1) + '</td>';
        html += '<td class="col-player"><div class="player-cell">';
        html += '<div class="player-headshot"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/' + p.player_id + '.png" onerror="this.src=\\'\\'"></div>';
        html += '<span class="player-name">' + p.name + '</span></div></td>';
        html += '<td class="col-team"><span class="team-badge">' + p.team + '</span></td>';
        html += '<td class="col-gp">' + p.gp + '</td>';
        
        if (rankMode !== 'none') {
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'triple_doubles')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'double_doubles')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'near_triple_doubles')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'games_30plus')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'games_40plus')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'games_50plus')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'games_20_10')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'pts_max')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'reb_max')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'ast_max')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'blk_max')) + '</td>';
            html += '<td class="col-stat">' + formatRank(getRankFromMap(ranks, p.player_id, 'stl_max')) + '</td>';
        } else {
            html += '<td class="col-stat ' + (p.triple_doubles > 0 ? 'stat-highlight' : 'stat-neutral') + '">' + p.triple_doubles + '</td>';
            html += '<td class="col-stat ' + (p.double_doubles > 0 ? 'stat-positive' : 'stat-neutral') + '">' + p.double_doubles + '</td>';
            html += '<td class="col-stat">' + p.near_triple_doubles + '</td>';
            html += '<td class="col-stat ' + (p.games_30plus > 0 ? 'stat-positive' : 'stat-neutral') + '">' + p.games_30plus + '</td>';
            html += '<td class="col-stat ' + (p.games_40plus > 0 ? 'stat-highlight' : 'stat-neutral') + '">' + p.games_40plus + '</td>';
            html += '<td class="col-stat">' + (p.games_50plus || 0) + '</td>';
            html += '<td class="col-stat">' + p.games_20_10 + '</td>';
            html += '<td class="col-stat stat-highlight">' + p.pts_max + '</td>';
            html += '<td class="col-stat">' + p.reb_max + '</td>';
            html += '<td class="col-stat">' + p.ast_max + '</td>';
            html += '<td class="col-stat">' + p.blk_max + '</td>';
            html += '<td class="col-stat">' + p.stl_max + '</td>';
        }
        html += '</tr>';
    });
    tbody.innerHTML = html;
}

// =============================================================================
// EVENT LISTENERS
// =============================================================================

document.querySelectorAll('.tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
        document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
        this.classList.add('active');
        document.getElementById('tab-' + this.dataset.tab).classList.add('active');
    });
});

document.querySelectorAll('#stats-table th[data-sort]').forEach(function(th) {
    th.addEventListener('click', function() {
        var key = this.dataset.sort;
        if (currentSort.key === key) currentSort.asc = !currentSort.asc;
        else { currentSort.key = key; currentSort.asc = false; }
        
        document.querySelectorAll('#stats-table th').forEach(function(h) { h.classList.remove('sorted', 'asc'); });
        this.classList.add('sorted');
        if (currentSort.asc) this.classList.add('asc');
        
        sortPlayers(key);
        currentPage = 1;
        renderStatsTable();
    });
});

document.querySelectorAll('#custom-table th[data-sort]').forEach(function(th) {
    th.addEventListener('click', function() {
        var key = this.dataset.sort;
        if (customSort.key === key) customSort.asc = !customSort.asc;
        else { customSort.key = key; customSort.asc = false; }
        
        // Update dropdown if option exists
        var select = document.getElementById('custom-sort-by');
        if (select.querySelector('option[value="' + key + '"]')) {
            select.value = key;
        }
        applyCustomFilters();
    });
});

document.querySelectorAll('#ach-table th[data-sort]').forEach(function(th) {
    th.addEventListener('click', function() {
        var key = this.dataset.sort;
        if (achSort.key === key) achSort.asc = !achSort.asc;
        else { achSort.key = key; achSort.asc = false; }
        
        // Update dropdown if option exists
        var select = document.getElementById('ach-sort-by');
        if (select.querySelector('option[value="' + key + '"]')) {
            select.value = key;
        }
        applyAchFilters();
    });
});

document.querySelectorAll('input').forEach(function(input) {
    input.addEventListener('keyup', function(e) {
        if (e.key === 'Enter') {
            if (this.closest('#tab-stats')) applyFilters();
            else if (this.closest('#tab-custom')) applyCustomFilters(true);
            else if (this.closest('#tab-achievements')) applyAchFilters(true);
        }
    });
});

// =============================================================================
// VISUALIZE TAB - SCATTER PLOT
// =============================================================================

var vizChart = null;
var vizAddedPlayers = [];
var vizMaxAdded = 10;

// NBA Team Colors (primary)
var teamColors = {
    'ATL': '#E03A3E', 'BOS': '#007A33', 'BKN': '#FFFFFF', 'CHA': '#1D8CAB',
    'CHI': '#CE1141', 'CLE': '#860038', 'DAL': '#00538C', 'DEN': '#FEC524',
    'DET': '#C8102E', 'GSW': '#1D428A', 'HOU': '#CE1141', 'IND': '#FDBB30',
    'LAC': '#C8102E', 'LAL': '#552583', 'MEM': '#5D76A9', 'MIA': '#98002E',
    'MIL': '#00471B', 'MIN': '#236192', 'NOP': '#C8102E', 'NYK': '#F58426',
    'OKC': '#007AC1', 'ORL': '#0077C0', 'PHI': '#006BB6', 'PHX': '#E56020',
    'POR': '#E03A3E', 'SAC': '#5A2D81', 'SAS': '#C4CED4', 'TOR': '#CE1141',
    'UTA': '#4B7AB3', 'WAS': '#E31837'
};

// Pre-compute rankings
var ipmRanks = {};
var ethRanks = {};
(function() {
    var byIPM = [...allPlayers].sort((a, b) => (b.any_ipm || 0) - (a.any_ipm || 0));
    var byEth = [...allPlayers].sort((a, b) => (b.ethical_avg || 0) - (a.ethical_avg || 0));
    byIPM.forEach((p, i) => { ipmRanks[p.player_id] = i + 1; });
    byEth.forEach((p, i) => { ethRanks[p.player_id] = i + 1; });
})();

function getTeamColor(team) {
    return teamColors[team] || '#888888';
}

function getInitials(name) {
    var parts = name.split(' ');
    if (parts.length >= 2) {
        return parts[0][0] + parts[parts.length - 1][0];
    }
    return name.substring(0, 2).toUpperCase();
}

function getTop10Union() {
    // Get top 10 by Any IPM
    var byIPM = [...allPlayers].sort((a, b) => (b.any_ipm || 0) - (a.any_ipm || 0)).slice(0, 10);
    // Get top 10 by Ethical Avg
    var byEth = [...allPlayers].sort((a, b) => (b.ethical_avg || 0) - (a.ethical_avg || 0)).slice(0, 10);
    
    // Union (unique by player_id)
    var union = [...byIPM];
    byEth.forEach(function(p) {
        if (!union.find(u => u.player_id === p.player_id)) {
            union.push(p);
        }
    });
    return union;
}

function buildPointData(players) {
    return players.map(function(p) {
        return {
            x: p.any_ipm || 0,
            y: p.ethical_avg || 0,
            name: p.name,
            team: p.team,
            player_id: p.player_id,
            initials: getInitials(p.name),
            ipm_rank: ipmRanks[p.player_id] || '-',
            eth_rank: ethRanks[p.player_id] || '-',
            ppg: p.ppg || 0,
            rpg: p.rpg || 0,
            apg: p.apg || 0
        };
    });
}

// Chart.js plugin to draw initials on dots
var initialsPlugin = {
    id: 'initialsPlugin',
    afterDatasetsDraw: function(chart) {
        var ctx = chart.ctx;
        chart.data.datasets.forEach(function(dataset, i) {
            var meta = chart.getDatasetMeta(i);
            if (!meta.hidden) {
                meta.data.forEach(function(element, index) {
                    var data = dataset.data[index];
                    if (data && data.initials) {
                        // Get background color for contrast
                        var bgColor = Array.isArray(dataset.backgroundColor) 
                            ? dataset.backgroundColor[index] 
                            : dataset.backgroundColor;
                        var textColor = getContrastColor(bgColor);
                        
                        ctx.save();
                        ctx.font = 'bold 10px Arial';
                        ctx.fillStyle = textColor;
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillText(data.initials, element.x, element.y);
                        ctx.restore();
                    }
                });
            }
        });
    }
};

function getContrastColor(hexColor) {
    // Default to black if no color
    if (!hexColor) return '#000';
    
    // Remove # if present
    var hex = hexColor.replace('#', '');
    
    // Parse RGB
    var r = parseInt(hex.substr(0, 2), 16);
    var g = parseInt(hex.substr(2, 2), 16);
    var b = parseInt(hex.substr(4, 2), 16);
    
    // Calculate luminance
    var luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    
    // Return black for light backgrounds, white for dark
    return luminance > 0.5 ? '#000' : '#fff';
}

function initVizChart() {
    var ctx = document.getElementById('viz-scatter-chart').getContext('2d');
    
    var fixedPlayers = getTop10Union();
    var fixedData = buildPointData(fixedPlayers);
    var fixedColors = fixedPlayers.map(p => getTeamColor(p.team));
    
    vizChart = new Chart(ctx, {
        type: 'scatter',
        plugins: [initialsPlugin],
        data: {
            datasets: [
                {
                    label: 'Top 10 (fixed)',
                    data: fixedData,
                    backgroundColor: fixedColors,
                    borderColor: fixedColors.map(c => c),
                    borderWidth: 2,
                    pointRadius: 14,
                    pointHoverRadius: 17
                },
                {
                    label: 'User added',
                    data: [],
                    backgroundColor: [],
                    borderColor: [],
                    borderWidth: 2,
                    pointRadius: 14,
                    pointHoverRadius: 17
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1.5,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Any IPM (per game)',
                        color: '#aaa',
                        font: { size: 14 }
                    },
                    grid: { color: '#333' },
                    ticks: { color: '#aaa' }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Ethical Hoops (per game)',
                        color: '#aaa',
                        font: { size: 14 }
                    },
                    grid: { color: '#333' },
                    ticks: { color: '#aaa' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: false,
                    external: function(context) {
                        var tooltipEl = document.getElementById('viz-tooltip');
                        if (!tooltipEl) {
                            tooltipEl = document.createElement('div');
                            tooltipEl.id = 'viz-tooltip';
                            tooltipEl.className = 'viz-custom-tooltip';
                            document.body.appendChild(tooltipEl);
                        }
                        
                        var tooltipModel = context.tooltip;
                        if (tooltipModel.opacity === 0) {
                            tooltipEl.style.opacity = 0;
                            return;
                        }
                        
                        if (tooltipModel.dataPoints && tooltipModel.dataPoints.length > 0) {
                            var point = tooltipModel.dataPoints[0].raw;
                            var teamColor = getTeamColor(point.team);
                            
                            var html = '<div class="viz-tt-header" style="border-color:' + teamColor + '">';
                            html += '<img src="https://cdn.nba.com/headshots/nba/latest/1040x760/' + point.player_id + '.png" onerror="this.style.display=\\'none\\'">';
                            html += '<div class="viz-tt-name">' + point.name + '</div>';
                            html += '<div class="viz-tt-team" style="color:' + teamColor + '">' + point.team + '</div>';
                            html += '</div>';
                            html += '<div class="viz-tt-stats">';
                            html += '<div class="viz-tt-row"><span>Any IPM</span><strong>' + point.x.toFixed(3) + '</strong><span class="viz-tt-rank">#' + point.ipm_rank + '</span></div>';
                            html += '<div class="viz-tt-row"><span>Ethical</span><strong>' + point.y.toFixed(1) + '</strong><span class="viz-tt-rank">#' + point.eth_rank + '</span></div>';
                            html += '<div class="viz-tt-row viz-tt-sub"><span>PPG: ' + point.ppg.toFixed(1) + ' / RPG: ' + point.rpg.toFixed(1) + ' / APG: ' + point.apg.toFixed(1) + '</span></div>';
                            html += '</div>';
                            
                            tooltipEl.innerHTML = html;
                        }
                        
                        var position = context.chart.canvas.getBoundingClientRect();
                        tooltipEl.style.opacity = 1;
                        tooltipEl.style.left = position.left + window.pageXOffset + tooltipModel.caretX + 15 + 'px';
                        tooltipEl.style.top = position.top + window.pageYOffset + tooltipModel.caretY - 30 + 'px';
                    }
                }
            }
        }
    });
}

function updateVizChart() {
    if (!vizChart) return;
    
    var addedData = buildPointData(vizAddedPlayers);
    var addedColors = vizAddedPlayers.map(p => getTeamColor(p.team));
    
    vizChart.data.datasets[1].data = addedData;
    vizChart.data.datasets[1].backgroundColor = addedColors;
    vizChart.data.datasets[1].borderColor = addedColors;
    vizChart.update();
}

function renderVizAddedTags() {
    var container = document.getElementById('viz-added-list');
    container.innerHTML = '';
    
    vizAddedPlayers.forEach(function(p) {
        var tag = document.createElement('span');
        tag.className = 'viz-added-tag';
        tag.innerHTML = p.name + ' <span class="viz-remove" data-id="' + p.player_id + '">✕</span>';
        container.appendChild(tag);
    });
    
    // Attach remove handlers
    container.querySelectorAll('.viz-remove').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var id = parseInt(this.dataset.id);
            vizAddedPlayers = vizAddedPlayers.filter(p => p.player_id !== id);
            renderVizAddedTags();
            updateVizChart();
        });
    });
}

function addPlayerToViz(player) {
    // Check if already in fixed top 10
    var fixedPlayers = getTop10Union();
    if (fixedPlayers.find(p => p.player_id === player.player_id)) {
        return; // Already shown as fixed
    }
    
    // Check if already added
    if (vizAddedPlayers.find(p => p.player_id === player.player_id)) {
        return; // Already added
    }
    
    // Check max limit
    if (vizAddedPlayers.length >= vizMaxAdded) {
        alert('Maximum ' + vizMaxAdded + ' players can be added');
        return;
    }
    
    vizAddedPlayers.push(player);
    renderVizAddedTags();
    updateVizChart();
}

// Search functionality
var vizSearchInput = document.getElementById('viz-search-input');
var vizSearchResults = document.getElementById('viz-search-results');

vizSearchInput.addEventListener('input', function() {
    var query = this.value.toLowerCase().trim();
    
    if (query.length < 2) {
        vizSearchResults.classList.remove('active');
        return;
    }
    
    var matches = allPlayers.filter(function(p) {
        return p.name.toLowerCase().includes(query);
    }).slice(0, 8);
    
    if (matches.length === 0) {
        vizSearchResults.classList.remove('active');
        return;
    }
    
    vizSearchResults.innerHTML = '';
    matches.forEach(function(p) {
        var div = document.createElement('div');
        div.className = 'viz-search-item';
        div.textContent = p.name + ' (' + p.team + ')';
        div.addEventListener('click', function() {
            addPlayerToViz(p);
            vizSearchInput.value = '';
            vizSearchResults.classList.remove('active');
        });
        vizSearchResults.appendChild(div);
    });
    vizSearchResults.classList.add('active');
});

// Hide dropdown when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.viz-search')) {
        vizSearchResults.classList.remove('active');
    }
});

// Reset button
document.getElementById('viz-reset-btn').addEventListener('click', function() {
    vizAddedPlayers = [];
    renderVizAddedTags();
    updateVizChart();
});

// Initialize chart when Visualize tab is shown
document.querySelectorAll('.tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        if (this.dataset.tab === 'visualize' && !vizChart) {
            setTimeout(initVizChart, 100);
        }
    });
});

// Init on load
init();
    </script>
</body>
</html>'''
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Saved {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    generate_html()
