"""
================================================================================
GENERATE PARETO HTML (UNIFIED)
================================================================================

PURPOSE:
    Generates a unified standalone HTML dashboard combining:
    1. Current Season Pareto Analysis (Season Averages, Single Games, DAG)
    2. All-Time Historical Pareto Analysis (3D/4D scatter, top performances)

INPUTS:
    - pareto.json           (current season from compute_pareto.py)
    - alltime_pareto.json   (historical from compute_alltime_pareto.py)

OUTPUT:
    pareto_dashboard.html

USAGE:
    python generate_pareto_html_unified.py

================================================================================
"""

import json
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

CURRENT_SEASON = "2025-26"
PARETO_PATH = "pareto.json"
ALLTIME_PATH = "alltime_pareto.json"
OUTPUT_PATH = "pareto_dashboard.html"
ALLTIME_TOP_N = 100


# =============================================================================
# DATA LOADING
# =============================================================================

def load_json(path, default=None):
    """Load JSON file, return default if not found."""
    if Path(path).exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else {}


def js_escape(obj):
    """Escape object for safe JavaScript embedding."""
    s = json.dumps(obj, ensure_ascii=False)
    s = s.replace('</script>', '<\\/script>')
    return s


# =============================================================================
# PARETO DOMINANCE FUNCTIONS
# =============================================================================

def dominates_3d(a, b):
    """Check if a dominates b in 3D (PPG, RPG, APG)."""
    if a["ppg"] < b["ppg"] or a["rpg"] < b["rpg"] or a["apg"] < b["apg"]:
        return False
    if a["ppg"] > b["ppg"] or a["rpg"] > b["rpg"] or a["apg"] > b["apg"]:
        return True
    return False


def dominates_4d(a, b):
    """Check if a dominates b in 4D (PPG, RPG, APG, STOCKPG)."""
    if a["ppg"] < b["ppg"] or a["rpg"] < b["rpg"] or a["apg"] < b["apg"] or a["stockpg"] < b["stockpg"]:
        return False
    if a["ppg"] > b["ppg"] or a["rpg"] > b["rpg"] or a["apg"] > b["apg"] or a["stockpg"] > b["stockpg"]:
        return True
    return False


def get_top_n_with_ascendants(all_perfs, n, dominates_fn):
    """
    Get top N performances by dominance_pct.
    Also compute which top N performances dominate each other (ascendants).
    """
    # Sort by dominance_pct and take top N
    top_n = sorted(all_perfs, key=lambda x: x.get("dominance_pct", 0), reverse=True)[:n]
    
    # For each performance, find which TOP N performances dominate it
    for p in top_n:
        ascendants = []
        for other in top_n:
            if other is not p and dominates_fn(other, p):
                ascendants.append(f"{other['name']} {other['season']}")
        p['ascendants'] = ascendants
    
    return top_n


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_html():
    print("=" * 60)
    print("GENERATE PARETO HTML (UNIFIED)")
    print("=" * 60)
    
    # Load current season data
    pareto_data = load_json(PARETO_PATH)
    meta = pareto_data.get("meta", {})
    dimensions = meta.get("dimensions", {})
    season_pa = pareto_data.get("playeravg", {}).get(CURRENT_SEASON, {})
    season_gbg = pareto_data.get("gamebygame", {}).get(CURRENT_SEASON, {})
    season_dag = pareto_data.get("dag", {}).get(CURRENT_SEASON, {})
    
    print(f"Season: {CURRENT_SEASON}")
    print(f"Dimensions: {list(dimensions.keys())}")
    
    # Load all-time data
    # Structure: { "meta": {...}, "3D": { "all_performances": [...], "frontier": [...] }, "4D": {...} }
    alltime_data = load_json(ALLTIME_PATH)
    alltime_meta = alltime_data.get("meta", {})
    
    # Get top N from all_performances (sorted by dominance_pct descending)
    # Also compute ascendants (which top-N performances dominate each other)
    all_3d = alltime_data.get("3D", {}).get("all_performances", [])
    all_4d = alltime_data.get("4D", {}).get("all_performances", [])
    
    # Get top N with ascendant computation
    top_100_3d = get_top_n_with_ascendants(all_3d, ALLTIME_TOP_N, dominates_3d)
    top_100_4d = get_top_n_with_ascendants(all_4d, ALLTIME_TOP_N, dominates_4d)
    
    print(f"All-time 3D: {len(all_3d)} total, showing top {len(top_100_3d)}")
    print(f"All-time 4D: {len(all_4d)} total, showing top {len(top_100_4d)}")
    
    # Debug: show ascendant counts
    l1_3d = [p for p in top_100_3d if p.get('layer') == 1]
    if l1_3d:
        sample = l1_3d[0]
        print(f"  Sample L1 ascendants (3D): {sample['name']} -> {len(sample.get('ascendants', []))} dominators")
    
    # Serialize for JavaScript
    season_pa_json = js_escape(season_pa)
    season_gbg_json = js_escape(season_gbg)
    season_dag_json = js_escape(season_dag)
    dimensions_json = js_escape(dimensions)
    top_100_3d_json = js_escape(top_100_3d)
    top_100_4d_json = js_escape(top_100_4d)
    alltime_meta_json = js_escape(alltime_meta)
    
    # Stats for header
    alltime_total = alltime_meta.get("total_in_db", 0)  # Total performances in database
    alltime_3d_frontier = alltime_data.get("3D", {}).get("frontier_count", 0)
    alltime_4d_frontier = alltime_data.get("4D", {}).get("frontier_count", 0)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Build HTML using string replacement (not .format())
    html = get_html_template()
    
    # Replace placeholders
    html = html.replace("{{SEASON}}", CURRENT_SEASON)
    html = html.replace("{{TIMESTAMP}}", timestamp)
    html = html.replace("{{ALLTIME_TOTAL}}", str(alltime_total))
    html = html.replace("{{ALLTIME_3D_FRONTIER}}", str(alltime_3d_frontier))
    html = html.replace("{{ALLTIME_4D_FRONTIER}}", str(alltime_4d_frontier))
    html = html.replace("{{ALLTIME_TOP_N}}", str(ALLTIME_TOP_N))
    html = html.replace("{{SEASON_PA_JSON}}", season_pa_json)
    html = html.replace("{{SEASON_GBG_JSON}}", season_gbg_json)
    html = html.replace("{{SEASON_DAG_JSON}}", season_dag_json)
    html = html.replace("{{DIMENSIONS_JSON}}", dimensions_json)
    html = html.replace("{{TOP_100_3D_JSON}}", top_100_3d_json)
    html = html.replace("{{TOP_100_4D_JSON}}", top_100_4d_json)
    html = html.replace("{{ALLTIME_META_JSON}}", alltime_meta_json)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\nSaved {OUTPUT_PATH}")
    print("=" * 60)


def get_html_template():
    """Return the complete HTML template with {{PLACEHOLDER}} markers."""
    return '''<!DOCTYPE html>
<html>
<head>
    <title>NBA Pareto Analysis {{SEASON}}</title>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 {
            font-size: 2.5rem;
            background: linear-gradient(90deg, #f59e0b, #ef4444);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        .header .subtitle { color: #888; font-size: 1rem; }
        .header .timestamp { color: #666; font-size: 0.8rem; margin-top: 5px; }
        
        /* Meta Info */
        .meta-info { display: flex; gap: 15px; justify-content: center; margin-bottom: 25px; flex-wrap: wrap; }
        .meta-card { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 10px; padding: 12px 20px; text-align: center; }
        .meta-value { font-size: 1.4rem; font-weight: 700; color: #f59e0b; }
        .meta-value.gold { color: #fbbf24; }
        .meta-value.blue { color: #3b82f6; }
        .meta-value.purple { color: #a855f7; }
        .meta-label { font-size: 0.7rem; color: #888; text-transform: uppercase; margin-top: 2px; }
        
        /* Main Layout */
        .main-container { max-width: 1800px; margin: 0 auto; }
        
        /* Tabs */
        .tab-nav { display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #333; flex-wrap: wrap; }
        .tab-btn {
            background: transparent; color: #888; border: none; padding: 12px 24px;
            font-size: 1rem; cursor: pointer; border-bottom: 3px solid transparent;
            margin-bottom: -2px; transition: all 0.2s;
        }
        .tab-btn:hover { color: #fff; }
        .tab-btn.active { color: #f59e0b; border-bottom-color: #f59e0b; }
        .tab-btn.alltime { color: #a855f7; }
        .tab-btn.alltime.active { color: #a855f7; border-bottom-color: #a855f7; }
        .tab-divider { color: #333; padding: 12px 8px; font-size: 1.2rem; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Control Panel */
        .control-panel { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .control-row { display: flex; gap: 20px; flex-wrap: wrap; align-items: center; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        
        /* Toggle Buttons */
        .toggle-group { display: flex; gap: 5px; }
        .toggle-btn {
            background: #0a1628; color: #888; border: 2px solid #333; padding: 10px 20px;
            border-radius: 8px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s;
        }
        .toggle-btn:hover { border-color: #f59e0b; color: #fff; }
        .toggle-btn.active { background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; border-color: #f59e0b; font-weight: 600; }
        .toggle-btn.dim-btn.active { background: linear-gradient(135deg, #3b82f6, #2563eb); border-color: #3b82f6; color: #fff; }
        
        /* Stats Summary */
        .stats-summary { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
        .summary-card { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 10px; padding: 15px 25px; text-align: center; min-width: 140px; }
        .summary-value { font-size: 1.8rem; font-weight: 700; color: #f59e0b; }
        .summary-label { font-size: 0.75rem; color: #888; text-transform: uppercase; margin-top: 3px; }
        
        /* Explainer Box */
        .explainer {
            background: linear-gradient(135deg, #1e3a5f 0%, #0f3460 100%);
            border: 1px solid #2a4a6f; border-radius: 12px; padding: 20px 25px; margin-bottom: 20px;
        }
        .explainer h3 { color: #f59e0b; margin-bottom: 12px; font-size: 1.1rem; }
        .explainer p { color: #ccc; line-height: 1.6; font-size: 0.9rem; }
        .explainer .highlight { color: #fbbf24; font-weight: 600; }
        
        /* Table Container */
        .table-container { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 12px; overflow: hidden; }
        .table-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid #333; }
        .table-title { font-size: 1.1rem; color: #f59e0b; font-weight: 600; }
        .search-box input {
            background: #0a1628; border: 2px solid #333; border-radius: 6px; padding: 8px 12px;
            color: white; font-size: 0.9rem; width: 200px;
        }
        .search-box input:focus { border-color: #f59e0b; outline: none; }
        .table-scroll { max-height: 70vh; overflow-y: auto; }
        .table-scroll::-webkit-scrollbar { width: 8px; }
        .table-scroll::-webkit-scrollbar-track { background: #0a1628; }
        .table-scroll::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
        .table-scroll::-webkit-scrollbar-thumb:hover { background: #f59e0b; }
        
        /* Table */
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        thead { position: sticky; top: 0; z-index: 10; }
        th {
            background: #0a1628; padding: 12px 8px; text-align: right; font-weight: 600;
            color: #888; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.5px;
            cursor: pointer; user-select: none; white-space: nowrap; border-bottom: 2px solid #333; transition: all 0.2s;
        }
        th:hover { color: #f59e0b; background: #0d1d35; }
        th.sorted { color: #f59e0b; }
        th.sorted::after { content: ' ▼'; font-size: 0.6rem; }
        th.sorted.asc::after { content: ' ▲'; }
        td { padding: 10px 8px; border-bottom: 1px solid #2a3a5a; vertical-align: middle; text-align: right; }
        tbody tr { transition: background 0.2s; }
        tbody tr:hover { background: rgba(245, 158, 11, 0.1); }
        
        /* Column types */
        .col-rank { width: 40px; text-align: center !important; color: #f59e0b; font-weight: 700; }
        .col-player { width: 180px; text-align: left !important; }
        .col-team { width: 50px; text-align: center !important; }
        .col-date { width: 90px; text-align: center !important; }
        .col-season { width: 70px; text-align: center !important; }
        .col-strength { width: 80px; text-align: center !important; }
        .col-dim { width: 50px; text-align: center !important; }
        .col-vars { width: 140px; text-align: left !important; }
        .col-stat { width: 55px; }
        .col-layer { width: 60px; text-align: center !important; }
        .col-dom { width: 100px; }
        
        /* Player Cell */
        .player-cell { display: flex; align-items: center; gap: 8px; }
        .player-chip {
            display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
            padding: 4px 8px; border-radius: 6px; transition: all 0.2s;
        }
        .player-chip:hover { background: rgba(245, 158, 11, 0.2); }
        .player-chip.selected { background: rgba(245, 158, 11, 0.3); box-shadow: 0 0 0 2px #f59e0b; }
        .player-headshot { width: 32px; height: 24px; border-radius: 4px; overflow: hidden; background: #0a1628; }
        .player-headshot img { width: 100%; height: 100%; object-fit: cover; }
        .player-img { width: 32px; height: 24px; border-radius: 4px; object-fit: cover; background: #0a1628; }
        .player-name { font-weight: 600; color: #fff; }
        
        /* Team Badge */
        .team-badge { background: #0f3460; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; color: #4ade80; }
        
        /* Strength Badge */
        .strength-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 700; }
        .strength-elite { background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; }
        .strength-high { background: #166534; color: #4ade80; }
        .strength-mid { background: #1e40af; color: #60a5fa; }
        .strength-low { background: #374151; color: #9ca3af; }
        
        /* Dim Badge */
        .dim-badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; background: #581c87; color: #c084fc; }
        
        /* Vars Tags */
        .vars-tag { display: inline-block; background: #1e3a5f; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; color: #60a5fa; margin-right: 3px; }
        
        /* Layer Badge */
        .layer-badge { display: inline-block; padding: 3px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 700; cursor: help; position: relative; }
        .layer-badge.layer-0 { background: linear-gradient(135deg, #f59e0b, #d97706); color: #000; }
        .layer-badge.layer-1 { background: #1e40af; color: #60a5fa; }
        .layer-badge.layer-2 { background: #166534; color: #4ade80; }
        .layer-badge.layer-other { background: #374151; color: #9ca3af; }
        
        /* Tooltip for layer ascendants */
        .layer-badge[data-tooltip]:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #1a1a2e;
            border: 1px solid #fbbf24;
            color: #fff;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            white-space: pre-line;
            text-align: left;
            min-width: 200px;
            max-width: 300px;
            z-index: 100;
            margin-bottom: 5px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        .layer-badge[data-tooltip]:hover::before {
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: #fbbf24;
            margin-bottom: -1px;
            z-index: 101;
        }
        
        /* Dominance Bar */
        .dom-value { font-size: 0.8rem; color: #f59e0b; font-weight: 600; margin-bottom: 3px; }
        .dom-bar { width: 100%; height: 4px; background: #333; border-radius: 2px; overflow: hidden; }
        .dom-fill { height: 100%; background: linear-gradient(90deg, #f59e0b, #ef4444); border-radius: 2px; }
        
        /* Radar Chart */
        .radar-container { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 12px; padding: 20px; max-width: 500px; }
        .radar-container h4 { color: #f59e0b; margin-bottom: 15px; text-align: center; }
        
        /* Layout Grid */
        .pa-layout { display: grid; grid-template-columns: 1fr 350px; gap: 20px; }
        @media (max-width: 1200px) { .pa-layout { grid-template-columns: 1fr; } }
        
        /* 3D Plot Container */
        .plot-container { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 12px; padding: 20px; margin-bottom: 20px; max-width: 900px; margin-left: auto; margin-right: auto; }
        .plot-title { color: #f59e0b; font-size: 1.1rem; font-weight: 600; margin-bottom: 15px; text-align: center; }
        .plot-3d { width: 100%; height: 500px; }
        .plot-legend { display: flex; gap: 20px; justify-content: center; margin-top: 15px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #aaa; }
        .legend-dot { width: 12px; height: 12px; border-radius: 50%; }
        .colorbar-note { text-align: center; color: #888; font-size: 0.8rem; margin-top: 10px; }
        
        /* DAG Container */
        .dag-container { background: linear-gradient(135deg, #16213e 0%, #1a2744 100%); border-radius: 12px; padding: 20px; overflow: visible; position: relative; }
        .dag-svg-wrapper { width: 100%; overflow-x: auto; overflow-y: auto; max-height: 75vh; position: relative; z-index: 1; }
        .dag-svg { display: block; margin: 0 auto; }
        
        /* DAG Stats Panel */
        .dag-stats-panel { display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; }
        .dag-stat-card { background: #0a1628; border-radius: 8px; padding: 12px 20px; text-align: center; }
        .dag-stat-val { font-size: 1.5rem; font-weight: 700; color: #f59e0b; }
        .dag-stat-label { font-size: 0.7rem; color: #888; text-transform: uppercase; margin-top: 2px; }
        
        /* DAG Nodes */
        .dag-node { cursor: pointer; transition: all 0.2s; }
        .dag-node:hover .node-ring { stroke: #fff; stroke-width: 3; filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.6)); }
        .dag-node.selected-ancestor { filter: drop-shadow(0 0 8px #f59e0b); }
        .dag-node.selected-descendant { filter: drop-shadow(0 0 8px #10b981); }
        .dag-node.on-path { filter: drop-shadow(0 0 6px #3b82f6); }
        .dag-node.dimmed { opacity: 0.25; }
        .dag-layer-label { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; fill: #666; font-weight: 600; }
        
        /* DAG Edges */
        .dag-edge { fill: none; pointer-events: none; }
        .dag-edge.single-layer { stroke: #333; stroke-width: 1; opacity: 0.3; }
        .dag-edge.multi-layer { stroke: #444; stroke-width: 0.5; opacity: 0; }
        .dag-edge.hover-connected { stroke: #f59e0b; opacity: 1; }
        .dag-edge.hover-connected.single-layer { stroke-width: 2; }
        .dag-edge.hover-connected.multi-layer { stroke-width: 1; opacity: 0.5; }
        .dag-edge.path-edge { stroke: #3b82f6 !important; stroke-width: 3 !important; opacity: 1 !important; }
        
        /* DAG Search Panel */
        .dag-search-panel {
            position: absolute; top: 10px; right: 0; z-index: 2000;
            display: flex; align-items: flex-start; pointer-events: auto; transition: transform 0.3s ease;
        }
        .dag-search-panel.collapsed { transform: translateX(calc(100% - 36px)); }
        .dag-panel-toggle {
            width: 36px; height: 60px; background: rgba(10, 22, 40, 0.95);
            border: 1px solid #333; border-right: none; border-radius: 10px 0 0 10px;
            color: #f59e0b; font-size: 1rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center; transition: all 0.2s; backdrop-filter: blur(8px);
        }
        .dag-panel-toggle:hover { background: rgba(20, 40, 70, 0.95); color: #fbbf24; }
        .dag-search-panel.collapsed .toggle-arrow { transform: rotate(180deg); }
        .toggle-arrow { transition: transform 0.3s ease; display: inline-block; }
        .dag-panel-content {
            background: rgba(10, 22, 40, 0.95); border: 1px solid #333; border-radius: 0 0 0 10px;
            padding: 12px 16px; display: flex; flex-direction: column; gap: 10px;
            backdrop-filter: blur(8px); min-width: 200px;
        }
        .dag-panel-header { font-size: 0.85rem; color: #f59e0b; font-weight: 600; padding-bottom: 8px; border-bottom: 1px solid #333; margin-bottom: 4px; }
        .dag-search-box { display: flex; flex-direction: column; gap: 6px; }
        .dag-search-box label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .dag-search-wrapper { position: relative; }
        .dag-search-input {
            background: #0f1a2a; border: 2px solid #333; border-radius: 6px; padding: 8px 12px;
            color: white; font-size: 0.9rem; width: 100%; outline: none;
        }
        .dag-search-input:focus { border-color: #f59e0b; }
        .dag-search-input::placeholder { color: #555; }
        .dag-search-arrow-down { color: #555; font-size: 1rem; text-align: center; }
        .dag-reset-btn {
            background: #333; border: none; border-radius: 6px; padding: 8px 14px;
            color: #aaa; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; width: 100%; margin-top: 4px;
        }
        .dag-reset-btn:hover { background: #ef4444; color: white; }
        .dag-path-result { font-size: 0.8rem; color: #888; text-align: center; min-height: 20px; }
        .dag-path-result.found { color: #4ade80; }
        .dag-path-result.not-found { color: #f87171; }
        
        /* DAG Autocomplete */
        .dag-autocomplete {
            position: absolute; top: 100%; left: 0; right: 0; background: #0f1a2a;
            border: 1px solid #444; border-radius: 6px; max-height: 200px; overflow-y: auto;
            display: none; z-index: 3000; margin-top: 4px;
        }
        .dag-autocomplete.active { display: block; }
        .dag-autocomplete-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; cursor: pointer; border-bottom: 1px solid #333; transition: background 0.15s; }
        .dag-autocomplete-item:hover { background: #1a2a4a; }
        .dag-autocomplete-item:last-child { border-bottom: none; }
        .dag-autocomplete-img { width: 32px; height: 24px; border-radius: 4px; object-fit: cover; background: #1a2a4a; }
        .dag-autocomplete-info { flex: 1; min-width: 0; }
        .dag-autocomplete-name { font-size: 0.85rem; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .dag-autocomplete-meta { font-size: 0.7rem; color: #888; }
        
        /* DAG Selected Chip */
        .dag-selected { min-height: 32px; }
        .dag-selected-chip {
            display: inline-flex; align-items: center; gap: 6px;
            background: linear-gradient(135deg, #1e3a5f, #0f2a4a); border: 1px solid #3b82f6;
            border-radius: 16px; padding: 3px 8px 3px 3px;
        }
        .dag-selected-chip.ancestor { border-color: #f59e0b; }
        .dag-selected-chip.descendant { border-color: #10b981; }
        .dag-selected-chip img { width: 24px; height: 18px; border-radius: 8px; object-fit: cover; }
        .dag-selected-chip span { font-size: 0.75rem; color: #fff; }
        .dag-chip-remove {
            width: 16px; height: 16px; border-radius: 50%; background: #444; border: none;
            color: #aaa; font-size: 11px; cursor: pointer; display: flex; align-items: center;
            justify-content: center; margin-left: 2px; transition: all 0.15s;
        }
        .dag-chip-remove:hover { background: #ef4444; color: white; }
        
        /* DAG Tooltip */
        .dag-tooltip {
            position: fixed; background: rgba(26, 26, 46, 0.92); border: 2px solid #f59e0b;
            border-radius: 12px; padding: 0; z-index: 1000; pointer-events: none;
            opacity: 0; transition: opacity 0.15s; min-width: 240px; max-width: 320px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5); backdrop-filter: blur(8px);
        }
        .dag-tooltip.visible { opacity: 1; }
        .dag-tt-header {
            display: flex; align-items: center; gap: 12px; padding: 12px;
            background: rgba(13, 13, 26, 0.85); border-radius: 10px 10px 0 0; border-bottom: 2px solid #f59e0b;
        }
        .dag-tt-header img { width: 50px; height: 38px; object-fit: cover; border-radius: 6px; background: #0a1628; }
        .dag-tt-name { font-weight: 700; font-size: 1rem; color: #fff; }
        .dag-tt-team { font-size: 0.8rem; color: #4ade80; font-weight: 600; }
        .dag-tt-body { padding: 12px; }
        .dag-tt-layer {
            display: inline-block; background: linear-gradient(135deg, #f59e0b, #d97706);
            color: #000; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem; margin-bottom: 10px;
        }
        .dag-tt-counts { display: flex; gap: 10px; margin-bottom: 10px; }
        .dag-tt-count { background: #0a1628; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; }
        .dag-tt-count strong { color: #f59e0b; }
        .dag-tt-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
        .dag-tt-stat { text-align: center; }
        .dag-tt-stat-val { font-weight: 700; font-size: 1rem; color: #f59e0b; }
        .dag-tt-stat-label { font-size: 0.65rem; color: #888; text-transform: uppercase; }
        .dag-tt-relation { padding-top: 8px; border-top: 1px solid #333; font-size: 0.75rem; color: #aaa; line-height: 1.5; }
        .dag-tt-relation-label { color: #888; font-weight: 600; }
        .dag-tt-relation-names { color: #60a5fa; }
        
        /* Methodology */
        .methodology { background: #0a1628; border: 1px solid #333; border-radius: 12px; padding: 30px; max-width: 900px; }
        .methodology h2 { color: #f59e0b; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px; }
        .methodology h3 { color: #60a5fa; margin: 25px 0 15px 0; }
        .methodology p { color: #bbb; line-height: 1.7; margin-bottom: 12px; }
        .methodology ul { margin: 10px 0 10px 25px; color: #aaa; }
        .methodology li { margin: 8px 0; line-height: 1.5; }
        .methodology code { background: #1e3a5f; padding: 2px 6px; border-radius: 4px; color: #4ade80; font-family: monospace; }
        .methodology .formula {
            background: #0f1a2a; border: 1px solid #2a4a6f; border-radius: 8px;
            padding: 15px 20px; margin: 15px 0; font-family: monospace; color: #f59e0b; overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏀 NBA Pareto Analysis</h1>
        <div class="subtitle">{{SEASON}} Season + All-Time Historical</div>
        <div class="timestamp">Generated: {{TIMESTAMP}}</div>
    </div>
    
    <div class="meta-info">
        <div class="meta-card"><div class="meta-value gold">{{SEASON}}</div><div class="meta-label">Current Season</div></div>
        <div class="meta-card"><div class="meta-value">{{ALLTIME_TOTAL}}</div><div class="meta-label">Historical Seasons</div></div>
        <div class="meta-card"><div class="meta-value blue">{{ALLTIME_3D_FRONTIER}}</div><div class="meta-label">3D Frontier</div></div>
        <div class="meta-card"><div class="meta-value purple">{{ALLTIME_4D_FRONTIER}}</div><div class="meta-label">4D Frontier</div></div>
    </div>
    
    <div class="main-container">
        <div class="tab-nav">
            <button class="tab-btn active" data-tab="playeravg">📊 Season Averages</button>
            <button class="tab-btn" data-tab="gamebygame">🎯 Single Games</button>
            <button class="tab-btn" data-tab="dag">🔗 Dominance Graph</button>
            <span class="tab-divider">│</span>
            <button class="tab-btn alltime" data-tab="alltime3d">🏆 All-Time 3D</button>
            <button class="tab-btn alltime" data-tab="alltime4d">🏆 All-Time 4D</button>
            <span class="tab-divider">│</span>
            <button class="tab-btn" data-tab="methodology">📐 Methodology</button>
        </div>
        
        <!-- SEASON AVERAGES TAB -->
        <div id="tab-playeravg" class="tab-content active">
            <div class="control-panel">
                <div class="control-row">
                    <div class="control-group">
                        <span class="control-label">Dimensions</span>
                        <div class="toggle-group">
                            <button class="toggle-btn dim-btn active" data-dim="6d" onclick="setPlayerAvgDim('6d')">6D Full</button>
                            <button class="toggle-btn dim-btn" data-dim="3d" onclick="setPlayerAvgDim('3d')">3D Traditional</button>
                        </div>
                    </div>
                    <div class="control-group">
                        <span class="control-label">Filter</span>
                        <div class="toggle-group">
                            <button class="toggle-btn filter-btn active" data-filter="none" onclick="setPlayerAvgFilter('none')">All Players</button>
                            <button class="toggle-btn filter-btn" data-filter="min15" onclick="setPlayerAvgFilter('min15')">MPG ≥ 15</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="stats-summary">
                <div class="summary-card"><div class="summary-value" id="pa-frontier-count">0</div><div class="summary-label">Frontier Size</div></div>
                <div class="summary-card"><div class="summary-value" id="pa-total-subsets">63</div><div class="summary-label">Total Subsets</div></div>
                <div class="summary-card"><div class="summary-value" id="pa-avg-strength">0</div><div class="summary-label">Avg Strength</div></div>
            </div>
            <div class="explainer">
                <h3>🏆 What is the Pareto Frontier?</h3>
                <p>The <span class="highlight">Pareto frontier</span> contains players who are <span class="highlight">not dominated</span> by any other player. A player X dominates player Y if X is <span class="highlight">≥ in ALL dimensions</span> and <span class="highlight">&gt; in at least one</span>. Frontier members represent unique, incomparable excellence.</p>
            </div>
            <div class="pa-layout">
                <div class="table-container">
                    <div class="table-scroll"><table id="pa-table"><thead id="pa-thead"></thead><tbody id="pa-tbody"></tbody></table></div>
                </div>
                <div class="radar-container">
                    <h4>Radar Comparison (click players)</h4>
                    <canvas id="pa-radar-chart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- SINGLE GAMES TAB -->
        <div id="tab-gamebygame" class="tab-content">
            <div class="control-panel">
                <div class="control-row">
                    <div class="control-group">
                        <span class="control-label">Dimensions</span>
                        <div class="toggle-group">
                            <button class="toggle-btn dim-btn active" data-dim="6d" onclick="setGbgDim('6d')">6D Full</button>
                            <button class="toggle-btn dim-btn" data-dim="3d" onclick="setGbgDim('3d')">3D Traditional</button>
                        </div>
                    </div>
                    <div class="control-group">
                        <span class="control-label">Filter</span>
                        <div class="toggle-group">
                            <button class="toggle-btn filter-btn active" data-filter="none" onclick="setGbgFilter('none')">All Games</button>
                            <button class="toggle-btn filter-btn" data-filter="min15" onclick="setGbgFilter('min15')">MIN ≥ 15</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="stats-summary">
                <div class="summary-card"><div class="summary-value" id="gbg-frontier-count">0</div><div class="summary-label">Frontier Size</div></div>
                <div class="summary-card"><div class="summary-value" id="gbg-total-subsets">63</div><div class="summary-label">Total Subsets</div></div>
            </div>
            <div class="table-container">
                <div class="table-scroll"><table id="gbg-table"><thead id="gbg-thead"></thead><tbody id="gbg-tbody"></tbody></table></div>
            </div>
        </div>
        
        <!-- DAG TAB -->
        <div id="tab-dag" class="tab-content">
            <div class="control-panel">
                <div class="control-row">
                    <div class="control-group">
                        <span class="control-label">Dimensions</span>
                        <div class="toggle-group">
                            <button class="toggle-btn dim-btn active" data-dim="6d" onclick="setDagDim('6d')">6D Full</button>
                            <button class="toggle-btn dim-btn" data-dim="3d" onclick="setDagDim('3d')">3D Traditional</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="dag-stats-panel" id="dag-stats-panel"></div>
            <div class="explainer">
                <h3>🔗 Dominance Hierarchy (DAG)</h3>
                <p>This graph shows the <span class="highlight">Pareto dominance structure</span> for top 150 players. <span class="highlight">Layer 0</span> (gold) is the Pareto frontier. Edges show direct dominance. Hover for details.</p>
            </div>
            <div class="dag-container">
                <div class="dag-search-panel collapsed" id="dag-search-panel">
                    <button class="dag-panel-toggle" onclick="toggleDagPanel()"><span class="toggle-arrow">◀</span></button>
                    <div class="dag-panel-content">
                        <div class="dag-panel-header">🔍 Path Finder</div>
                        <div class="dag-search-box">
                            <label>Ancestor (↑)</label>
                            <div class="dag-search-wrapper">
                                <input type="text" class="dag-search-input" id="dag-ancestor-input" placeholder="Type name..." autocomplete="off">
                                <div class="dag-autocomplete" id="dag-ancestor-dropdown"></div>
                            </div>
                            <div class="dag-selected" id="dag-ancestor-selected"></div>
                        </div>
                        <div class="dag-search-arrow-down">↓</div>
                        <div class="dag-search-box">
                            <label>Descendant (↓)</label>
                            <div class="dag-search-wrapper">
                                <input type="text" class="dag-search-input" id="dag-descendant-input" placeholder="Type name..." autocomplete="off">
                                <div class="dag-autocomplete" id="dag-descendant-dropdown"></div>
                            </div>
                            <div class="dag-selected" id="dag-descendant-selected"></div>
                        </div>
                        <div class="dag-path-result" id="dag-path-result"></div>
                        <button class="dag-reset-btn" onclick="clearDagSelection()">Clear All</button>
                    </div>
                </div>
                <div class="dag-svg-wrapper"><svg id="dag-svg" class="dag-svg"></svg></div>
            </div>
        </div>
        
        <!-- ALL-TIME 3D TAB -->
        <div id="tab-alltime3d" class="tab-content">
            <div class="plot-container">
                <div class="plot-title">🌐 3D Scatter: PPG × RPG × APG (Color = Layer)</div>
                <div id="plot3d" class="plot-3d"></div>
                <div class="plot-legend">
                    <div class="legend-item"><div class="legend-dot" style="background:#fbbf24;"></div>Layer 0</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#3b82f6;"></div>Layer 1</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#10b981;"></div>Layer 2</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#6b7280;"></div>Layer 3+</div>
                </div>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">🏆 Top {{ALLTIME_TOP_N}} All-Time (3D: PPG/RPG/APG)</div>
                    <div class="search-box"><input type="text" id="search3d" placeholder="Search player/team/season..."></div>
                </div>
                <div class="table-scroll">
                    <table id="table3d">
                        <thead><tr><th class="col-rank">#</th><th class="col-player">Player</th><th class="col-season">Season</th><th class="col-team">Team</th><th class="col-stat">PPG</th><th class="col-stat">RPG</th><th class="col-stat">APG</th><th class="col-layer">Layer</th><th class="col-dom">Dominance</th></tr></thead>
                        <tbody id="tbody3d"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- ALL-TIME 4D TAB -->
        <div id="tab-alltime4d" class="tab-content">
            <div class="plot-container">
                <div class="plot-title">🌐 3D Scatter: PPG × RPG × APG (Color = STOCKPG)</div>
                <div id="plot4d" class="plot-3d"></div>
                <div class="colorbar-note">Color intensity = STOCKPG (Steals + Blocks per game)</div>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">🏆 Top {{ALLTIME_TOP_N}} All-Time (4D: PPG/RPG/APG/STOCKPG)</div>
                    <div class="search-box"><input type="text" id="search4d" placeholder="Search player/team/season..."></div>
                </div>
                <div class="table-scroll">
                    <table id="table4d">
                        <thead><tr><th class="col-rank">#</th><th class="col-player">Player</th><th class="col-season">Season</th><th class="col-team">Team</th><th class="col-stat">PPG</th><th class="col-stat">RPG</th><th class="col-stat">APG</th><th class="col-stat">STK</th><th class="col-layer">Layer</th><th class="col-dom">Dominance</th></tr></thead>
                        <tbody id="tbody4d"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- METHODOLOGY TAB -->
        <div id="tab-methodology" class="tab-content">
            <div class="methodology">
                <h2>📐 Pareto Analysis Methodology</h2>
                
                <h3>1. Pareto Dominance</h3>
                <p>Given two performances A and B, <code>A dominates B</code> if A ≥ B in ALL dimensions AND A > B in at least one.</p>
                <div class="formula">A dominates B ⟺ (∀d: A[d] ≥ B[d]) ∧ (∃d: A[d] > B[d])</div>
                
                <h3>2. Pareto Frontier (Layer 0)</h3>
                <p>The Pareto frontier contains all performances NOT dominated by any other — unique, incomparable excellence.</p>
                
                <h3>3. Pareto Layers</h3>
                <ul>
                    <li><strong>Layer 0:</strong> Pareto frontier (undominated)</li>
                    <li><strong>Layer 1:</strong> Frontier after removing Layer 0</li>
                    <li><strong>Layer N:</strong> Frontier after removing Layers 0 to N-1</li>
                </ul>
                
                <h3>4. Sub-Pareto Analysis (Current Season)</h3>
                <p>We compute frontiers for ALL subsets of dimensions (63 for 6D, 7 for 3D).</p>
                <ul>
                    <li><strong>Strength:</strong> How many subsets player appears on</li>
                    <li><strong>Min Dim:</strong> Smallest subset where Pareto-optimal</li>
                    <li><strong>Best Vars:</strong> Variables forming smallest unbeatable combo</li>
                </ul>
                
                <h3>5. Dominance Percentage</h3>
                <div class="formula">Dominance % = (# performances dominated) / (Total - 1) × 100</div>
                
                <h3>6. 3D vs 4D Analysis</h3>
                <p><strong>3D:</strong> PPG, RPG, APG — the classic stat line<br>
                <strong>4D:</strong> Adds STOCKPG (steals + blocks) for two-way players</p>
            </div>
        </div>
    </div>
    
    <!-- DAG Tooltip -->
    <div class="dag-tooltip" id="dag-tooltip">
        <div class="dag-tt-header">
            <img id="dag-tt-img" src="" onerror="this.style.display='none'">
            <div><div id="dag-tt-name"></div><div id="dag-tt-team"></div></div>
        </div>
        <div class="dag-tt-body">
            <div id="dag-tt-layer"></div>
            <div id="dag-tt-counts" class="dag-tt-counts"></div>
            <div id="dag-tt-stats" class="dag-tt-stats"></div>
            <div id="dag-tt-parents" class="dag-tt-relation"></div>
            <div id="dag-tt-children" class="dag-tt-relation"></div>
        </div>
    </div>
    
    <script>
// =============================================================================
// DATA
// =============================================================================
const SEASON = "{{SEASON}}";
const seasonPA = {{SEASON_PA_JSON}};
const seasonGBG = {{SEASON_GBG_JSON}};
const seasonDAG = {{SEASON_DAG_JSON}};
const dimensions = {{DIMENSIONS_JSON}};
const top100_3d = {{TOP_100_3D_JSON}};
const top100_4d = {{TOP_100_4D_JSON}};
const alltimeMeta = {{ALLTIME_META_JSON}};

// State
let currentPaDim = '6d';
let currentPaFilter = 'none';
let currentGbgDim = '6d';
let currentGbgFilter = 'none';
let currentDagDim = '6d';

let paSort = { key: 'pareto_count', asc: false };
let gbgSort = { key: 'pareto_count', asc: false };

let paRadarChart = null;
let selectedPlayers = [];
const maxSelected = 5;

let dagNodeMap = {};
let dagParentMap = {};
let dagChildMap = {};
let dagAncestorCount = {};
let dagDescendantCount = {};
let dagSelection = { ancestor: null, descendant: null };
let dagAdjacency = { children: {}, parents: {} };
let dagSearchSetup = false;

let alltime3dRendered = false;
let alltime4dRendered = false;
let dagRendered = false;

const chartColors = [
    'rgba(245, 158, 11, 0.8)', 'rgba(59, 130, 246, 0.8)', 'rgba(16, 185, 129, 0.8)',
    'rgba(239, 68, 68, 0.8)', 'rgba(139, 92, 246, 0.8)',
];
const layerColors = ['#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ef4444', '#ec4899', '#14b8a6', '#f97316', '#6b7280'];

// =============================================================================
// HELPERS
// =============================================================================
function getDimConfig(dimKey) { return dimensions[dimKey] || dimensions['6d']; }
function getTotalSubsets(dimKey) { return getDimConfig(dimKey).total_subsets || 63; }
function getVariables(dimKey) { return getDimConfig(dimKey).variables || ['PPG', 'RPG', 'APG', 'SPG', 'BPG', 'TS%']; }
function getStrengthClass(count, total) {
    const pct = count / total;
    if (pct >= 0.7) return 'strength-elite';
    if (pct >= 0.5) return 'strength-high';
    if (pct >= 0.3) return 'strength-mid';
    return 'strength-low';
}
function formatVars(vars) {
    if (!vars || vars.length === 0) return '-';
    return vars.map(v => `<span class="vars-tag">${v}</span>`).join('');
}
function getData(mode, dimKey, filterKey) {
    const modeData = mode === 'pa' ? seasonPA : seasonGBG;
    return (modeData[dimKey] || {})[filterKey] || [];
}
function getDagData(dimKey, filterKey) {
    return (seasonDAG[dimKey] || {})[filterKey] || { stats: {}, nodes: [], edges: [] };
}
function getLayerColor(layer) { return layer < layerColors.length - 1 ? layerColors[layer] : layerColors[layerColors.length - 1]; }
function getLayerClass(layer) {
    if (layer === 0) return 'layer-0';
    if (layer === 1) return 'layer-1';
    if (layer === 2) return 'layer-2';
    return 'layer-other';
}

// =============================================================================
// INITIALIZATION
// =============================================================================
function init() {
    renderPaHeaders();
    renderGbgHeaders();
    renderPlayerAvgTable();
    renderGameByGameTable();
    initTabs();
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById('tab-' + this.dataset.tab).classList.add('active');
            
            if (this.dataset.tab === 'dag' && !dagRendered) { renderDag(); dagRendered = true; }
            if (this.dataset.tab === 'alltime3d' && !alltime3dRendered) {
                render3DPlot_Layers('plot3d', top100_3d);
                renderAllTimeTable('tbody3d', top100_3d, '3d');
                setupAllTimeSearch('search3d', 'tbody3d', top100_3d, '3d');
                alltime3dRendered = true;
            }
            if (this.dataset.tab === 'alltime4d' && !alltime4dRendered) {
                render3DPlot_StockColor('plot4d', top100_4d);
                renderAllTimeTable('tbody4d', top100_4d, '4d');
                setupAllTimeSearch('search4d', 'tbody4d', top100_4d, '4d');
                alltime4dRendered = true;
            }
        });
    });
    setupDagSearch();
}

function updateSortIndicators(tableId, sortState) {
    document.querySelectorAll(`#${tableId} th`).forEach(h => h.classList.remove('sorted', 'asc'));
    const th = document.querySelector(`#${tableId} th[data-sort="${sortState.key}"]`);
    if (th) { th.classList.add('sorted'); if (sortState.asc) th.classList.add('asc'); }
}

// =============================================================================
// FILTERS & DIMENSION SWITCHES
// =============================================================================
function setPlayerAvgDim(dim) {
    currentPaDim = dim;
    document.querySelectorAll('#tab-playeravg .dim-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.dim === dim));
    selectedPlayers = [];
    renderPaHeaders();
    renderPlayerAvgTable();
}
function setPlayerAvgFilter(filter) {
    currentPaFilter = filter;
    document.querySelectorAll('#tab-playeravg .filter-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.filter === filter));
    selectedPlayers = [];
    renderPlayerAvgTable();
}
function setGbgDim(dim) {
    currentGbgDim = dim;
    document.querySelectorAll('#tab-gamebygame .dim-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.dim === dim));
    renderGbgHeaders();
    renderGameByGameTable();
}
function setGbgFilter(filter) {
    currentGbgFilter = filter;
    document.querySelectorAll('#tab-gamebygame .filter-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.filter === filter));
    renderGameByGameTable();
}
function setDagDim(dim) {
    currentDagDim = dim;
    document.querySelectorAll('#tab-dag .dim-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.dim === dim));
    clearDagSelection();
    dagRendered = false;
    renderDag();
    dagRendered = true;
}

// =============================================================================
// TABLE HEADERS
// =============================================================================
function renderPaHeaders() {
    const vars = getVariables(currentPaDim);
    const thead = document.getElementById('pa-thead');
    let html = `<tr><th class="col-rank">#</th><th class="col-player" data-sort="name">Player</th><th class="col-team" data-sort="team">Team</th><th class="col-strength" data-sort="pareto_count">Strength</th><th class="col-dim" data-sort="min_pareto_dim">Dim</th><th class="col-vars">Best Vars</th>`;
    vars.forEach(v => { html += `<th class="col-stat" data-sort="${v}">${v}</th>`; });
    html += `</tr>`;
    thead.innerHTML = html;
    thead.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', function() {
            const key = this.dataset.sort;
            if (paSort.key === key) paSort.asc = !paSort.asc;
            else { paSort.key = key; paSort.asc = false; }
            updateSortIndicators('pa-table', paSort);
            renderPlayerAvgTable();
        });
    });
    updateSortIndicators('pa-table', paSort);
}

function renderGbgHeaders() {
    const vars = getVariables(currentGbgDim);
    const thead = document.getElementById('gbg-thead');
    let html = `<tr><th class="col-rank">#</th><th class="col-player" data-sort="name">Player</th><th class="col-team" data-sort="team">Team</th><th class="col-date" data-sort="date">Date</th><th class="col-strength" data-sort="pareto_count">Strength</th><th class="col-dim" data-sort="min_pareto_dim">Dim</th><th class="col-vars">Best Vars</th>`;
    vars.forEach(v => { html += `<th class="col-stat" data-sort="${v}">${v}</th>`; });
    html += `</tr>`;
    thead.innerHTML = html;
    thead.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', function() {
            const key = this.dataset.sort;
            if (gbgSort.key === key) gbgSort.asc = !gbgSort.asc;
            else { gbgSort.key = key; gbgSort.asc = false; }
            updateSortIndicators('gbg-table', gbgSort);
            renderGameByGameTable();
        });
    });
    updateSortIndicators('gbg-table', gbgSort);
}

// =============================================================================
// PLAYER AVG TABLE
// =============================================================================
function renderPlayerAvgTable() {
    const data = getData('pa', currentPaDim, currentPaFilter);
    const vars = getVariables(currentPaDim);
    const total = getTotalSubsets(currentPaDim);
    const tbody = document.getElementById('pa-tbody');
    
    document.getElementById('pa-frontier-count').textContent = data.length;
    document.getElementById('pa-total-subsets').textContent = total;
    if (data.length > 0) {
        const avgStrength = data.reduce((s, p) => s + p.pareto_count, 0) / data.length;
        document.getElementById('pa-avg-strength').textContent = avgStrength.toFixed(1);
    }
    
    const sorted = [...data].sort((a, b) => {
        let valA = a[paSort.key] ?? 0;
        let valB = b[paSort.key] ?? 0;
        if (typeof valA === 'string') return paSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        return paSort.asc ? valA - valB : valB - valA;
    });
    
    let html = '';
    sorted.forEach((p, idx) => {
        const strengthClass = getStrengthClass(p.pareto_count, total);
        html += `<tr><td class="col-rank">${idx + 1}</td>
            <td class="col-player"><div class="player-chip ${selectedPlayers.includes(p.player_id) ? 'selected' : ''}" data-id="${p.player_id}" onclick="togglePlayerSelection(${p.player_id})">
                <div class="player-headshot"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/${p.player_id}.png" onerror="this.style.display='none'"></div>
                <span class="player-name">${p.name}</span></div></td>
            <td class="col-team"><span class="team-badge">${p.team}</span></td>
            <td class="col-strength"><span class="strength-badge ${strengthClass}">${p.pareto_count}/${total}</span></td>
            <td class="col-dim"><span class="dim-badge">${p.min_pareto_dim}D</span></td>
            <td class="col-vars">${formatVars(p.min_pareto_vars)}</td>`;
        vars.forEach(v => { html += `<td class="col-stat">${p[v]?.toFixed?.(1) ?? p[v] ?? '-'}</td>`; });
        html += `</tr>`;
    });
    tbody.innerHTML = html || '<tr><td colspan="12" style="color:#888;text-align:center;padding:40px;">No data</td></tr>';
    updateRadarChart(sorted);
}

// =============================================================================
// GAME BY GAME TABLE
// =============================================================================
function renderGameByGameTable() {
    const data = getData('gbg', currentGbgDim, currentGbgFilter);
    const vars = getVariables(currentGbgDim);
    const total = getTotalSubsets(currentGbgDim);
    const tbody = document.getElementById('gbg-tbody');
    
    document.getElementById('gbg-frontier-count').textContent = data.length;
    document.getElementById('gbg-total-subsets').textContent = total;
    
    const sorted = [...data].sort((a, b) => {
        let valA = a[gbgSort.key] ?? 0;
        let valB = b[gbgSort.key] ?? 0;
        if (typeof valA === 'string') return gbgSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        return gbgSort.asc ? valA - valB : valB - valA;
    });
    
    let html = '';
    sorted.forEach((p, idx) => {
        const strengthClass = getStrengthClass(p.pareto_count, total);
        html += `<tr><td class="col-rank">${idx + 1}</td>
            <td class="col-player"><div class="player-chip">
                <div class="player-headshot"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/${p.player_id}.png" onerror="this.style.display='none'"></div>
                <span class="player-name">${p.name}</span></div></td>
            <td class="col-team"><span class="team-badge">${p.team}</span></td>
            <td class="col-date">${p.date || '-'}</td>
            <td class="col-strength"><span class="strength-badge ${strengthClass}">${p.pareto_count}/${total}</span></td>
            <td class="col-dim"><span class="dim-badge">${p.min_pareto_dim}D</span></td>
            <td class="col-vars">${formatVars(p.min_pareto_vars)}</td>`;
        vars.forEach(v => { html += `<td class="col-stat">${p[v]?.toFixed?.(1) ?? p[v] ?? '-'}</td>`; });
        html += `</tr>`;
    });
    tbody.innerHTML = html || '<tr><td colspan="12" style="color:#888;text-align:center;padding:40px;">No data</td></tr>';
}

// =============================================================================
// DAG VISUALIZATION
// =============================================================================
function renderDag() {
    const dagData = getDagData(currentDagDim, 'none');
    const stats = dagData.stats || {};
    const nodes = dagData.nodes || [];
    const edges = dagData.edges || [];
    const vars = getVariables(currentDagDim);
    
    clearDagSelection();
    
    const statsPanel = document.getElementById('dag-stats-panel');
    statsPanel.innerHTML = `
        <div class="dag-stat-card"><div class="dag-stat-val">${stats.total_players || nodes.length}</div><div class="dag-stat-label">Players</div></div>
        <div class="dag-stat-card"><div class="dag-stat-val">${(stats.max_layer || 0) + 1}</div><div class="dag-stat-label">Layers</div></div>
        <div class="dag-stat-card"><div class="dag-stat-val">${stats.layer_sizes?.[0] || 0}</div><div class="dag-stat-label">Frontier</div></div>
        <div class="dag-stat-card"><div class="dag-stat-val">${stats.total_edges || edges.length}</div><div class="dag-stat-label">Edges</div></div>
        <div class="dag-stat-card"><div class="dag-stat-val">${stats.avg_parents_per_child || 0}</div><div class="dag-stat-label">Avg Parents</div></div>
    `;
    
    if (nodes.length === 0) {
        document.getElementById('dag-svg').innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#888">No DAG data</text>';
        return;
    }
    
    dagNodeMap = {}; nodes.forEach(n => dagNodeMap[n.id] = n);
    dagParentMap = {}; dagChildMap = {};
    edges.forEach(([parent, child]) => {
        if (!dagParentMap[child]) dagParentMap[child] = [];
        dagParentMap[child].push(parent);
        if (!dagChildMap[parent]) dagChildMap[parent] = [];
        dagChildMap[parent].push(child);
    });
    
    dagAncestorCount = {};
    nodes.forEach(node => {
        const visited = new Set();
        const queue = [...(dagParentMap[node.id] || [])];
        while (queue.length > 0) {
            const pid = queue.shift();
            if (!visited.has(pid)) { visited.add(pid); (dagParentMap[pid] || []).forEach(p => queue.push(p)); }
        }
        dagAncestorCount[node.id] = visited.size;
    });
    
    dagDescendantCount = {};
    nodes.forEach(node => {
        const visited = new Set();
        const queue = [...(dagChildMap[node.id] || [])];
        while (queue.length > 0) {
            const cid = queue.shift();
            if (!visited.has(cid)) { visited.add(cid); (dagChildMap[cid] || []).forEach(c => queue.push(c)); }
        }
        dagDescendantCount[node.id] = visited.size;
    });
    
    const nodeRadius = 18;
    const layerHeight = 80;
    const minNodeSpacing = 50;
    const padding = { top: 120, right: 40, bottom: 40, left: 80 };
    
    const layerSizes = stats.layer_sizes || [];
    const maxNodesInLayer = Math.max(...layerSizes, 1);
    const maxLayers = (stats.max_layer || 0) + 1;
    
    const svgWidth = Math.max(maxNodesInLayer * minNodeSpacing + padding.left + padding.right, 800);
    const svgHeight = maxLayers * layerHeight + padding.top + padding.bottom;
    
    const nodesByLayer = {};
    nodes.forEach(n => { if (!nodesByLayer[n.layer]) nodesByLayer[n.layer] = []; nodesByLayer[n.layer].push(n); });
    Object.values(nodesByLayer).forEach(layerNodes => layerNodes.sort((a, b) => (b.PPG || 0) - (a.PPG || 0)));
    
    const positions = {};
    for (let layer = 0; layer < maxLayers; layer++) {
        const layerNodes = nodesByLayer[layer] || [];
        const y = padding.top + layer * layerHeight;
        const totalWidth = svgWidth - padding.left - padding.right;
        const spacing = totalWidth / (layerNodes.length + 1);
        layerNodes.forEach((node, i) => { positions[node.id] = { x: padding.left + spacing * (i + 1), y: y }; });
    }
    
    let svg = `<svg id="dag-svg" width="${svgWidth}" height="${svgHeight}" class="dag-svg">`;
    svg += '<defs>';
    nodes.forEach(node => {
        const pos = positions[node.id];
        if (pos) svg += `<clipPath id="clip-${node.id}"><circle cx="${pos.x}" cy="${pos.y}" r="${nodeRadius}"/></clipPath>`;
    });
    svg += '</defs>';
    
    for (let layer = 0; layer < maxLayers; layer++) {
        const y = padding.top + layer * layerHeight;
        svg += `<text x="15" y="${y + 4}" class="dag-layer-label">L${layer}</text>`;
    }
    
    edges.forEach(([parentId, childId]) => {
        const p1 = positions[parentId];
        const p2 = positions[childId];
        const parentNode = dagNodeMap[parentId];
        const childNode = dagNodeMap[childId];
        if (p1 && p2 && parentNode && childNode) {
            const layerGap = childNode.layer - parentNode.layer;
            const isMultiLayer = layerGap > 1;
            svg += `<path class="dag-edge${isMultiLayer ? ' multi-layer' : ' single-layer'}" data-parent="${parentId}" data-child="${childId}" data-gap="${layerGap}" d="M${p1.x},${p1.y + nodeRadius} Q${(p1.x + p2.x) / 2},${(p1.y + p2.y) / 2} ${p2.x},${p2.y - nodeRadius}"/>`;
        }
    });
    
    nodes.forEach(node => {
        const pos = positions[node.id];
        if (!pos) return;
        const color = getLayerColor(node.layer);
        const parentNames = (dagParentMap[node.id] || []).map(pid => dagNodeMap[pid]?.name || pid).join(', ');
        const childNames = (dagChildMap[node.id] || []).map(cid => dagNodeMap[cid]?.name || cid).join(', ');
        const statsJson = JSON.stringify(vars.reduce((o, v) => { o[v] = node[v]; return o; }, {}));
        const safeName = node.name.replace(/'/g, "\\'");
        svg += `<g class="dag-node" data-id="${node.id}" data-name="${node.name}" data-team="${node.team}" data-layer="${node.layer}" data-stats='${statsJson}' data-parents="${parentNames}" data-children="${childNames}" data-ancestors="${dagAncestorCount[node.id] || 0}" data-descendants="${dagDescendantCount[node.id] || 0}" onclick="handleDagNodeClick('${node.id}', '${safeName}', '${node.team}')" onmouseenter="showDagTooltip(event, this)" onmouseleave="hideDagTooltip()" onmousemove="moveDagTooltip(event)" style="cursor: pointer;">
            <circle class="node-ring" cx="${pos.x}" cy="${pos.y}" r="${nodeRadius + 2}" fill="none" stroke="${color}" stroke-width="3"/>
            <image href="https://cdn.nba.com/headshots/nba/latest/1040x760/${node.id}.png" x="${pos.x - nodeRadius}" y="${pos.y - nodeRadius}" width="${nodeRadius * 2}" height="${nodeRadius * 2}" clip-path="url(#clip-${node.id})" preserveAspectRatio="xMidYMid slice"/>
            <circle cx="${pos.x}" cy="${pos.y}" r="${nodeRadius}" fill="none" stroke="${color}" stroke-width="2"/>
        </g>`;
    });
    
    svg += '</svg>';
    document.getElementById('dag-svg').outerHTML = svg;
    buildDagAdjacency();
    setupDagSearch();
}

function buildDagAdjacency() {
    dagAdjacency = { children: {}, parents: {} };
    document.querySelectorAll('.dag-edge').forEach(edge => {
        const parent = edge.dataset.parent;
        const child = edge.dataset.child;
        if (!dagAdjacency.children[parent]) dagAdjacency.children[parent] = [];
        if (!dagAdjacency.parents[child]) dagAdjacency.parents[child] = [];
        dagAdjacency.children[parent].push(child);
        dagAdjacency.parents[child].push(parent);
    });
}

// =============================================================================
// DAG SEARCH & SELECTION
// =============================================================================
function setupDagSearch() {
    const ancestorInput = document.getElementById('dag-ancestor-input');
    const descendantInput = document.getElementById('dag-descendant-input');
    const ancestorDropdown = document.getElementById('dag-ancestor-dropdown');
    const descendantDropdown = document.getElementById('dag-descendant-dropdown');
    if (!ancestorInput || !descendantInput) return;
    
    const dagPlayers = [];
    document.querySelectorAll('.dag-node').forEach(node => {
        dagPlayers.push({ id: node.dataset.id, name: node.dataset.name, team: node.dataset.team, layer: parseInt(node.dataset.layer) });
    });
    window.dagPlayersForSearch = dagPlayers;
    
    if (!dagSearchSetup) {
        setupAutocomplete(ancestorInput, ancestorDropdown, 'ancestor');
        setupAutocomplete(descendantInput, descendantDropdown, 'descendant');
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dag-search-wrapper')) {
                ancestorDropdown.classList.remove('active');
                descendantDropdown.classList.remove('active');
            }
        });
        dagSearchSetup = true;
    }
}

function setupAutocomplete(input, dropdown, type) {
    input.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        const players = window.dagPlayersForSearch || [];
        if (query.length < 1) { dropdown.classList.remove('active'); return; }
        const matches = players.filter(p => p.name.toLowerCase().includes(query)).sort((a, b) => a.layer - b.layer).slice(0, 8);
        if (matches.length === 0) { dropdown.classList.remove('active'); return; }
        dropdown.innerHTML = matches.map(p => `<div class="dag-autocomplete-item" data-id="${p.id}" data-name="${p.name}" data-team="${p.team}"><img class="dag-autocomplete-img" src="https://cdn.nba.com/headshots/nba/latest/1040x760/${p.id}.png" onerror="this.style.display='none'"><div class="dag-autocomplete-info"><div class="dag-autocomplete-name">${p.name}</div><div class="dag-autocomplete-meta">${p.team} · Layer ${p.layer}</div></div></div>`).join('');
        dropdown.querySelectorAll('.dag-autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                selectDagPlayer(type, { id: item.dataset.id, name: item.dataset.name, team: item.dataset.team });
                input.value = '';
                dropdown.classList.remove('active');
            });
        });
        dropdown.classList.add('active');
    });
    input.addEventListener('focus', function() { if (this.value.length >= 1) this.dispatchEvent(new Event('input')); });
}

function selectDagPlayer(type, player) {
    if (dagSelection[type] && dagSelection[type].id === player.id) { deselectDagPlayer(type); return; }
    dagSelection[type] = player;
    const chipContainer = document.getElementById(`dag-${type}-selected`);
    chipContainer.innerHTML = `<div class="dag-selected-chip ${type}"><img src="https://cdn.nba.com/headshots/nba/latest/1040x760/${player.id}.png" onerror="this.style.display='none'"><span>${player.name}</span><button class="dag-chip-remove" onclick="deselectDagPlayer('${type}')">&times;</button></div>`;
    updateDagHighlights();
    if (dagSelection.ancestor && dagSelection.descendant) findAndShowPath();
}

function deselectDagPlayer(type) {
    dagSelection[type] = null;
    document.getElementById(`dag-${type}-selected`).innerHTML = '';
    updateDagHighlights();
    clearPath();
}

function clearDagSelection() {
    dagSelection.ancestor = null;
    dagSelection.descendant = null;
    ['dag-ancestor-selected', 'dag-descendant-selected'].forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = ''; });
    ['dag-ancestor-input', 'dag-descendant-input'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    const result = document.getElementById('dag-path-result');
    if (result) result.innerHTML = '';
    document.querySelectorAll('.dag-node').forEach(node => node.classList.remove('selected-ancestor', 'selected-descendant', 'on-path', 'dimmed'));
    document.querySelectorAll('.dag-edge').forEach(edge => edge.classList.remove('path-edge', 'hover-connected'));
}

function toggleDagPanel() { const panel = document.getElementById('dag-search-panel'); if (panel) panel.classList.toggle('collapsed'); }

function updateDagHighlights() {
    document.querySelectorAll('.dag-node').forEach(node => node.classList.remove('selected-ancestor', 'selected-descendant', 'on-path'));
    if (dagSelection.ancestor) { const node = document.querySelector(`.dag-node[data-id="${dagSelection.ancestor.id}"]`); if (node) node.classList.add('selected-ancestor'); }
    if (dagSelection.descendant) { const node = document.querySelector(`.dag-node[data-id="${dagSelection.descendant.id}"]`); if (node) node.classList.add('selected-descendant'); }
}

// =============================================================================
// PATH FINDING
// =============================================================================
function findShortestPath(ancestorId, descendantId) {
    if (ancestorId === descendantId) return [ancestorId];
    const queue = [[ancestorId]];
    const visited = new Set([ancestorId]);
    while (queue.length > 0) {
        const path = queue.shift();
        const current = path[path.length - 1];
        const children = dagAdjacency.children[current] || [];
        for (const child of children) {
            if (child === descendantId) return [...path, child];
            if (!visited.has(child)) { visited.add(child); queue.push([...path, child]); }
        }
    }
    return null;
}

function findAndShowPath() {
    clearPath();
    const ancestorId = dagSelection.ancestor.id;
    const descendantId = dagSelection.descendant.id;
    const result = document.getElementById('dag-path-result');
    const ancestorNode = document.querySelector(`.dag-node[data-id="${ancestorId}"]`);
    const descendantNode = document.querySelector(`.dag-node[data-id="${descendantId}"]`);
    if (!ancestorNode || !descendantNode) { result.innerHTML = '<span class="not-found">Nodes not found</span>'; result.className = 'dag-path-result not-found'; return; }
    const ancestorLayer = parseInt(ancestorNode.dataset.layer);
    const descendantLayer = parseInt(descendantNode.dataset.layer);
    if (ancestorLayer >= descendantLayer) { result.innerHTML = `<span class="not-found">Invalid: Ancestor (L${ancestorLayer}) must be above Descendant (L${descendantLayer})</span>`; result.className = 'dag-path-result not-found'; return; }
    const path = findShortestPath(ancestorId, descendantId);
    if (!path) { result.innerHTML = '<span class="not-found">No dominance path exists</span>'; result.className = 'dag-path-result not-found'; return; }
    result.innerHTML = `<span class="found">Path found! ${path.length} nodes, ${path.length - 1} edges</span>`;
    result.className = 'dag-path-result found';
    path.forEach(nodeId => { const node = document.querySelector(`.dag-node[data-id="${nodeId}"]`); if (node && nodeId !== ancestorId && nodeId !== descendantId) node.classList.add('on-path'); });
    for (let i = 0; i < path.length - 1; i++) { const edge = document.querySelector(`.dag-edge[data-parent="${path[i]}"][data-child="${path[i+1]}"]`); if (edge) edge.classList.add('path-edge'); }
    document.querySelectorAll('.dag-node').forEach(node => { if (!path.includes(node.dataset.id)) node.classList.add('dimmed'); });
}

function clearPath() {
    document.querySelectorAll('.dag-node').forEach(node => node.classList.remove('on-path', 'dimmed'));
    document.querySelectorAll('.dag-edge').forEach(edge => edge.classList.remove('path-edge'));
    const result = document.getElementById('dag-path-result');
    if (result) result.innerHTML = '';
}

function handleDagNodeClick(nodeId, nodeName, nodeTeam) {
    const player = { id: nodeId, name: nodeName, team: nodeTeam };
    if (dagSelection.ancestor && dagSelection.ancestor.id === nodeId) { deselectDagPlayer('ancestor'); return; }
    if (dagSelection.descendant && dagSelection.descendant.id === nodeId) { deselectDagPlayer('descendant'); return; }
    const panel = document.getElementById('dag-search-panel');
    if (panel && panel.classList.contains('collapsed')) panel.classList.remove('collapsed');
    if (!dagSelection.ancestor) selectDagPlayer('ancestor', player);
    else if (!dagSelection.descendant) selectDagPlayer('descendant', player);
}

// =============================================================================
// DAG TOOLTIP
// =============================================================================
function showDagTooltip(event, elem) {
    const tooltip = document.getElementById('dag-tooltip');
    const id = elem.dataset.id;
    const name = elem.dataset.name;
    const team = elem.dataset.team;
    const layer = elem.dataset.layer;
    const stats = JSON.parse(elem.dataset.stats || '{}');
    const parents = elem.dataset.parents;
    const children = elem.dataset.children;
    const ancestors = elem.dataset.ancestors;
    const descendants = elem.dataset.descendants;
    
    document.getElementById('dag-tt-img').src = `https://cdn.nba.com/headshots/nba/latest/1040x760/${id}.png`;
    document.getElementById('dag-tt-name').textContent = name;
    document.getElementById('dag-tt-team').textContent = team;
    document.getElementById('dag-tt-layer').textContent = `Layer ${layer}`;
    document.getElementById('dag-tt-counts').innerHTML = `<div class="dag-tt-count">↑ Ancestors: <strong>${ancestors}</strong></div><div class="dag-tt-count">↓ Descendants: <strong>${descendants}</strong></div>`;
    
    const vars = getVariables(currentDagDim);
    let statsHtml = '';
    vars.forEach(v => { const val = stats[v]; statsHtml += `<div class="dag-tt-stat"><div class="dag-tt-stat-val">${val?.toFixed?.(1) ?? val ?? '-'}</div><div class="dag-tt-stat-label">${v}</div></div>`; });
    document.getElementById('dag-tt-stats').innerHTML = statsHtml;
    
    const parentsDiv = document.getElementById('dag-tt-parents');
    if (parents && layer !== '0') { parentsDiv.innerHTML = `<span class="dag-tt-relation-label">Dominated by:</span> <span class="dag-tt-relation-names">${parents}</span>`; parentsDiv.style.display = 'block'; }
    else if (layer === '0') { parentsDiv.innerHTML = `<span class="dag-tt-relation-label">Dominated by:</span> <span style="color:#f59e0b;">None (Pareto Frontier)</span>`; parentsDiv.style.display = 'block'; }
    else { parentsDiv.style.display = 'none'; }
    
    const childrenDiv = document.getElementById('dag-tt-children');
    if (children) { const childList = children.length > 60 ? children.substring(0, 60) + '...' : children; childrenDiv.innerHTML = `<span class="dag-tt-relation-label">Dominates:</span> <span class="dag-tt-relation-names">${childList}</span>`; childrenDiv.style.display = 'block'; }
    else { childrenDiv.innerHTML = `<span class="dag-tt-relation-label">Dominates:</span> <span style="color:#888;">None</span>`; childrenDiv.style.display = 'block'; }
    
    tooltip.classList.add('visible');
    moveDagTooltip(event);
    
    document.querySelectorAll('.dag-edge').forEach(edge => {
        const isConnected = edge.dataset.parent === id || edge.dataset.child === id;
        edge.classList.toggle('hover-connected', isConnected);
    });
}

function hideDagTooltip() {
    document.getElementById('dag-tooltip').classList.remove('visible');
    document.querySelectorAll('.dag-edge').forEach(edge => edge.classList.remove('hover-connected'));
}

function moveDagTooltip(event) {
    const tooltip = document.getElementById('dag-tooltip');
    const tooltipWidth = 280;
    const windowWidth = window.innerWidth;
    let x = event.clientX > windowWidth / 2 ? event.clientX - tooltipWidth - 15 : event.clientX + 15;
    let y = event.clientY - 10;
    if (x < 10) x = 10;
    if (y < 10) y = 10;
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
}

// =============================================================================
// RADAR CHART
// =============================================================================
function togglePlayerSelection(playerId) {
    const idx = selectedPlayers.indexOf(playerId);
    if (idx >= 0) selectedPlayers.splice(idx, 1);
    else { if (selectedPlayers.length >= maxSelected) selectedPlayers.shift(); selectedPlayers.push(playerId); }
    document.querySelectorAll('.player-chip').forEach(chip => chip.classList.toggle('selected', selectedPlayers.includes(parseInt(chip.dataset.id))));
    const data = getData('pa', currentPaDim, currentPaFilter);
    updateRadarChart(data);
}

function updateRadarChart(allData) {
    const ctx = document.getElementById('pa-radar-chart').getContext('2d');
    const vars = getVariables(currentPaDim);
    let playersToShow = selectedPlayers.length > 0 ? selectedPlayers : allData.slice(0, 3).map(p => p.player_id);
    const scales = { 'PPG': 35, 'RPG': 15, 'APG': 12, 'SPG': 2.5, 'BPG': 3.5, 'TS%': 70 };
    const datasets = playersToShow.map((id, i) => {
        const player = allData.find(p => p.player_id === id);
        if (!player) return null;
        const normalized = vars.map(v => Math.min((player[v] || 0) / (scales[v] || 100) * 100, 100));
        return { label: player.name, data: normalized, backgroundColor: chartColors[i % chartColors.length].replace('0.8', '0.2'), borderColor: chartColors[i % chartColors.length], borderWidth: 2, pointBackgroundColor: chartColors[i % chartColors.length] };
    }).filter(d => d !== null);
    if (paRadarChart) paRadarChart.destroy();
    paRadarChart = new Chart(ctx, {
        type: 'radar',
        data: { labels: vars, datasets: datasets },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { color: '#aaa' } } }, scales: { r: { angleLines: { color: '#333' }, grid: { color: '#333' }, pointLabels: { color: '#aaa', font: { size: 12 } }, ticks: { display: false }, suggestedMin: 0, suggestedMax: 100 } } }
    });
}

// =============================================================================
// ALL-TIME 3D PLOT (Layer Color)
// =============================================================================
function render3DPlot_Layers(containerId, data) {
    if (!data || data.length === 0) return;
    const trace = {
        x: data.map(p => p.ppg), y: data.map(p => p.rpg), z: data.map(p => p.apg),
        mode: 'markers', type: 'scatter3d',
        marker: { size: data.map(p => 6 + p.dominance_pct / 12), color: data.map(p => getLayerColor(p.layer)), opacity: 0.9, line: { color: 'rgba(255,255,255,0.2)', width: 0.5 } },
        text: data.map(p => `<b>${p.name}</b> ${p.season}<br>${p.team}<br>PPG: ${p.ppg} | RPG: ${p.rpg} | APG: ${p.apg}<br>Layer: ${p.layer} | Dominance: ${p.dominance_pct.toFixed(1)}%`),
        hoverinfo: 'text', hoverlabel: { bgcolor: '#1a1a2e', bordercolor: '#fbbf24', font: { color: '#fff', size: 12 } }
    };
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        scene: {
            xaxis: { title: 'PPG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, gridcolor: '#333', zerolinecolor: '#444' },
            yaxis: { title: 'RPG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, gridcolor: '#333', zerolinecolor: '#444' },
            zaxis: { title: 'APG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, gridcolor: '#333', zerolinecolor: '#444' },
            bgcolor: 'rgba(0,0,0,0)', camera: { eye: { x: 1.8, y: 1.8, z: 1.0 } }
        },
        margin: { l: 0, r: 0, t: 10, b: 10 }, showlegend: false
    };
    Plotly.newPlot(containerId, [trace], layout, { responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'], displaylogo: false });
}

// =============================================================================
// ALL-TIME 4D PLOT (Stock Color)
// =============================================================================
function render3DPlot_StockColor(containerId, data) {
    if (!data || data.length === 0) return;
    const stockValues = data.map(p => p.stockpg);
    const trace = {
        x: data.map(p => p.ppg), y: data.map(p => p.rpg), z: data.map(p => p.apg),
        mode: 'markers', type: 'scatter3d',
        marker: {
            size: data.map(p => 6 + p.dominance_pct / 12), color: stockValues,
            colorscale: [[0, '#3b82f6'], [0.5, '#22c55e'], [1, '#fbbf24']],
            cmin: Math.min(...stockValues), cmax: Math.max(...stockValues),
            colorbar: { title: 'STOCKPG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, thickness: 15, len: 0.6, x: 1.02 },
            opacity: 0.9, line: { color: 'rgba(255,255,255,0.2)', width: 0.5 }
        },
        text: data.map(p => `<b>${p.name}</b> ${p.season}<br>${p.team}<br>PPG: ${p.ppg} | RPG: ${p.rpg} | APG: ${p.apg}<br>STOCKPG: ${p.stockpg.toFixed(1)}<br>Layer: ${p.layer} | Dominance: ${p.dominance_pct.toFixed(1)}%`),
        hoverinfo: 'text', hoverlabel: { bgcolor: '#1a1a2e', bordercolor: '#fbbf24', font: { color: '#fff', size: 12 } }
    };
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        scene: {
            xaxis: { title: 'PPG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, gridcolor: '#333', zerolinecolor: '#444' },
            yaxis: { title: 'RPG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, gridcolor: '#333', zerolinecolor: '#444' },
            zaxis: { title: 'APG', titlefont: { color: '#888', size: 12 }, tickfont: { color: '#666', size: 10 }, gridcolor: '#333', zerolinecolor: '#444' },
            bgcolor: 'rgba(0,0,0,0)', camera: { eye: { x: 1.8, y: 1.8, z: 1.0 } }
        },
        margin: { l: 0, r: 50, t: 10, b: 10 }, showlegend: false
    };
    Plotly.newPlot(containerId, [trace], layout, { responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'], displaylogo: false });
}

// =============================================================================
// ALL-TIME TABLE
// =============================================================================
function renderAllTimeTable(tbodyId, data, mode) {
    const tbody = document.getElementById(tbodyId);
    if (!data || data.length === 0) { tbody.innerHTML = '<tr><td colspan="10" style="color:#888;text-align:center;padding:40px;">No all-time data available</td></tr>'; return; }
    let html = '';
    data.forEach((p, idx) => {
        let tooltip = '';
        if (p.layer > 0 && p.ascendants && p.ascendants.length > 0) {
            const ascList = p.ascendants.slice(0, 5).join('\\n');
            const more = p.ascendants.length > 5 ? `\\n+${p.ascendants.length - 5} more...` : '';
            tooltip = `Dominated by:\\n${ascList}${more}`;
        } else if (p.layer === 0) { tooltip = 'Undominated (Pareto Frontier)'; }
        html += `<tr>
            <td class="col-rank">${idx + 1}</td>
            <td class="col-player"><div class="player-cell"><img class="player-img" src="https://cdn.nba.com/headshots/nba/latest/1040x760/${p.player_id}.png" onerror="this.style.display='none'"><span class="player-name">${p.name}</span></div></td>
            <td class="col-season">${p.season}</td>
            <td class="col-team"><span class="team-badge">${p.team}</span></td>
            <td class="col-stat">${p.ppg.toFixed(1)}</td>
            <td class="col-stat">${p.rpg.toFixed(1)}</td>
            <td class="col-stat">${p.apg.toFixed(1)}</td>
            ${mode === '4d' ? `<td class="col-stat">${p.stockpg.toFixed(1)}</td>` : ''}
            <td class="col-layer"><span class="layer-badge ${getLayerClass(p.layer)}" data-tooltip="${tooltip}">L${p.layer}</span></td>
            <td class="col-dom"><div class="dom-value">${p.dominance_pct.toFixed(1)}%</div><div class="dom-bar"><div class="dom-fill" style="width: ${p.dominance_pct}%"></div></div></td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function setupAllTimeSearch(inputId, tbodyId, data, mode) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.addEventListener('input', () => {
        const query = input.value.toLowerCase().trim();
        if (!query) { renderAllTimeTable(tbodyId, data, mode); return; }
        const filtered = data.filter(p => p.name.toLowerCase().includes(query) || p.team.toLowerCase().includes(query) || p.season.includes(query));
        renderAllTimeTable(tbodyId, filtered, mode);
    });
}

// =============================================================================
// INIT
// =============================================================================
init();
    </script>
</body>
</html>'''


if __name__ == "__main__":
    generate_html()
