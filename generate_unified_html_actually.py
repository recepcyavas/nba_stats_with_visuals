"""
================================================================================
GENERATE UNIFIED HTML (actually correct)
================================================================================

PURPOSE:
    Generates single HTML dashboard with 3 tabs:
    - Tab 1: Point Differential (main dashboard)
    - Tab 2: Clutch Index
    - Tab 3: Momentum Analysis

INPUT:
    unified_display.json - Combined data from compute_unified.py

OUTPUT:
    nba_unified_dashboard.html

DATA ACCESS MAPPING:
    - Display data: data["OKC"], data["_clusters"], etc. (same as before)
    - Clutch index: data["_clutch_index"]["games"], data["_clutch_index"]["team_summary"]
    - Momentum: data["_momentum"]["teams"], data["_momentum"]["league"]

================================================================================
"""

import json

INPUT_PATH = "unified_display.json"
OUTPUT_PATH = "nba_unified_dashboard.html"


def generate_html():
    print("=" * 60)
    print("GENERATE UNIFIED HTML")
    print("=" * 60)
    
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract team names (non-underscore keys)
    team_names = [t for t in data.keys() if not t.startswith("_")]
    
    # Stats
    clutch_games = len(data.get("_clutch_index", {}).get("games", {}))
    momentum_teams = len(data.get("_momentum", {}).get("teams", {}))
    
    print(f"Loaded {len(team_names)} teams")
    print(f"Clutch index: {clutch_games} games")
    print(f"Momentum: {momentum_teams} teams")
    
    data_json = json.dumps(data)
    team_names_json = json.dumps(team_names)
    
    # Get the original HTML content for Tab 1 from the existing generate_html.py style
    # This is a full replacement with all sections
    
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>NBA Unified Dashboard</title>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false}
            ]
        });"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #1a1a2e; color: white; }
        
        /* Tab Navigation */
        .tab-nav {
            display: flex;
            background: #0f0f1a;
            border-bottom: 2px solid #333;
            padding: 0 20px;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        .tab-btn {
            padding: 15px 30px;
            background: none;
            border: none;
            color: #888;
            font-size: 1rem;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }
        .tab-btn:hover { color: #ccc; }
        .tab-btn.active { color: #007AC1; border-bottom-color: #007AC1; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* ==================== TAB 1: POINT DIFFERENTIAL STYLES ==================== */
        .tab1-content { padding: 20px; }
        h1 { text-align: center; color: #ccc; margin-bottom: 5px; }
        h2 { color: #aaa; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 10px; text-align: center; }
        .subtitle { text-align: center; color: #888; font-size: 14px; margin-bottom: 15px; }
        
        #main { display: flex; justify-content: center; gap: 30px; }
        #chart-container { display: flex; flex-direction: column; align-items: center; }
        #chart { position: relative; }
        canvas { background: #16213e; border-radius: 8px; }
        #tooltip { 
            position: absolute; background: #0f3460; border: 2px solid #007AC1;
            border-radius: 10px; padding: 15px; display: none; z-index: 100; pointer-events: none;
        }
        #tooltip h3 { margin: 0 0 5px 0; text-align: center; }
        #tooltip .diff { text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 5px; }
        #tooltip .diff.positive { color: #4ade80; }
        #tooltip .diff.negative { color: #f87171; }
        #tooltip .leading-pct { text-align: center; font-size: 12px; color: #aaa; margin-bottom: 10px; }
        #headshots { display: flex; gap: 10px; }
        .player { text-align: center; width: 80px; }
        .player img { width: 70px; height: 52px; object-fit: cover; border-radius: 5px; background: #1a1a2e; }
        .player span { font-size: 11px; display: block; margin-top: 3px; }
        
        #period-selector, #filter-selector, .mode-selector {
            display: flex; gap: 8px; margin-bottom: 10px; justify-content: center; flex-wrap: wrap;
        }
        #period-selector button, #filter-selector button, .mode-selector button {
            background: #0f3460; color: white; border: 2px solid #333;
            padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s;
        }
        #period-selector button:hover, #filter-selector button:hover, .mode-selector button:hover { border-color: #007AC1; }
        #period-selector button.active, .mode-selector button.active { background: #007AC1; border-color: #007AC1; }
        #filter-selector button.active { background: #006644; border-color: #00aa66; }
        .burst-window-btn {
            background: #0f3460; color: white; border: 2px solid #333;
            padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s;
        }
        .burst-window-btn:hover { border-color: #e94560; }
        .burst-window-btn.active { background: #e94560; border-color: #e94560; }
        .timeout-mode-btn {
            background: #0f3460; color: white; border: 1px solid #333;
            padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; width: 100%;
        }
        .timeout-mode-btn:hover { border-color: #4ade80; }
        .timeout-mode-btn.active { background: #4ade80; border-color: #4ade80; color: #000; }
        .to-rank-table { border-collapse: collapse; font-size: 12px; }
        .to-rank-table th, .to-rank-table td { padding: 6px 12px; text-align: center; border-bottom: 1px solid #333; }
        .to-rank-table th { background: #16213e; color: #ccc; }
        .to-rank-table td { color: #fff; }
        .to-rank-table tr:hover { background: #1a1a3e; }
        .separator { width: 2px; background: #333; margin: 0 5px; align-self: stretch; }
        
        #controls, .chart-controls {
            background: #16213e; border-radius: 8px; padding: 15px;
            min-width: 360px; max-height: 520px; overflow-y: auto;
        }
        .controls-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #333; }
        .controls-header h3 { margin: 0; color: #ccc; }
        .btn-group { display: flex; gap: 5px; }
        .btn-group button { background: #0f3460; color: white; border: 1px solid #007AC1; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; }
        .btn-group button:hover { background: #007AC1; }
        
        .team-header { display: flex; align-items: center; font-size: 10px; color: #888; padding: 0 0 5px 0; border-bottom: 1px solid #333; margin-bottom: 5px; }
        .th-checkbox { width: 21px; }
        .th-rank { width: 22px; text-align: right; padding-right: 4px; }
        .th-color { width: 16px; }
        .th-name { width: 36px; }
        .th-record { width: 50px; text-align: center; }
        .th-diff { width: 50px; text-align: center; }
        .th-lead { width: 45px; text-align: center; }
        .th-deficit { width: 45px; text-align: center; }
        
        .team-checkbox { display: flex; align-items: center; margin-bottom: 4px; }
        .team-checkbox input { margin-right: 6px; width: 15px; height: 15px; cursor: pointer; }
        .team-checkbox label { cursor: pointer; font-size: 11px; display: flex; align-items: center; flex: 1; }
        .team-color { width: 12px; height: 12px; border-radius: 2px; flex-shrink: 0; margin-right: 4px; }
        .team-rank { color: #666; font-size: 10px; width: 22px; text-align: right; padding-right: 4px; }
        .team-name { width: 36px; font-weight: bold; }
        .team-record { font-size: 10px; color: #888; width: 50px; text-align: center; }
        .team-final { font-size: 11px; font-family: monospace; width: 50px; text-align: center; }
        .team-lead { font-size: 10px; font-family: monospace; width: 45px; text-align: center; color: #4ade80; }
        .team-deficit { font-size: 10px; font-family: monospace; width: 45px; text-align: center; color: #f87171; }
        
        #band-toggle { margin-top: 10px; padding-top: 10px; border-top: 1px solid #333; }
        #band-toggle label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 12px; }
        
        .legend { display: flex; justify-content: center; gap: 20px; margin-top: 10px; font-size: 12px; color: #888; }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-line { width: 20px; height: 3px; }
        .legend-band { width: 20px; height: 12px; opacity: 0.3; }
        
        /* Tables shared styles */
        .data-section { margin-top: 40px; padding-top: 20px; border-top: 2px solid #333; }
        .table-container { max-width: 1100px; margin: 0 auto; overflow-x: auto; }
        .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .data-table th { 
            background: #0f3460; padding: 10px 8px; text-align: center; cursor: pointer;
            border-bottom: 2px solid #007AC1; position: relative;
        }
        .data-table th:hover { background: #1a4a7a; }
        .data-table th.sorted-asc::after { content: " \\25B2"; font-size: 10px; }
        .data-table th.sorted-desc::after { content: " \\25BC"; font-size: 10px; }
        .data-table td { padding: 8px; text-align: center; border-bottom: 1px solid #333; }
        .data-table tr:hover { background: #1a1a3e; }
        .data-table .team-cell { display: flex; align-items: center; justify-content: center; gap: 8px; }
        .highlight-good { color: #4ade80; }
        .highlight-bad { color: #f87171; }
        
        /* Threshold chart section */
        .threshold-section { display: flex; justify-content: center; gap: 30px; margin-top: 20px; }
        .threshold-chart { position: relative; }
        #threshold-tooltip, #heatmap-tooltip {
            position: absolute; background: #0f3460; border: 2px solid #007AC1;
            border-radius: 8px; padding: 10px; display: none; z-index: 100; pointer-events: none;
            font-size: 12px;
        }
        
        .team-select-grid {
            display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px;
        }
        .team-select-grid label {
            display: flex; align-items: center; gap: 4px; font-size: 11px; cursor: pointer;
        }
        .team-select-grid input { width: 14px; height: 14px; }
        
        /* Heatmap */
        .heatmap-section { display: flex; justify-content: center; gap: 30px; margin-top: 20px; }
        .heatmap-container { position: relative; }
        .heatmap-controls { background: #16213e; border-radius: 8px; padding: 15px; min-width: 200px; }
        .heatmap-controls select { 
            width: 100%; padding: 8px; background: #0f3460; color: white; 
            border: 1px solid #007AC1; border-radius: 4px; font-size: 13px; margin-bottom: 10px;
        }
        .color-scale { 
            display: flex; align-items: center; gap: 10px; margin-top: 15px; 
            padding-top: 15px; border-top: 1px solid #333;
        }
        .color-bar { 
            flex: 1; height: 20px; border-radius: 4px;
            background: linear-gradient(to right, #dc2626, #fbbf24, #22c55e);
        }
        .color-labels { display: flex; justify-content: space-between; font-size: 11px; color: #888; margin-top: 5px; }
        
        /* ==================== TAB 2 & 3: CLUTCH & MOMENTUM STYLES ==================== */
        .tab23-container { display: flex; height: calc(100vh - 52px); width: 100%; }
        .tab23-main {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        .tab23-main h1 { color: #fff; margin-bottom: 10px; font-size: 1.5rem; text-align: left; }
        .tab23-subtitle { color: #666; font-size: 0.85rem; margin-bottom: 15px; }
        .tab23-chart-container { flex: 1; position: relative; min-height: 400px; }
        
        .tab23-sidebar {
            width: 340px;
            background: #141414;
            border-left: 1px solid #333;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-header {
            padding: 15px;
            background: #1a1a1a;
            border-bottom: 1px solid #333;
        }
        .sidebar-header h2 { font-size: 1rem; color: #fff; margin-bottom: 10px; }
        .sidebar-controls { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .sidebar-controls button {
            padding: 6px 12px; border: 1px solid #444; background: #222;
            color: #ccc; border-radius: 4px; cursor: pointer; font-size: 0.8rem;
        }
        .sidebar-controls button:hover { background: #333; border-color: #555; }
        
        .team-list-23 { flex: 1; overflow-y: auto; padding: 10px; }
        .team-item-23 {
            display: flex; align-items: center; padding: 8px 10px; margin-bottom: 4px;
            background: #1a1a1a; border-radius: 6px; cursor: pointer; border: 1px solid transparent;
        }
        .team-item-23:hover { background: #252525; }
        .team-item-23.selected { background: #1e3a5f; border: 1px solid #2d5a8a; }
        .team-item-23 input { margin-right: 10px; accent-color: #4a9eff; }
        .team-abbrev-23 { font-weight: 600; width: 40px; color: #fff; }
        .team-stats-23 { flex: 1; display: flex; gap: 8px; font-size: 0.75rem; color: #888; }
        .team-stat-23 { display: flex; flex-direction: column; align-items: center; }
        .team-stat-23 .label { font-size: 0.65rem; color: #666; }
        .team-stat-23 .value { color: #aaa; }
        .team-stat-23 .value.high { color: #ff6b6b; }
        .team-stat-23 .value.low { color: #4ecdc4; }
        
        .summary-panel { padding: 15px; background: #1a1a1a; border-top: 1px solid #333; }
        .summary-panel h3 { font-size: 0.9rem; color: #fff; margin-bottom: 12px; }
        .summary-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px; }
        .summary-stat { background: #222; padding: 10px; border-radius: 6px; text-align: center; }
        .summary-stat .label { font-size: 0.7rem; color: #666; margin-bottom: 4px; }
        .summary-stat .value { font-size: 1.1rem; font-weight: 600; color: #4a9eff; }
        
        /* Game Tooltip for Clutch */
        .game-tooltip {
            position: fixed; background: #1a1a1a; border: 1px solid #444; padding: 16px;
            border-radius: 10px; font-size: 0.85rem; pointer-events: none; z-index: 1000;
            display: none; box-shadow: 0 8px 32px rgba(0,0,0,0.7); min-width: 360px;
        }
        .game-tooltip .matchup { font-weight: 700; color: #fff; font-size: 1.1rem; margin-bottom: 4px; }
        .game-tooltip .score { font-size: 1.2rem; color: #4a9eff; font-weight: 600; margin-bottom: 4px; }
        .game-tooltip .winner { font-size: 0.85rem; color: #4ecdc4; margin-bottom: 8px; }
        .game-tooltip .date { color: #888; font-size: 0.8rem; margin-bottom: 10px; }
        .game-tooltip .clutch { color: #ff6b6b; font-size: 1.05rem; font-weight: 600; }
        .game-tooltip .details { margin-top: 8px; font-size: 0.8rem; color: #888; }
        .game-tooltip .margin-chart { margin-top: 14px; background: #0d0d0d; border-radius: 8px; padding: 12px; }
        .game-tooltip .margin-chart-title { font-size: 0.75rem; color: #888; margin-bottom: 10px; text-align: center; }
        .game-tooltip .margin-chart-wrapper { display: flex; align-items: stretch; }
        .game-tooltip .y-labels { display: flex; flex-direction: column; justify-content: space-between; font-size: 0.7rem; font-weight: 700; padding-right: 6px; min-width: 32px; text-align: right; }
        .game-tooltip .y-label-home { color: #4ecdc4; }
        .game-tooltip .y-label-away { color: #ff6b6b; padding-bottom: 18px; }
        .game-tooltip .chart-area { flex: 1; height: 120px; }
        
        /* Momentum legend */
        .momentum-legend { padding: 15px; background: #1a1a1a; border-top: 1px solid #333; }
        .momentum-legend h3 { font-size: 0.85rem; color: #fff; margin-bottom: 10px; }
        
        /* Team Colors */
        .team-color-ATL { --team-color: #E03A3E; } .team-color-BOS { --team-color: #007A33; }
        .team-color-BKN { --team-color: #888888; } .team-color-CHA { --team-color: #1D1160; }
        .team-color-CHI { --team-color: #CE1141; } .team-color-CLE { --team-color: #860038; }
        .team-color-DAL { --team-color: #00538C; } .team-color-DEN { --team-color: #FEC524; }
        .team-color-DET { --team-color: #C8102E; } .team-color-GSW { --team-color: #1D428A; }
        .team-color-HOU { --team-color: #CE1141; } .team-color-IND { --team-color: #002D62; }
        .team-color-LAC { --team-color: #C8102E; } .team-color-LAL { --team-color: #552583; }
        .team-color-MEM { --team-color: #5D76A9; } .team-color-MIA { --team-color: #98002E; }
        .team-color-MIL { --team-color: #00471B; } .team-color-MIN { --team-color: #0C2340; }
        .team-color-NOP { --team-color: #0C2340; } .team-color-NYK { --team-color: #F58426; }
        .team-color-OKC { --team-color: #007AC1; } .team-color-ORL { --team-color: #0077C0; }
        .team-color-PHI { --team-color: #006BB6; } .team-color-PHX { --team-color: #E56020; }
        .team-color-POR { --team-color: #E03A3E; } .team-color-SAC { --team-color: #5A2D81; }
        .team-color-SAS { --team-color: #C4CED4; } .team-color-TOR { --team-color: #CE1141; }
        .team-color-UTA { --team-color: #002B5C; } .team-color-WAS { --team-color: #002B5C; }
    </style>
</head>
<body>
    <!-- Back to Index -->
    <a href="index.html" style="position:fixed;top:10px;right:10px;background:#333;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;z-index:9999;font-size:13px;">← Index</a>
    
    <!-- Tab Navigation -->
    <div class="tab-nav">
        <button class="tab-btn active" data-tab="diff">Point Differential</button>
        <button class="tab-btn" data-tab="clutch">Clutch Index</button>
        <button class="tab-btn" data-tab="momentum">Momentum</button>
    </div>
    
    <!-- ==================== TAB 1: POINT DIFFERENTIAL ==================== -->
    <div class="tab-content active" id="tab-diff">
        <div class="tab1-content">
            <h1>NBA 2025-26: Point Differential Analysis</h1>
            <div class="subtitle">Interactive visualization of team performance patterns</div>
            <p style="text-align: center; color: #666; font-size: 12px; max-width: 800px; margin: 0 auto 15px auto;">
                Average point margin throughout the game. Solid line = mean, shaded band = 25th-75th percentile range, dashed lines = min/max. Filter by period or opponent quality.
            </p>
            
            <div id="period-selector">
                <button class="active" data-period="all">Full Game</button>
                <button data-period="clutch">Clutch (Last 5 min)</button>
                <button data-period="OT">OT Only</button>
                <div class="separator"></div>
                <button data-period="1H">1st Half</button>
                <button data-period="2H">2nd Half</button>
                <div class="separator"></div>
                <button data-period="1">Q1</button>
                <button data-period="2">Q2</button>
                <button data-period="3">Q3</button>
                <button data-period="4">Q4</button>
            </div>
            
            <div id="filter-selector">
                <button class="active" data-filter="all">All Games</button>
                <button data-filter="vs_good">vs Teams &gt;.500</button>
                <button data-filter="vs_bad">vs Teams &lt;.500</button>
            </div>
            
            <div id="main">
                <div id="chart-container">
                    <div id="chart">
                        <canvas id="canvas" width="1000" height="500"></canvas>
                        <div id="tooltip">
                            <h3 id="time-label">Time: 0:00</h3>
                            <div id="team-label" style="text-align:center; font-weight:bold; margin-bottom:5px;"></div>
                            <div id="diff-label" class="diff"></div>
                            <div id="leading-pct" class="leading-pct"></div>
                            <div id="headshots"></div>
                        </div>
                    </div>
                    <div class="legend">
                        <div class="legend-item"><div class="legend-line" style="background: #007AC1;"></div> Average margin</div>
                        <div class="legend-item"><div class="legend-band" style="background: #007AC1;"></div> 25th-75th percentile</div>
                        <div class="legend-item"><div class="legend-line" style="background: #007AC1; border-top: 2px dashed #007AC1; height: 0;"></div> Min / Max</div>
                    </div>
                </div>
                <div id="controls">
                    <div class="controls-header">
                        <h3>Teams</h3>
                        <div class="btn-group">
                            <button id="btn-all">All</button>
                            <button id="btn-none">None</button>
                        </div>
                    </div>
                    <div class="team-header">
                        <span class="th-checkbox"></span>
                        <span class="th-rank">#</span>
                        <span class="th-color"></span>
                        <span class="th-name">Team</span>
                        <span class="th-record">Record</span>
                        <span class="th-diff">Diff</span>
                        <span class="th-lead">Lead</span>
                        <span class="th-deficit">Deficit</span>
                    </div>
                    <div id="team-list"></div>
                    <div id="band-toggle">
                        <label><input type="checkbox" id="show-bands" checked> Show 25th-75th percentile bands</label>
                        <label style="margin-top: 5px;"><input type="checkbox" id="show-minmax"> Show min-max range</label>
                    </div>
                </div>
            </div>
            
            <!-- Win Probability Heatmap -->
            <div class="data-section">
                <h2>Win Probability Heatmap</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px; max-width: 900px; margin-left: auto; margin-right: auto;">
                    Win probability at each margin and minute. Green = high win probability, red = low.
                </p>
                <div class="heatmap-section">
                    <div class="heatmap-container">
                        <canvas id="heatmap-canvas" width="800" height="450"></canvas>
                        <div id="heatmap-tooltip"></div>
                    </div>
                    <div class="heatmap-controls">
                        <h3 style="margin: 0 0 10px 0; color: #ccc; font-size: 14px;">Select Team</h3>
                        <select id="heatmap-team">
                            <option value="_league">League Average</option>
                        </select>
                        <div class="color-scale">
                            <span style="font-size: 11px;">0%</span>
                            <div class="color-bar"></div>
                            <span style="font-size: 11px;">100%</span>
                        </div>
                        <div class="color-labels"><span>Lose</span><span>Win</span></div>
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #333; font-size: 11px; color: #888;">
                            <div id="heatmap-stats"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Margin Threshold Chart -->
            <div class="data-section">
                <h2>Margin Threshold Analysis</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px; max-width: 900px; margin-left: auto; margin-right: auto;">
                    Positive thresholds: games that reached that value or better. Negative thresholds: games that fell to that value or worse.
                </p>
                <div class="mode-selector" id="threshold-mode">
                    <button class="active" data-mode="frequency">Frequency %</button>
                    <button data-mode="time">Time at Margin %</button>
                    <button data-mode="win_pct">Win %</button>
                </div>
                <div class="threshold-section">
                    <div class="threshold-chart">
                        <canvas id="threshold-canvas" width="900" height="400"></canvas>
                        <div id="threshold-tooltip"></div>
                    </div>
                    <div class="chart-controls" style="min-width: 280px; max-height: 400px;">
                        <div class="controls-header">
                            <h3>Teams</h3>
                            <div class="btn-group">
                                <button id="th-btn-all">All</button>
                                <button id="th-btn-none">None</button>
                                <button id="th-btn-top5">Top 5</button>
                            </div>
                        </div>
                        <div class="team-select-grid" id="threshold-teams"></div>
                    </div>
                </div>
            </div>
            
            <!-- Checkpoints Table -->
            <div class="data-section">
                <h2>Margin at Checkpoints</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px;">
                    Average margin at key points. Click headers to sort.
                </p>
                <div class="table-container">
                    <table class="data-table" id="checkpoints-table">
                        <thead>
                            <tr>
                                <th data-col="team">Team</th>
                                <th data-col="6">6 min</th>
                                <th data-col="12">12 min (Q1)</th>
                                <th data-col="18">18 min</th>
                                <th data-col="24">24 min (Half)</th>
                                <th data-col="30">30 min</th>
                                <th data-col="36">36 min (Q3)</th>
                                <th data-col="42">42 min</th>
                                <th data-col="48">48 min</th>
                                <th data-col="final">Final</th>
                            </tr>
                        </thead>
                        <tbody id="checkpoints-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <!-- Comeback & Blown Lead Table -->
            <div class="data-section">
                <h2>Comeback & Blown Lead Analysis</h2>
                <div class="table-container">
                    <table class="data-table" id="comeback-table">
                        <thead>
                            <tr>
                                <th data-col="team">Team</th>
                                <th data-col="wins">Comeback Wins</th>
                                <th data-col="comeback">Avg Deficit</th>
                                <th data-col="max_comeback">Max Deficit</th>
                                <th data-col="wire_wins">Wins No Trail</th>
                                <th data-col="losses">Blown Losses</th>
                                <th data-col="blown">Avg Lead</th>
                                <th data-col="max_blown">Max Lead</th>
                                <th data-col="wire_losses">Losses No Lead</th>
                            </tr>
                        </thead>
                        <tbody id="comeback-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <!-- Garbage Time Table -->
            <div class="data-section">
                <h2>Garbage Time Analysis</h2>
                <div class="table-container">
                    <table class="data-table" id="garbage-table">
                        <thead>
                            <tr>
                                <th data-col="team">Team</th>
                                <th data-col="freq_pct">Frequency %</th>
                                <th data-col="total">Total</th>
                                <th data-col="wins">In Wins</th>
                                <th data-col="losses">In Losses</th>
                                <th data-col="win_pct">Win %</th>
                                <th data-col="successful">Successful</th>
                                <th data-col="failed">Failed</th>
                                <th data-col="success_rate">Success %</th>
                                <th data-col="avg_start">Avg Start</th>
                                <th data-col="avg_duration">Avg Duration</th>
                                <th data-col="avg_diff">Avg Diff</th>
                            </tr>
                        </thead>
                        <tbody id="garbage-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <!-- Average Runs Table -->
            <div class="data-section">
                <h2>Average Best & Worst Runs</h2>
                <div class="table-container">
                    <table class="data-table" id="runs-table">
                        <thead>
                            <tr>
                                <th data-col="team">Team</th>
                                <th data-col="1min_best" class="highlight-good">1min Best</th>
                                <th data-col="1min_worst" class="highlight-bad">1min Worst</th>
                                <th data-col="3min_best" class="highlight-good">3min Best</th>
                                <th data-col="3min_worst" class="highlight-bad">3min Worst</th>
                                <th data-col="6min_best" class="highlight-good">6min Best</th>
                                <th data-col="6min_worst" class="highlight-bad">6min Worst</th>
                                <th data-col="quarter_best" class="highlight-good">Quarter Best</th>
                                <th data-col="quarter_worst" class="highlight-bad">Quarter Worst</th>
                                <th data-col="half_best" class="highlight-good">Half Best</th>
                                <th data-col="half_worst" class="highlight-bad">Half Worst</th>
                            </tr>
                        </thead>
                        <tbody id="runs-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <!-- Maximum Runs Table -->
            <div class="data-section">
                <h2>Maximum Best & Worst Runs</h2>
                <div class="table-container">
                    <table class="data-table" id="max-runs-table">
                        <thead>
                            <tr>
                                <th data-col="team">Team</th>
                                <th data-col="1min_best" class="highlight-good">1min Best</th>
                                <th data-col="1min_worst" class="highlight-bad">1min Worst</th>
                                <th data-col="3min_best" class="highlight-good">3min Best</th>
                                <th data-col="3min_worst" class="highlight-bad">3min Worst</th>
                                <th data-col="6min_best" class="highlight-good">6min Best</th>
                                <th data-col="6min_worst" class="highlight-bad">6min Worst</th>
                                <th data-col="quarter_best" class="highlight-good">Quarter Best</th>
                                <th data-col="quarter_worst" class="highlight-bad">Quarter Worst</th>
                                <th data-col="half_best" class="highlight-good">Half Best</th>
                                <th data-col="half_worst" class="highlight-bad">Half Worst</th>
                            </tr>
                        </thead>
                        <tbody id="max-runs-tbody"></tbody>
                    </table>
                </div>
            </div>
            
            <!-- Burst Frequency Scatter Plot -->
            <div class="data-section">
                <h2>Burst Frequency Analysis</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px;">
                    Non-overlapping scoring runs per game. Bottom-right = elite (explosive but composed).
                </p>
                <div style="display: flex; justify-content: center; gap: 10px; margin-bottom: 15px;">
                    <button class="burst-window-btn active" data-window="1min">1 min</button>
                    <button class="burst-window-btn" data-window="3min">3 min</button>
                    <button class="burst-window-btn" data-window="6min">6 min</button>
                </div>
                <div style="display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 15px;">
                    <span style="color: #888; font-size: 12px;">Threshold: +<span id="burst-thresh-value">5</span></span>
                    <input type="range" id="burst-thresh-slider" min="3" max="8" value="5" style="width: 200px;">
                </div>
                <div style="display: flex; justify-content: center;">
                    <canvas id="burst-canvas" width="600" height="500" style="background: #1a1a2e; border-radius: 8px;"></canvas>
                    <div id="burst-tooltip" style="position: absolute; display: none; background: rgba(0,0,0,0.9); color: white; padding: 10px; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 1000;"></div>
                </div>
            </div>
            
            <!-- Lead Changes Bar Chart -->
            <div class="data-section">
                <h2>Lead Changes Per Game</h2>
                <div style="display: flex; justify-content: center;">
                    <canvas id="leadchange-canvas" width="800" height="700" style="background: #1a1a2e; border-radius: 8px;"></canvas>
                </div>
            </div>
            
            <!-- Timeout Analysis -->
            <div class="data-section">
                <h2>Timeout Analysis</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px;">
                    Average point differential around timeouts (-2min to +2min). Normalized: 0 = margin at timeout moment.
                </p>
                <div style="display: flex; gap: 20px; justify-content: center;">
                    <canvas id="timeout-canvas" width="700" height="400" style="background: #1a1a2e; border-radius: 8px;"></canvas>
                    <div style="background: #16213e; border-radius: 8px; padding: 15px; width: 180px;">
                        <h4 style="margin: 0 0 10px 0; color: #ccc;">Team</h4>
                        <select id="timeout-team-select" style="width: 100%; padding: 8px; background: #0f3460; color: white; border: 1px solid #333; border-radius: 4px; margin-bottom: 15px;"></select>
                        <h4 style="margin: 0 0 10px 0; color: #ccc;">Mode</h4>
                        <div style="display: flex; flex-direction: column; gap: 5px;">
                            <button class="timeout-mode-btn active" data-mode="my_to">My Timeout</button>
                            <button class="timeout-mode-btn" data-mode="opp_to">Opponent Timeout</button>
                            <button class="timeout-mode-btn" data-mode="both">All TOs</button>
                        </div>
                    </div>
                </div>
                <h3 style="text-align: center; margin-top: 30px; color: #ccc;">Timeout Efficiency Rankings</h3>
                <div style="display: flex; justify-content: center;">
                    <div id="timeout-rankings-table" style="max-height: 400px; overflow-y: auto;"></div>
                </div>
            </div>
            
            <!-- Player Activity Timeline -->
            <div class="data-section">
                <h2>Player Activity Timeline</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px;">
                    On-court percentage over game time. Select a team, then tick players.
                </p>
                <div style="display: flex; gap: 20px; justify-content: center;">
                    <div id="activity-active-panel" style="background: #16213e; border-radius: 8px; padding: 15px; width: 180px; max-height: 400px; overflow-y: auto;">
                        <h4 style="margin: 0 0 10px 0; color: #ccc;">Active Players</h4>
                        <div id="activity-active-list"><p style="color: #666; font-size: 12px;">No players selected</p></div>
                    </div>
                    <div>
                        <canvas id="activity-canvas" width="800" height="400" style="background: #1a1a2e; border-radius: 8px;"></canvas>
                        <div id="activity-tooltip" style="position: absolute; display: none; background: rgba(0,0,0,0.9); color: white; padding: 10px; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 1000;"></div>
                    </div>
                    <div id="activity-controls" style="background: #16213e; border-radius: 8px; padding: 15px; width: 250px; max-height: 400px; overflow-y: auto;">
                        <h4 style="margin: 0 0 10px 0; color: #ccc;">Select Team</h4>
                        <select id="activity-team-select" style="width: 100%; padding: 5px; margin-bottom: 15px; background: #1a1a2e; color: white; border: 1px solid #444; border-radius: 4px;">
                            <option value="">-- Select Team --</option>
                        </select>
                        <h4 style="margin: 0 0 10px 0; color: #ccc;">Players</h4>
                        <div id="activity-player-list"></div>
                        <div style="margin-top: 15px;">
                            <button id="activity-clear-btn" style="width: 100%; padding: 8px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer;">Clear All</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Game Shape Clusters -->
            <div class="data-section">
                <h2>Game Shape Clusters</h2>
                <p style="text-align: center; color: #888; margin-bottom: 15px; font-size: 12px;">
                    Games clustered by margin progression (from winner's perspective). Hover for details.
                </p>
                <div style="display: flex; gap: 20px; justify-content: center;">
                    <div>
                        <canvas id="cluster-canvas" width="700" height="550" style="background: #1a1a2e; border-radius: 8px;"></canvas>
                        <div id="cluster-tooltip" style="position: absolute; display: none; background: rgba(0,0,0,0.9); color: white; padding: 10px; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 1000;"></div>
                    </div>
                    <div id="cluster-controls" style="background: #16213e; border-radius: 8px; padding: 15px; width: 220px;">
                        <h4 style="margin: 0 0 10px 0; color: #ccc;">Filter by Team</h4>
                        <div style="margin-bottom: 10px;">
                            <select id="cluster-team-select" style="width: 100%; padding: 8px; background: #0f3460; color: white; border: 1px solid #333; border-radius: 4px;">
                                <option value="all">All Teams</option>
                            </select>
                        </div>
                        <h4 style="margin: 15px 0 10px 0; color: #ccc;">Cluster Shapes</h4>
                        <div id="cluster-legend"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- ==================== TAB 2: CLUTCH INDEX ==================== -->
    <div class="tab-content" id="tab-clutch">
        <div class="tab23-container">
            <div class="tab23-main">
                <h1>NBA Clutch Index</h1>
                <p class="tab23-subtitle">Season 2025-26 | Showing <span id="clutchShowingCount">0</span> of <span id="clutchGameCount">0</span> games</p>
                <div class="tab23-chart-container"><canvas id="clutchChart"></canvas></div>
            </div>
            <div class="tab23-sidebar">
                <div class="sidebar-header">
                    <h2>Controls</h2>
                    <div class="sidebar-controls">
                        <label style="color:#888;font-size:12px;">Max:</label>
                        <input type="number" id="clutchMaxGames" value="50" min="1" max="500" style="width:60px;padding:4px;background:#222;color:#fff;border:1px solid #444;border-radius:4px;">
                        <select id="clutchSortOrder" style="padding:4px;background:#222;color:#fff;border:1px solid #444;border-radius:4px;">
                            <option value="desc">High→Low</option>
                            <option value="asc">Low→High</option>
                        </select>
                    </div>
                    <div class="sidebar-controls">
                        <button id="clutchSelectAll">All</button>
                        <button id="clutchSelectNone">Clear</button>
                    </div>
                </div>
                <div class="team-header" style="padding: 0 15px;">
                    <span class="th-checkbox"></span>
                    <span class="th-color"></span>
                    <span class="th-name">Team</span>
                    <span class="team-record">Avg</span>
                    <span class="team-final">Max</span>
                    <span class="team-final">Min</span>
                </div>
                <div class="team-list-23" id="clutchTeamList" style="padding: 0 15px;"></div>
                <div class="summary-panel">
                    <h3>Summary</h3>
                    <div class="summary-stats">
                        <div class="summary-stat"><div class="label">Games</div><div class="value" id="clutchSummaryGames">0</div></div>
                        <div class="summary-stat"><div class="label">Avg</div><div class="value" id="clutchSummaryAvg">-</div></div>
                        <div class="summary-stat"><div class="label">Max</div><div class="value" id="clutchSummaryMax">-</div></div>
                        <div class="summary-stat"><div class="label">Min</div><div class="value" id="clutchSummaryMin">-</div></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Clutch Index Documentation -->
        <div style="padding: 20px 40px; border-top: 2px solid #333;">
            <h2 style="color: #007AC1; font-size: 1.5rem; margin: 20px 0; border-left: 4px solid #007AC1; padding-left: 15px;">Formula</h2>
            
            <div style="background: linear-gradient(135deg, #16213e 0%, #1a3a5c 100%); border: 2px solid #007AC1; border-radius: 8px; padding: 40px; margin: 25px 0; text-align: center;">
                $$\\text{Clutch Index} = \\Bigl(1 + \\gamma \\cdot L\\Bigr) \\cdot \\int_0^T \\frac{1 + \\alpha \\cdot \\mathbf{1}\\{\\text{trailing team has ball}\\}}{\\lvert m(t) \\rvert + \\varepsilon} \\cdot \\tilde{t}^{\\,2} \\, dt$$
                
                <div style="text-align: left; margin-top: 20px; padding-top: 20px; border-top: 1px solid #333;">
                    <p style="margin: 8px 0; padding-left: 20px;">$L$ = number of lead changes in the period</p>
                    <p style="margin: 8px 0; padding-left: 20px;">$m(t)$ = point margin at time $t$ (home − away)</p>
                    <p style="margin: 8px 0; padding-left: 20px;">$\\tilde{t} = t / T$ = normalized time (0 at period start, 1 at period end)</p>
                    <p style="margin: 8px 0; padding-left: 20px;">$\\mathbf{1}\\{\\cdot\\}$ = indicator function (1 if true, 0 otherwise)</p>
                </div>
            </div>
            
            <h2 style="color: #007AC1; font-size: 1.5rem; margin: 40px 0 20px 0; border-left: 4px solid #007AC1; padding-left: 15px;">Parameters</h2>
            
            <table style="width: 100%; max-width: 800px; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <th style="background: #0f3460; color: #fff; padding: 12px 15px; text-align: left; border-bottom: 2px solid #007AC1;">Parameter</th>
                    <th style="background: #0f3460; color: #fff; padding: 12px 15px; text-align: left; border-bottom: 2px solid #007AC1;">Symbol</th>
                    <th style="background: #0f3460; color: #fff; padding: 12px 15px; text-align: left; border-bottom: 2px solid #007AC1;">Value</th>
                    <th style="background: #0f3460; color: #fff; padding: 12px 15px; text-align: left; border-bottom: 2px solid #007AC1;">Description</th>
                </tr>
                <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #fbbf24; font-family: monospace; font-weight: bold;">CLUTCH_ALPHA</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333;">$\\alpha$</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">0.3</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333;">Possession bonus when trailing team has the ball</td>
                </tr>
                <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #fbbf24; font-family: monospace; font-weight: bold;">CLUTCH_BETA</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333;">$\\varepsilon$</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">1.0</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333;">Denominator offset (smooths small margins, prevents ÷0)</td>
                </tr>
                <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #fbbf24; font-family: monospace; font-weight: bold;">CLUTCH_GAMMA</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333;">$\\gamma$</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">0.15</td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #333;">Lead change multiplier</td>
                </tr>
            </table>
            
            <h2 style="color: #007AC1; font-size: 1.5rem; margin: 40px 0 20px 0; border-left: 4px solid #007AC1; padding-left: 15px;">Components</h2>
            
            <h3 style="color: #4ade80; font-size: 1.1rem; margin: 25px 0 10px 0;">1. Instantaneous Tension</h3>
            <p style="margin-bottom: 15px;">At each moment, tension is inversely proportional to the margin:</p>
            
            <div style="background: #16213e; border: 1px solid #333; border-radius: 8px; padding: 30px; margin: 25px 0; text-align: center;">
                $$\\text{Tension}(t) = \\frac{1 + \\alpha \\cdot \\mathbf{1}\\{\\text{trailing has ball}\\}}{\\lvert m(t) \\rvert + \\varepsilon}$$
            </div>
            
            <p style="margin-bottom: 15px;">Examples:</p>
            <ul style="margin: 15px 0 15px 30px;">
                <li style="margin-bottom: 8px;">Tie game, trailing team has ball: $\\frac{1 + 0.3}{0 + 1} = 1.30$</li>
                <li style="margin-bottom: 8px;">5-point game, trailing team has ball: $\\frac{1.3}{5 + 1} = 0.217$</li>
                <li style="margin-bottom: 8px;">10-point game, leading team has ball: $\\frac{1.0}{10 + 1} = 0.091$</li>
            </ul>
            
            <h3 style="color: #4ade80; font-size: 1.1rem; margin: 25px 0 10px 0;">2. Time Weighting</h3>
            <p style="margin-bottom: 15px;">Later moments matter more via quadratic weighting:</p>
            
            <div style="background: #16213e; border: 1px solid #333; border-radius: 8px; padding: 30px; margin: 25px 0; text-align: center;">
                $$w(t) = \\tilde{t}^{\\,2} = \\left(\\frac{t - t_{\\text{start}}}{T}\\right)^2$$
            </div>
            
            <p style="margin-bottom: 15px;">For Q4 ($T = 720$ seconds):</p>
            <ul style="margin: 15px 0 15px 30px;">
                <li style="margin-bottom: 8px;">Start of Q4: $w = 0^2 = 0.00$</li>
                <li style="margin-bottom: 8px;">Mid Q4: $w = 0.5^2 = 0.25$</li>
                <li style="margin-bottom: 8px;">End of Q4: $w = 1^2 = 1.00$</li>
            </ul>
            
            <h3 style="color: #4ade80; font-size: 1.1rem; margin: 25px 0 10px 0;">3. Lead Change Multiplier</h3>
            <p style="margin-bottom: 15px;">More lead changes = more exciting game:</p>
            
            <div style="background: #16213e; border: 1px solid #333; border-radius: 8px; padding: 30px; margin: 25px 0; text-align: center;">
                $$\\text{Multiplier} = 1 + \\gamma \\cdot L$$
            </div>
            
            <p style="margin-bottom: 15px;">Example: 4 lead changes → $1 + 0.15 \\times 4 = 1.60$</p>
            
            <h2 style="color: #007AC1; font-size: 1.5rem; margin: 40px 0 20px 0; border-left: 4px solid #007AC1; padding-left: 15px;">Overtime Handling</h2>
            <p style="margin-bottom: 15px;">Each overtime period contributes at 50% weight:</p>
            
            <div style="background: #16213e; border: 1px solid #333; border-radius: 8px; padding: 30px; margin: 25px 0; text-align: center;">
                $$\\text{Clutch}_{\\text{total}} = \\text{Clutch}_{\\text{Q4}} + \\sum_{i=1}^{n_{\\text{OT}}} 0.5 \\cdot \\text{Clutch}_{\\text{OT}_i}$$
            </div>
            
            <h2 style="color: #007AC1; font-size: 1.5rem; margin: 40px 0 20px 0; border-left: 4px solid #007AC1; padding-left: 15px;">Interpretation</h2>
            
            <table style="width: 100%; max-width: 600px; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <th style="background: #0f3460; color: #fff; padding: 12px 15px; text-align: left; border-bottom: 2px solid #007AC1;">Clutch Index</th>
                    <th style="background: #0f3460; color: #fff; padding: 12px 15px; text-align: left; border-bottom: 2px solid #007AC1;">Interpretation</th>
                </tr>
                <tr><td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">&lt; 0.05</td><td style="padding: 12px 15px; border-bottom: 1px solid #333;">Blowout — game decided early</td></tr>
                <tr><td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">0.05 – 0.15</td><td style="padding: 12px 15px; border-bottom: 1px solid #333;">Comfortable win — some tension</td></tr>
                <tr><td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">0.15 – 0.25</td><td style="padding: 12px 15px; border-bottom: 1px solid #333;">Competitive — close game</td></tr>
                <tr><td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">0.25 – 0.40</td><td style="padding: 12px 15px; border-bottom: 1px solid #333;">Clutch — exciting finish</td></tr>
                <tr><td style="padding: 12px 15px; border-bottom: 1px solid #333; color: #4ade80; font-family: monospace;">&gt; 0.40</td><td style="padding: 12px 15px; border-bottom: 1px solid #333;">Instant classic — overtime thriller</td></tr>
            </table>
            
            <div style="background: rgba(251, 191, 36, 0.1); border-left: 4px solid #fbbf24; padding: 15px 20px; margin: 20px 0; font-size: 0.95rem;">
                <strong>Note:</strong> The integral is computed numerically by sampling every 10 seconds during Q4 and OT periods.
            </div>
        </div>
    </div>
    
    <!-- ==================== TAB 3: MOMENTUM ==================== -->
    <div class="tab-content" id="tab-momentum">
        <div class="tab23-container">
            <div class="tab23-main">
                <h1>Momentum Analysis</h1>
                <p class="tab23-subtitle">Velocity (pts/min) vs Current Margin | Forward window: 60s</p>
                <div class="tab23-chart-container"><canvas id="momentumChart"></canvas></div>
            </div>
            <div class="tab23-sidebar">
                <div class="sidebar-header">
                    <h2>Controls</h2>
                    <div class="sidebar-controls">
                        <label style="color:#888;font-size:12px;">Mode:</label>
                        <select id="momentumModeSelect" style="padding:4px;background:#222;color:#fff;border:1px solid #444;border-radius:4px;">
                            <option value="all_game">All Game</option>
                            <option value="Q1">Q1</option>
                            <option value="Q2">Q2</option>
                            <option value="Q3">Q3</option>
                            <option value="Q4">Q4 + OT</option>
                            <option value="clutch">Clutch (43+)</option>
                        </select>
                    </div>
                    <div class="sidebar-controls">
                        <button id="momSelectAll">All</button>
                        <button id="momSelectNone">Clear</button>
                        <button id="momSelectTop">Top 6</button>
                    </div>
                </div>
                <div class="team-header" style="padding: 0 15px;">
                    <span class="th-checkbox"></span>
                    <span class="th-color"></span>
                    <span class="th-name">Team</span>
                </div>
                <div class="team-list-23" id="momentumTeamList" style="padding: 0 15px;"></div>
                <div class="momentum-legend">
                    <h3>Interpretation</h3>
                    <div style="font-size:0.75rem; color:#888; line-height:1.6;">
                        <div><span style="color:#4ecdc4;">▲ +vel</span> at deficit → comeback</div>
                        <div><span style="color:#ff6b6b;">▼ -vel</span> at deficit → collapse</div>
                        <div><span style="color:#4ecdc4;">▲ +vel</span> at lead → extend</div>
                        <div><span style="color:#ff6b6b;">▼ -vel</span> at lead → regression</div>
                        <div style="margin-top:8px; color:#666;">Gray dashed = League Avg</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Game Tooltip for Clutch -->
    <div class="game-tooltip" id="gameTooltip">
        <div class="matchup"></div>
        <div class="score"></div>
        <div class="winner"></div>
        <div class="date"></div>
        <div class="clutch"></div>
        <div class="details"></div>
        <div class="margin-chart">
            <div class="margin-chart-title">Point Diff (Q4+OT)</div>
            <div class="margin-chart-wrapper">
                <div class="y-labels">
                    <div class="y-label-home" id="yLabelHome">HOME</div>
                    <div class="y-label-away" id="yLabelAway">AWAY</div>
                </div>
                <div class="chart-area"><canvas id="marginChart"></canvas></div>
            </div>
        </div>
    </div>

    <script>
// ==================== LOAD DATA ====================
var data = ''' + data_json + ''';
var teamNames = ''' + team_names_json + ''';

// Extract sub-data
var clutchIndexData = data._clutch_index || {games: {}, team_summary: {}};
var momentumData = data._momentum || {teams: {}, league: {}};

// ==================== TAB SWITCHING ====================
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
});

// ==================== TAB 1: POINT DIFFERENTIAL ====================
var currentPeriod = "all";
var currentFilter = "all";
var selectedTeams = {"OKC": true, "CLE": true, "BOS": true};

var periodElapsedRanges = {
    "all": [0, 2880], "1": [0, 720], "2": [720, 1440], "3": [1440, 2160], "4": [2160, 2880],
    "1H": [0, 1440], "2H": [1440, 2880], "OT": [0, 0], "clutch": [2580, 2880]
};

var canvas = document.getElementById("canvas");
var ctx = canvas.getContext("2d");
var tooltip = document.getElementById("tooltip");
var padding = { left: 50, right: 20, top: 20, bottom: 50 };
var chartWidth = canvas.width - padding.left - padding.right;
var chartHeight = canvas.height - padding.top - padding.bottom;

function getPeriodsSource(team) {
    if (currentFilter === "vs_good") return data[team].vs_good;
    if (currentFilter === "vs_bad") return data[team].vs_bad;
    return data[team].periods;
}

function getClutchSource(team) {
    if (currentFilter === "vs_good") return data[team].clutch_vs_good;
    if (currentFilter === "vs_bad") return data[team].clutch_vs_bad;
    return data[team].clutch;
}

function getLineups(team) {
    if (currentPeriod === "clutch") {
        if (currentFilter === "vs_good") return data[team].lineups_clutch_vs_good || {};
        if (currentFilter === "vs_bad") return data[team].lineups_clutch_vs_bad || {};
        return data[team].lineups_clutch || {};
    }
    if (currentFilter === "vs_good") return data[team].lineups_vs_good || {};
    if (currentFilter === "vs_bad") return data[team].lineups_vs_bad || {};
    return data[team].lineups || {};
}

function getPeriodData(team) {
    var ps = getPeriodsSource(team);
    if (currentPeriod === "OT") {
        var ot = ps.OT;
        if (!ot || ot.games === 0) return [];
        if (ot.diff && ot.diff.length > 0) {
            return ot.diff;
        }
        return [[0, ot.margin, ot.margin, ot.margin, 50]];
    }
    if (currentPeriod === "clutch") {
        var cs = getClutchSource(team);
        return cs ? cs.diff || [] : [];
    }
    var pd = ps[currentPeriod];
    return pd ? pd.diff || [] : [];
}

function getPeriodStats(team) {
    var ps = getPeriodsSource(team);
    if (currentPeriod === "OT") return ps.OT;
    if (currentPeriod === "clutch") return getClutchSource(team);
    return ps[currentPeriod];
}

function getEnabledTeams() { return teamNames.filter(t => selectedTeams[t]); }

function getSortedTeams() {
    return teamNames.slice().sort((a, b) => {
        var aS = getPeriodStats(a), bS = getPeriodStats(b);
        if (!aS || !bS) return 0;
        var aM = aS.margin !== undefined ? aS.margin : (aS.diff && aS.diff.length ? aS.diff[aS.diff.length-1][1] : 0);
        var bM = bS.margin !== undefined ? bS.margin : (bS.diff && bS.diff.length ? bS.diff[bS.diff.length-1][1] : 0);
        return bM - aM;
    });
}

function renderTeamList() {
    var sorted = getSortedTeams();
    var html = "";
    sorted.forEach((team, i) => {
        var stats = getPeriodStats(team);
        var color = data[team].color;
        var border = (color === "#FFFFFF" || color === "#C4CED4") ? " border: 1px solid #888;" : "";
        var hasData = stats && (stats.wins !== undefined || (stats.diff && stats.diff.length));
        var margin = hasData && stats.margin !== undefined ? stats.margin : 0;
        var wins = hasData ? (stats.wins || 0) : 0;
        var losses = hasData ? (stats.losses || 0) : 0;
        var ties = hasData ? (stats.ties || 0) : 0;
        var record = ties > 0 ? wins + "-" + losses + "-" + ties : wins + "-" + losses;
        var lead = hasData && stats.avg_lead ? stats.avg_lead : 0;
        var deficit = hasData && stats.avg_deficit ? stats.avg_deficit : 0;
        var marginColor = margin >= 0 ? "#4ade80" : "#f87171";
        html += '<div class="team-checkbox" style="' + (hasData ? '' : 'opacity:0.4;') + '">';
        html += '<input type="checkbox" id="check-' + team + '" ' + (selectedTeams[team] ? 'checked' : '') + '>';
        html += '<label for="check-' + team + '">';
        html += '<span class="team-rank">' + (i+1) + '.</span>';
        html += '<span class="team-color" style="background:' + color + ';' + border + '"></span>';
        html += '<span class="team-name">' + team + '</span>';
        html += '<span class="team-record">' + record + '</span>';
        html += '<span class="team-final" style="color:' + marginColor + '">' + (margin >= 0 ? '+' : '') + margin.toFixed(1) + '</span>';
        html += '<span class="team-lead">+' + lead.toFixed(1) + '</span>';
        html += '<span class="team-deficit">' + deficit.toFixed(1) + '</span>';
        html += '</label></div>';
    });
    document.getElementById("team-list").innerHTML = html;
    sorted.forEach(team => {
        document.getElementById("check-" + team).addEventListener("change", function() {
            selectedTeams[team] = this.checked;
            drawChart(null, null);
        });
    });
}

function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1,3), 16), g = parseInt(hex.slice(3,5), 16), b = parseInt(hex.slice(5,7), 16);
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
}

function getMaxElapsed() {
    if (currentPeriod === "OT") return 300;
    if (currentPeriod === "clutch") return 300;
    if (["1","2","3","4"].includes(currentPeriod)) return 720;
    if (["1H","2H"].includes(currentPeriod)) return 1440;
    return 2880;
}

function calculateYRange() {
    var enabled = getEnabledTeams(), all = [0];
    var showBands = document.getElementById("show-bands").checked;
    var showMinMax = document.getElementById("show-minmax").checked;
    enabled.forEach(t => {
        var pd = getPeriodData(t);
        pd.forEach(p => { all.push(p[1]); if (showBands) { all.push(p[2]); all.push(p[3]); } if (showMinMax && p.length > 6) { all.push(p[5]); all.push(p[6]); } });
    });
    var min = Math.min(...all), max = Math.max(...all), range = max - min;
    if (range < 10) range = 10;
    return { min: min - 1, max: max + 1, range: range + 2 };
}

function xToCanvas(e, maxE) { return padding.left + (e / maxE) * chartWidth; }
function yToCanvas(m, yInfo) { return padding.top + chartHeight - ((m - yInfo.min) / yInfo.range) * chartHeight; }

function drawChart(highlightTeam, highlightElapsed) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    var enabled = getEnabledTeams(), maxE = getMaxElapsed(), yInfo = calculateYRange(), showBands = document.getElementById("show-bands").checked;
    ctx.strokeStyle = "#333"; ctx.lineWidth = 1;
    for (var m = 0; m <= 4; m++) { var x = xToCanvas(m * maxE / 4, maxE); ctx.beginPath(); ctx.moveTo(x, padding.top); ctx.lineTo(x, canvas.height - padding.bottom); ctx.stroke(); }
    ctx.strokeStyle = "#888"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(padding.left, yToCanvas(0, yInfo)); ctx.lineTo(canvas.width - padding.right, yToCanvas(0, yInfo)); ctx.stroke();
    var showMinMax = document.getElementById("show-minmax").checked;
    if (showBands) {
        enabled.forEach(team => {
            var td = getPeriodData(team), isHi = team === highlightTeam;
            if (td.length < 2) return;
            ctx.fillStyle = hexToRgba(data[team].color, isHi ? 0.25 : (highlightTeam ? 0.05 : 0.15));
            ctx.beginPath();
            td.forEach((p, i) => { var px = xToCanvas(p[0], maxE), py = yToCanvas(p[3], yInfo); i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py); });
            for (var i = td.length - 1; i >= 0; i--) ctx.lineTo(xToCanvas(td[i][0], maxE), yToCanvas(td[i][2], yInfo));
            ctx.closePath(); ctx.fill();
        });
    }
    enabled.forEach(team => {
        var td = getPeriodData(team), isHi = team === highlightTeam;
        if (!td.length) return;
        ctx.strokeStyle = data[team].color; ctx.lineWidth = isHi ? 4 : 2; ctx.globalAlpha = isHi ? 1 : (highlightTeam ? 0.3 : 0.8);
        ctx.beginPath(); td.forEach((p, i) => { var px = xToCanvas(p[0], maxE), py = yToCanvas(p[1], yInfo); i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py); }); ctx.stroke(); ctx.globalAlpha = 1;
    });
    if (showMinMax) {
        enabled.forEach(team => {
            var td = getPeriodData(team), isHi = team === highlightTeam;
            if (td.length < 2 || td[0].length < 7) return;
            ctx.strokeStyle = data[team].color; ctx.lineWidth = isHi ? 3 : 2; ctx.globalAlpha = isHi ? 1 : (highlightTeam ? 0.3 : 0.7); ctx.setLineDash([8, 4]);
            ctx.beginPath(); td.forEach((p, i) => { var px = xToCanvas(p[0], maxE), py = yToCanvas(p[6], yInfo); i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py); }); ctx.stroke();
            ctx.beginPath(); td.forEach((p, i) => { var px = xToCanvas(p[0], maxE), py = yToCanvas(p[5], yInfo); i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py); }); ctx.stroke();
            ctx.setLineDash([]); ctx.globalAlpha = 1;
        });
    }
    ctx.fillStyle = "#aaa"; ctx.font = "12px Arial"; ctx.textAlign = "center";
    var range = periodElapsedRanges[currentPeriod] || [0, 2880], startMin = range[0] / 60;
    for (var m = 0; m <= 4; m++) { var sec = m * maxE / 4, actualMin = startMin + sec / 60; ctx.fillText(Math.floor(actualMin).toString(), xToCanvas(sec, maxE), canvas.height - 25); }
    ctx.fillText("Minutes", canvas.width / 2, canvas.height - 5);
    ctx.textAlign = "right"; var yStep = Math.ceil(yInfo.range / 8); if (yStep < 1) yStep = 1;
    for (var v = Math.ceil(yInfo.min / yStep) * yStep; v <= yInfo.max; v += yStep) { ctx.fillText((v > 0 ? "+" : "") + v, padding.left - 5, yToCanvas(v, yInfo) + 4); }
}

document.querySelectorAll("#period-selector button").forEach(btn => {
    btn.addEventListener("click", function() {
        currentPeriod = this.dataset.period;
        document.querySelectorAll("#period-selector button").forEach(b => b.classList.remove("active"));
        this.classList.add("active"); renderTeamList(); drawChart(null, null);
    });
});
document.querySelectorAll("#filter-selector button").forEach(btn => {
    btn.addEventListener("click", function() {
        currentFilter = this.dataset.filter;
        document.querySelectorAll("#filter-selector button").forEach(b => b.classList.remove("active"));
        this.classList.add("active"); renderTeamList(); drawChart(null, null);
    });
});
document.getElementById("btn-all").addEventListener("click", () => { teamNames.forEach(t => selectedTeams[t] = true); renderTeamList(); drawChart(null, null); });
document.getElementById("btn-none").addEventListener("click", () => { teamNames.forEach(t => selectedTeams[t] = false); renderTeamList(); drawChart(null, null); });
document.getElementById("show-bands").addEventListener("change", () => drawChart(null, null));
document.getElementById("show-minmax").addEventListener("change", () => drawChart(null, null));

canvas.addEventListener("mousemove", function(e) {
    var rect = canvas.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
    if (x < padding.left || x > canvas.width - padding.right) { tooltip.style.display = "none"; drawChart(null, null); return; }
    var maxE = getMaxElapsed(), yInfo = calculateYRange();
    var elapsed = Math.round(((x - padding.left) / chartWidth) * maxE / 10) * 10;
    var mouseMargin = yInfo.min + (1 - (y - padding.top) / chartHeight) * yInfo.range;
    var closest = null, closestDist = Infinity, closestMargin = null;
    getEnabledTeams().forEach(team => {
        getPeriodData(team).forEach(p => {
            if (Math.abs(p[0] - elapsed) <= 10) { var dist = Math.abs(mouseMargin - p[1]); if (dist <= 2 && dist < closestDist) { closestDist = dist; closest = team; closestMargin = p[1]; } }
        });
    });
    if (!closest) { tooltip.style.display = "none"; drawChart(null, null); return; }
    drawChart(closest, elapsed);
    var range = periodElapsedRanges[currentPeriod] || [0, 2880], actualElapsed = elapsed + range[0];
    var totalMin = Math.floor(actualElapsed / 60), totalSec = Math.floor(actualElapsed % 60);
    document.getElementById("time-label").textContent = "Time: " + totalMin + ":" + (totalSec < 10 ? "0" : "") + totalSec;
    document.getElementById("team-label").textContent = closest; document.getElementById("team-label").style.color = data[closest].color;
    document.getElementById("diff-label").textContent = (closestMargin >= 0 ? "+" : "") + closestMargin.toFixed(1);
    document.getElementById("diff-label").className = "diff " + (closestMargin >= 0 ? "positive" : "negative");
    var periodData = getPeriodData(closest), leadingPct = null;
    for (var i = 0; i < periodData.length; i++) { if (periodData[i][0] === elapsed) { leadingPct = periodData[i][4]; break; } }
    document.getElementById("leading-pct").textContent = leadingPct !== null ? "Leading in " + leadingPct.toFixed(0) + "% of games" : "";
    var lineups = getLineups(closest), lineupKey = currentPeriod === "clutch" ? String(elapsed) : String(actualElapsed), lineup = lineups[lineupKey];
    if (lineup && lineup.length > 0) {
        var htmlStr = ""; for (var i = 0; i < lineup.length; i++) { var p = lineup[i]; htmlStr += '<div class="player"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/' + p[0] + '.png"><span>' + p[1] + '</span></div>'; }
        document.getElementById("headshots").innerHTML = htmlStr;
    } else { document.getElementById("headshots").innerHTML = ""; }
    tooltip.style.display = "block"; tooltip.style.borderColor = data[closest].color;
    tooltip.style.left = (x + 15) + "px"; tooltip.style.top = Math.max(0, y - 100) + "px";
});
canvas.addEventListener("mouseleave", () => { tooltip.style.display = "none"; drawChart(null, null); });

// ==================== WIN PROBABILITY HEATMAP ====================
var hmCanvas = document.getElementById("heatmap-canvas");
var hmCtx = hmCanvas.getContext("2d");
var hmTooltip = document.getElementById("heatmap-tooltip");
var hmPadding = { left: 50, right: 20, top: 20, bottom: 40 };
var hmWidth = hmCanvas.width - hmPadding.left - hmPadding.right;
var hmHeight = hmCanvas.height - hmPadding.top - hmPadding.bottom;
var hmSelectedTeam = "_league";

var hmSelect = document.getElementById("heatmap-team");
teamNames.forEach(team => { var opt = document.createElement("option"); opt.value = team; opt.textContent = team; hmSelect.appendChild(opt); });

function winPctToColor(pct) {
    if (pct <= 50) { var t = pct / 50; return "rgb(220," + Math.round(38 + t * 149) + "," + Math.round(38 - t * 2) + ")"; }
    else { var t = (pct - 50) / 50; return "rgb(" + Math.round(251 - t * 217) + "," + Math.round(191 + t * 6) + "," + Math.round(36 + t * 58) + ")"; }
}

function drawHeatmap() {
    hmCtx.clearRect(0, 0, hmCanvas.width, hmCanvas.height);
    var winProb = data[hmSelectedTeam] ? data[hmSelectedTeam].win_prob || {} : {};
    var cellWidth = hmWidth / 49, cellHeight = hmHeight / 51;
    for (var m = 0; m <= 48; m++) {
        for (var margin = -25; margin <= 25; margin++) {
            var key = m + "," + margin, x = hmPadding.left + m * cellWidth, y = hmPadding.top + (25 - margin) * cellHeight;
            hmCtx.fillStyle = winProb[key] ? winPctToColor(winProb[key][0]) : "#1a1a2e";
            hmCtx.fillRect(x, y, cellWidth + 1, cellHeight + 1);
        }
    }
    var zeroY = hmPadding.top + 25 * cellHeight;
    hmCtx.strokeStyle = "#fff"; hmCtx.lineWidth = 1; hmCtx.setLineDash([5, 5]);
    hmCtx.beginPath(); hmCtx.moveTo(hmPadding.left, zeroY); hmCtx.lineTo(hmCanvas.width - hmPadding.right, zeroY); hmCtx.stroke(); hmCtx.setLineDash([]);
    hmCtx.strokeStyle = "#666"; [12, 24, 36].forEach(q => { var qx = hmPadding.left + q * cellWidth; hmCtx.beginPath(); hmCtx.moveTo(qx, hmPadding.top); hmCtx.lineTo(qx, hmCanvas.height - hmPadding.bottom); hmCtx.stroke(); });
    hmCtx.fillStyle = "#aaa"; hmCtx.font = "11px Arial"; hmCtx.textAlign = "center";
    [0, 12, 24, 36, 48].forEach(m => { hmCtx.fillText(m.toString(), hmPadding.left + m * cellWidth, hmCanvas.height - 10); });
    hmCtx.fillText("Minutes", hmCanvas.width / 2, hmCanvas.height - 25);
    hmCtx.textAlign = "right"; [-20, -10, 0, 10, 20].forEach(margin => { hmCtx.fillText((margin > 0 ? "+" : "") + margin, hmPadding.left - 5, hmPadding.top + (25 - margin) * cellHeight + 4); });
    document.getElementById("heatmap-stats").innerHTML = "<strong>" + (hmSelectedTeam === "_league" ? "League" : hmSelectedTeam) + "</strong><br>Data points: " + Object.keys(winProb).length;
}

hmSelect.addEventListener("change", function() { hmSelectedTeam = this.value; drawHeatmap(); });
hmCanvas.addEventListener("mousemove", function(e) {
    var rect = hmCanvas.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
    if (x < hmPadding.left || x > hmCanvas.width - hmPadding.right || y < hmPadding.top || y > hmCanvas.height - hmPadding.bottom) { hmTooltip.style.display = "none"; return; }
    var cellWidth = hmWidth / 49, cellHeight = hmHeight / 51;
    var minute = Math.floor((x - hmPadding.left) / cellWidth), marginIdx = Math.floor((y - hmPadding.top) / cellHeight), margin = 25 - marginIdx;
    minute = Math.max(0, Math.min(48, minute)); margin = Math.max(-25, Math.min(25, margin));
    var key = minute + "," + margin, winProb = data[hmSelectedTeam] ? data[hmSelectedTeam].win_prob || {} : {};
    var content = "<strong>Minute " + minute + ", Margin " + (margin > 0 ? "+" : "") + margin + "</strong><br>";
    if (winProb[key]) { content += "Win %: <span style='color:" + winPctToColor(winProb[key][0]) + "'>" + winProb[key][0].toFixed(1) + "%</span><br>Games: " + winProb[key][1]; }
    else { content += "<em>No data</em>"; }
    hmTooltip.innerHTML = content; hmTooltip.style.display = "block"; hmTooltip.style.left = (x + 15) + "px"; hmTooltip.style.top = (y - 30) + "px";
});
hmCanvas.addEventListener("mouseleave", () => { hmTooltip.style.display = "none"; });

// ==================== THRESHOLD CHART ====================
var thCanvas = document.getElementById("threshold-canvas"), thCtx = thCanvas.getContext("2d"), thTooltip = document.getElementById("threshold-tooltip");
var thPadding = { left: 50, right: 20, top: 20, bottom: 40 }, thChartWidth = thCanvas.width - thPadding.left - thPadding.right, thChartHeight = thCanvas.height - thPadding.top - thPadding.bottom;
var thresholds = []; for (var t = -25; t <= 25; t++) thresholds.push(t);
var thMode = "frequency", thSelectedTeams = {"OKC": true, "CLE": true, "BOS": true, "WAS": true};

function renderThresholdTeamList() {
    var html = ""; teamNames.forEach(team => {
        var color = data[team].color, border = (color === "#FFFFFF" || color === "#C4CED4") ? "border: 1px solid #888;" : "";
        html += '<label><input type="checkbox" id="th-check-' + team + '" ' + (thSelectedTeams[team] ? 'checked' : '') + '><span class="team-color" style="background:' + color + ';' + border + '"></span>' + team + '</label>';
    });
    document.getElementById("threshold-teams").innerHTML = html;
    teamNames.forEach(team => { document.getElementById("th-check-" + team).addEventListener("change", function() { thSelectedTeams[team] = this.checked; drawThresholdChart(); }); });
}

function getThEnabledTeams() { return teamNames.filter(t => thSelectedTeams[t]); }

function drawThresholdChart() {
    thCtx.clearRect(0, 0, thCanvas.width, thCanvas.height);
    var enabled = getThEnabledTeams(), allValues = [0];
    enabled.forEach(team => { var th = data[team].thresholds || {}; thresholds.forEach(t => { var val = th[t] ? th[t][thMode] : null; if (val !== null && val !== undefined) allValues.push(val); }); });
    var yMax = Math.max(...allValues); if (thMode === "win_pct" || thMode === "frequency") yMax = Math.max(yMax, 100); if (yMax < 10) yMax = 10;
    thCtx.strokeStyle = "#333"; thCtx.lineWidth = 1;
    for (var i = 0; i <= 5; i++) { var y = thPadding.top + (i / 5) * thChartHeight; thCtx.beginPath(); thCtx.moveTo(thPadding.left, y); thCtx.lineTo(thCanvas.width - thPadding.right, y); thCtx.stroke(); }
    var zeroX = thPadding.left + (25 / 50) * thChartWidth;
    thCtx.strokeStyle = "#888"; thCtx.lineWidth = 2; thCtx.beginPath(); thCtx.moveTo(zeroX, thPadding.top); thCtx.lineTo(zeroX, thCanvas.height - thPadding.bottom); thCtx.stroke();
    enabled.forEach(team => {
        var th = data[team].thresholds || {}; thCtx.strokeStyle = data[team].color; thCtx.lineWidth = 2; thCtx.beginPath(); var started = false;
        thresholds.forEach((t, i) => { var val = th[t] ? th[t][thMode] : null; if (val === null || val === undefined) { started = false; return; }
            var x = thPadding.left + (i / (thresholds.length - 1)) * thChartWidth, y = thPadding.top + thChartHeight - (val / yMax) * thChartHeight;
            if (!started) { thCtx.moveTo(x, y); started = true; } else { thCtx.lineTo(x, y); }
        }); thCtx.stroke();
    });
    thCtx.fillStyle = "#aaa"; thCtx.font = "11px Arial"; thCtx.textAlign = "center";
    [-25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25].forEach(t => { var idx = t + 25, x = thPadding.left + (idx / 50) * thChartWidth; thCtx.fillText((t > 0 ? "+" : "") + t, x, thCanvas.height - 10); });
    thCtx.fillText("Margin Threshold", thCanvas.width / 2, thCanvas.height - 25);
    thCtx.textAlign = "right"; for (var i = 0; i <= 5; i++) { var val = yMax * (1 - i / 5), y = thPadding.top + (i / 5) * thChartHeight + 4; thCtx.fillText(val.toFixed(0) + "%", thPadding.left - 5, y); }
}

document.querySelectorAll("#threshold-mode button").forEach(btn => {
    btn.addEventListener("click", function() { thMode = this.dataset.mode; document.querySelectorAll("#threshold-mode button").forEach(b => b.classList.remove("active")); this.classList.add("active"); drawThresholdChart(); });
});
document.getElementById("th-btn-all").addEventListener("click", () => { teamNames.forEach(t => thSelectedTeams[t] = true); renderThresholdTeamList(); drawThresholdChart(); });
document.getElementById("th-btn-none").addEventListener("click", () => { teamNames.forEach(t => thSelectedTeams[t] = false); renderThresholdTeamList(); drawThresholdChart(); });
document.getElementById("th-btn-top5").addEventListener("click", () => { teamNames.forEach(t => thSelectedTeams[t] = false); ["OKC", "CLE", "BOS", "HOU", "MEM"].forEach(t => thSelectedTeams[t] = true); renderThresholdTeamList(); drawThresholdChart(); });

thCanvas.addEventListener("mousemove", function(e) {
    var rect = thCanvas.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
    if (x < thPadding.left || x > thCanvas.width - thPadding.right) { thTooltip.style.display = "none"; return; }
    var thIdx = Math.round(((x - thPadding.left) / thChartWidth) * 50); thIdx = Math.max(0, Math.min(50, thIdx)); var threshold = thresholds[thIdx];
    var enabled = getThEnabledTeams();
    var lines = enabled.map(team => { var th = data[team].thresholds || {}, val = th[threshold] ? th[threshold][thMode] : null;
        return '<span style="color:' + data[team].color + '">' + team + ': ' + (val !== null && val !== undefined ? val.toFixed(1) + '%' : 'N/A') + '</span>'; });
    var modeLabel = {frequency: "Frequency", time: "Time at margin", win_pct: "Win %"}[thMode];
    thTooltip.innerHTML = '<strong>Threshold: ' + (threshold > 0 ? '+' : '') + threshold + '</strong><br><em>' + modeLabel + '</em><br>' + lines.join('<br>');
    thTooltip.style.display = "block"; thTooltip.style.left = (x + 15) + "px"; thTooltip.style.top = Math.max(0, y - 50) + "px";
});
thCanvas.addEventListener("mouseleave", () => { thTooltip.style.display = "none"; });

// ==================== CHECKPOINTS TABLE ====================
var cpSortCol = "48", cpSortDir = "desc";
function renderCheckpointsTable() {
    var teams = teamNames.slice();
    teams.sort((a, b) => { var aVal = cpSortCol === "team" ? a : (data[a].checkpoints || {})[cpSortCol] || 0, bVal = cpSortCol === "team" ? b : (data[b].checkpoints || {})[cpSortCol] || 0;
        if (cpSortCol === "team") return cpSortDir === "asc" ? a.localeCompare(b) : b.localeCompare(a); return cpSortDir === "asc" ? aVal - bVal : bVal - aVal; });
    var html = ""; teams.forEach(team => { var cp = data[team].checkpoints || {}, color = data[team].color, border = (color === "#FFFFFF" || color === "#C4CED4") ? "border: 1px solid #888;" : "";
        html += "<tr><td><div class='team-cell'><span class='team-color' style='background:" + color + ";" + border + "'></span>" + team + "</div></td>";
        [6, 12, 18, 24, 30, 36, 42, 48].forEach(m => { var val = cp[m] || 0, cls = val >= 0 ? "highlight-good" : "highlight-bad"; html += '<td class="' + cls + '">' + (val >= 0 ? '+' : '') + val.toFixed(1) + '</td>'; });
        var finalVal = cp["final"] || 0, finalCls = finalVal >= 0 ? "highlight-good" : "highlight-bad"; html += '<td class="' + finalCls + '">' + (finalVal >= 0 ? '+' : '') + finalVal.toFixed(1) + '</td></tr>'; });
    document.getElementById("checkpoints-tbody").innerHTML = html;
    document.querySelectorAll("#checkpoints-table th").forEach(th => { th.classList.remove("sorted-asc", "sorted-desc"); if (th.dataset.col === cpSortCol) th.classList.add(cpSortDir === "asc" ? "sorted-asc" : "sorted-desc"); });
}
document.querySelectorAll("#checkpoints-table th").forEach(th => { th.addEventListener("click", function() { var col = this.dataset.col; if (cpSortCol === col) { cpSortDir = cpSortDir === "asc" ? "desc" : "asc"; } else { cpSortCol = col; cpSortDir = col === "team" ? "asc" : "desc"; } renderCheckpointsTable(); }); });

// ==================== COMEBACK & BLOWN LEAD TABLE ====================
var cbSortCol = "comeback", cbSortDir = "asc";
function getCbValue(team, col) { var cb = data[team].comeback || {}, bl = data[team].blown_lead || {};
    if (col === "team") return team; if (col === "wins") return cb.games || 0; if (col === "comeback") return cb.avg_worst_deficit || 0; if (col === "max_comeback") return cb.max_deficit || 0;
    if (col === "wire_wins") return cb.wins_without_trailing || 0; if (col === "losses") return bl.games || 0; if (col === "blown") return bl.avg_best_lead || 0;
    if (col === "max_blown") return bl.max_lead || 0; if (col === "wire_losses") return bl.losses_without_leading || 0; return 0; }
function renderComebackTable() {
    var teams = teamNames.slice(); teams.sort((a, b) => { var aVal = getCbValue(a, cbSortCol), bVal = getCbValue(b, cbSortCol);
        if (cbSortCol === "team") return cbSortDir === "asc" ? a.localeCompare(b) : b.localeCompare(a); return cbSortDir === "asc" ? aVal - bVal : bVal - aVal; });
    var html = ""; teams.forEach(team => { var cb = data[team].comeback || {}, bl = data[team].blown_lead || {}, color = data[team].color, border = (color === "#FFFFFF" || color === "#C4CED4") ? "border: 1px solid #888;" : "";
        html += "<tr><td><div class='team-cell'><span class='team-color' style='background:" + color + ";" + border + "'></span>" + team + "</div></td>";
        html += '<td>' + (cb.games || 0) + '</td><td class="highlight-bad">' + (cb.avg_worst_deficit || 0).toFixed(1) + '</td><td class="highlight-bad">' + (cb.max_deficit || 0) + '</td><td class="highlight-good">' + (cb.wins_without_trailing || 0) + '</td>';
        html += '<td>' + (bl.games || 0) + '</td><td class="highlight-good">+' + (bl.avg_best_lead || 0).toFixed(1) + '</td><td class="highlight-good">+' + (bl.max_lead || 0) + '</td><td class="highlight-bad">' + (bl.losses_without_leading || 0) + '</td></tr>'; });
    document.getElementById("comeback-tbody").innerHTML = html;
    document.querySelectorAll("#comeback-table th").forEach(th => { th.classList.remove("sorted-asc", "sorted-desc"); if (th.dataset.col === cbSortCol) th.classList.add(cbSortDir === "asc" ? "sorted-asc" : "sorted-desc"); });
}
document.querySelectorAll("#comeback-table th").forEach(th => { th.addEventListener("click", function() { var col = this.dataset.col; if (cbSortCol === col) { cbSortDir = cbSortDir === "asc" ? "desc" : "asc"; } else { cbSortCol = col; cbSortDir = (col === "comeback" || col === "max_comeback") ? "asc" : (col === "blown" || col === "max_blown" || col === "wire_wins") ? "desc" : "desc"; } renderComebackTable(); }); });

// ==================== GARBAGE TIME TABLE ====================
var gtSortCol = "freq_pct", gtSortDir = "desc";
function getGtValue(team, col) { var gt = data[team].garbage_time || {};
    if (col === "team") return team; if (col === "freq_pct") return gt.frequency_pct || 0; if (col === "total") return gt.total_instances || 0;
    if (col === "wins") return gt.in_wins || 0; if (col === "losses") return gt.in_losses || 0;
    if (col === "win_pct") { var total = gt.total_instances || 0; return total > 0 ? (gt.in_wins || 0) / total * 100 : 0; }
    if (col === "successful") return gt.successful || 0; if (col === "failed") return gt.failed || 0;
    if (col === "success_rate") { var total = gt.total_instances || 0; return total > 0 ? (gt.successful || 0) / total * 100 : 0; }
    if (col === "avg_start") return gt.avg_start || 0; if (col === "avg_duration") return gt.avg_duration || 0; if (col === "avg_diff") return gt.avg_garbage_diff || 0; return 0; }
function renderGarbageTable() {
    var teams = teamNames.slice(); teams.sort((a, b) => { var aVal = getGtValue(a, gtSortCol), bVal = getGtValue(b, gtSortCol);
        if (gtSortCol === "team") return gtSortDir === "asc" ? a.localeCompare(b) : b.localeCompare(a); return gtSortDir === "asc" ? aVal - bVal : bVal - aVal; });
    var html = ""; teams.forEach(team => { var gt = data[team].garbage_time || {}, color = data[team].color, border = (color === "#FFFFFF" || color === "#C4CED4") ? "border: 1px solid #888;" : "";
        var total = gt.total_instances || 0, winPct = total > 0 ? (gt.in_wins || 0) / total * 100 : 0, successRate = total > 0 ? (gt.successful || 0) / total * 100 : 0;
        var avgDiff = gt.avg_garbage_diff || 0, diffColor = avgDiff >= 0 ? "highlight-good" : "highlight-bad";
        html += "<tr><td><div class='team-cell'><span class='team-color' style='background:" + color + ";" + border + "'></span>" + team + "</div></td>";
        html += '<td>' + (gt.frequency_pct || 0).toFixed(1) + '%</td><td>' + total + '</td><td class="highlight-good">' + (gt.in_wins || 0) + '</td><td class="highlight-bad">' + (gt.in_losses || 0) + '</td>';
        html += '<td>' + winPct.toFixed(1) + '%</td><td class="highlight-good">' + (gt.successful || 0) + '</td><td class="highlight-bad">' + (gt.failed || 0) + '</td><td>' + successRate.toFixed(1) + '%</td>';
        html += '<td>' + (gt.avg_start || 0).toFixed(1) + '</td><td>' + (gt.avg_duration || 0).toFixed(1) + ' min</td><td class="' + diffColor + '">' + (avgDiff >= 0 ? '+' : '') + avgDiff.toFixed(1) + '</td></tr>'; });
    document.getElementById("garbage-tbody").innerHTML = html;
    document.querySelectorAll("#garbage-table th").forEach(th => { th.classList.remove("sorted-asc", "sorted-desc"); if (th.dataset.col === gtSortCol) th.classList.add(gtSortDir === "asc" ? "sorted-asc" : "sorted-desc"); });
}
document.querySelectorAll("#garbage-table th").forEach(th => { th.addEventListener("click", function() { var col = this.dataset.col; if (gtSortCol === col) { gtSortDir = gtSortDir === "asc" ? "desc" : "asc"; } else { gtSortCol = col; gtSortDir = col === "team" ? "asc" : "desc"; } renderGarbageTable(); }); });

// ==================== RUNS TABLE ====================
var runsSortCol = "3min_best", runsSortDir = "desc";
function getRunsValue(team, col) { var runs = data[team].runs || {}; if (col === "team") return team; var parts = col.split("_"), duration = parts[0], type = parts[1], r = runs[duration] || {}; return type === "best" ? (r.avg_best || 0) : (r.avg_worst || 0); }
function renderRunsTable() {
    var teams = teamNames.slice(); teams.sort((a, b) => { var aVal = getRunsValue(a, runsSortCol), bVal = getRunsValue(b, runsSortCol);
        if (runsSortCol === "team") return runsSortDir === "asc" ? a.localeCompare(b) : b.localeCompare(a); return runsSortDir === "asc" ? aVal - bVal : bVal - aVal; });
    var durations = ["1min", "3min", "6min", "quarter", "half"];
    var html = ""; teams.forEach(team => { var runs = data[team].runs || {}, color = data[team].color, border = (color === "#FFFFFF" || color === "#C4CED4") ? "border: 1px solid #888;" : "";
        html += "<tr><td><div class='team-cell'><span class='team-color' style='background:" + color + ";" + border + "'></span>" + team + "</div></td>";
        durations.forEach(dur => { var r = runs[dur] || {avg_best: 0, avg_worst: 0}; html += '<td class="highlight-good">+' + r.avg_best.toFixed(1) + '</td><td class="highlight-bad">' + r.avg_worst.toFixed(1) + '</td>'; }); html += "</tr>"; });
    document.getElementById("runs-tbody").innerHTML = html;
    document.querySelectorAll("#runs-table th").forEach(th => { th.classList.remove("sorted-asc", "sorted-desc"); if (th.dataset.col === runsSortCol) th.classList.add(runsSortDir === "asc" ? "sorted-asc" : "sorted-desc"); });
}
document.querySelectorAll("#runs-table th").forEach(th => { th.addEventListener("click", function() { var col = this.dataset.col; if (runsSortCol === col) { runsSortDir = runsSortDir === "asc" ? "desc" : "asc"; } else { runsSortCol = col; runsSortDir = col.includes("_worst") ? "asc" : "desc"; } renderRunsTable(); }); });

// ==================== MAX RUNS TABLE ====================
var maxRunsSortCol = "3min_best", maxRunsSortDir = "desc";
function getMaxRunsValue(team, col) { var runs = data[team].runs || {}; if (col === "team") return team; var parts = col.split("_"), duration = parts[0], type = parts[1], r = runs[duration] || {}; return type === "best" ? (r.max_best || 0) : (r.max_worst || 0); }
function renderMaxRunsTable() {
    var teams = teamNames.slice(); teams.sort((a, b) => { var aVal = getMaxRunsValue(a, maxRunsSortCol), bVal = getMaxRunsValue(b, maxRunsSortCol);
        if (maxRunsSortCol === "team") return maxRunsSortDir === "asc" ? a.localeCompare(b) : b.localeCompare(a); return maxRunsSortDir === "asc" ? aVal - bVal : bVal - aVal; });
    var durations = ["1min", "3min", "6min", "quarter", "half"];
    var html = ""; teams.forEach(team => { var runs = data[team].runs || {}, color = data[team].color, border = (color === "#FFFFFF" || color === "#C4CED4") ? "border: 1px solid #888;" : "";
        html += "<tr><td><div class='team-cell'><span class='team-color' style='background:" + color + ";" + border + "'></span>" + team + "</div></td>";
        durations.forEach(dur => { var r = runs[dur] || {max_best: 0, max_worst: 0}; html += '<td class="highlight-good">+' + (r.max_best || 0) + '</td><td class="highlight-bad">' + (r.max_worst || 0) + '</td>'; }); html += "</tr>"; });
    document.getElementById("max-runs-tbody").innerHTML = html;
    document.querySelectorAll("#max-runs-table th").forEach(th => { th.classList.remove("sorted-asc", "sorted-desc"); if (th.dataset.col === maxRunsSortCol) th.classList.add(maxRunsSortDir === "asc" ? "sorted-asc" : "sorted-desc"); });
}
document.querySelectorAll("#max-runs-table th").forEach(th => { th.addEventListener("click", function() { var col = this.dataset.col; if (maxRunsSortCol === col) { maxRunsSortDir = maxRunsSortDir === "asc" ? "desc" : "asc"; } else { maxRunsSortCol = col; maxRunsSortDir = col.includes("_worst") ? "asc" : "desc"; } renderMaxRunsTable(); }); });

// ==================== BURST FREQUENCY SCATTER PLOT ====================
var burstCanvas = document.getElementById("burst-canvas"), burstCtx = burstCanvas.getContext("2d"), burstTooltip = document.getElementById("burst-tooltip");
var burstWindow = "1min", burstPoints = [];
var burstThresholds = { "1min": {min: 3, max: 8, default: 5}, "3min": {min: 6, max: 15, default: 10}, "6min": {min: 10, max: 20, default: 15} };

function updateBurstSlider() { var config = burstThresholds[burstWindow], slider = document.getElementById("burst-thresh-slider");
    slider.min = config.min; slider.max = config.max; slider.value = config.default; document.getElementById("burst-thresh-value").textContent = config.default; }

function drawBurstScatter() {
    var thresh = document.getElementById("burst-thresh-slider").value;
    var pad = {left: 60, right: 30, top: 30, bottom: 60}, w = burstCanvas.width - pad.left - pad.right, h = burstCanvas.height - pad.top - pad.bottom;
    var points = [], minGen = Infinity, maxGen = 0, minAllowed = Infinity, maxAllowed = 0;
    teamNames.forEach(team => { var bf = data[team].burst_freq;
        if (bf && bf[burstWindow] && bf[burstWindow][thresh]) { var d = bf[burstWindow][thresh], periods = data[team].periods;
            var wins = periods && periods.all ? periods.all.wins : 0, losses = periods && periods.all ? periods.all.losses : 0, margin = periods && periods.all ? periods.all.margin : 0;
            points.push({team: team, gen: d.gen, allowed: d.allowed, color: data[team].color, wins: wins, losses: losses, margin: margin});
            minGen = Math.min(minGen, d.gen); maxGen = Math.max(maxGen, d.gen); minAllowed = Math.min(minAllowed, d.allowed); maxAllowed = Math.max(maxAllowed, d.allowed); } });
    if (points.length === 0) { minGen = 0; maxGen = 1; minAllowed = 0; maxAllowed = 1; }
    var range = Math.max(maxGen - minGen, maxAllowed - minAllowed, 0.5) * 1.3;
    var lo = Math.min(minGen, minAllowed) - range * 0.1, hi = Math.max(maxGen, maxAllowed) + range * 0.1;
    burstCtx.fillStyle = "#1a1a2e"; burstCtx.fillRect(0, 0, burstCanvas.width, burstCanvas.height);
    burstCtx.strokeStyle = "#333"; burstCtx.lineWidth = 1;
    for (var i = lo; i <= hi; i += (hi - lo) / 5) { var x = pad.left + ((i - lo) / (hi - lo)) * w, y = pad.top + h - ((i - lo) / (hi - lo)) * h;
        burstCtx.beginPath(); burstCtx.moveTo(x, pad.top); burstCtx.lineTo(x, pad.top + h); burstCtx.stroke();
        burstCtx.beginPath(); burstCtx.moveTo(pad.left, y); burstCtx.lineTo(pad.left + w, y); burstCtx.stroke(); }
    burstCtx.strokeStyle = "#666"; burstCtx.setLineDash([5, 5]); burstCtx.beginPath(); burstCtx.moveTo(pad.left, pad.top + h); burstCtx.lineTo(pad.left + w, pad.top); burstCtx.stroke(); burstCtx.setLineDash([]);
    points.forEach(p => { var x = pad.left + ((p.gen - lo) / (hi - lo)) * w, y = pad.top + h - ((p.allowed - lo) / (hi - lo)) * h; p.screenX = x; p.screenY = y;
        var border = (p.color === "#FFFFFF" || p.color === "#C4CED4") ? "#888" : p.color;
        burstCtx.beginPath(); burstCtx.arc(x, y, 6, 0, Math.PI * 2); burstCtx.fillStyle = p.color; burstCtx.fill(); burstCtx.strokeStyle = border; burstCtx.lineWidth = 1; burstCtx.stroke(); });
    burstCtx.font = "9px Arial"; burstCtx.fillStyle = "#fff"; burstCtx.textAlign = "left";
    points.forEach(p => { burstCtx.fillText(p.team, p.screenX + 8, p.screenY + 3); });
    burstCtx.fillStyle = "#aaa"; burstCtx.font = "12px Arial"; burstCtx.textAlign = "center";
    burstCtx.fillText("Generated per Game", pad.left + w/2, burstCanvas.height - 10);
    burstCtx.save(); burstCtx.translate(15, pad.top + h/2); burstCtx.rotate(-Math.PI/2); burstCtx.fillText("Allowed per Game", 0, 0); burstCtx.restore();
    burstPoints = points;
}

document.querySelectorAll(".burst-window-btn").forEach(btn => { btn.addEventListener("click", function() {
    document.querySelectorAll(".burst-window-btn").forEach(b => b.classList.remove("active")); this.classList.add("active"); burstWindow = this.dataset.window; updateBurstSlider(); drawBurstScatter(); }); });
document.getElementById("burst-thresh-slider").addEventListener("input", function() { document.getElementById("burst-thresh-value").textContent = this.value; drawBurstScatter(); });
burstCanvas.addEventListener("mousemove", function(e) { var rect = burstCanvas.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top;
    var hovered = null, minDist = 15; burstPoints.forEach(p => { var dist = Math.sqrt(Math.pow(mx - p.screenX, 2) + Math.pow(my - p.screenY, 2)); if (dist < minDist) { minDist = dist; hovered = p; } });
    if (hovered) { var marginStr = hovered.margin >= 0 ? "+" + hovered.margin.toFixed(1) : hovered.margin.toFixed(1);
        burstTooltip.innerHTML = '<div style="font-weight: bold; margin-bottom: 5px;">' + hovered.team + '</div><div>Generated: ' + hovered.gen.toFixed(2) + '/game</div><div>Allowed: ' + hovered.allowed.toFixed(2) + '/game</div><div style="margin-top: 5px;">Record: ' + hovered.wins + '-' + hovered.losses + '</div><div>Avg Margin: ' + marginStr + '</div>';
        burstTooltip.style.display = "block"; burstTooltip.style.left = (e.pageX + 15) + "px"; burstTooltip.style.top = (e.pageY - 10) + "px";
    } else { burstTooltip.style.display = "none"; } });
burstCanvas.addEventListener("mouseleave", function() { burstTooltip.style.display = "none"; });
updateBurstSlider(); drawBurstScatter();

// ==================== LEAD CHANGES BAR CHART ====================
var lcCanvas = document.getElementById("leadchange-canvas"), lcCtx = lcCanvas.getContext("2d");
function drawLeadChangesChart() {
    var pad = {left: 50, right: 120, top: 30, bottom: 40}, w = lcCanvas.width - pad.left - pad.right, h = lcCanvas.height - pad.top - pad.bottom;
    var teams = []; teamNames.forEach(team => { var lc = data[team].lead_changes; if (lc && lc.games > 0) { teams.push({team: team, avg: lc.avg, std: lc.std, color: data[team].color}); } });
    teams.sort((a, b) => b.avg - a.avg); if (teams.length === 0) return;
    var maxVal = 0; teams.forEach(t => { maxVal = Math.max(maxVal, t.avg + t.std); }); maxVal = Math.ceil(maxVal / 2) * 2 + 2;
    var barHeight = Math.min(20, h / teams.length - 2), barGap = (h - barHeight * teams.length) / (teams.length + 1);
    lcCtx.fillStyle = "#1a1a2e"; lcCtx.fillRect(0, 0, lcCanvas.width, lcCanvas.height);
    lcCtx.strokeStyle = "#333"; lcCtx.lineWidth = 1; var tickInterval = maxVal <= 10 ? 2 : maxVal <= 20 ? 5 : 10;
    for (var i = 0; i <= maxVal; i += tickInterval) { var x = pad.left + (i / maxVal) * w; lcCtx.beginPath(); lcCtx.moveTo(x, pad.top); lcCtx.lineTo(x, pad.top + h); lcCtx.stroke(); }
    teams.forEach((t, idx) => { var y = pad.top + barGap + idx * (barHeight + barGap), barW = (t.avg / maxVal) * w;
        var border = (t.color === "#FFFFFF" || t.color === "#C4CED4") ? "#888" : t.color;
        lcCtx.fillStyle = t.color; lcCtx.fillRect(pad.left, y, barW, barHeight); lcCtx.strokeStyle = border; lcCtx.lineWidth = 1; lcCtx.strokeRect(pad.left, y, barW, barHeight);
        var errLeft = Math.max(0, ((t.avg - t.std) / maxVal) * w), errRight = ((t.avg + t.std) / maxVal) * w, midY = y + barHeight / 2;
        lcCtx.strokeStyle = "#fff"; lcCtx.lineWidth = 1.5; lcCtx.beginPath(); lcCtx.moveTo(pad.left + errLeft, midY); lcCtx.lineTo(pad.left + errRight, midY); lcCtx.stroke();
        var capH = barHeight * 0.4; lcCtx.beginPath(); lcCtx.moveTo(pad.left + errLeft, midY - capH/2); lcCtx.lineTo(pad.left + errLeft, midY + capH/2); lcCtx.stroke();
        lcCtx.beginPath(); lcCtx.moveTo(pad.left + errRight, midY - capH/2); lcCtx.lineTo(pad.left + errRight, midY + capH/2); lcCtx.stroke();
        lcCtx.fillStyle = "#fff"; lcCtx.font = "11px Arial"; lcCtx.textAlign = "right"; lcCtx.fillText(t.team, pad.left - 5, y + barHeight/2 + 4);
        lcCtx.textAlign = "left"; lcCtx.fillStyle = "#aaa"; lcCtx.fillText(t.avg.toFixed(1) + " ± " + t.std.toFixed(1), pad.left + w + 10, y + barHeight/2 + 4); });
    lcCtx.strokeStyle = "#888"; lcCtx.lineWidth = 2; lcCtx.beginPath(); lcCtx.moveTo(pad.left, pad.top + h); lcCtx.lineTo(pad.left + w, pad.top + h); lcCtx.stroke();
    lcCtx.fillStyle = "#aaa"; lcCtx.font = "10px Arial"; lcCtx.textAlign = "center";
    for (var i = 0; i <= maxVal; i += tickInterval) { lcCtx.fillText(i, pad.left + (i / maxVal) * w, pad.top + h + 15); }
    lcCtx.font = "12px Arial"; lcCtx.fillText("Lead Changes per Game", pad.left + w/2, lcCanvas.height - 10);
}
drawLeadChangesChart();

// ==================== TIMEOUT ANALYSIS ====================
var toCanvas = document.getElementById("timeout-canvas"), toCtx = toCanvas.getContext("2d");
var toSelectedTeam = "OKC", toMode = "my_to";
function initTimeoutControls() {
    var select = document.getElementById("timeout-team-select");
    teamNames.forEach(team => { var opt = document.createElement("option"); opt.value = team; opt.textContent = team; if (team === "OKC") opt.selected = true; select.appendChild(opt); });
    select.addEventListener("change", function() { toSelectedTeam = this.value; drawTimeoutChart(); });
    document.querySelectorAll(".timeout-mode-btn").forEach(btn => { btn.addEventListener("click", function() {
        document.querySelectorAll(".timeout-mode-btn").forEach(b => b.classList.remove("active")); this.classList.add("active"); toMode = this.dataset.mode; drawTimeoutChart(); renderTimeoutRankings(); }); });
}
function drawTimeoutChart() {
    var pad = {left: 60, right: 30, top: 30, bottom: 50}, w = toCanvas.width - pad.left - pad.right, h = toCanvas.height - pad.top - pad.bottom;
    toCtx.fillStyle = "#1a1a2e"; toCtx.fillRect(0, 0, toCanvas.width, toCanvas.height);
    var teamData = data[toSelectedTeam]; if (!teamData || !teamData.timeout_analysis) { toCtx.fillStyle = "#888"; toCtx.font = "14px Arial"; toCtx.textAlign = "center"; toCtx.fillText("No timeout data available", toCanvas.width/2, toCanvas.height/2); return; }
    var ta = teamData.timeout_analysis, myData = ta.my_to || {curve: [], count: 0}, oppData = ta.opp_to || {curve: [], count: 0}, allData = ta.all_to || {curve: [], count: 0};
    var curves = []; if (toMode === "my_to") { curves.push({data: myData.curve, color: "#4ade80", label: "My TO (" + myData.count + ")"}); }
    else if (toMode === "opp_to") { curves.push({data: oppData.curve, color: "#f87171", label: "Opp TO (" + oppData.count + ")"}); }
    else if (toMode === "both") { curves.push({data: allData.curve, color: "#60a5fa", label: "All TOs (" + allData.count + ")"}); }
    var allVals = []; curves.forEach(c => { allVals = allVals.concat(c.data); });
    var minY = Math.min(0, ...allVals), maxY = Math.max(0, ...allVals), range = Math.max(Math.abs(minY), Math.abs(maxY), 1); range = Math.ceil(range) + 1; minY = -range; maxY = range;
    toCtx.strokeStyle = "#333"; toCtx.lineWidth = 1; for (var y = minY; y <= maxY; y += 1) { var py = pad.top + h * (1 - (y - minY) / (maxY - minY)); toCtx.beginPath(); toCtx.moveTo(pad.left, py); toCtx.lineTo(pad.left + w, py); toCtx.stroke(); }
    var zeroY = pad.top + h * (1 - (0 - minY) / (maxY - minY)); toCtx.strokeStyle = "#888"; toCtx.lineWidth = 2; toCtx.beginPath(); toCtx.moveTo(pad.left, zeroY); toCtx.lineTo(pad.left + w, zeroY); toCtx.stroke();
    var zeroX = pad.left + w * (120 / 240); toCtx.strokeStyle = "#888"; toCtx.setLineDash([5, 5]); toCtx.beginPath(); toCtx.moveTo(zeroX, pad.top); toCtx.lineTo(zeroX, pad.top + h); toCtx.stroke(); toCtx.setLineDash([]);
    curves.forEach(curve => { toCtx.strokeStyle = curve.color; toCtx.lineWidth = 3; toCtx.beginPath();
        curve.data.forEach((val, i) => { var x = pad.left + (i / (curve.data.length - 1)) * w, y = pad.top + h * (1 - (val - minY) / (maxY - minY)); if (i === 0) toCtx.moveTo(x, y); else toCtx.lineTo(x, y); }); toCtx.stroke(); });
    toCtx.strokeStyle = "#aaa"; toCtx.lineWidth = 2; toCtx.beginPath(); toCtx.moveTo(pad.left, pad.top); toCtx.lineTo(pad.left, pad.top + h); toCtx.lineTo(pad.left + w, pad.top + h); toCtx.stroke();
    toCtx.fillStyle = "#aaa"; toCtx.font = "10px Arial"; toCtx.textAlign = "center";
    [-120, -60, 0, 60, 120].forEach(t => { var x = pad.left + w * ((t + 120) / 240); toCtx.fillText((t > 0 ? "+" : "") + t + "s", x, pad.top + h + 15); });
    toCtx.font = "12px Arial"; toCtx.fillText("Seconds from Timeout", pad.left + w/2, toCanvas.height - 10);
    toCtx.textAlign = "right"; toCtx.font = "10px Arial"; for (var y = minY; y <= maxY; y += 1) { var py = pad.top + h * (1 - (y - minY) / (maxY - minY)); toCtx.fillText((y > 0 ? "+" : "") + y, pad.left - 5, py + 4); }
    toCtx.font = "11px Arial"; curves.forEach((curve, i) => { var lx = pad.left + 20, ly = pad.top + 20 + i * 18; toCtx.fillStyle = curve.color; toCtx.fillRect(lx, ly - 8, 12, 12); toCtx.fillStyle = "#fff"; toCtx.textAlign = "left"; toCtx.fillText(curve.label, lx + 18, ly + 2); });
}
var toRankingsData = data["_timeout_rankings"] || null;
function renderTimeoutRankings() {
    var container = document.getElementById("timeout-rankings-table"), rankKey = (toMode === "both") ? "all_to" : toMode;
    if (!toRankingsData || !toRankingsData[rankKey]) { container.innerHTML = '<p style="color: #888;">No ranking data available</p>'; return; }
    var rankings = toRankingsData[rankKey], html = '<table class="to-rank-table"><tr><th>Rank</th><th>Team</th><th>TOs</th><th>Before</th><th>After</th><th>Recovery</th></tr>';
    rankings.forEach(function(r, i) { var beforeColor = r.avg_before < 0 ? "#f87171" : "#4ade80", afterColor = r.avg_after > 0 ? "#4ade80" : "#f87171", recColor = r.recovery > 2 ? "#4ade80" : (r.recovery < 1 ? "#f87171" : "#fbbf24");
        html += '<tr><td>' + (i + 1) + '</td><td style="font-weight: bold;">' + r.team + '</td><td>' + r.count + '</td><td style="color: ' + beforeColor + ';">' + (r.avg_before > 0 ? "+" : "") + r.avg_before.toFixed(2) + '</td><td style="color: ' + afterColor + ';">' + (r.avg_after > 0 ? "+" : "") + r.avg_after.toFixed(2) + '</td><td style="color: ' + recColor + '; font-weight: bold;">' + (r.recovery > 0 ? "+" : "") + r.recovery.toFixed(2) + '</td></tr>'; });
    html += '</table>'; container.innerHTML = html;
}
initTimeoutControls(); drawTimeoutChart(); renderTimeoutRankings();

// ==================== PLAYER ACTIVITY TIMELINE ====================
var activityCanvas = document.getElementById("activity-canvas"), activityCtx = activityCanvas.getContext("2d"), activityTooltip = document.getElementById("activity-tooltip");
var selectedActivityPlayers = [], playerColorIndex = 0, playerColors = ["#e94560", "#4ade80", "#60a5fa", "#fbbf24", "#a78bfa", "#f472b6", "#34d399", "#818cf8", "#fb923c", "#22d3d8"];
var activityTeamSelect = document.getElementById("activity-team-select");
teamNames.forEach(function(team) { var opt = document.createElement("option"); opt.value = team; opt.textContent = team; activityTeamSelect.appendChild(opt); });

function renderActivityPlayerList(team) {
    var container = document.getElementById("activity-player-list");
    if (!team || !data[team] || !data[team].player_activity) { container.innerHTML = '<p style="color: #888;">Select a team</p>'; return; }
    var activity = data[team].player_activity, players = Object.keys(activity).map(function(pid) { return {id: pid, name: activity[pid].name, gp: activity[pid].gp || 0, data: activity[pid].data}; });
    players.sort(function(a, b) { if (b.gp !== a.gp) return b.gp - a.gp; return b.data.reduce(function(s, d) { return s + d[1]; }, 0) - a.data.reduce(function(s, d) { return s + d[1]; }, 0); });
    var html = ''; players.forEach(function(p) { var isSelected = selectedActivityPlayers.some(function(sp) { return sp.team === team && sp.playerId === p.id; }), checkId = "activity-check-" + team + "-" + p.id;
        html += '<div style="margin-bottom: 5px;"><input type="checkbox" id="' + checkId + '" ' + (isSelected ? 'checked' : '') + ' data-team="' + team + '" data-pid="' + p.id + '" data-name="' + p.name + '" data-gp="' + p.gp + '">';
        html += '<label for="' + checkId + '" style="color: #ccc; margin-left: 5px; cursor: pointer;">' + p.name + ' <span style="color: #666;">(' + p.gp + 'g)</span></label></div>'; });
    container.innerHTML = html;
    players.forEach(function(p) { var checkId = "activity-check-" + team + "-" + p.id;
        document.getElementById(checkId).addEventListener("change", function() { var t = this.dataset.team, pid = this.dataset.pid, name = this.dataset.name, gp = parseInt(this.dataset.gp) || 0;
            if (this.checked) { var pdata = data[t].player_activity[pid].data, color = playerColors[playerColorIndex % playerColors.length]; playerColorIndex++;
                selectedActivityPlayers.push({team: t, playerId: pid, name: name, gp: gp, color: color, data: pdata}); }
            else { selectedActivityPlayers = selectedActivityPlayers.filter(function(sp) { return !(sp.team === t && sp.playerId === pid); }); }
            renderActivePlayersList(); drawActivityChart(); }); });
}
function renderActivePlayersList() {
    var container = document.getElementById("activity-active-list");
    if (selectedActivityPlayers.length === 0) { container.innerHTML = '<p style="color: #666; font-size: 12px;">No players selected</p>'; return; }
    var html = ''; selectedActivityPlayers.forEach(function(sp, idx) {
        html += '<div style="margin-bottom: 8px; display: flex; align-items: center; gap: 6px;"><span style="color:' + sp.color + '; font-size: 14px;">■</span>';
        html += '<span style="color: #ccc; font-size: 12px; flex: 1;">' + sp.name + ' <span style="color: #666;">(' + sp.team + ')</span></span>';
        html += '<button data-idx="' + idx + '" class="remove-player-btn" style="background: #e74c3c; color: white; border: none; border-radius: 3px; padding: 2px 6px; cursor: pointer; font-size: 10px;">✕</button></div>'; });
    container.innerHTML = html;
    document.querySelectorAll('.remove-player-btn').forEach(function(btn) { btn.addEventListener('click', function() { var idx = parseInt(this.dataset.idx), removed = selectedActivityPlayers[idx];
        selectedActivityPlayers.splice(idx, 1); var checkId = "activity-check-" + removed.team + "-" + removed.playerId, checkbox = document.getElementById(checkId); if (checkbox) checkbox.checked = false;
        renderActivePlayersList(); drawActivityChart(); }); });
}
function drawActivityChart() {
    var ctx = activityCtx, width = activityCanvas.width, height = activityCanvas.height, pad = {left: 50, right: 20, top: 30, bottom: 50}, chartW = width - pad.left - pad.right, chartH = height - pad.top - pad.bottom;
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "#444"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, height - pad.bottom); ctx.lineTo(width - pad.right, height - pad.bottom); ctx.stroke();
    ctx.fillStyle = "#888"; ctx.font = "11px sans-serif"; ctx.textAlign = "right";
    for (var pct = 0; pct <= 100; pct += 20) { var y = pad.top + chartH * (1 - pct / 100); ctx.fillText(pct + "%", pad.left - 5, y + 4); ctx.strokeStyle = "#333"; ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke(); }
    ctx.textAlign = "center"; for (var min = 0; min <= 48; min += 6) { var x = pad.left + (min / 48) * chartW; ctx.fillText(min + "m", x, height - pad.bottom + 15); }
    ctx.strokeStyle = "#555"; ctx.setLineDash([3, 3]); [12, 24, 36].forEach(function(min) { var x = pad.left + (min / 48) * chartW; ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, height - pad.bottom); ctx.stroke(); }); ctx.setLineDash([]);
    selectedActivityPlayers.forEach(function(sp) { ctx.strokeStyle = sp.color; ctx.lineWidth = 2; ctx.beginPath();
        sp.data.forEach(function(d, i) { var elapsed = d[0], pct = d[1]; if (elapsed > 2880) return; var x = pad.left + (elapsed / 2880) * chartW, y = pad.top + chartH * (1 - pct / 100); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }); ctx.stroke(); });
    ctx.font = "11px sans-serif"; ctx.textAlign = "left"; selectedActivityPlayers.forEach(function(sp, i) { var lx = pad.left + 10, ly = pad.top + 15 + i * 15;
        ctx.fillStyle = sp.color; ctx.fillRect(lx, ly - 8, 12, 12); ctx.fillStyle = "#ccc"; ctx.fillText(sp.name + " (" + sp.team + ", " + sp.gp + "g)", lx + 18, ly + 2); });
}
activityTeamSelect.addEventListener("change", function() { renderActivityPlayerList(this.value); });
document.getElementById("activity-clear-btn").addEventListener("click", function() { selectedActivityPlayers = []; playerColorIndex = 0; renderActivityPlayerList(activityTeamSelect.value); renderActivePlayersList(); drawActivityChart(); });
drawActivityChart();

// ==================== GAME SHAPE CLUSTERS ====================
var clusterCanvas = document.getElementById("cluster-canvas"), clusterCtx = clusterCanvas.getContext("2d"), clusterTooltip = document.getElementById("cluster-tooltip");
var clusterData = data["_clusters"] || null, selectedClusterTeam = "all";
var clusterColors = ["#e94560", "#4ade80", "#60a5fa", "#fbbf24", "#a78bfa"];

function initClusterControls() {
    if (!clusterData) return;
    var select = document.getElementById("cluster-team-select"), teams = new Set();
    clusterData.games.forEach(g => { teams.add(g.home); teams.add(g.away); });
    Array.from(teams).sort().forEach(team => { var opt = document.createElement("option"); opt.value = team; opt.textContent = team; select.appendChild(opt); });
    select.addEventListener("change", function() { selectedClusterTeam = this.value; drawClusterScatter(); });
    var legend = document.getElementById("cluster-legend"), html = "";
    clusterData.names.forEach((name, i) => { var count = clusterData.games.filter(g => g.cluster === i).length;
        html += '<div style="margin-bottom: 12px;"><div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">';
        html += '<span style="display: inline-block; width: 12px; height: 12px; background: ' + clusterColors[i] + '; border-radius: 50%;"></span>';
        html += '<span style="color: #fff; font-size: 11px;">' + name + ' (' + count + ')</span></div>';
        html += '<canvas id="centroid-' + i + '" width="180" height="40" style="background: #0f3460; border-radius: 4px;"></canvas></div>'; });
    legend.innerHTML = html;
    clusterData.centroids.forEach((centroid, i) => { drawCentroidMini(i, centroid); });
}
function drawCentroidMini(idx, centroid) {
    var canvas = document.getElementById("centroid-" + idx); if (!canvas) return;
    var ctx = canvas.getContext("2d"), w = canvas.width, h = canvas.height, pad = {left: 5, right: 5, top: 8, bottom: 8}, cw = w - pad.left - pad.right, ch = h - pad.top - pad.bottom;
    var minY = Math.min(0, ...centroid), maxY = Math.max(0, ...centroid), range = Math.max(maxY - minY, 1);
    var zeroY = pad.top + ch * (maxY / range); ctx.strokeStyle = "#666"; ctx.lineWidth = 1; ctx.setLineDash([2, 2]); ctx.beginPath(); ctx.moveTo(pad.left, zeroY); ctx.lineTo(w - pad.right, zeroY); ctx.stroke(); ctx.setLineDash([]);
    ctx.strokeStyle = clusterColors[idx]; ctx.lineWidth = 2; ctx.beginPath();
    centroid.forEach((val, j) => { var x = pad.left + (j / 7) * cw, y = pad.top + ch * ((maxY - val) / range); if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }); ctx.stroke();
}
function drawClusterScatter() {
    if (!clusterData) { clusterCtx.fillStyle = "#1a1a2e"; clusterCtx.fillRect(0, 0, clusterCanvas.width, clusterCanvas.height); clusterCtx.fillStyle = "#888"; clusterCtx.font = "14px Arial"; clusterCtx.textAlign = "center"; clusterCtx.fillText("No cluster data available", clusterCanvas.width/2, clusterCanvas.height/2); return; }
    var pad = {left: 50, right: 30, top: 30, bottom: 50}, w = clusterCanvas.width - pad.left - pad.right, h = clusterCanvas.height - pad.top - pad.bottom;
    var games = clusterData.games; if (selectedClusterTeam !== "all") { games = games.filter(g => g.home === selectedClusterTeam || g.away === selectedClusterTeam); }
    var allGames = clusterData.games, minX = Math.min(...allGames.map(g => g.pc1)), maxX = Math.max(...allGames.map(g => g.pc1)), minY = Math.min(...allGames.map(g => g.pc2)), maxY = Math.max(...allGames.map(g => g.pc2));
    var rangeX = maxX - minX || 1, rangeY = maxY - minY || 1; minX -= rangeX * 0.1; maxX += rangeX * 0.1; minY -= rangeY * 0.1; maxY += rangeY * 0.1;
    clusterCtx.fillStyle = "#1a1a2e"; clusterCtx.fillRect(0, 0, clusterCanvas.width, clusterCanvas.height);
    clusterCtx.strokeStyle = "#333"; clusterCtx.lineWidth = 1;
    for (var i = 0; i <= 4; i++) { var x = pad.left + (i/4) * w, y = pad.top + (i/4) * h; clusterCtx.beginPath(); clusterCtx.moveTo(x, pad.top); clusterCtx.lineTo(x, pad.top + h); clusterCtx.stroke(); clusterCtx.beginPath(); clusterCtx.moveTo(pad.left, y); clusterCtx.lineTo(pad.left + w, y); clusterCtx.stroke(); }
    clusterCtx.strokeStyle = "#888"; clusterCtx.lineWidth = 2; clusterCtx.beginPath(); clusterCtx.moveTo(pad.left, pad.top + h); clusterCtx.lineTo(pad.left + w, pad.top + h); clusterCtx.moveTo(pad.left, pad.top); clusterCtx.lineTo(pad.left, pad.top + h); clusterCtx.stroke();
    clusterCtx.fillStyle = "#aaa"; clusterCtx.font = "12px Arial"; clusterCtx.textAlign = "center"; clusterCtx.fillText("PC1 (Dominance)", pad.left + w/2, clusterCanvas.height - 10);
    clusterCtx.save(); clusterCtx.translate(15, pad.top + h/2); clusterCtx.rotate(-Math.PI/2); clusterCtx.fillText("PC2 (Timing)", 0, 0); clusterCtx.restore();
    clusterCanvas._points = [];
    games.forEach(g => { var x = pad.left + ((g.pc1 - minX) / (maxX - minX)) * w, y = pad.top + h - ((g.pc2 - minY) / (maxY - minY)) * h, color = clusterColors[g.cluster];
        clusterCtx.beginPath(); clusterCtx.arc(x, y, 4, 0, Math.PI * 2); clusterCtx.fillStyle = color; clusterCtx.fill();
        clusterCtx.fillStyle = "rgba(255,255,255,0.7)"; clusterCtx.font = "8px Arial"; clusterCtx.textAlign = "center"; clusterCtx.fillText(g.away + "@" + g.home, x, y - 6);
        clusterCanvas._points.push({x: x, y: y, game: g}); });
    clusterCtx.fillStyle = "#888"; clusterCtx.font = "11px Arial"; clusterCtx.textAlign = "center";
    var title = selectedClusterTeam === "all" ? "All Games" : "Games involving " + selectedClusterTeam; clusterCtx.fillText(title + " (" + games.length + " games)", clusterCanvas.width/2, 15);
}
clusterCanvas.addEventListener("mousemove", function(e) {
    if (!clusterCanvas._points) return; var rect = clusterCanvas.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top, hovered = null;
    for (var i = 0; i < clusterCanvas._points.length; i++) { var p = clusterCanvas._points[i], dist = Math.sqrt((mx - p.x) ** 2 + (my - p.y) ** 2); if (dist < 10) { hovered = p.game; break; } }
    if (hovered) { var g = hovered, winner = g.home_won ? g.home : g.away, clusterName = clusterData.names[g.cluster], dateStr = g.date ? g.date : "";
        clusterTooltip.innerHTML = '<strong>' + g.away + ' @ ' + g.home + '</strong>' + (dateStr ? ' <span style="color:#888;">(' + dateStr + ')</span>' : '') + '<br>Score: ' + g.score + ' (' + winner + ' wins)<br>Lead changes: ' + g.lc + '<br>' + g.home + ' best lead: +' + g.max_home + '<br>' + g.away + ' best lead: +' + g.max_away + '<br><span style="color: ' + clusterColors[g.cluster] + ';">● ' + clusterName + '</span>';
        clusterTooltip.style.display = "block"; clusterTooltip.style.left = (e.pageX + 15) + "px"; clusterTooltip.style.top = (e.pageY - 10) + "px";
    } else { clusterTooltip.style.display = "none"; }
});
clusterCanvas.addEventListener("mouseleave", function() { clusterTooltip.style.display = "none"; });
initClusterControls(); drawClusterScatter();

// Init Tab 1
renderTeamList(); drawChart(null, null); drawHeatmap(); renderThresholdTeamList(); drawThresholdChart();
renderCheckpointsTable(); renderComebackTable(); renderGarbageTable(); renderRunsTable(); renderMaxRunsTable();

// ==================== TAB 2: CLUTCH INDEX ====================
var clutchChart = null, marginChart = null;
var clutchSelectedTeams = new Set();
var allClutchGames = [], clutchTeamStats = {};
const TEAM_COLORS = { ATL:'#E03A3E',BOS:'#007A33',BKN:'#888',CHA:'#1D1160',CHI:'#CE1141',CLE:'#860038',DAL:'#00538C',DEN:'#FEC524',DET:'#C8102E',GSW:'#1D428A',HOU:'#CE1141',IND:'#002D62',LAC:'#C8102E',LAL:'#552583',MEM:'#5D76A9',MIA:'#98002E',MIL:'#00471B',MIN:'#0C2340',NOP:'#0C2340',NYK:'#F58426',OKC:'#007AC1',ORL:'#0077C0',PHI:'#006BB6',PHX:'#E56020',POR:'#E03A3E',SAC:'#5A2D81',SAS:'#C4CED4',TOR:'#CE1141',UTA:'#002B5C',WAS:'#002B5C' };

function initClutch() {
    // Convert games object to array
    allClutchGames = Object.entries(clutchIndexData.games || {}).map(([id, d]) => ({ id, ...d }));
    allClutchGames.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    
    // Build team stats
    var tg = {};
    allClutchGames.forEach(g => {
        [g.home, g.away].forEach(t => { if (t && !tg[t]) tg[t] = []; if (t) tg[t].push(g); });
    });
    Object.entries(tg).forEach(([t, gs]) => {
        var idx = gs.map(g => g.clutch_index);
        clutchTeamStats[t] = { games: gs.length, avg: idx.reduce((a,b)=>a+b,0)/idx.length, max: Math.max(...idx), min: Math.min(...idx) };
    });
    
    Object.keys(clutchTeamStats).forEach(t => clutchSelectedTeams.add(t));
    document.getElementById('clutchGameCount').textContent = allClutchGames.length;
    
    populateClutchTeamList();
    createClutchChart();
    createMarginChart();
    updateClutchSummary();
    
    document.getElementById('clutchMaxGames').addEventListener('change', () => { updateClutchChart(); updateClutchSummary(); });
    document.getElementById('clutchSortOrder').addEventListener('change', updateClutchChart);
    document.getElementById('clutchSelectAll').addEventListener('click', () => { clutchSelectedTeams = new Set(Object.keys(clutchTeamStats)); updateClutchTeamUI(); updateClutchChart(); updateClutchSummary(); });
    document.getElementById('clutchSelectNone').addEventListener('click', () => { clutchSelectedTeams.clear(); updateClutchTeamUI(); updateClutchChart(); updateClutchSummary(); });
}

function populateClutchTeamList() {
    var c = document.getElementById('clutchTeamList');
    c.innerHTML = Object.entries(clutchTeamStats).sort((a,b) => a[0].localeCompare(b[0])).map(([t, s]) => {
        var color = TEAM_COLORS[t] || '#888';
        var border = (color === '#FFFFFF' || color === '#C4CED4') ? 'border: 1px solid #888;' : '';
        return '<div class="team-checkbox" data-team="' + t + '">' +
        '<input type="checkbox" id="clutch-check-' + t + '" ' + (clutchSelectedTeams.has(t)?'checked':'') + '>' +
        '<label for="clutch-check-' + t + '">' +
        '<span class="team-color" style="background:' + color + ';' + border + '"></span>' +
        '<span class="team-name">' + t + '</span>' +
        '<span class="team-record">' + s.avg.toFixed(3) + '</span>' +
        '<span class="team-final" style="color:#ff6b6b;">' + s.max.toFixed(3) + '</span>' +
        '<span class="team-final" style="color:#4ecdc4;">' + s.min.toFixed(3) + '</span>' +
        '</label></div>';
    }).join('');
    c.querySelectorAll('.team-checkbox').forEach(item => {
        item.querySelector('input').addEventListener('change', function() {
            var t = item.dataset.team;
            clutchSelectedTeams.has(t) ? clutchSelectedTeams.delete(t) : clutchSelectedTeams.add(t);
            updateClutchTeamUI(); updateClutchChart(); updateClutchSummary();
        });
    });
}

function updateClutchTeamUI() {
    document.querySelectorAll('#clutchTeamList .team-checkbox').forEach(item => {
        var sel = clutchSelectedTeams.has(item.dataset.team);
        item.querySelector('input').checked = sel;
    });
}

function getFilteredClutchGames() {
    if (!clutchSelectedTeams.size) return [];
    var g = allClutchGames.filter(x => clutchSelectedTeams.has(x.home) || clutchSelectedTeams.has(x.away));
    var ord = document.getElementById('clutchSortOrder').value;
    g.sort((a,b) => ord === 'desc' ? b.clutch_index - a.clutch_index : a.clutch_index - b.clutch_index);
    return g.slice(0, parseInt(document.getElementById('clutchMaxGames').value) || 50);
}

function createClutchChart() {
    var fg = getFilteredClutchGames();
    document.getElementById('clutchShowingCount').textContent = fg.length;
    clutchChart = new Chart(document.getElementById('clutchChart'), {
        type: 'bar',
        data: { labels: fg.map(g => g.away+'@'+g.home), datasets: [{ data: fg.map(g => g.clutch_index), backgroundColor: fg.map(g => getClutchColor(g.clutch_index)), borderRadius: 2 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#222' }, ticks: { color: '#666' } } }, onHover: (e, el) => handleClutchHover(e, el, fg) }
    });
}

function createMarginChart() {
    marginChart = new Chart(document.getElementById('marginChart'), {
        type: 'line',
        data: { datasets: [
            { data: [], borderWidth: 0, fill: { target: 'origin', above: 'rgba(78,205,196,0.4)', below: 'transparent' }, tension: 0.2, pointRadius: 0 },
            { data: [], borderWidth: 0, fill: { target: 'origin', above: 'transparent', below: 'rgba(255,107,107,0.4)' }, tension: 0.2, pointRadius: 0 },
            { data: [], borderColor: '#fff', borderWidth: 2, fill: false, tension: 0.2, pointRadius: 0 }
        ] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { type: 'linear', min: 36, grid: { color: '#2a2a2a' }, ticks: { color: '#888', font: { size: 9 }, stepSize: 2 } }, y: { grid: { color: c => c.tick.value === 0 ? '#888' : '#2a2a2a' }, ticks: { color: '#888', font: { size: 9 }, stepSize: 5, callback: v => (v>0?'+':'')+v } } } }
    });
}

function handleClutchHover(e, el, fg) {
    var tt = document.getElementById('gameTooltip');
    if (el.length) {
        var g = fg[el[0].index];
        tt.querySelector('.matchup').textContent = g.away + ' @ ' + g.home;
        tt.querySelector('.score').textContent = (g.score_away||'?') + ' - ' + (g.score_home||'?');
        tt.querySelector('.winner').textContent = 'Winner: ' + (g.winner||'N/A');
        tt.querySelector('.date').textContent = g.date || '';
        tt.querySelector('.clutch').textContent = 'Clutch: ' + g.clutch_index.toFixed(4);
        tt.querySelector('.details').innerHTML = 'Q4 LC: '+(g.q4_lead_changes||0)+' | OT: '+(g.ot_count||0)+(g.went_to_ot?'<br>🔥 Overtime!':'');
        updateMarginChart(g);
        tt.style.display = 'block';
        var l = e.native.pageX + 25, t = e.native.pageY - 30;
        if (l + 380 > innerWidth) l = e.native.pageX - 385;
        if (t + 380 > innerHeight) t = innerHeight - 400;
        tt.style.left = l + 'px'; tt.style.top = Math.max(10, t) + 'px';
    } else tt.style.display = 'none';
}

function updateMarginChart(g) {
    var pts = [];
    if (g.q4_timeline) g.q4_timeline.forEach(([s,m]) => pts.push({ x: 36+s/60, y: m }));
    if (g.ot_timelines) g.ot_timelines.forEach((ot,i) => ot.forEach(([s,m]) => pts.push({ x: 48+i*5+s/60, y: m })));
    var maxX = pts.length ? Math.ceil(Math.max(...pts.map(p=>p.x))/2)*2 : 48;
    var maxY = Math.ceil((Math.max(...pts.map(p=>Math.abs(p.y)),5)+2)/5)*5;
    document.getElementById('yLabelHome').textContent = g.home || 'HOME';
    document.getElementById('yLabelAway').textContent = g.away || 'AWAY';
    marginChart.data.datasets.forEach(ds => ds.data = [...pts]);
    marginChart.options.scales.x.max = maxX;
    marginChart.options.scales.y.min = -maxY;
    marginChart.options.scales.y.max = maxY;
    marginChart.update('none');
}

function updateClutchChart() {
    var fg = getFilteredClutchGames();
    document.getElementById('clutchShowingCount').textContent = fg.length;
    clutchChart.data.labels = fg.map(g => g.away+'@'+g.home);
    clutchChart.data.datasets[0].data = fg.map(g => g.clutch_index);
    clutchChart.data.datasets[0].backgroundColor = fg.map(g => getClutchColor(g.clutch_index));
    clutchChart.options.onHover = (e, el) => handleClutchHover(e, el, fg);
    clutchChart.update();
}

function getClutchColor(i) { return i < 0.1 ? '#1a5276' : i < 0.2 ? '#2874a6' : i < 0.3 ? '#3498db' : i < 0.4 ? '#5dade2' : i < 0.5 ? '#f39c12' : i < 0.6 ? '#e67e22' : '#e74c3c'; }

function updateClutchSummary() {
    var fg = clutchSelectedTeams.size ? allClutchGames.filter(g => clutchSelectedTeams.has(g.home) || clutchSelectedTeams.has(g.away)) : [];
    document.getElementById('clutchSummaryGames').textContent = fg.length;
    if (!fg.length) { ['clutchSummaryAvg','clutchSummaryMax','clutchSummaryMin'].forEach(id => document.getElementById(id).textContent = '-'); return; }
    var idx = fg.map(g => g.clutch_index);
    document.getElementById('clutchSummaryAvg').textContent = (idx.reduce((a,b)=>a+b,0)/idx.length).toFixed(4);
    document.getElementById('clutchSummaryMax').textContent = Math.max(...idx).toFixed(4);
    document.getElementById('clutchSummaryMin').textContent = Math.min(...idx).toFixed(4);
}

document.addEventListener('mousemove', e => { var tt = document.getElementById('gameTooltip'); if (!document.querySelector('.tab23-chart-container')?.contains(e.target)) tt.style.display = 'none'; });

// Init Tab 2
initClutch();

// ==================== TAB 3: MOMENTUM ====================
var momentumChart = null;
var selectedMomTeams = new Set(['OKC', 'BOS', 'CLE']);

function initMomentum() {
    populateMomTeams();
    createMomChart();
    document.getElementById('momentumModeSelect').addEventListener('change', updateMomChart);
    document.getElementById('momSelectAll').addEventListener('click', () => { selectedMomTeams = new Set(Object.keys(momentumData.teams || {})); updateMomTeamUI(); updateMomChart(); });
    document.getElementById('momSelectNone').addEventListener('click', () => { selectedMomTeams.clear(); updateMomTeamUI(); updateMomChart(); });
    document.getElementById('momSelectTop').addEventListener('click', () => { selectedMomTeams = new Set(['OKC','BOS','CLE','HOU','GSW','MEM']); updateMomTeamUI(); updateMomChart(); });
}

function populateMomTeams() {
    var c = document.getElementById('momentumTeamList');
    c.innerHTML = Object.keys(momentumData.teams || {}).sort().map(t => {
        var color = TEAM_COLORS[t] || '#888';
        var border = (color === '#FFFFFF' || color === '#C4CED4') ? 'border: 1px solid #888;' : '';
        return '<div class="team-checkbox" data-team="' + t + '">' +
        '<input type="checkbox" id="mom-check-' + t + '" ' + (selectedMomTeams.has(t)?'checked':'') + '>' +
        '<label for="mom-check-' + t + '">' +
        '<span class="team-color" style="background:' + color + ';' + border + '"></span>' +
        '<span class="team-name">' + t + '</span>' +
        '</label></div>';
    }).join('');
    c.querySelectorAll('.team-checkbox').forEach(item => {
        item.querySelector('input').addEventListener('change', function() {
            var t = item.dataset.team;
            selectedMomTeams.has(t) ? selectedMomTeams.delete(t) : selectedMomTeams.add(t);
            updateMomTeamUI(); updateMomChart();
        });
    });
}

function updateMomTeamUI() {
    document.querySelectorAll('#momentumTeamList .team-checkbox').forEach(item => {
        var sel = selectedMomTeams.has(item.dataset.team);
        item.querySelector('input').checked = sel;
    });
}

function createMomChart() {
    momentumChart = new Chart(document.getElementById('momentumChart'), {
        type: 'line',
        data: { datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: true, position: 'top', labels: { color: '#888', usePointStyle: true, padding: 15 } }, tooltip: { backgroundColor: '#1a1a1a', borderColor: '#444', borderWidth: 1, callbacks: { label: c => c.raw === null ? c.dataset.label+': N/A' : c.dataset.label+': '+(c.raw>0?'+':'')+c.raw.toFixed(2)+'/min' } } },
            scales: {
                x: { type: 'linear', min: -20, max: 20, grid: { color: '#2a2a2a' }, ticks: { color: '#888', stepSize: 5, callback: v => (v>0?'+':'')+v }, title: { display: true, text: 'Current Margin', color: '#888' } },
                y: { grid: { color: c => c.tick.value === 0 ? '#666' : '#2a2a2a', lineWidth: c => c.tick.value === 0 ? 2 : 1 }, ticks: { color: '#888', callback: v => (v>0?'+':'')+v.toFixed(1) }, title: { display: true, text: 'Velocity (pts/min)', color: '#888' } }
            }
        }
    });
    updateMomChart();
}

function updateMomChart() {
    var mode = document.getElementById('momentumModeSelect').value;
    var ds = [];
    
    // League avg
    var leagueMode = (momentumData.league || {})[mode];
    var ld = leagueMode?.velocity || leagueMode || {};
    var lp = [];
    for (var m = -20; m <= 20; m++) { var d = ld[m]; lp.push({ x: m, y: d && d.mean !== null ? d.mean * 60 : null }); }
    ds.push({ label: 'League', data: lp, borderColor: '#666', borderWidth: 2, borderDash: [5,5], pointRadius: 0, tension: 0.3, spanGaps: true });
    
    // Teams
    selectedMomTeams.forEach(t => {
        var teamMode = (momentumData.teams || {})[t]?.[mode];
        var td = teamMode?.velocity || teamMode || {};
        var pts = [];
        for (var m = -20; m <= 20; m++) { var d = td[m]; pts.push({ x: m, y: d && d.mean !== null && d.n >= 5 ? d.mean * 60 : null }); }
        ds.push({ label: t, data: pts, borderColor: TEAM_COLORS[t] || '#888', borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5, tension: 0.3, spanGaps: true });
    });
    
    momentumChart.data.datasets = ds;
    momentumChart.update();
}

// Init Tab 3
initMomentum();
    </script>
</body>
</html>'''
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Saved {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    generate_html()
