"""
================================================================================
GENERATE GRAPH HTML - Player Similarity Network Visualization
================================================================================

PURPOSE:
    Generate interactive HTML visualization for the player similarity graph.
    Uses UMAP coordinates for layout, shows communities, and allows shortest
    path queries between players.

INPUT:
    player_graph.json (from cluster_graph.py)

OUTPUT:
    player_graph_dashboard.html

VISUALIZATION FEATURES:
    1. UMAP-based scatter plot (nodes = players with headshots)
    2. Nodes colored by community
    3. Convex hulls around communities (subtle fill)
    4. Only bridge edges drawn (inter-community), thickness = similarity
    5. Click player → highlight all their connections
    6. Click two players → show shortest path (Dijkstra)
    7. Search to find players
    8. Show top bridge players (highest betweenness)

USAGE:
    python generate_graph_html.py
    python generate_graph_html.py --input custom.json --output custom.html

================================================================================
"""

import json
import argparse

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_PATH = "player_graph.json"
OUTPUT_PATH = "player_graph_dashboard.html"

# Community colors (distinct, colorblind-friendly)
COMMUNITY_COLORS = [
    '#E03A3E',  # Red
    '#007A33',  # Green
    '#1D428A',  # Blue
    '#552583',  # Purple
    '#FEC524',  # Gold
    '#007AC1',  # Cyan
    '#F58426',  # Orange
    '#CE1141',  # Crimson
    '#5D76A9',  # Slate blue
    '#00471B',  # Dark green
    '#C8102E',  # Red 2
    '#5A2D81',  # Purple 2
    '#236192',  # Blue 2
    '#E56020',  # Orange 2
    '#98002E',  # Maroon
]

# Team colors for tooltip
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
    """Returns the complete HTML template with placeholders."""
    
    return '''<!DOCTYPE html>
<html>
<head>
    <title>NBA Player Similarity Network</title>
    <meta charset="UTF-8">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        /* ================================================================
           BASE STYLES
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
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 2.2rem;
            background: linear-gradient(90deg, #007AC1, #4ade80);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }}
        .header .subtitle {{
            color: #888;
            font-size: 0.95rem;
        }}
        
        /* ================================================================
           LAYOUT
           ================================================================ */
        .main-container {{
            max-width: 1800px;
            margin: 0 auto;
        }}
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
        
        /* ================================================================
           META BADGES
           ================================================================ */
        .meta-info {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            justify-content: center;
        }}
        .meta-badge {{
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
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
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #2a3a5a;
        }}
        .section-card h2 {{
            color: #4ade80;
            font-size: 1.2rem;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-card .description {{
            color: #888;
            font-size: 0.85rem;
            margin-bottom: 15px;
            line-height: 1.5;
        }}
        
        /* ================================================================
           GRAPH CONTAINER
           ================================================================ */
        .graph-wrapper {{
            background: #0a1628;
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #1a2744;
            position: relative;
            overflow: hidden;
        }}
        #graph-svg {{
            display: block;
            width: 100%;
            cursor: grab;
        }}
        #graph-svg:active {{
            cursor: grabbing;
        }}
        
        /* ================================================================
           GRAPH ELEMENTS
           ================================================================ */
        .community-hull {{
            fill-opacity: 0.08;
            stroke-width: 2;
            stroke-opacity: 0.3;
        }}
        
        .edge {{
            transition: stroke-opacity 0.2s, stroke 0.2s;
        }}
        .edge.bridge {{
            stroke-opacity: 0.5;
        }}
        .edge.non-bridge {{
            stroke-opacity: 0;
        }}
        .edge.dimmed {{
            stroke-opacity: 0.05 !important;
        }}
        .edge.path-edge {{
            stroke-opacity: 1 !important;
            stroke: #fbbf24 !important;
            stroke-width: 4 !important;
        }}
        
        .node {{
            cursor: pointer;
        }}
        .node circle {{
            transition: r 0.15s, stroke-width 0.15s;
        }}
        .node:hover circle {{
            stroke-width: 3 !important;
        }}
        .node.dimmed {{
            opacity: 0.15;
        }}
        .node.highlighted {{
            opacity: 1;
        }}
        .node.selected circle {{
            stroke: #fbbf24 !important;
            stroke-width: 4 !important;
            fill: #fbbf24 !important;
        }}
        .node.path-node circle {{
            stroke: #4ade80 !important;
            stroke-width: 3 !important;
        }}
        
        .node-initials {{
            font-size: 7px;
            fill: #fff;
            pointer-events: none;
            text-anchor: middle;
            dominant-baseline: central;
            font-weight: 600;
        }}
        .node.selected .node-initials {{
            font-size: 9px;
            fill: #000;
        }}
        
        /* ================================================================
           TOOLTIP
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
            gap: 10px;
            padding: 10px 12px;
            background: #0a1628;
            border-bottom: 3px solid #4ade80;
        }}
        .tooltip-headshot {{
            width: 45px;
            height: 33px;
            border-radius: 4px;
            object-fit: cover;
            background: #1a1a2e;
        }}
        .tooltip-name {{
            font-weight: 700;
            font-size: 0.9rem;
            color: #fff;
        }}
        .tooltip-team {{
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .tooltip-body {{
            padding: 10px 12px;
        }}
        .tooltip-stat {{
            display: flex;
            justify-content: space-between;
            padding: 3px 0;
            font-size: 0.8rem;
            color: #aaa;
        }}
        .tooltip-stat-value {{
            font-weight: 600;
            color: #fff;
        }}
        
        /* ================================================================
           RIGHT PANEL
           ================================================================ */
        .finder-card {{
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 15px;
            border: 1px solid #2a3a5a;
            margin-bottom: 15px;
        }}
        .finder-card h3 {{
            color: #4ade80;
            font-size: 0.95rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* Search */
        .search-container {{
            position: relative;
            margin-bottom: 12px;
        }}
        .search-input {{
            width: 100%;
            padding: 9px 12px;
            border: 2px solid #2a3a5a;
            border-radius: 8px;
            background: #0a1628;
            color: #fff;
            font-size: 0.85rem;
            outline: none;
        }}
        .search-input:focus {{
            border-color: #4ade80;
        }}
        .search-dropdown {{
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #0a1628;
            border: 1px solid #2a3a5a;
            border-radius: 8px;
            max-height: 180px;
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
            gap: 8px;
            padding: 8px 10px;
            cursor: pointer;
            border-bottom: 1px solid #1a2744;
            font-size: 0.8rem;
        }}
        .search-item:hover {{
            background: #1a2744;
        }}
        .search-item-headshot {{
            width: 24px;
            height: 18px;
            border-radius: 3px;
            object-fit: cover;
        }}
        
        /* Selected players */
        .selected-players {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 12px;
        }}
        .selected-player {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 10px;
            background: #0a1628;
            border-radius: 8px;
            border: 2px solid #fbbf24;
        }}
        .selected-player-headshot {{
            width: 28px;
            height: 20px;
            border-radius: 3px;
        }}
        .selected-player-name {{
            color: #fbbf24;
            font-size: 0.8rem;
            font-weight: 600;
            flex: 1;
        }}
        .selected-player-remove {{
            color: #f87171;
            cursor: pointer;
            font-size: 1.1rem;
            font-weight: bold;
        }}
        
        .clear-btn {{
            width: 100%;
            padding: 7px;
            background: #333;
            border: none;
            border-radius: 6px;
            color: #aaa;
            font-size: 0.75rem;
            cursor: pointer;
        }}
        .clear-btn:hover {{
            background: #444;
            color: #fff;
        }}
        
        .no-selection {{
            color: #666;
            font-size: 0.8rem;
            text-align: center;
            padding: 10px;
        }}
        
        /* Path result */
        .path-result {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #2a3a5a;
        }}
        .path-result h4 {{
            color: #fbbf24;
            font-size: 0.85rem;
            margin-bottom: 8px;
        }}
        .path-stats {{
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
            font-size: 0.8rem;
        }}
        .path-stat {{
            color: #aaa;
        }}
        .path-stat strong {{
            color: #4ade80;
        }}
        .path-list {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-height: 200px;
            overflow-y: auto;
        }}
        .path-step {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            background: #0d1a2a;
            border-radius: 6px;
            font-size: 0.75rem;
        }}
        .path-step-headshot {{
            width: 22px;
            height: 16px;
            border-radius: 2px;
        }}
        .path-step-name {{
            color: #ccc;
            flex: 1;
        }}
        .path-step-dist {{
            color: #4ade80;
            font-size: 0.7rem;
        }}
        .path-arrow {{
            color: #4ade80;
            text-align: center;
            font-size: 0.8rem;
            padding: 2px 0;
        }}
        
        /* Bridge players */
        .bridge-list {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .bridge-player {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            background: #0a1628;
            border-radius: 6px;
            cursor: pointer;
        }}
        .bridge-player:hover {{
            background: #1a2744;
        }}
        .bridge-player-rank {{
            color: #4ade80;
            font-weight: 700;
            font-size: 0.8rem;
            width: 20px;
        }}
        .bridge-player-headshot {{
            width: 26px;
            height: 19px;
            border-radius: 3px;
        }}
        .bridge-player-name {{
            color: #ccc;
            font-size: 0.8rem;
            flex: 1;
        }}
        .bridge-player-score {{
            color: #888;
            font-size: 0.7rem;
        }}
        
        /* Legend */
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.7rem;
            color: #888;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        
        /* ================================================================
           RESPONSIVE
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
    <div class="header">
        <h1>🕸️ NBA Player Similarity Network</h1>
        <div class="subtitle">ε-Graph • UMAP Layout • Louvain Communities • 2025-26 Season</div>
    </div>
    
    <div class="main-container">
        <div class="meta-info">
            <div class="meta-badge"><strong>{player_count}</strong> players</div>
            <div class="meta-badge"><strong>{edge_count}</strong> edges (ε={epsilon})</div>
            <div class="meta-badge"><strong>{community_count}</strong> communities</div>
            <div class="meta-badge">Avg degree: <strong>{avg_degree}</strong></div>
            <div class="meta-badge">Bridge edges: <strong>{bridge_count}</strong></div>
        </div>
        
        <div class="page-layout">
            <div class="main-content">
                <div class="section-card">
                    <h2>📊 Similarity Graph</h2>
                    <p class="description">
                        Players positioned by UMAP (similar players cluster together). 
                        Edges connect players within ε distance. Only <strong>bridge edges</strong> 
                        (connecting different communities) are shown. Click players to explore connections 
                        or find shortest paths.
                    </p>
                    <div class="graph-wrapper">
                        <svg id="graph-svg"></svg>
                    </div>
                </div>
            </div>
            
            <div class="right-panel">
                <!-- Path Finder -->
                <div class="finder-card">
                    <h3>🔎 Path Finder</h3>
                    <div class="search-container">
                        <input type="text" id="player-search" class="search-input" 
                               placeholder="Search player...">
                        <div id="search-dropdown" class="search-dropdown"></div>
                    </div>
                    <div id="selected-players" class="selected-players">
                        <div class="no-selection">Select 2 players to find path</div>
                    </div>
                    <button id="clear-btn" class="clear-btn" style="display: none;">Clear</button>
                    <div id="path-result" class="path-result" style="display: none;"></div>
                </div>
                
                <!-- Bridge Players -->
                <div class="finder-card">
                    <h3>🌉 Top Bridge Players</h3>
                    <p style="color: #666; font-size: 0.75rem; margin-bottom: 10px;">
                        Highest betweenness centrality — connecting different archetypes
                    </p>
                    <div id="bridge-list" class="bridge-list">
                        {bridge_players_html}
                    </div>
                </div>
                
                <!-- Legend -->
                <div class="finder-card">
                    <h3>🎨 Communities</h3>
                    <div id="legend" class="legend">
                        {legend_html}
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="tooltip" id="tooltip"></div>
    
    <script>
    // =========================================================================
    // DATA
    // =========================================================================
    const graphData = {graph_data_json};
    const communityColors = {community_colors_json};
    const teamColors = {team_colors_json};
    
    // =========================================================================
    // STATE
    // =========================================================================
    let selectedPlayers = [];
    let nodeElements = null;
    let edgeElements = null;
    let currentPath = null;
    
    // Build adjacency list for Dijkstra (uses ALL edges, not just bridge edges)
    const adjacency = new Map();
    graphData.nodes.forEach(n => adjacency.set(n.id, []));
    graphData.edges.forEach(e => {{
        if (adjacency.has(e.source) && adjacency.has(e.target)) {{
            adjacency.get(e.source).push({{ target: e.target, weight: e.weight }});
            adjacency.get(e.target).push({{ target: e.source, weight: e.weight }});
        }} else {{
            console.warn('Edge references unknown node:', e);
        }}
    }});
    
    // Debug: verify graph connectivity
    console.log('Nodes:', graphData.nodes.length, 'Edges:', graphData.edges.length);
    console.log('Sample adjacency:', adjacency.get(0));
    
    // =========================================================================
    // UTILITY
    // =========================================================================
    function getTeamColor(team) {{
        return teamColors[team] || '#4ade80';
    }}
    
    function getCommunityColor(commId) {{
        return communityColors[commId % communityColors.length];
    }}
    
    function normalizeName(name) {{
        return name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }}
    
    function positionTooltip(event) {{
        const tooltip = document.getElementById('tooltip');
        const rect = tooltip.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const pad = 15;
        
        let left = event.clientX + pad;
        let top = event.clientY - pad;
        
        if (left + rect.width > vw - pad) left = event.clientX - rect.width - pad;
        if (top + rect.height > vh - pad) top = vh - rect.height - pad;
        if (top < pad) top = pad;
        if (left < pad) left = pad;
        
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }}
    
    // =========================================================================
    // DIJKSTRA'S SHORTEST PATH
    // =========================================================================
    function dijkstra(startId, endId) {{
        const dist = new Map();
        const prev = new Map();
        const visited = new Set();
        const pq = [];  // Simple array-based priority queue
        
        graphData.nodes.forEach(n => {{
            dist.set(n.id, Infinity);
            prev.set(n.id, null);
        }});
        
        dist.set(startId, 0);
        pq.push({{ id: startId, dist: 0 }});
        
        while (pq.length > 0) {{
            // Get node with minimum distance
            pq.sort((a, b) => a.dist - b.dist);
            const current = pq.shift();
            
            if (visited.has(current.id)) continue;
            visited.add(current.id);
            
            if (current.id === endId) break;
            
            // Check neighbors
            const neighbors = adjacency.get(current.id) || [];
            for (const neighbor of neighbors) {{
                if (visited.has(neighbor.target)) continue;
                
                const newDist = dist.get(current.id) + neighbor.weight;
                if (newDist < dist.get(neighbor.target)) {{
                    dist.set(neighbor.target, newDist);
                    prev.set(neighbor.target, current.id);
                    pq.push({{ id: neighbor.target, dist: newDist }});
                }}
            }}
        }}
        
        // Reconstruct path
        if (dist.get(endId) === Infinity) return null;
        
        const path = [];
        let current = endId;
        while (current !== null) {{
            path.unshift(current);
            current = prev.get(current);
        }}
        
        return {{
            path: path,
            distance: dist.get(endId),
            hops: path.length - 1
        }};
    }}
    
    // =========================================================================
    // SEARCH
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
            
            const matches = graphData.nodes.filter(n => 
                normalizeName(n.name).includes(query)
            ).slice(0, 8);
            
            if (matches.length === 0) {{
                dropdown.classList.remove('active');
                return;
            }}
            
            dropdown.innerHTML = matches.map(n => `
                <div class="search-item" data-id="${{n.id}}">
                    <img class="search-item-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{n.player_id}}.png"
                         onerror="this.style.visibility='hidden'">
                    <span>${{n.abbrev}}</span>
                    <span style="color:#666;margin-left:auto">${{n.team}}</span>
                </div>
            `).join('');
            
            dropdown.querySelectorAll('.search-item').forEach(item => {{
                item.addEventListener('click', function() {{
                    const id = parseInt(this.dataset.id);
                    addSelectedPlayer(id);
                    searchInput.value = '';
                    dropdown.classList.remove('active');
                }});
            }});
            
            dropdown.classList.add('active');
        }});
        
        document.addEventListener('click', e => {{
            if (!e.target.closest('.search-container')) {{
                dropdown.classList.remove('active');
            }}
        }});
    }}
    
    // =========================================================================
    // SELECTION MANAGEMENT
    // =========================================================================
    function addSelectedPlayer(id) {{
        // If already selected, deselect
        if (selectedPlayers.find(p => p.id === id)) {{
            removeSelectedPlayer(id);
            return;
        }}
        
        if (selectedPlayers.length >= 2) {{
            // Replace second player
            selectedPlayers[1] = graphData.nodes.find(n => n.id === id);
        }} else {{
            selectedPlayers.push(graphData.nodes.find(n => n.id === id));
        }}
        updateSelectionUI();
        updateHighlighting();
    }}
    
    function removeSelectedPlayer(id) {{
        selectedPlayers = selectedPlayers.filter(p => p.id !== id);
        currentPath = null;
        updateSelectionUI();
        updateHighlighting();
    }}
    
    function clearSelection() {{
        selectedPlayers = [];
        currentPath = null;
        updateSelectionUI();
        updateHighlighting();
    }}
    
    function updateSelectionUI() {{
        const container = document.getElementById('selected-players');
        const clearBtn = document.getElementById('clear-btn');
        const pathResult = document.getElementById('path-result');
        
        if (selectedPlayers.length === 0) {{
            container.innerHTML = '<div class="no-selection">Select 2 players to find path</div>';
            clearBtn.style.display = 'none';
            pathResult.style.display = 'none';
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
        
        container.querySelectorAll('.selected-player-remove').forEach(btn => {{
            btn.addEventListener('click', function() {{
                removeSelectedPlayer(parseInt(this.dataset.id));
            }});
        }});
        
        clearBtn.style.display = 'block';
        
        // Compute path if 2 selected
        if (selectedPlayers.length === 2) {{
            currentPath = dijkstra(selectedPlayers[0].id, selectedPlayers[1].id);
            showPathResult();
        }} else {{
            pathResult.style.display = 'none';
        }}
    }}
    
    function showPathResult() {{
        const pathResult = document.getElementById('path-result');
        
        if (!currentPath) {{
            pathResult.innerHTML = '<p style="color:#f87171;font-size:0.8rem;">No path found</p>';
            pathResult.style.display = 'block';
            return;
        }}
        
        let html = `
            <h4>📍 Shortest Path</h4>
            <div class="path-stats">
                <span class="path-stat">Hops: <strong>${{currentPath.hops}}</strong></span>
                <span class="path-stat">Distance: <strong>${{currentPath.distance.toFixed(2)}}</strong></span>
            </div>
            <div class="path-list">
        `;
        
        for (let i = 0; i < currentPath.path.length; i++) {{
            const nodeId = currentPath.path[i];
            const node = graphData.nodes.find(n => n.id === nodeId);
            
            // Calculate edge distance to next node
            let edgeDist = '';
            if (i < currentPath.path.length - 1) {{
                const nextId = currentPath.path[i + 1];
                const edge = graphData.edges.find(e => 
                    (e.source === nodeId && e.target === nextId) ||
                    (e.source === nextId && e.target === nodeId)
                );
                if (edge) edgeDist = edge.weight.toFixed(2);
            }}
            
            html += `
                <div class="path-step">
                    <img class="path-step-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{node.player_id}}.png"
                         onerror="this.style.visibility='hidden'">
                    <span class="path-step-name">${{node.abbrev}}</span>
                    <span style="color:#666;font-size:0.7rem">${{node.team}}</span>
                </div>
            `;
            
            if (i < currentPath.path.length - 1) {{
                html += `<div class="path-arrow">↓ <span style="font-size:0.7rem;color:#888">${{edgeDist}}</span></div>`;
            }}
        }}
        
        html += '</div>';
        pathResult.innerHTML = html;
        pathResult.style.display = 'block';
    }}
    
    // =========================================================================
    // HIGHLIGHTING
    // =========================================================================
    function updateHighlighting() {{
        if (!nodeElements || !edgeElements) return;
        
        const selectedIds = new Set(selectedPlayers.map(p => p.id));
        const pathIds = currentPath ? new Set(currentPath.path) : new Set();
        
        // Build set of path edges
        const pathEdges = new Set();
        if (currentPath && currentPath.path.length > 1) {{
            for (let i = 0; i < currentPath.path.length - 1; i++) {{
                const a = currentPath.path[i];
                const b = currentPath.path[i + 1];
                pathEdges.add(`${{Math.min(a,b)}}-${{Math.max(a,b)}}`);
            }}
        }}
        
        if (selectedPlayers.length === 0) {{
            // Reset all
            nodeElements.classed('dimmed', false)
                        .classed('selected', false)
                        .classed('path-node', false);
            edgeElements.classed('dimmed', false)
                        .classed('path-edge', false)
                        .attr('stroke-opacity', d => d.bridge ? 0.5 : 0)
                        .attr('stroke', '#666');
            return;
        }}
        
        // Single selection - just highlight the selected node
        if (selectedPlayers.length === 1) {{
            nodeElements
                .classed('selected', d => selectedIds.has(d.id))
                .classed('path-node', false)
                .classed('dimmed', false);
            edgeElements
                .classed('path-edge', false)
                .classed('dimmed', false)
                .attr('stroke-opacity', d => d.bridge ? 0.5 : 0)
                .attr('stroke', '#666');
            return;
        }}
        
        // Two selections - show path
        nodeElements
            .classed('selected', d => selectedIds.has(d.id))
            .classed('path-node', d => pathIds.has(d.id) && !selectedIds.has(d.id))
            .classed('dimmed', d => currentPath && !pathIds.has(d.id));
        
        edgeElements
            .classed('path-edge', d => {{
                const key = `${{Math.min(d.source, d.target)}}-${{Math.max(d.source, d.target)}}`;
                return pathEdges.has(key);
            }})
            .classed('dimmed', d => {{
                const key = `${{Math.min(d.source, d.target)}}-${{Math.max(d.source, d.target)}}`;
                return currentPath && !pathEdges.has(key);
            }})
            .attr('stroke-opacity', d => {{
                const key = `${{Math.min(d.source, d.target)}}-${{Math.max(d.source, d.target)}}`;
                if (pathEdges.has(key)) return 1;
                if (currentPath) return 0.05;
                return d.bridge ? 0.5 : 0;
            }})
            .attr('stroke', d => {{
                const key = `${{Math.min(d.source, d.target)}}-${{Math.max(d.source, d.target)}}`;
                if (pathEdges.has(key)) return '#fbbf24';
                return '#666';
            }})
            .attr('stroke-width', d => {{
                const key = `${{Math.min(d.source, d.target)}}-${{Math.max(d.source, d.target)}}`;
                if (pathEdges.has(key)) return 4;
                return null;  // Keep original
            }});
    }}
    
    // =========================================================================
    // RENDER GRAPH
    // =========================================================================
    function renderGraph() {{
        const width = 1000;
        const height = 700;
        const margin = 50;
        
        const svg = d3.select('#graph-svg')
            .attr('width', width)
            .attr('height', height)
            .attr('viewBox', `0 0 ${{width}} ${{height}}`);
        
        svg.selectAll('*').remove();
        
        // Create zoom container
        const g = svg.append('g');
        
        // Setup zoom
        const zoom = d3.zoom()
            .scaleExtent([0.3, 4])
            .on('zoom', (event) => g.attr('transform', event.transform));
        
        svg.call(zoom);
        
        // Scale UMAP coordinates to SVG
        const xExtent = d3.extent(graphData.nodes, d => d.x);
        const yExtent = d3.extent(graphData.nodes, d => d.y);
        
        const xScale = d3.scaleLinear()
            .domain(xExtent)
            .range([margin, width - margin]);
        
        const yScale = d3.scaleLinear()
            .domain(yExtent)
            .range([margin, height - margin]);
        
        // Draw community hulls
        const communities = d3.group(graphData.nodes, d => d.community);
        
        communities.forEach((members, commId) => {{
            if (members.length < 3) return;
            
            const points = members.map(m => [xScale(m.x), yScale(m.y)]);
            const hull = d3.polygonHull(points);
            
            if (hull) {{
                // Expand hull slightly
                const centroid = d3.polygonCentroid(hull);
                const expandedHull = hull.map(p => {{
                    const dx = p[0] - centroid[0];
                    const dy = p[1] - centroid[1];
                    const len = Math.sqrt(dx*dx + dy*dy);
                    const expand = 20;
                    return [p[0] + dx/len * expand, p[1] + dy/len * expand];
                }});
                
                g.append('path')
                    .attr('class', 'community-hull')
                    .attr('d', `M${{expandedHull.join('L')}}Z`)
                    .attr('fill', getCommunityColor(commId))
                    .attr('stroke', getCommunityColor(commId));
            }}
        }});
        
        // Draw ALL edges (bridge edges visible, non-bridge hidden until path)
        // Compute edge thickness scale (inverse of weight - closer = thicker)
        const weightExtent = d3.extent(graphData.edges, d => d.weight);
        const strokeScale = d3.scaleLinear()
            .domain(weightExtent)
            .range([3, 0.5]);  // Closer (smaller weight) = thicker
        
        edgeElements = g.selectAll('.edge')
            .data(graphData.edges)
            .join('line')
            .attr('class', d => d.bridge ? 'edge bridge' : 'edge non-bridge')
            .attr('x1', d => xScale(graphData.nodes.find(n => n.id === d.source).x))
            .attr('y1', d => yScale(graphData.nodes.find(n => n.id === d.source).y))
            .attr('x2', d => xScale(graphData.nodes.find(n => n.id === d.target).x))
            .attr('y2', d => yScale(graphData.nodes.find(n => n.id === d.target).y))
            .attr('stroke', '#666')
            .attr('stroke-width', d => strokeScale(d.weight))
            .attr('stroke-opacity', d => d.bridge ? 0.5 : 0);  // Non-bridge hidden initially
        
        // Draw nodes
        const nodeGroup = g.selectAll('.node')
            .data(graphData.nodes)
            .join('g')
            .attr('class', 'node')
            .attr('transform', d => `translate(${{xScale(d.x)}},${{yScale(d.y)}})`);
        
        // Node circles
        nodeGroup.append('circle')
            .attr('r', d => 8 + d.betweenness * 0.06)  // Size by betweenness
            .attr('fill', d => getCommunityColor(d.community))
            .attr('stroke', '#fff')
            .attr('stroke-width', 1.5);
        
        // Node initials (always visible)
        nodeGroup.append('text')
            .attr('class', 'node-initials')
            .text(d => d.initials || d.abbrev.substring(0, 2));
        
        nodeElements = nodeGroup;
        
        // Tooltip
        const tooltip = document.getElementById('tooltip');
        
        nodeGroup.on('mouseenter', function(event, d) {{
            const teamColor = getTeamColor(d.team);
            tooltip.innerHTML = `
                <div class="tooltip-header" style="border-bottom-color:${{teamColor}}">
                    <img class="tooltip-headshot" 
                         src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{d.player_id}}.png"
                         onerror="this.style.visibility='hidden'">
                    <div>
                        <div class="tooltip-name">${{d.name}}</div>
                        <div class="tooltip-team" style="color:${{teamColor}}">${{d.team}}</div>
                    </div>
                </div>
                <div class="tooltip-body">
                    <div class="tooltip-stat"><span>PPG</span><span class="tooltip-stat-value">${{d.ppg}}</span></div>
                    <div class="tooltip-stat"><span>RPG</span><span class="tooltip-stat-value">${{d.rpg}}</span></div>
                    <div class="tooltip-stat"><span>APG</span><span class="tooltip-stat-value">${{d.apg}}</span></div>
                    <div class="tooltip-stat"><span>TS%</span><span class="tooltip-stat-value">${{d.ts_pct || '-'}}</span></div>
                    <div class="tooltip-stat"><span>3PT%</span><span class="tooltip-stat-value">${{d.three_pt_ratio || '-'}}%</span></div>
                    <div class="tooltip-stat"><span>Connections</span><span class="tooltip-stat-value">${{d.degree}}</span></div>
                    <div class="tooltip-stat"><span>Bridge Score</span><span class="tooltip-stat-value">${{d.betweenness}}</span></div>
                </div>
            `;
            positionTooltip(event);
            tooltip.classList.add('visible');
        }});
        
        nodeGroup.on('mousemove', positionTooltip);
        nodeGroup.on('mouseleave', () => tooltip.classList.remove('visible'));
        
        // Click to select
        nodeGroup.on('click', function(event, d) {{
            event.stopPropagation();
            addSelectedPlayer(d.id);
        }});
        
        // Click background to clear
        svg.on('click', () => clearSelection());
    }}
    
    // =========================================================================
    // BRIDGE PLAYER CLICK
    // =========================================================================
    function initBridgeClicks() {{
        document.querySelectorAll('.bridge-player').forEach(el => {{
            el.addEventListener('click', function() {{
                const id = parseInt(this.dataset.id);
                clearSelection();
                addSelectedPlayer(id);
            }});
        }});
    }}
    
    // =========================================================================
    // INIT
    // =========================================================================
    document.addEventListener('DOMContentLoaded', function() {{
        renderGraph();
        initSearch();
        initBridgeClicks();
        document.getElementById('clear-btn').addEventListener('click', clearSelection);
    }});
    </script>
</body>
</html>
'''


# =============================================================================
# HTML GENERATION HELPERS
# =============================================================================

def generate_bridge_players_html(graph_data):
    """Generate HTML for top bridge players list."""
    html_parts = []
    
    for i, bridge in enumerate(graph_data['top_bridges'][:10]):
        node = next(n for n in graph_data['nodes'] if n['id'] == bridge['id'])
        html_parts.append(f'''
            <div class="bridge-player" data-id="{node['id']}">
                <span class="bridge-player-rank">{i+1}.</span>
                <img class="bridge-player-headshot" 
                     src="https://cdn.nba.com/headshots/nba/latest/1040x760/{node['player_id']}.png"
                     onerror="this.style.visibility='hidden'">
                <span class="bridge-player-name">{node['abbrev']}</span>
                <span class="bridge-player-score">{bridge['score']}</span>
            </div>
        ''')
    
    return '\n'.join(html_parts)


def generate_legend_html(graph_data):
    """Generate HTML for community legend."""
    html_parts = []
    
    for comm in sorted(graph_data['communities'], key=lambda c: c['size'], reverse=True)[:10]:
        color = COMMUNITY_COLORS[comm['id'] % len(COMMUNITY_COLORS)]
        html_parts.append(f'''
            <div class="legend-item">
                <span class="legend-color" style="background:{color}"></span>
                <span>C{comm['id']} ({comm['size']})</span>
            </div>
        ''')
    
    return '\n'.join(html_parts)


# =============================================================================
# MAIN
# =============================================================================

def main(input_path=None, output_path=None):
    """Main function."""
    # Handle args
    if input_path is None and output_path is None:
        try:
            import sys
            if 'ipykernel' in sys.modules:
                input_path = INPUT_PATH
                output_path = OUTPUT_PATH
            else:
                parser = argparse.ArgumentParser()
                parser.add_argument('--input', type=str, default=INPUT_PATH)
                parser.add_argument('--output', type=str, default=OUTPUT_PATH)
                args = parser.parse_args()
                input_path = args.input
                output_path = args.output
        except SystemExit:
            input_path = INPUT_PATH
            output_path = OUTPUT_PATH
    
    input_path = input_path or INPUT_PATH
    output_path = output_path or OUTPUT_PATH
    
    print("=" * 70)
    print("GENERATE GRAPH HTML")
    print("=" * 70)
    
    # Load data
    print(f"\n[1/3] Loading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    
    meta = graph_data['meta']
    print(f"       Players: {meta['player_count']}")
    print(f"       Edges: {meta['edge_count']}")
    print(f"       Communities: {meta['community_count']}")
    
    # Generate HTML sections
    print(f"\n[2/3] Generating HTML...")
    bridge_html = generate_bridge_players_html(graph_data)
    legend_html = generate_legend_html(graph_data)
    
    # Assemble HTML
    print(f"\n[3/3] Assembling...")
    html = get_html_template().format(
        player_count=meta['player_count'],
        edge_count=meta['edge_count'],
        epsilon=meta['epsilon'],
        community_count=meta['community_count'],
        avg_degree=meta['actual_degree'],
        bridge_count=meta['bridge_edge_count'],
        bridge_players_html=bridge_html,
        legend_html=legend_html,
        graph_data_json=json.dumps(graph_data, ensure_ascii=False),
        community_colors_json=json.dumps(COMMUNITY_COLORS),
        team_colors_json=json.dumps(TEAM_COLORS)
    )
    
    # Save
    print(f"\nSaving to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"       File size: {len(html):,} bytes")
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"\nOpen {output_path} in a browser.")


if __name__ == "__main__":
    main()
