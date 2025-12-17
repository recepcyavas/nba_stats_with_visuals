"""
================================================================================
GENERATE ALL-TIME PARETO HTML (v2)
================================================================================

Creates interactive HTML dashboard showing:
1. Top 100 all-time performances by dominance %
2. 3D scatter plot (PPG/RPG/APG) with pan/zoom/rotate
3. Hover on layer badges shows dominating performances

FIXES:
- Compact 3D plot (centered, smaller)
- 4D color = STOCKPG (continuous scale, not layer)
- Layer hover shows ascendants within top 100

================================================================================
"""

import json
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_PATH = "alltime_pareto.json"
OUTPUT_PATH = "alltime_pareto.html"

TOP_N = 100


# =============================================================================
# LOAD DATA
# =============================================================================

print("Loading data...")
with open(INPUT_PATH, 'r') as f:
    data = json.load(f)

meta = data["meta"]
results_3d = data["3D"]
results_4d = data["4D"]

print(f"  3D frontier: {results_3d['frontier_count']}")
print(f"  4D frontier: {results_4d['frontier_count']}")


# =============================================================================
# DOMINANCE CHECK FUNCTIONS
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


# =============================================================================
# PREPARE DATA FOR HTML
# =============================================================================

def get_top_n_with_ascendants(results, n, dominates_fn):
    """
    Get top N performances by dominance_pct.
    Also compute which top N performances dominate each other.
    """
    all_perfs = results["all_performances"]
    top_n = all_perfs[:n]
    
    # Build lookup by unique key
    def key(p):
        return f"{p['player_id']}_{p['season']}"
    
    # For each performance, find which TOP N performances dominate it
    for p in top_n:
        ascendants = []
        for other in top_n:
            if other is not p and dominates_fn(other, p):
                ascendants.append(f"{other['name']} {other['season']}")
        p['ascendants'] = ascendants
    
    return top_n


print("Computing ascendants within top 100...")
top_100_3d = get_top_n_with_ascendants(results_3d, TOP_N, dominates_3d)
top_100_4d = get_top_n_with_ascendants(results_4d, TOP_N, dominates_4d)

print(f"  Top {TOP_N} (3D): layers {set(p['layer'] for p in top_100_3d)}")
print(f"  Top {TOP_N} (4D): layers {set(p['layer'] for p in top_100_4d)}")

# Check ascendant counts
l1_3d = [p for p in top_100_3d if p['layer'] == 1]
if l1_3d:
    print(f"  Sample L1 ascendants (3D): {l1_3d[0]['name']} -> {l1_3d[0]['ascendants'][:3]}...")


# =============================================================================
# GENERATE HTML
# =============================================================================

def js_safe(obj):
    """JSON encode for JavaScript embedding."""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace('</script>', '<\\/script>')

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All-Time NBA Pareto Analysis</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            background: linear-gradient(90deg, #fbbf24, #f59e0b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: #888;
            font-size: 1rem;
        }}
        
        .meta-info {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        
        .meta-card {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px 25px;
            text-align: center;
        }}
        
        .meta-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #4ade80;
        }}
        
        .meta-label {{
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* Tabs */
        .tab-nav {{
            display: flex;
            gap: 0;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
        }}
        
        .tab-btn {{
            background: transparent;
            color: #888;
            border: none;
            padding: 12px 30px;
            font-size: 1rem;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }}
        
        .tab-btn:hover {{
            color: #fff;
        }}
        
        .tab-btn.active {{
            color: #fbbf24;
            border-bottom-color: #fbbf24;
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        /* 3D Plot - COMPACT */
        .plot-container {{
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        .plot-title {{
            font-size: 1.2rem;
            color: #fbbf24;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .plot-3d {{
            width: 100%;
            height: 450px;
        }}
        
        .plot-legend {{
            display: flex;
            justify-content: center;
            gap: 25px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
            color: #aaa;
        }}
        
        .legend-dot {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
        }}
        
        /* Table */
        .table-container {{
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            overflow: hidden;
        }}
        
        .table-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        .table-title {{
            font-size: 1.2rem;
            color: #fbbf24;
        }}
        
        .search-box {{
            display: flex;
            gap: 10px;
        }}
        
        .search-box input {{
            background: rgba(0,0,0,0.3);
            border: 1px solid #333;
            color: #fff;
            padding: 8px 15px;
            border-radius: 6px;
            font-size: 0.9rem;
            width: 200px;
        }}
        
        .search-box input:focus {{
            outline: none;
            border-color: #fbbf24;
        }}
        
        .table-scroll {{
            max-height: 600px;
            overflow-y: auto;
        }}
        
        .table-scroll::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .table-scroll::-webkit-scrollbar-track {{
            background: rgba(0,0,0,0.2);
        }}
        
        .table-scroll::-webkit-scrollbar-thumb {{
            background: #333;
            border-radius: 4px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        
        th {{
            background: rgba(0,0,0,0.4);
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        
        td {{
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            vertical-align: middle;
        }}
        
        tr:hover {{
            background: rgba(255,255,255,0.03);
        }}
        
        .col-rank {{
            width: 50px;
            text-align: center;
            color: #fbbf24;
            font-weight: 700;
        }}
        
        .col-player {{
            min-width: 180px;
        }}
        
        .player-cell {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .player-img {{
            width: 40px;
            height: 30px;
            border-radius: 4px;
            object-fit: cover;
            background: #1a1a2e;
        }}
        
        .player-name {{
            font-weight: 600;
        }}
        
        .col-season {{
            width: 80px;
            color: #888;
        }}
        
        .col-team {{
            width: 60px;
        }}
        
        .team-badge {{
            background: rgba(74, 222, 128, 0.2);
            color: #4ade80;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .col-stat {{
            width: 55px;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}
        
        .col-layer {{
            width: 70px;
            text-align: center;
        }}
        
        .layer-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: default;
            position: relative;
        }}
        
        .layer-0 {{
            background: linear-gradient(135deg, #fbbf24, #f59e0b);
            color: #000;
        }}
        
        .layer-1 {{
            background: linear-gradient(135deg, #9ca3af, #6b7280);
            color: #000;
        }}
        
        .layer-2 {{
            background: linear-gradient(135deg, #cd7f32, #a0522d);
            color: #fff;
        }}
        
        .layer-other {{
            background: rgba(255,255,255,0.1);
            color: #888;
        }}
        
        /* Tooltip for ascendants */
        .layer-badge[data-tooltip]:hover::after {{
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
        }}
        
        .layer-badge[data-tooltip]:hover::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: #fbbf24;
            margin-bottom: -1px;
            z-index: 101;
        }}
        
        .col-dom {{
            width: 100px;
            text-align: right;
        }}
        
        .dom-value {{
            font-weight: 700;
            color: #4ade80;
        }}
        
        .dom-bar {{
            height: 4px;
            background: rgba(255,255,255,0.1);
            border-radius: 2px;
            margin-top: 4px;
            overflow: hidden;
        }}
        
        .dom-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4ade80, #22c55e);
            border-radius: 2px;
        }}
        
        /* Methodology */
        .methodology {{
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 30px;
            margin-top: 30px;
        }}
        
        .methodology h2 {{
            color: #fbbf24;
            margin-bottom: 20px;
        }}
        
        .methodology h3 {{
            color: #60a5fa;
            margin: 20px 0 10px 0;
        }}
        
        .methodology p {{
            color: #aaa;
            line-height: 1.7;
            margin-bottom: 10px;
        }}
        
        .methodology code {{
            background: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 4px;
            color: #4ade80;
            font-family: monospace;
        }}
        
        .formula-box {{
            background: rgba(0,0,0,0.3);
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px 20px;
            margin: 15px 0;
            font-family: monospace;
            color: #4ade80;
        }}
        
        /* 4D colorbar note */
        .colorbar-note {{
            text-align: center;
            color: #888;
            font-size: 0.85rem;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏀 All-Time NBA Pareto Analysis</h1>
        <div class="subtitle">Greatest Statistical Seasons in NBA History (1996-2025)</div>
    </div>
    
    <div class="meta-info">
        <div class="meta-card">
            <div class="meta-value">{meta['true_total']:,}</div>
            <div class="meta-label">Player-Seasons Analyzed</div>
        </div>
        <div class="meta-card">
            <div class="meta-value">{results_3d['frontier_count']}</div>
            <div class="meta-label">3D Frontier (Undominated)</div>
        </div>
        <div class="meta-card">
            <div class="meta-value">{results_4d['frontier_count']}</div>
            <div class="meta-label">4D Frontier (Undominated)</div>
        </div>
        <div class="meta-card">
            <div class="meta-value">30</div>
            <div class="meta-label">Seasons (1996-2025)</div>
        </div>
    </div>
    
    <div class="container">
        <div class="tab-nav">
            <button class="tab-btn active" data-tab="3d">📊 3D Analysis (PPG/RPG/APG)</button>
            <button class="tab-btn" data-tab="4d">📈 4D Analysis (+STOCKPG)</button>
            <button class="tab-btn" data-tab="methodology">📐 Methodology</button>
        </div>
        
        <!-- 3D TAB -->
        <div id="tab-3d" class="tab-content active">
            <div class="plot-container">
                <div class="plot-title">🌐 3D Scatter: PPG × RPG × APG</div>
                <div id="plot3d" class="plot-3d"></div>
                <div class="plot-legend">
                    <div class="legend-item">
                        <div class="legend-dot" style="background: #fbbf24;"></div>
                        <span>Layer 0 (Frontier)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot" style="background: #9ca3af;"></div>
                        <span>Layer 1</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot" style="background: #cd7f32;"></div>
                        <span>Layer 2</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot" style="background: #6b7280;"></div>
                        <span>Layer 3+</span>
                    </div>
                    <div class="legend-item">
                        <span style="color: #666;">Size = Dominance %</span>
                    </div>
                </div>
            </div>
            
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">🏆 Top {TOP_N} Performances (3D: PPG/RPG/APG)</div>
                    <div class="search-box">
                        <input type="text" id="search3d" placeholder="Search player...">
                    </div>
                </div>
                <div class="table-scroll">
                    <table id="table3d">
                        <thead>
                            <tr>
                                <th class="col-rank">#</th>
                                <th class="col-player">Player</th>
                                <th class="col-season">Season</th>
                                <th class="col-team">Team</th>
                                <th class="col-stat">PPG</th>
                                <th class="col-stat">RPG</th>
                                <th class="col-stat">APG</th>
                                <th class="col-layer">Layer</th>
                                <th class="col-dom">Dominance</th>
                            </tr>
                        </thead>
                        <tbody id="tbody3d"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- 4D TAB -->
        <div id="tab-4d" class="tab-content">
            <div class="plot-container">
                <div class="plot-title">🌐 3D Scatter: PPG × RPG × APG (Color = STOCKPG)</div>
                <div id="plot4d" class="plot-3d"></div>
                <div class="colorbar-note">Color intensity = STOCKPG (Steals + Blocks per game)</div>
            </div>
            
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">🏆 Top {TOP_N} Performances (4D: PPG/RPG/APG/STOCKPG)</div>
                    <div class="search-box">
                        <input type="text" id="search4d" placeholder="Search player...">
                    </div>
                </div>
                <div class="table-scroll">
                    <table id="table4d">
                        <thead>
                            <tr>
                                <th class="col-rank">#</th>
                                <th class="col-player">Player</th>
                                <th class="col-season">Season</th>
                                <th class="col-team">Team</th>
                                <th class="col-stat">PPG</th>
                                <th class="col-stat">RPG</th>
                                <th class="col-stat">APG</th>
                                <th class="col-stat">STK</th>
                                <th class="col-layer">Layer</th>
                                <th class="col-dom">Dominance</th>
                            </tr>
                        </thead>
                        <tbody id="tbody4d"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- METHODOLOGY TAB -->
        <div id="tab-methodology" class="tab-content">
            <div class="methodology">
                <h2>📐 Methodology: Pareto Dominance Analysis</h2>
                
                <h3>What is Pareto Dominance?</h3>
                <p>
                    A player-season <code>A</code> <strong>dominates</strong> player-season <code>B</code> if A is 
                    <em>at least as good</em> in ALL statistical categories and <em>strictly better</em> in at least one.
                </p>
                <div class="formula-box">
                    A dominates B ⟺ (A.PPG ≥ B.PPG) ∧ (A.RPG ≥ B.RPG) ∧ (A.APG ≥ B.APG)<br>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;∧ (A.PPG > B.PPG ∨ A.RPG > B.RPG ∨ A.APG > B.APG)
                </div>
                
                <h3>Pareto Frontier (Layer 0)</h3>
                <p>
                    The <strong>Pareto frontier</strong> consists of all <em>undominated</em> player-seasons — 
                    performances so exceptional that no single season beats them across all dimensions.
                    These represent different "archetypes" of greatness: pure scorers, triple-double machines, 
                    rebounding monsters, etc.
                </p>
                
                <h3>Pareto Layers</h3>
                <p>
                    <strong>Layer 0:</strong> Undominated (Pareto frontier)<br>
                    <strong>Layer 1:</strong> Dominated only by Layer 0<br>
                    <strong>Layer 2:</strong> Dominated only by Layers 0-1<br>
                    And so on...
                </p>
                <p>
                    Lower layer = more elite. Being in Layer 5 means at least 5 "generations" of 
                    performances are definitively better.
                </p>
                
                <h3>Dominance Percentage</h3>
                <p>
                    For each player-season, we compute what percentage of ALL historical performances it dominates:
                </p>
                <div class="formula-box">
                    Dominance % = (# of seasons dominated) / ({meta['true_total']:,} - 1) × 100
                </div>
                <p>
                    A dominance of <strong>99%</strong> means that season is statistically superior to 99% of 
                    all NBA player-seasons since 1996-97.
                </p>
                
                <h3>3D vs 4D Analysis</h3>
                <p>
                    <strong>3D:</strong> PPG, RPG, APG — the classic "triple-double" stats<br>
                    <strong>4D:</strong> PPG, RPG, APG, STOCKPG (steals + blocks) — adds defensive value
                </p>
                <p>
                    More dimensions = harder to dominate = smaller frontier. The 4D analysis rewards 
                    two-way players who contribute on both ends.
                </p>
                
                <h3>Ascendants (Hover on Layer)</h3>
                <p>
                    For Layer 1+ performances, hovering on the layer badge shows which top-100 performances 
                    dominate them. These are the "ascendants" — the performances that are strictly better 
                    in all dimensions.
                </p>
                
                <h3>Data</h3>
                <p>
                    <strong>Source:</strong> NBA Stats API (LeagueDashPlayerStats)<br>
                    <strong>Seasons:</strong> 1996-97 to 2025-26 (30 seasons)<br>
                    <strong>Players:</strong> {meta['total_in_db']:,} player-seasons (≥5 MPG)<br>
                    <strong>Total:</strong> {meta['true_total']:,} including filtered (&lt;5 MPG assumed dominated by all)
                </p>
            </div>
        </div>
    </div>
    
    <script>
// =============================================================================
// DATA
// =============================================================================

const top100_3d = {js_safe(top_100_3d)};
const top100_4d = {js_safe(top_100_4d)};

// =============================================================================
// LAYER COLORS (for 3D plot)
// =============================================================================

function getLayerColor(layer) {{
    if (layer === 0) return '#fbbf24';
    if (layer === 1) return '#9ca3af';
    if (layer === 2) return '#cd7f32';
    return '#6b7280';
}}

function getLayerClass(layer) {{
    if (layer === 0) return 'layer-0';
    if (layer === 1) return 'layer-1';
    if (layer === 2) return 'layer-2';
    return 'layer-other';
}}

// =============================================================================
// 3D PLOT (Layer colors)
// =============================================================================

function render3DPlot_Layers(containerId, data) {{
    const trace = {{
        x: data.map(p => p.ppg),
        y: data.map(p => p.rpg),
        z: data.map(p => p.apg),
        mode: 'markers',
        type: 'scatter3d',
        marker: {{
            size: data.map(p => 6 + p.dominance_pct / 12),
            color: data.map(p => getLayerColor(p.layer)),
            opacity: 0.9,
            line: {{
                color: 'rgba(255,255,255,0.2)',
                width: 0.5
            }}
        }},
        text: data.map(p => 
            `<b>${{p.name}}</b> ${{p.season}}<br>` +
            `${{p.team}}<br>` +
            `PPG: ${{p.ppg}} | RPG: ${{p.rpg}} | APG: ${{p.apg}}<br>` +
            `Layer: ${{p.layer}} | Dominance: ${{p.dominance_pct.toFixed(1)}}%`
        ),
        hoverinfo: 'text',
        hoverlabel: {{
            bgcolor: '#1a1a2e',
            bordercolor: '#fbbf24',
            font: {{ color: '#fff', size: 12 }}
        }}
    }};
    
    const layout = {{
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        scene: {{
            xaxis: {{
                title: 'PPG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                gridcolor: '#333',
                zerolinecolor: '#444'
            }},
            yaxis: {{
                title: 'RPG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                gridcolor: '#333',
                zerolinecolor: '#444'
            }},
            zaxis: {{
                title: 'APG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                gridcolor: '#333',
                zerolinecolor: '#444'
            }},
            bgcolor: 'rgba(0,0,0,0)',
            camera: {{
                eye: {{ x: 1.8, y: 1.8, z: 1.0 }}
            }}
        }},
        margin: {{ l: 0, r: 0, t: 10, b: 10 }},
        showlegend: false
    }};
    
    const config = {{
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
        displaylogo: false
    }};
    
    Plotly.newPlot(containerId, [trace], layout, config);
}}

// =============================================================================
// 4D PLOT (STOCKPG color scale)
// =============================================================================

function render3DPlot_StockColor(containerId, data) {{
    const stockValues = data.map(p => p.stockpg);
    
    const trace = {{
        x: data.map(p => p.ppg),
        y: data.map(p => p.rpg),
        z: data.map(p => p.apg),
        mode: 'markers',
        type: 'scatter3d',
        marker: {{
            size: data.map(p => 6 + p.dominance_pct / 12),
            color: stockValues,
            colorscale: [
                [0, '#3b82f6'],      // Low STOCKPG: blue
                [0.5, '#22c55e'],    // Mid: green
                [1, '#fbbf24']       // High STOCKPG: gold
            ],
            cmin: Math.min(...stockValues),
            cmax: Math.max(...stockValues),
            colorbar: {{
                title: 'STOCKPG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                thickness: 15,
                len: 0.6,
                x: 1.02
            }},
            opacity: 0.9,
            line: {{
                color: 'rgba(255,255,255,0.2)',
                width: 0.5
            }}
        }},
        text: data.map(p => 
            `<b>${{p.name}}</b> ${{p.season}}<br>` +
            `${{p.team}}<br>` +
            `PPG: ${{p.ppg}} | RPG: ${{p.rpg}} | APG: ${{p.apg}}<br>` +
            `STOCKPG: ${{p.stockpg.toFixed(1)}} (STL+BLK)<br>` +
            `Layer: ${{p.layer}} | Dominance: ${{p.dominance_pct.toFixed(1)}}%`
        ),
        hoverinfo: 'text',
        hoverlabel: {{
            bgcolor: '#1a1a2e',
            bordercolor: '#fbbf24',
            font: {{ color: '#fff', size: 12 }}
        }}
    }};
    
    const layout = {{
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        scene: {{
            xaxis: {{
                title: 'PPG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                gridcolor: '#333',
                zerolinecolor: '#444'
            }},
            yaxis: {{
                title: 'RPG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                gridcolor: '#333',
                zerolinecolor: '#444'
            }},
            zaxis: {{
                title: 'APG',
                titlefont: {{ color: '#888', size: 12 }},
                tickfont: {{ color: '#666', size: 10 }},
                gridcolor: '#333',
                zerolinecolor: '#444'
            }},
            bgcolor: 'rgba(0,0,0,0)',
            camera: {{
                eye: {{ x: 1.8, y: 1.8, z: 1.0 }}
            }}
        }},
        margin: {{ l: 0, r: 50, t: 10, b: 10 }},
        showlegend: false
    }};
    
    const config = {{
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
        displaylogo: false
    }};
    
    Plotly.newPlot(containerId, [trace], layout, config);
}}

// =============================================================================
// TABLE RENDERING
// =============================================================================

function renderTable(tbodyId, data, mode) {{
    const tbody = document.getElementById(tbodyId);
    
    let html = '';
    data.forEach((p, idx) => {{
        // Build tooltip for ascendants
        let tooltip = '';
        if (p.layer > 0 && p.ascendants && p.ascendants.length > 0) {{
            const ascList = p.ascendants.slice(0, 5).join('\\n');
            const more = p.ascendants.length > 5 ? `\\n+${{p.ascendants.length - 5}} more...` : '';
            tooltip = `Dominated by:\\n${{ascList}}${{more}}`;
        }} else if (p.layer === 0) {{
            tooltip = 'Undominated (Pareto Frontier)';
        }}
        
        html += `
            <tr>
                <td class="col-rank">${{idx + 1}}</td>
                <td class="col-player">
                    <div class="player-cell">
                        <img class="player-img" 
                             src="https://cdn.nba.com/headshots/nba/latest/1040x760/${{p.player_id}}.png"
                             onerror="this.style.display='none'">
                        <span class="player-name">${{p.name}}</span>
                    </div>
                </td>
                <td class="col-season">${{p.season}}</td>
                <td class="col-team"><span class="team-badge">${{p.team}}</span></td>
                <td class="col-stat">${{p.ppg.toFixed(1)}}</td>
                <td class="col-stat">${{p.rpg.toFixed(1)}}</td>
                <td class="col-stat">${{p.apg.toFixed(1)}}</td>
                ${{mode === '4d' ? `<td class="col-stat">${{p.stockpg.toFixed(1)}}</td>` : ''}}
                <td class="col-layer">
                    <span class="layer-badge ${{getLayerClass(p.layer)}}" 
                          data-tooltip="${{tooltip}}">L${{p.layer}}</span>
                </td>
                <td class="col-dom">
                    <div class="dom-value">${{p.dominance_pct.toFixed(1)}}%</div>
                    <div class="dom-bar">
                        <div class="dom-fill" style="width: ${{p.dominance_pct}}%"></div>
                    </div>
                </td>
            </tr>
        `;
    }});
    
    tbody.innerHTML = html;
}}

// =============================================================================
// SEARCH
// =============================================================================

function setupSearch(inputId, tbodyId, data, mode) {{
    const input = document.getElementById(inputId);
    
    input.addEventListener('input', () => {{
        const query = input.value.toLowerCase().trim();
        
        if (!query) {{
            renderTable(tbodyId, data, mode);
            return;
        }}
        
        const filtered = data.filter(p => 
            p.name.toLowerCase().includes(query) ||
            p.team.toLowerCase().includes(query) ||
            p.season.includes(query)
        );
        
        renderTable(tbodyId, filtered, mode);
    }});
}}

// =============================================================================
// TABS
// =============================================================================

document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        
        // Resize plots when tab becomes visible
        if (btn.dataset.tab === '3d') {{
            Plotly.Plots.resize('plot3d');
        }} else if (btn.dataset.tab === '4d') {{
            Plotly.Plots.resize('plot4d');
        }}
    }});
}});

// =============================================================================
// INIT
// =============================================================================

render3DPlot_Layers('plot3d', top100_3d);
render3DPlot_StockColor('plot4d', top100_4d);
renderTable('tbody3d', top100_3d, '3d');
renderTable('tbody4d', top100_4d, '4d');
setupSearch('search3d', 'tbody3d', top100_3d, '3d');
setupSearch('search4d', 'tbody4d', top100_4d, '4d');

    </script>
</body>
</html>
'''

# =============================================================================
# SAVE
# =============================================================================

print(f"\nSaving to {OUTPUT_PATH}...")
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Done!")
print(f"\nTop 5 (3D):")
for i, p in enumerate(top_100_3d[:5]):
    asc_count = len(p.get('ascendants', []))
    print(f"  {i+1}. {p['name']} {p['season']}: {p['ppg']}/{p['rpg']}/{p['apg']} [L{p['layer']}, {p['dominance_pct']:.1f}%, {asc_count} asc]")
