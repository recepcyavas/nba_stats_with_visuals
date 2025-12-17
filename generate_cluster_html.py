"""
================================================================================
GENERATE CLUSTER HTML
================================================================================

PURPOSE:
    Generate interactive HTML visualization for hierarchical player clustering.
    Reads JSON output from cluster_players.py and creates a D3.js dendrogram.

INPUT:
    player_clusters.json (from cluster_players.py)

OUTPUT:
    player_clusters_dashboard.html

VISUALIZATION FEATURES:
    1. Horizontal D3.js dendrogram (tree grows left-to-right)
    2. Leaf nodes display abbreviated player names with headshots
    3. Hover tooltip shows full player info (only on leaf nodes)
    4. Branch coloring based on high-level tree structure (depth <= 3)
    5. Tight clusters section with player cards
    6. Similarity section showing "most similar to X" for key players

STYLE:
    Matches the main player_stats_dashboard.html:
    - Dark gradient background (#0f0f1a to #1a1a2e)
    - Green accent (#4ade80), blue accent (#007AC1)
    - Card-based layout with gradients
    - Same fonts, spacing, and visual language

TOOLTIP POSITIONING:
    - Checks viewport bounds before rendering
    - Positions above/left if would be cut off at bottom/right
    - Never clips outside viewport

USAGE:
    python generate_cluster_html.py
    python generate_cluster_html.py --input custom.json --output custom.html

DEPENDENCIES:
    - player_clusters.json (from cluster_players.py)

================================================================================
"""

import json
import argparse

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_PATH = "player_clusters.json"
OUTPUT_PATH = "player_clusters_dashboard.html"

# Branch colors for high-level tree structure (8 distinct colors)
# These are applied at depth <= 3 and propagate down
BRANCH_COLORS = [
    '#E03A3E',  # Red (Hawks-like)
    '#007A33',  # Green (Celtics-like)
    '#1D428A',  # Blue (Warriors-like)
    '#552583',  # Purple (Lakers-like)
    '#FEC524',  # Gold (Nuggets-like)
    '#007AC1',  # Cyan (Thunder-like)
    '#CE1141',  # Crimson (Rockets-like)
    '#F58426',  # Orange (Knicks-like)
]

# Team colors for tooltip borders
TEAM_COLORS = {
    'ATL': '#E03A3E', 'BOS': '#007A33', 'BKN': '#777777', 'CHA': '#1D8CAB',
    'CHI': '#CE1141', 'CLE': '#860038', 'DAL': '#00538C', 'DEN': '#FEC524',
    'DET': '#C8102E', 'GSW': '#1D428A', 'HOU': '#CE1141', 'IND': '#FDBB30',
    'LAC': '#C8102E', 'LAL': '#552583', 'MEM': '#5D76A9', 'MIA': '#98002E',
    'MIL': '#00471B', 'MIN': '#236192', 'NOP': '#C8102E', 'NYK': '#F58426',
    'OKC': '#007AC1', 'ORL': '#0077C0', 'PHI': '#006BB6', 'PHX': '#E56020',
    'POR': '#E03A3E', 'SAC': '#5A2D81', 'SAS': '#C4CED4', 'TOR': '#CE1141',
    'UTA': '#4B7AB3', 'WAS': '#E31837'
}


# =============================================================================
# HTML TEMPLATE
# =============================================================================

def get_html_template():
    """
    Returns the complete HTML template with placeholders for data injection.
    
    Placeholders:
        {player_count} - Number of players in clustering
        {min_mpg} - Minimum MPG threshold used
        {feature_count} - Number of features (dimensions)
        {cluster_data_json} - Full cluster data as JSON string
        {branch_colors_json} - Branch colors array as JSON string
        {team_colors_json} - Team colors dict as JSON string
        {tight_clusters_html} - Pre-rendered tight clusters cards
        {similarity_html} - Pre-rendered similarity cards
    """
    
    return '''<!DOCTYPE html>
<html>
<head>
    <title>NBA Player Clustering - Hierarchical Analysis</title>
    <meta charset="UTF-8">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        /* ================================================================
           BASE STYLES - Matching player_stats_dashboard.html
           ================================================================ */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%); 
            color: white; 
            min-height: 100vh;
            padding: 20px;
        }}
        
        /* ================================================================
           HEADER
           ================================================================ */
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2.5rem;
            background: linear-gradient(90deg, #007AC1, #4ade80);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            color: #888;
            font-size: 1rem;
        }}
        
        /* ================================================================
           MAIN LAYOUT
           ================================================================ */
        .main-container {{
            max-width: 1800px;
            margin: 0 auto;
        }}
        
        /* ================================================================
           META BADGES (top info bar)
           ================================================================ */
        .meta-info {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 25px;
            justify-content: center;
        }}
        .meta-badge {{
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            padding: 10px 18px;
            border-radius: 25px;
            font-size: 0.85rem;
            color: #aaa;
            border: 1px solid #2a3a5a;
        }}
        .meta-badge strong {{
            color: #4ade80;
        }}
        
        /* ================================================================
           SECTION CARDS
           ================================================================ */
        .section-card {{
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid #2a3a5a;
        }}
        .section-card h2 {{
            color: #4ade80;
            font-size: 1.3rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-card .description {{
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 20px;
            line-height: 1.6;
        }}
        
        /* ================================================================
           DENDROGRAM CONTAINER
           ================================================================ */
        .dendrogram-wrapper {{
            background: #0a1628;
            border-radius: 10px;
            padding: 20px;
            overflow-x: auto;
            overflow-y: visible;
            border: 1px solid #1a2744;
        }}
        
        #dendrogram-svg {{
            display: block;
            min-width: 100%;
        }}
        
        /* ================================================================
           DENDROGRAM ELEMENTS
           ================================================================ */
        .link {{
            fill: none;
            stroke-width: 2px;
            stroke-opacity: 0.7;
            transition: stroke-opacity 0.2s, stroke-width 0.2s;
        }}
        .link:hover {{
            stroke-opacity: 1;
            stroke-width: 3px;
        }}
        
        .node {{
            cursor: default;
        }}
        .node.leaf {{
            cursor: pointer;
        }}
        .node circle {{
            stroke-width: 2px;
            transition: r 0.2s;
        }}
        .node.leaf:hover circle {{
            r: 7;
        }}
        
        /* Leaf label (headshot + name) */
        .leaf-label {{
            display: flex;
            align-items: center;
            gap: 6px;
            pointer-events: none;
        }}
        .leaf-headshot {{
            width: 24px;
            height: 18px;
            border-radius: 3px;
            object-fit: cover;
            background: #1a1a2e;
        }}
        .leaf-name {{
            font-size: 11px;
            font-weight: 500;
            color: #e0e0e0;
        }}
        
        /* ================================================================
           TOOLTIP (positioned fixed, smart placement)
           ================================================================ */
        .tooltip {{
            position: fixed;
            background: linear-gradient(135deg, #1a2744 0%, #16213e 100%);
            border: 2px solid #4ade80;
            border-radius: 10px;
            padding: 0;
            pointer-events: none;
            z-index: 10000;
            min-width: 200px;
            max-width: 260px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.6);
            opacity: 0;
            transition: opacity 0.15s ease;
            overflow: hidden;
        }}
        .tooltip.visible {{
            opacity: 1;
        }}
        
        .tooltip-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 15px;
            background: #0a1628;
            border-bottom: 3px solid #4ade80;
        }}
        .tooltip-headshot {{
            width: 50px;
            height: 36px;
            border-radius: 5px;
            object-fit: cover;
            background: #1a1a2e;
            flex-shrink: 0;
        }}
        .tooltip-info {{
            flex: 1;
            min-width: 0;
        }}
        .tooltip-name {{
            font-weight: 700;
            font-size: 0.95rem;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .tooltip-team {{
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .tooltip-body {{
            padding: 12px 15px;
        }}
        .tooltip-stat {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            font-size: 0.85rem;
            color: #aaa;
        }}
        .tooltip-stat-label {{
            color: #888;
        }}
        .tooltip-stat-value {{
            font-weight: 600;
            color: #fff;
        }}
        
        /* ================================================================
           LEGEND (branch colors)
           ================================================================ */
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 15px;
            padding: 10px 15px;
            background: #0a1628;
            border-radius: 8px;
            border: 1px solid #1a2744;
        }}
        .legend-title {{
            color: #888;
            font-size: 0.8rem;
            margin-right: 10px;
            display: flex;
            align-items: center;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.8rem;
            color: #aaa;
        }}
        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
        }}
        
        /* ================================================================
           TIGHT CLUSTERS GRID
           ================================================================ */
        .clusters-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }}
        
        .cluster-card {{
            background: #0a1628;
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid #4ade80;
            border: 1px solid #1a2744;
            border-left: 4px solid #4ade80;
        }}
        .cluster-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid #2a3a5a;
        }}
        .cluster-title {{
            font-weight: 700;
            color: #4ade80;
            font-size: 0.95rem;
        }}
        .cluster-stats {{
            font-size: 0.75rem;
            color: #888;
        }}
        
        .cluster-members {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .cluster-member {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .cluster-member-headshot {{
            width: 36px;
            height: 26px;
            border-radius: 4px;
            object-fit: cover;
            background: #1a1a2e;
            flex-shrink: 0;
        }}
        .cluster-member-name {{
            font-size: 0.85rem;
            color: #ccc;
            flex: 1;
        }}
        .cluster-member-ppg {{
            font-size: 0.8rem;
            color: #fbbf24;
            font-weight: 600;
        }}
        
        /* ================================================================
           SIMILARITY GRID
           ================================================================ */
        .similarity-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 15px;
        }}
        
        .similarity-card {{
            background: #0a1628;
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #1a2744;
        }}
        .similarity-target {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid #2a3a5a;
        }}
        .similarity-target-headshot {{
            width: 50px;
            height: 36px;
            border-radius: 5px;
            object-fit: cover;
            background: #1a1a2e;
            flex-shrink: 0;
        }}
        .similarity-target-info {{
            flex: 1;
        }}
        .similarity-target-name {{
            font-weight: 700;
            color: #fff;
            font-size: 1rem;
        }}
        .similarity-target-team {{
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .similarity-list {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .similarity-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.85rem;
        }}
        .similarity-item-rank {{
            color: #4ade80;
            font-weight: 700;
            width: 22px;
            text-align: right;
        }}
        .similarity-item-headshot {{
            width: 28px;
            height: 20px;
            border-radius: 3px;
            object-fit: cover;
            background: #1a1a2e;
            flex-shrink: 0;
        }}
        .similarity-item-name {{
            color: #ccc;
            flex: 1;
        }}
        .similarity-item-distance {{
            color: #666;
            font-size: 0.75rem;
        }}
        
        /* ================================================================
           RIGHT PANEL - PLAYER FINDER
           ================================================================ */
        .page-layout {{
            display: flex;
            gap: 20px;
        }}
        .main-content {{
            flex: 1;
            min-width: 0;
        }}
        .right-panel {{
            width: 320px;
            flex-shrink: 0;
            position: sticky;
            top: 20px;
            align-self: flex-start;
            max-height: calc(100vh - 40px);
            overflow-y: auto;
        }}
        
        .finder-card {{
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #2a3a5a;
            margin-bottom: 15px;
        }}
        .finder-card h3 {{
            color: #4ade80;
            font-size: 1rem;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* Search input */
        .search-container {{
            position: relative;
            margin-bottom: 15px;
        }}
        .search-input {{
            width: 100%;
            padding: 10px 15px;
            border: 2px solid #2a3a5a;
            border-radius: 8px;
            background: #0a1628;
            color: #fff;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-input:focus {{
            border-color: #4ade80;
        }}
        .search-input::placeholder {{
            color: #555;
        }}
        
        /* Search dropdown */
        .search-dropdown {{
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #0a1628;
            border: 1px solid #2a3a5a;
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 100;
            display: none;
            margin-top: 4px;
        }}
        .search-dropdown.active {{
            display: block;
        }}
        .search-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            cursor: pointer;
            border-bottom: 1px solid #1a2744;
            transition: background 0.15s;
        }}
        .search-item:last-child {{
            border-bottom: none;
        }}
        .search-item:hover {{
            background: #1a2744;
        }}
        .search-item-headshot {{
            width: 28px;
            height: 20px;
            border-radius: 3px;
            object-fit: cover;
            background: #1a1a2e;
        }}
        .search-item-name {{
            color: #ccc;
            font-size: 0.85rem;
        }}
        .search-item-team {{
            color: #888;
            font-size: 0.75rem;
            margin-left: auto;
        }}
        
        /* Selected players */
        .selected-players {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 15px;
        }}
        .selected-player {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            background: #0a1628;
            border-radius: 8px;
            border: 2px solid #4ade80;
        }}
        .selected-player-headshot {{
            width: 32px;
            height: 24px;
            border-radius: 4px;
            object-fit: cover;
            background: #1a1a2e;
        }}
        .selected-player-name {{
            color: #fff;
            font-size: 0.85rem;
            font-weight: 600;
            flex: 1;
        }}
        .selected-player-remove {{
            color: #f87171;
            cursor: pointer;
            font-size: 1.2rem;
            font-weight: bold;
            padding: 0 5px;
            transition: color 0.15s;
        }}
        .selected-player-remove:hover {{
            color: #ff4444;
        }}
        
        .clear-all-btn {{
            width: 100%;
            padding: 8px;
            background: #333;
            border: none;
            border-radius: 6px;
            color: #aaa;
            font-size: 0.8rem;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .clear-all-btn:hover {{
            background: #444;
            color: #fff;
        }}
        
        .no-selection {{
            color: #666;
            font-size: 0.85rem;
            text-align: center;
            padding: 15px;
        }}
        
        /* Path info section */
        .path-info {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #2a3a5a;
        }}
        .path-info h4 {{
            color: #fbbf24;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }}
        .path-players {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-height: 350px;
            overflow-y: auto;
        }}
        .path-player {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 10px;
            background: #0d1a2a;
            border-radius: 6px;
            font-size: 0.8rem;
            border-left: 3px solid #333;
        }}
        .path-player.selected {{
            background: #1a2a1a;
            border-left-color: #fbbf24;
        }}
        .path-player.intermediate {{
            border-left-color: #0ea5e9;
            margin-left: 15px;
        }}
        .path-player.intermediate .path-player-name {{
            color: #0ea5e9;
        }}
        .path-player-headshot {{
            width: 24px;
            height: 18px;
            border-radius: 3px;
            object-fit: cover;
            background: #1a1a2e;
            flex-shrink: 0;
        }}
        .path-player-name {{
            color: #ccc;
            flex: 1;
        }}
        .path-player.selected .path-player-name {{
            color: #fbbf24;
            font-weight: 600;
        }}
        .path-player-badge {{
            font-size: 0.65rem;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            flex-shrink: 0;
        }}
        .path-player-badge.start {{
            background: #fbbf24;
            color: #000;
        }}
        .path-player-badge.end {{
            background: #fbbf24;
            color: #000;
        }}
        .path-player-badge.stop {{
            background: #f97316;
            color: #000;
        }}
        .path-player-badge.via {{
            background: #0ea5e9;
            color: #000;
        }}
        .path-arrow {{
            text-align: center;
            color: #4ade80;
            font-size: 0.9rem;
            padding: 2px 0;
            margin-left: 15px;
        }}
        
        .path-empty {{
            color: #555;
            font-size: 0.8rem;
            text-align: center;
            padding: 10px;
        }}
        
        /* ================================================================
           RESPONSIVE - Hide panel on small screens
           ================================================================ */
        @media (max-width: 1100px) {{
            .page-layout {{
                flex-direction: column;
            }}
            .right-panel {{
                width: 100%;
                position: static;
                max-height: none;
            }}
        }}
    </style>
</head>
<body>
    <!-- ================================================================
         HEADER
         ================================================================ -->
    <div class="header">
        <h1>🌲 NBA Player Clustering</h1>
        <div class="subtitle">Hierarchical Analysis • Ward Linkage • 2025-26 Season</div>
    </div>
    
    <div class="main-container">
        <!-- ================================================================
             META INFORMATION
             ================================================================ -->
        <div class="meta-info">
            <div class="meta-badge"><strong>{player_count}</strong> players (≥{min_mpg} MPG)</div>
            <div class="meta-badge">Method: <strong>Ward Linkage</strong></div>
            <div class="meta-badge">Features: <strong>{feature_count}</strong> dimensions</div>
            <div class="meta-badge">Distance: <strong>Cophenetic</strong> (tree-based)</div>
        </div>
        
        <!-- Page layout with main content and right panel -->
        <div class="page-layout">
            <div class="main-content">
                <!-- ================================================================
                     DENDROGRAM SECTION
                     ================================================================ -->
                <div class="section-card">
                    <h2>📊 Hierarchical Dendrogram</h2>
                    <p class="description">
                        Players grouped by statistical similarity. Tree branches merge at heights 
                        proportional to dissimilarity (Ward distance). <strong>Hover over leaf nodes</strong> 
                        (rightmost) to see player details. Use the panel on the right to find and 
                        highlight paths between players.
                    </p>
                    
                    <!-- Legend -->
                    <div class="legend">
                        <span class="legend-title">Branch Colors:</span>
                        <div id="legend-items"></div>
                    </div>
                    
                    <!-- Dendrogram -->
                    <div class="dendrogram-wrapper">
                        <svg id="dendrogram-svg"></svg>
                    </div>
                </div>
                
                <!-- ================================================================
                     TIGHT CLUSTERS SECTION
                     ================================================================ -->
                <div class="section-card">
                    <h2>🎯 Tight Clusters</h2>
                    <p class="description">
                        Natural groupings of 2-6 players who merge early in the tree (most similar 
                        to each other). Sorted by average PPG descending.
                    </p>
                    <div class="clusters-grid">
                        {tight_clusters_html}
                    </div>
                </div>
                
                <!-- ================================================================
                     SIMILARITY SECTION
                     ================================================================ -->
                <div class="section-card">
                    <h2>🔍 Player Similarity</h2>
                    <p class="description">
                        Most similar players based on cophenetic distance (height at which they 
                        merge in the tree). Lower distance = more similar according to Ward's criterion.
                    </p>
                    <div class="similarity-grid">
                        {similarity_html}
                    </div>
                </div>
            </div>
            
            <!-- ================================================================
                 RIGHT PANEL - PLAYER FINDER
                 ================================================================ -->
            <div class="right-panel">
                <div class="finder-card">
                    <h3>🔎 Path Finder</h3>
                    
                    <!-- Search input -->
                    <div class="search-container">
                        <input type="text" 
                               id="player-search" 
                               class="search-input" 
                               placeholder="Search player (e.g., Luka, Jokic)">
                        <div id="search-dropdown" class="search-dropdown"></div>
                    </div>
                    
                    <!-- Selected players -->
                    <div id="selected-players" class="selected-players">
                        <div class="no-selection">Select 2+ players to see merge path</div>
                    </div>
                    
                    <button id="clear-all" class="clear-all-btn" style="display: none;">
                        Clear All
                    </button>
                    
                    <!-- Path info (shows when 2 players selected) -->
                    <div id="path-info" class="path-info" style="display: none;">
                        <h4>📍 Merge Path</h4>
                        <div id="path-players" class="path-players"></div>
                    </div>
                </div>
                
                <div class="finder-card">
                    <h3>ℹ️ How it works</h3>
                    <p style="color: #888; font-size: 0.8rem; line-height: 1.5;">
                        Select 2+ players to highlight their connecting path in the tree. 
                        Players are ordered by their tree position (top to bottom).
                        <br><br>
                        <strong style="color: #fbbf24;">● Yellow</strong> = selected players<br>
                        <strong style="color: #0ea5e9;">● Cyan</strong> = players on the merge path<br>
                        <strong style="color: #4ade80;">— Green line</strong> = connecting branches<br>
                        <strong style="color: #555;">● Gray</strong> = unrelated players
                    </p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Tooltip (positioned by JS) -->
    <div class="tooltip" id="tooltip"></div>
    
    <!-- ================================================================
         JAVASCRIPT
         ================================================================ -->
    <script>
    // =========================================================================
    // DATA INJECTION
    // =========================================================================
    
    const clusterData = {cluster_data_json};
    const branchColors = {branch_colors_json};
    const teamColors = {team_colors_json};
    
    // =========================================================================
    // GLOBAL STATE
    // =========================================================================
    
    let selectedPlayers = [];  // Array of player objects with id, name, abbrev, team, player_id, node
    let allLeafNodes = [];     // Populated after rendering
    let rootNode = null;       // D3 hierarchy root
    let linkElements = null;   // D3 selection of links
    let nodeElements = null;   // D3 selection of nodes
    
    // =========================================================================
    // UTILITY FUNCTIONS
    // =========================================================================
    
    /**
     * Get team color for tooltip border
     */
    function getTeamColor(team) {{
        return teamColors[team] || '#4ade80';
    }}
    
    /**
     * Get branch color by index (cycles if > 8)
     */
    function getBranchColor(colorIdx) {{
        if (colorIdx === undefined || colorIdx === null) return '#4ade80';
        return branchColors[colorIdx % branchColors.length];
    }}
    
    /**
     * Normalize name for search (remove accents)
     */
    function normalizeName(name) {{
        return name.toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '');
    }}
    
    /**
     * Position tooltip smartly to avoid viewport cutoff
     */
    function positionTooltip(event) {{
        const tooltip = document.getElementById('tooltip');
        const rect = tooltip.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        
        const padding = 15;
        let left = event.clientX + padding;
        let top = event.clientY - padding;
        
        if (left + rect.width > vw - padding) left = event.clientX - rect.width - padding;
        if (top + rect.height > vh - padding) top = vh - rect.height - padding;
        if (top < padding) top = padding;
        if (left < padding) left = padding;
        
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }}
    
    // =========================================================================
    // PATH FINDING ALGORITHMS
    // =========================================================================
    
    /**
     * Get path from a node to the root (list of ancestors)
     */
    function getPathToRoot(node) {{
        const path = [];
        let current = node;
        while (current) {{
            path.push(current);
            current = current.parent;
        }}
        return path;
    }}
    
    /**
     * Find Lowest Common Ancestor (LCA) of two nodes
     */
    function findLCA(node1, node2) {{
        const path1 = getPathToRoot(node1);
        const path2Set = new Set(getPathToRoot(node2));
        
        for (const node of path1) {{
            if (path2Set.has(node)) {{
                return node;
            }}
        }}
        return null;
    }}
    
    /**
     * Find LCA of multiple nodes
     */
    function findLCAMultiple(nodes) {{
        if (nodes.length === 0) return null;
        if (nodes.length === 1) return nodes[0];
        
        let lca = nodes[0];
        for (let i = 1; i < nodes.length; i++) {{
            lca = findLCA(lca, nodes[i]);
        }}
        return lca;
    }}
    
    /**
     * Get all nodes on the path between two nodes (through LCA)
     */
    function getPathBetween(node1, node2) {{
        const lca = findLCA(node1, node2);
        if (!lca) return [];
        
        const path1 = [];
        let current = node1;
        while (current && current !== lca) {{
            path1.push(current);
            current = current.parent;
        }}
        path1.push(lca);
        
        const path2 = [];
        current = node2;
        while (current && current !== lca) {{
            path2.push(current);
            current = current.parent;
        }}
        
        // Combine: node1 -> lca -> node2
        return [...path1, ...path2.reverse()];
    }}
    
    /**
     * Get all leaf players in a subtree
     */
    function getLeafPlayers(node) {{
        const leaves = [];
        node.each(d => {{
            if (d.data.is_leaf) {{
                leaves.push(d);
            }}
        }});
        return leaves;
    }}
    
    /**
     * Get linear path of all leaf players from node1 to node2
     * Returns array in order: [node1, ...intermediates..., node2]
     */
    function getLinearPath(node1, node2) {{
        const lca = findLCA(node1, node2);
        if (!lca) return [node1, node2];
        
        // Get path from node1 to LCA (collecting leaf siblings along the way)
        const path1Leaves = [];
        let current = node1;
        while (current && current !== lca) {{
            // Add this node if it's a leaf
            if (current.data.is_leaf) {{
                path1Leaves.push(current);
            }}
            // Also check sibling subtree for leaves that merge before reaching LCA
            if (current.parent && current.parent !== lca) {{
                const sibling = current.parent.children.find(c => c !== current);
                if (sibling) {{
                    const siblingLeaves = getLeafPlayers(sibling);
                    path1Leaves.push(...siblingLeaves);
                }}
            }}
            current = current.parent;
        }}
        
        // Get path from node2 to LCA
        const path2Leaves = [];
        current = node2;
        while (current && current !== lca) {{
            if (current.data.is_leaf) {{
                path2Leaves.push(current);
            }}
            if (current.parent && current.parent !== lca) {{
                const sibling = current.parent.children.find(c => c !== current);
                if (sibling) {{
                    const siblingLeaves = getLeafPlayers(sibling);
                    path2Leaves.push(...siblingLeaves);
                }}
            }}
            current = current.parent;
        }}
        
        // Combine: node1 side + node2 side (reversed)
        // Remove duplicates and the selected nodes themselves
        const selectedIds = new Set([node1.data.id, node2.data.id]);
        const allIntermediate = [...path1Leaves, ...path2Leaves]
            .filter(n => !selectedIds.has(n.data.id));
        
        // Remove duplicates
        const seen = new Set();
        const unique = allIntermediate.filter(n => {{
            if (seen.has(n.data.id)) return false;
            seen.add(n.data.id);
            return true;
        }});
        
        return unique;
    }}
    
    /**
     * Get all players "on the path" between selected players
     * For 2 players: returns linear path
     * For 3+ players: returns union of all pairwise paths
     */
    function getPlayersOnPath(selectedNodes) {{
        if (selectedNodes.length < 2) return [];
        
        if (selectedNodes.length === 2) {{
            return getLinearPath(selectedNodes[0], selectedNodes[1]);
        }}
        
        // For 3+ players, get union of all paths
        const allOnPath = new Map();
        
        for (let i = 0; i < selectedNodes.length; i++) {{
            for (let j = i + 1; j < selectedNodes.length; j++) {{
                const pathLeaves = getLinearPath(selectedNodes[i], selectedNodes[j]);
                pathLeaves.forEach(n => allOnPath.set(n.data.id, n));
            }}
        }}
        
        return Array.from(allOnPath.values());
    }}
    
    /**
     * Get all links that are on the path between selected nodes
     */
    function getPathLinks(selectedNodes) {{
        if (selectedNodes.length < 2) return new Set();
        
        const pathNodes = new Set();
        
        // For each pair, add all nodes on path
        for (let i = 0; i < selectedNodes.length; i++) {{
            for (let j = i + 1; j < selectedNodes.length; j++) {{
                const path = getPathBetween(selectedNodes[i], selectedNodes[j]);
                path.forEach(n => pathNodes.add(n));
            }}
        }}
        
        return pathNodes;
    }}
    
    // =========================================================================
    // SEARCH FUNCTIONALITY
    // =========================================================================
    
    function initSearch() {{
        const searchInput = document.getElementById('player-search');
        const dropdown = document.getElementById('search-dropdown');
        
        searchInput.addEventListener('input', function() {{
            const query = normalizeName(this.value.trim());
            
            if (query.length < 2) {{
                dropdown.classList.remove('active');
                return;
            }}
            
            // Filter leaf nodes by name
            const matches = allLeafNodes.filter(node => {{
                const name = normalizeName(node.data.name);
                return name.includes(query);
            }}).slice(0, 8);
            
            if (matches.length === 0) {{
                dropdown.classList.remove('active');
                return;
            }}
            
            // Render dropdown
            dropdown.innerHTML = matches.map(node => `
                <div class="search-item" data-id="${{node.data.id}}">
                    <img class="search-item-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{node.data.player_id}}.png"
                         onerror="this.style.visibility='hidden'">
                    <span class="search-item-name">${{node.data.abbrev}}</span>
                    <span class="search-item-team">${{node.data.team}}</span>
                </div>
            `).join('');
            
            // Add click handlers
            dropdown.querySelectorAll('.search-item').forEach(item => {{
                item.addEventListener('click', function() {{
                    const id = parseInt(this.dataset.id);
                    const node = allLeafNodes.find(n => n.data.id === id);
                    if (node) {{
                        addSelectedPlayer(node);
                    }}
                    searchInput.value = '';
                    dropdown.classList.remove('active');
                }});
            }});
            
            dropdown.classList.add('active');
        }});
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.search-container')) {{
                dropdown.classList.remove('active');
            }}
        }});
    }}
    
    // =========================================================================
    // SELECTED PLAYERS MANAGEMENT
    // =========================================================================
    
    function addSelectedPlayer(node) {{
        // Check if already selected
        if (selectedPlayers.find(p => p.id === node.data.id)) {{
            return;
        }}
        
        // Max 8 players
        if (selectedPlayers.length >= 8) {{
            alert('Maximum 8 players can be selected');
            return;
        }}
        
        selectedPlayers.push({{
            id: node.data.id,
            name: node.data.name,
            abbrev: node.data.abbrev,
            team: node.data.team,
            player_id: node.data.player_id,
            node: node
        }});
        
        updateSelectedPlayersUI();
        updatePathHighlighting();
    }}
    
    function removeSelectedPlayer(id) {{
        selectedPlayers = selectedPlayers.filter(p => p.id !== id);
        updateSelectedPlayersUI();
        updatePathHighlighting();
    }}
    
    function clearAllSelected() {{
        selectedPlayers = [];
        updateSelectedPlayersUI();
        updatePathHighlighting();
    }}
    
    function updateSelectedPlayersUI() {{
        const container = document.getElementById('selected-players');
        const clearBtn = document.getElementById('clear-all');
        const pathInfo = document.getElementById('path-info');
        
        if (selectedPlayers.length === 0) {{
            container.innerHTML = '<div class="no-selection">Select 2+ players to see merge path</div>';
            clearBtn.style.display = 'none';
            pathInfo.style.display = 'none';
            return;
        }}
        
        container.innerHTML = selectedPlayers.map(p => `
            <div class="selected-player">
                <img class="selected-player-headshot" 
                     src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{p.player_id}}.png"
                     onerror="this.style.visibility='hidden'">
                <span class="selected-player-name">${{p.abbrev}}</span>
                <span class="selected-player-remove" data-id="${{p.id}}">×</span>
            </div>
        `).join('');
        
        // Add remove handlers
        container.querySelectorAll('.selected-player-remove').forEach(btn => {{
            btn.addEventListener('click', function() {{
                removeSelectedPlayer(parseInt(this.dataset.id));
            }});
        }});
        
        clearBtn.style.display = 'block';
        
        // Update path info
        updatePathInfo();
    }}
    
    /**
     * Order selected nodes by their position in the tree (vertical position = x coordinate)
     * This gives a natural top-to-bottom ordering in the dendrogram
     */
    function orderNodesByTreePosition(nodes) {{
        return [...nodes].sort((a, b) => a.x - b.x);
    }}
    
    /**
     * Get all leaf nodes ordered by tree position (top to bottom)
     * This is the fundamental 1D ordering of the dendrogram
     */
    function getOrderedLeaves() {{
        return [...allLeafNodes].sort((a, b) => a.x - b.x);
    }}
    
    /**
     * Get all players between two selected nodes (in tree order)
     * Since the tree is 1D ordered, this is just a slice of the array
     */
    function getPlayersBetween(orderedLeaves, node1, node2) {{
        const idx1 = orderedLeaves.findIndex(n => n.data.id === node1.data.id);
        const idx2 = orderedLeaves.findIndex(n => n.data.id === node2.data.id);
        
        const minIdx = Math.min(idx1, idx2);
        const maxIdx = Math.max(idx1, idx2);
        
        // Return everyone between (exclusive of endpoints)
        return orderedLeaves.slice(minIdx + 1, maxIdx);
    }}
    
    function updatePathInfo() {{
        const pathInfo = document.getElementById('path-info');
        const pathPlayers = document.getElementById('path-players');
        
        if (selectedPlayers.length < 2) {{
            pathInfo.style.display = 'none';
            return;
        }}
        
        pathInfo.style.display = 'block';
        
        // Get ordered leaves (the 1D order)
        const orderedLeaves = getOrderedLeaves();
        
        // Order selected players by tree position
        const selectedNodes = selectedPlayers.map(p => p.node);
        const orderedSelected = orderNodesByTreePosition(selectedNodes);
        
        // Build linear display
        let html = '';
        
        for (let i = 0; i < orderedSelected.length; i++) {{
            const node = orderedSelected[i];
            const playerData = selectedPlayers.find(p => p.id === node.data.id);
            
            // Badge: first = START, last = END, middle = STOP N
            let badgeClass = 'stop';
            let badgeText = `STOP ${{i + 1}}`;
            if (i === 0) {{
                badgeClass = 'start';
                badgeText = 'START';
            }} else if (i === orderedSelected.length - 1) {{
                badgeClass = 'end';
                badgeText = 'END';
            }}
            
            // Selected player
            html += `
                <div class="path-player selected">
                    <img class="path-player-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{playerData.player_id}}.png"
                         onerror="this.style.visibility='hidden'">
                    <span class="path-player-name">${{playerData.abbrev}}</span>
                    <span class="path-player-badge ${{badgeClass}}">${{badgeText}}</span>
                </div>
            `;
            
            // Players between this and next selected (just slice the 1D array)
            if (i < orderedSelected.length - 1) {{
                const nextNode = orderedSelected[i + 1];
                const between = getPlayersBetween(orderedLeaves, node, nextNode);
                
                if (between.length > 0) {{
                    html += '<div class="path-arrow">↓</div>';
                    
                    // Show up to 6 intermediates, collapse if more
                    const showCount = Math.min(between.length, 6);
                    const remaining = between.length - showCount;
                    
                    for (let j = 0; j < showCount; j++) {{
                        const intNode = between[j];
                        html += `
                            <div class="path-player intermediate">
                                <img class="path-player-headshot" 
                                     src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{intNode.data.player_id}}.png"
                                     onerror="this.style.visibility='hidden'">
                                <span class="path-player-name">${{intNode.data.abbrev}}</span>
                                <span class="path-player-badge via">VIA</span>
                            </div>
                        `;
                        if (j < showCount - 1) {{
                            html += '<div class="path-arrow">↓</div>';
                        }}
                    }}
                    
                    if (remaining > 0) {{
                        html += `<div class="path-arrow">↓ +${{remaining}} more</div>`;
                    }} else {{
                        html += '<div class="path-arrow">↓</div>';
                    }}
                }} else {{
                    html += '<div class="path-arrow">↓ adjacent</div>';
                }}
            }}
        }}
        
        pathPlayers.innerHTML = html;
    }}
    
    // =========================================================================
    // PATH HIGHLIGHTING
    // =========================================================================
    
    function updatePathHighlighting() {{
        if (!linkElements || !nodeElements) return;
        
        if (selectedPlayers.length === 0) {{
            // Reset all to default
            linkElements
                .attr('stroke-opacity', 0.7)
                .attr('stroke-width', 2)
                .attr('stroke', d => getBranchColor(d.source.data.branch_color));
            
            nodeElements.selectAll('circle')
                .attr('r', d => d.data.is_leaf ? 5 : 3)
                .attr('fill', d => d.data.is_leaf ? '#1a1a2e' : '#0a1628')
                .attr('stroke', d => getBranchColor(d.data.branch_color))
                .attr('stroke-width', 2);
            
            nodeElements.selectAll('foreignObject')
                .attr('x', 10);
            
            nodeElements.selectAll('.leaf-name')
                .style('color', '#e0e0e0')
                .style('font-weight', '500')
                .style('font-size', '11px');
            
            nodeElements.selectAll('.leaf-headshot')
                .style('filter', 'none')
                .style('width', '24px')
                .style('height', '18px');
            
            return;
        }}
        
        // Get the 1D ordering
        const orderedLeaves = getOrderedLeaves();
        const selectedIds = new Set(selectedPlayers.map(p => p.id));
        
        // Find min/max indices of selected players in the 1D order
        let minIdx = Infinity, maxIdx = -1;
        orderedLeaves.forEach((node, idx) => {{
            if (selectedIds.has(node.data.id)) {{
                minIdx = Math.min(minIdx, idx);
                maxIdx = Math.max(maxIdx, idx);
            }}
        }});
        
        // Everyone between min and max is "on path"
        const onPathIds = new Set();
        for (let i = minIdx; i <= maxIdx; i++) {{
            onPathIds.add(orderedLeaves[i].data.id);
        }}
        
        // For link highlighting, we need to know which internal nodes are on the path
        // An internal node is on path if it's an ancestor of any on-path leaf
        const pathNodes = new Set();
        orderedLeaves.forEach(leaf => {{
            if (onPathIds.has(leaf.data.id)) {{
                let current = leaf;
                while (current) {{
                    pathNodes.add(current);
                    current = current.parent;
                }}
            }}
        }});
        
        // Links: highlight if both ends are on path
        linkElements
            .attr('stroke-opacity', d => {{
                const onPath = pathNodes.has(d.source) && pathNodes.has(d.target);
                return onPath ? 1 : 0.15;
            }})
            .attr('stroke-width', d => {{
                const onPath = pathNodes.has(d.source) && pathNodes.has(d.target);
                return onPath ? 4 : 1;
            }})
            .attr('stroke', d => {{
                const onPath = pathNodes.has(d.source) && pathNodes.has(d.target);
                return onPath ? '#4ade80' : '#333';
            }});
        
        // Nodes
        nodeElements.selectAll('circle')
            .attr('r', d => {{
                if (selectedIds.has(d.data.id)) return 12;
                if (d.data.is_leaf && onPathIds.has(d.data.id)) return 8;
                if (pathNodes.has(d)) return d.data.is_leaf ? 5 : 3;
                return d.data.is_leaf ? 3 : 2;
            }})
            .attr('fill', d => {{
                if (selectedIds.has(d.data.id)) return '#fbbf24';
                if (d.data.is_leaf && onPathIds.has(d.data.id)) return '#0ea5e9';
                return d.data.is_leaf ? '#1a1a2e' : '#0a1628';
            }})
            .attr('stroke', d => {{
                if (selectedIds.has(d.data.id)) return '#fbbf24';
                if (d.data.is_leaf && onPathIds.has(d.data.id)) return '#0ea5e9';
                if (pathNodes.has(d)) return '#4ade80';
                return '#222';
            }})
            .attr('stroke-width', d => {{
                if (selectedIds.has(d.data.id)) return 3;
                if (d.data.is_leaf && onPathIds.has(d.data.id)) return 2;
                return 2;
            }});
        
        // Labels
        nodeElements.each(function(d) {{
            if (!d.data.is_leaf) return;
            
            const node = d3.select(this);
            const isSelected = selectedIds.has(d.data.id);
            const isOnPath = onPathIds.has(d.data.id) && !isSelected;
            
            node.selectAll('foreignObject')
                .attr('x', isSelected ? 18 : (isOnPath ? 14 : 8));
            
            node.selectAll('.leaf-name')
                .style('color', isSelected ? '#fbbf24' : (isOnPath ? '#0ea5e9' : '#555'))
                .style('font-weight', isSelected ? '700' : (isOnPath ? '600' : '400'))
                .style('font-size', isSelected ? '12px' : (isOnPath ? '11px' : '9px'));
            
            node.selectAll('.leaf-headshot')
                .style('filter', isSelected || isOnPath ? 'none' : 'grayscale(100%) brightness(0.4)')
                .style('width', isSelected ? '28px' : (isOnPath ? '26px' : '16px'))
                .style('height', isSelected ? '20px' : (isOnPath ? '19px' : '12px'));
        }});
    }}
    
    // =========================================================================
    // LEGEND RENDERING
    // =========================================================================
    
    function buildLegend() {{
        const container = document.getElementById('legend-items');
        container.innerHTML = '';
        
        for (let i = 0; i < Math.min(8, branchColors.length); i++) {{
            const item = document.createElement('span');
            item.className = 'legend-item';
            item.innerHTML = `
                <span class="legend-color" style="background: ${{branchColors[i]}}"></span>
                <span>Branch ${{i + 1}}</span>
            `;
            container.appendChild(item);
        }}
    }}
    
    // =========================================================================
    // DENDROGRAM RENDERING
    // =========================================================================
    
    /**
     * Render the D3.js dendrogram
     */
    function renderDendrogram() {{
        const tree = clusterData.tree;
        const leafCount = tree.count;
        
        // Layout dimensions
        const nodeHeight = 26;
        const margin = {{ top: 20, right: 200, bottom: 20, left: 40 }};
        const width = 1100;
        const height = Math.max(600, leafCount * nodeHeight + margin.top + margin.bottom);
        
        const svg = d3.select('#dendrogram-svg')
            .attr('width', width)
            .attr('height', height);
        
        svg.selectAll('*').remove();
        
        const g = svg.append('g')
            .attr('transform', `translate(${{margin.left}},${{margin.top}})`);
        
        // Create cluster layout
        const cluster = d3.cluster()
            .size([height - margin.top - margin.bottom, width - margin.left - margin.right - 120]);
        
        // Convert to D3 hierarchy
        rootNode = d3.hierarchy(tree);
        cluster(rootNode);
        
        // Store all leaf nodes for search
        allLeafNodes = rootNode.descendants().filter(d => d.data.is_leaf);
        
        // Draw links - store reference globally
        linkElements = g.selectAll('.link')
            .data(rootNode.links())
            .join('path')
            .attr('class', 'link')
            .attr('stroke', d => getBranchColor(d.source.data.branch_color))
            .attr('d', d => `
                M${{d.source.y}},${{d.source.x}}
                H${{(d.source.y + d.target.y) / 2}}
                V${{d.target.x}}
                H${{d.target.y}}
            `);
        
        // Draw nodes - store reference globally
        nodeElements = g.selectAll('.node')
            .data(rootNode.descendants())
            .join('g')
            .attr('class', d => `node ${{d.data.is_leaf ? 'leaf' : 'internal'}}`)
            .attr('transform', d => `translate(${{d.y}},${{d.x}})`);
        
        // Circle for all nodes
        nodeElements.append('circle')
            .attr('r', d => d.data.is_leaf ? 5 : 3)
            .attr('fill', d => d.data.is_leaf ? '#1a1a2e' : '#0a1628')
            .attr('stroke', d => getBranchColor(d.data.branch_color));
        
        // Leaf node labels
        const leaves = nodeElements.filter(d => d.data.is_leaf);
        
        leaves.each(function(d) {{
            const leaf = d3.select(this);
            const data = d.data;
            
            const fo = leaf.append('foreignObject')
                .attr('x', 10)
                .attr('y', -10)
                .attr('width', 160)
                .attr('height', 20)
                .style('overflow', 'visible');
            
            const div = fo.append('xhtml:div')
                .attr('class', 'leaf-label');
            
            div.append('xhtml:img')
                .attr('class', 'leaf-headshot')
                .attr('src', `https://cdn.nba.com/headshots/nba/latest/1040x760/${{data.player_id}}.png`)
                .attr('onerror', "this.style.visibility='hidden'");
            
            div.append('xhtml:span')
                .attr('class', 'leaf-name')
                .text(data.abbrev);
        }});
        
        // Tooltip handling
        const tooltip = document.getElementById('tooltip');
        
        leaves.on('mouseenter', function(event, d) {{
            const data = d.data;
            const teamColor = getTeamColor(data.team);
            
            tooltip.innerHTML = `
                <div class="tooltip-header" style="border-bottom-color: ${{teamColor}}">
                    <img class="tooltip-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{data.player_id}}.png"
                         onerror="this.style.visibility='hidden'">
                    <div class="tooltip-info">
                        <div class="tooltip-name">${{data.name}}</div>
                        <div class="tooltip-team" style="color: ${{teamColor}}">${{data.team}}</div>
                    </div>
                </div>
                <div class="tooltip-body">
                    <div class="tooltip-stat">
                        <span class="tooltip-stat-label">PPG</span>
                        <span class="tooltip-stat-value">${{data.ppg}}</span>
                    </div>
                    <div class="tooltip-stat">
                        <span class="tooltip-stat-label">RPG</span>
                        <span class="tooltip-stat-value">${{data.rpg}}</span>
                    </div>
                    <div class="tooltip-stat">
                        <span class="tooltip-stat-label">APG</span>
                        <span class="tooltip-stat-value">${{data.apg}}</span>
                    </div>
                </div>
            `;
            
            positionTooltip(event);
            tooltip.classList.add('visible');
        }});
        
        leaves.on('mousemove', function(event) {{
            positionTooltip(event);
        }});
        
        leaves.on('mouseleave', function() {{
            tooltip.classList.remove('visible');
        }});
        
        // Click to add to selection
        leaves.on('click', function(event, d) {{
            event.stopPropagation();
            addSelectedPlayer(d);
        }});
    }}
    
    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    
    document.addEventListener('DOMContentLoaded', function() {{
        buildLegend();
        renderDendrogram();
        initSearch();
        
        // Clear all button
        document.getElementById('clear-all').addEventListener('click', clearAllSelected);
    }});
    </script>
</body>
</html>
'''


# =============================================================================
# HTML GENERATION HELPERS
# =============================================================================

def generate_tight_clusters_html(tight_clusters):
    """
    Generate HTML cards for tight clusters section.
    
    Args:
        tight_clusters: List of cluster dicts from cluster_players.py
        
    Returns:
        HTML string with cluster cards
    """
    html_parts = []
    
    for i, cluster in enumerate(tight_clusters):
        members_html = ''
        for m in cluster['members']:
            members_html += f'''
                <div class="cluster-member">
                    <img class="cluster-member-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/{m['player_id']}.png"
                         onerror="this.style.visibility='hidden'">
                    <span class="cluster-member-name">{m['abbrev']}</span>
                    <span class="cluster-member-ppg">{m['ppg']}</span>
                </div>
            '''
        
        card_html = f'''
            <div class="cluster-card" style="border-left-color: {BRANCH_COLORS[i % len(BRANCH_COLORS)]}">
                <div class="cluster-header">
                    <span class="cluster-title">Group {i + 1}</span>
                    <span class="cluster-stats">{cluster['count']} players • ~{cluster['mean_ppg']} PPG</span>
                </div>
                <div class="cluster-members">
                    {members_html}
                </div>
            </div>
        '''
        html_parts.append(card_html)
    
    return '\n'.join(html_parts)


def generate_similarity_html(similarity):
    """
    Generate HTML cards for similarity section.
    
    Args:
        similarity: Dict mapping player names to similarity data
        
    Returns:
        HTML string with similarity cards
    """
    html_parts = []
    
    for name, data in similarity.items():
        # Get last name for display
        last_name = name.split()[-1] if ' ' in name else name
        team_color = TEAM_COLORS.get(data['team'], '#4ade80')
        
        similar_html = ''
        for i, s in enumerate(data['similar']):
            similar_html += f'''
                <div class="similarity-item">
                    <span class="similarity-item-rank">{i + 1}.</span>
                    <img class="similarity-item-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/{s['player_id']}.png"
                         onerror="this.style.visibility='hidden'">
                    <span class="similarity-item-name">{s['abbrev']}</span>
                    <span class="similarity-item-distance">({s['distance']})</span>
                </div>
            '''
        
        card_html = f'''
            <div class="similarity-card">
                <div class="similarity-target">
                    <img class="similarity-target-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/{data['player_id']}.png"
                         onerror="this.style.visibility='hidden'">
                    <div class="similarity-target-info">
                        <div class="similarity-target-name">{last_name}</div>
                        <div class="similarity-target-team" style="color: {team_color}">{data['team']}</div>
                    </div>
                </div>
                <div class="similarity-list">
                    {similar_html}
                </div>
            </div>
        '''
        html_parts.append(card_html)
    
    return '\n'.join(html_parts)


# =============================================================================
# MAIN
# =============================================================================

def main(input_path=None, output_path=None):
    """
    Main function. Can be called directly with arguments (for Jupyter)
    or via command line with argparse.
    
    Args:
        input_path: Input JSON path from cluster_players.py (default: INPUT_PATH)
        output_path: Output HTML path (default: OUTPUT_PATH)
    """
    # Handle command line vs direct call
    if input_path is None and output_path is None:
        try:
            import sys
            # Check if running in Jupyter
            if 'ipykernel' in sys.modules:
                input_path = INPUT_PATH
                output_path = OUTPUT_PATH
            else:
                parser = argparse.ArgumentParser(
                    description='Generate interactive HTML visualization for player clustering'
                )
                parser.add_argument(
                    '--input', type=str, default=INPUT_PATH,
                    help=f'Input JSON path from cluster_players.py (default: {INPUT_PATH})'
                )
                parser.add_argument(
                    '--output', type=str, default=OUTPUT_PATH,
                    help=f'Output HTML path (default: {OUTPUT_PATH})'
                )
                args = parser.parse_args()
                input_path = args.input
                output_path = args.output
        except SystemExit:
            input_path = INPUT_PATH
            output_path = OUTPUT_PATH
    
    # Apply defaults
    input_path = input_path if input_path is not None else INPUT_PATH
    output_path = output_path if output_path is not None else OUTPUT_PATH
    
    print("=" * 70)
    print("GENERATE CLUSTER HTML")
    print("=" * 70)
    
    # -------------------------------------------------------------------------
    # Load cluster data
    # -------------------------------------------------------------------------
    print(f"\n[1/3] Loading {input_path}...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        cluster_data = json.load(f)
    
    meta = cluster_data['meta']
    print(f"       Players: {meta['player_count']}")
    print(f"       Features: {meta['features']}")
    print(f"       Tight clusters: {len(cluster_data['tight_clusters'])}")
    print(f"       Similarity targets: {len(cluster_data['similarity'])}")
    
    # -------------------------------------------------------------------------
    # Generate HTML sections
    # -------------------------------------------------------------------------
    print(f"\n[2/3] Generating HTML sections...")
    
    tight_clusters_html = generate_tight_clusters_html(cluster_data['tight_clusters'])
    print(f"       Generated {len(cluster_data['tight_clusters'])} cluster cards")
    
    similarity_html = generate_similarity_html(cluster_data['similarity'])
    print(f"       Generated {len(cluster_data['similarity'])} similarity cards")
    
    # -------------------------------------------------------------------------
    # Assemble final HTML
    # -------------------------------------------------------------------------
    print(f"\n[3/3] Assembling final HTML...")
    
    html = get_html_template().format(
        player_count=meta['player_count'],
        min_mpg=meta['min_mpg'],
        feature_count=len(meta['features']),
        cluster_data_json=json.dumps(cluster_data, ensure_ascii=False),
        branch_colors_json=json.dumps(BRANCH_COLORS),
        team_colors_json=json.dumps(TEAM_COLORS),
        tight_clusters_html=tight_clusters_html,
        similarity_html=similarity_html
    )
    
    # -------------------------------------------------------------------------
    # Write output
    # -------------------------------------------------------------------------
    print(f"\nSaving to {output_path}...")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"       File size: {len(html):,} bytes")
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"\nOpen {output_path} in a browser to view the visualization.")


if __name__ == "__main__":
    main()
