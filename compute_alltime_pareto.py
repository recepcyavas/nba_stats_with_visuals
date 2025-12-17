"""
================================================================================
COMPUTE ALL-TIME PARETO ANALYSIS
================================================================================

PURPOSE:
    Analyzes all historical player-seasons (1996-2025) to compute:
    1. Dominance percentile for every player-season
    2. All-time Pareto layers
    3. DAG for elite performances (Layer 0-2)

INPUT:
    historical_seasons.db (from fetch_historical_seasons.py)

OUTPUT:
    alltime_pareto.json
        - all_performances: dominance stats for every player-season
        - elite_dag: nodes + edges for Layer 0-2
        - frontier: Layer 0 only (the GOATs)

================================================================================
"""

import sqlite3
import json
from datetime import datetime
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "historical_seasons.db"
OUTPUT_PATH = "alltime_pareto.json"

# Pareto variables (6D)
VARIABLES = ["ppg", "rpg", "apg", "spg", "bpg", "ts_pct"]

# DAG: include layers 0, 1, 2
DAG_MAX_LAYER = 2

# Minimum filters for inclusion
MIN_GP = 20      # At least 20 games played
MIN_MPG = 20.0   # At least 20 minutes per game


# =============================================================================
# LOAD DATA
# =============================================================================

def load_all_seasons(db_path):
    """Load all player-seasons from database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT player_id, season, name, team, gp, mpg,
               ppg, rpg, apg, spg, bpg, ts_pct
        FROM season_averages
        WHERE gp >= ? AND mpg >= ?
        ORDER BY season DESC, ppg DESC
    """, (MIN_GP, MIN_MPG))
    
    performances = []
    for row in cursor:
        performances.append({
            "player_id": row["player_id"],
            "season": row["season"],
            "name": row["name"],
            "team": row["team"],
            "gp": row["gp"],
            "mpg": row["mpg"],
            "ppg": row["ppg"],
            "rpg": row["rpg"],
            "apg": row["apg"],
            "spg": row["spg"],
            "bpg": row["bpg"],
            "ts_pct": row["ts_pct"],
        })
    
    conn.close()
    return performances


# =============================================================================
# DOMINANCE LOGIC
# =============================================================================

def dominates(a, b, variables):
    """
    Check if performance 'a' dominates 'b'.
    Dominance: a >= b in ALL variables, a > b in at least ONE.
    """
    dominated_all = True
    better_in_one = False
    
    for v in variables:
        av = a.get(v, 0) or 0
        bv = b.get(v, 0) or 0
        
        if av < bv:
            dominated_all = False
            break
        if av > bv:
            better_in_one = True
    
    return dominated_all and better_in_one


def compute_dominance_counts(performances, variables):
    """
    Compute dominance count for each performance.
    
    Returns:
        Dict mapping (player_id, season) -> {dominates: N, dominated_by: M}
    """
    n = len(performances)
    print(f"  Computing dominance for {n} performances...")
    print(f"  Total comparisons: {n * (n-1) // 2:,}")
    
    # Initialize counts
    counts = {}
    for p in performances:
        key = (p["player_id"], p["season"])
        counts[key] = {"dominates": 0, "dominated_by": 0}
    
    # Pairwise comparison
    start_time = datetime.now()
    comparisons = 0
    
    for i in range(n):
        for j in range(i + 1, n):
            a = performances[i]
            b = performances[j]
            
            key_a = (a["player_id"], a["season"])
            key_b = (b["player_id"], b["season"])
            
            if dominates(a, b, variables):
                counts[key_a]["dominates"] += 1
                counts[key_b]["dominated_by"] += 1
            elif dominates(b, a, variables):
                counts[key_b]["dominates"] += 1
                counts[key_a]["dominated_by"] += 1
            # else: incomparable
            
            comparisons += 1
            
            # Progress update
            if comparisons % 5_000_000 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                pct = comparisons / (n * (n-1) // 2) * 100
                print(f"    {pct:.1f}% done ({elapsed:.1f}s elapsed)")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"  Done: {comparisons:,} comparisons in {elapsed:.1f}s")
    
    return counts


# =============================================================================
# PARETO LAYERS (NSGA-II style)
# =============================================================================

def compute_pareto_layers(performances, variables):
    """
    Compute Pareto layers for all performances.
    Layer 0 = frontier (undominated)
    Layer 1 = dominated only by Layer 0
    etc.
    
    Returns:
        Dict mapping (player_id, season) -> layer number
    """
    n = len(performances)
    print(f"  Computing Pareto layers for {n} performances...")
    
    remaining = list(range(n))  # indices
    layers = {}  # key -> layer
    layer_num = 0
    
    while remaining:
        # Find undominated in remaining set
        undominated = []
        
        for i in remaining:
            is_dominated = False
            for j in remaining:
                if i == j:
                    continue
                if dominates(performances[j], performances[i], variables):
                    is_dominated = True
                    break
            
            if not is_dominated:
                undominated.append(i)
        
        # Assign layer
        for i in undominated:
            p = performances[i]
            key = (p["player_id"], p["season"])
            layers[key] = layer_num
        
        print(f"    Layer {layer_num}: {len(undominated)} performances")
        
        # Remove from remaining
        remaining = [i for i in remaining if i not in undominated]
        layer_num += 1
        
        # Safety: stop if too many layers
        if layer_num > 100:
            print("    Warning: exceeded 100 layers, stopping")
            break
    
    return layers


# =============================================================================
# BUILD DAG
# =============================================================================

def build_elite_dag(performances, layers, dominance_counts, variables, max_layer):
    """
    Build DAG for elite performances (Layer 0 to max_layer).
    
    Returns:
        nodes: list of node dicts
        edges: list of (parent_key, child_key) tuples
    """
    # Filter to elite
    elite = []
    for p in performances:
        key = (p["player_id"], p["season"])
        layer = layers.get(key, 999)
        if layer <= max_layer:
            elite.append(p)
    
    print(f"  Building DAG for {len(elite)} elite performances (Layer 0-{max_layer})")
    
    # Build nodes
    nodes = []
    for p in elite:
        key = (p["player_id"], p["season"])
        dc = dominance_counts.get(key, {})
        
        nodes.append({
            "id": f"{p['player_id']}_{p['season']}",
            "player_id": p["player_id"],
            "season": p["season"],
            "name": p["name"],
            "team": p["team"],
            "layer": layers[key],
            "ppg": p["ppg"],
            "rpg": p["rpg"],
            "apg": p["apg"],
            "spg": p["spg"],
            "bpg": p["bpg"],
            "ts_pct": p["ts_pct"],
            "dominates": dc.get("dominates", 0),
            "dominated_by": dc.get("dominated_by", 0),
        })
    
    # Build edges (only between adjacent layers for cleaner graph)
    edges = []
    elite_keys = set((p["player_id"], p["season"]) for p in elite)
    
    for i, p1 in enumerate(elite):
        key1 = (p1["player_id"], p1["season"])
        layer1 = layers[key1]
        
        for j, p2 in enumerate(elite):
            if i == j:
                continue
            
            key2 = (p2["player_id"], p2["season"])
            layer2 = layers[key2]
            
            # Only connect adjacent layers (transitive reduction)
            if layer2 == layer1 + 1:
                if dominates(p1, p2, variables):
                    edges.append({
                        "source": f"{p1['player_id']}_{p1['season']}",
                        "target": f"{p2['player_id']}_{p2['season']}"
                    })
    
    print(f"    Nodes: {len(nodes)}, Edges: {len(edges)}")
    
    return nodes, edges


# =============================================================================
# MAIN
# =============================================================================

print("=" * 70)
print("COMPUTE ALL-TIME PARETO ANALYSIS")
print("=" * 70)
print(f"Database: {DB_PATH}")
print(f"Output: {OUTPUT_PATH}")
print(f"Variables: {VARIABLES}")
print(f"Filters: GP >= {MIN_GP}, MPG >= {MIN_MPG}")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Load data
print("[1/4] Loading data...")
performances = load_all_seasons(DB_PATH)
print(f"  Loaded {len(performances)} player-seasons")

n_total = len(performances)

# Compute dominance counts
print()
print("[2/4] Computing dominance counts...")
dominance_counts = compute_dominance_counts(performances, VARIABLES)

# Compute Pareto layers
print()
print("[3/4] Computing Pareto layers...")
layers = compute_pareto_layers(performances, VARIABLES)

# Build elite DAG
print()
print("[4/4] Building elite DAG...")
dag_nodes, dag_edges = build_elite_dag(
    performances, layers, dominance_counts, VARIABLES, DAG_MAX_LAYER
)

# Prepare output
print()
print("Preparing output...")

# All performances with stats
all_performances = []
for p in performances:
    key = (p["player_id"], p["season"])
    dc = dominance_counts.get(key, {})
    layer = layers.get(key, 999)
    
    dom_count = dc.get("dominates", 0)
    dom_pct = round(dom_count / (n_total - 1) * 100, 2) if n_total > 1 else 0
    
    all_performances.append({
        "player_id": p["player_id"],
        "season": p["season"],
        "name": p["name"],
        "team": p["team"],
        "gp": p["gp"],
        "mpg": p["mpg"],
        "ppg": p["ppg"],
        "rpg": p["rpg"],
        "apg": p["apg"],
        "spg": p["spg"],
        "bpg": p["bpg"],
        "ts_pct": p["ts_pct"],
        "layer": layer,
        "dominates": dom_count,
        "dominated_by": dc.get("dominated_by", 0),
        "dominance_pct": dom_pct,
    })

# Sort by dominance_pct descending
all_performances.sort(key=lambda x: x["dominance_pct"], reverse=True)

# Frontier only
frontier = [p for p in all_performances if p["layer"] == 0]

# Output
output = {
    "meta": {
        "generated": datetime.now().isoformat(),
        "source": DB_PATH,
        "variables": VARIABLES,
        "filters": {"min_gp": MIN_GP, "min_mpg": MIN_MPG},
        "total_performances": n_total,
        "frontier_count": len(frontier),
        "dag_layers": DAG_MAX_LAYER + 1,
    },
    "all_performances": all_performances,
    "frontier": frontier,
    "elite_dag": {
        "nodes": dag_nodes,
        "edges": dag_edges,
    }
}

# Save
with open(OUTPUT_PATH, 'w') as f:
    json.dump(output, f, indent=2)

print(f"  Saved to {OUTPUT_PATH}")

# Summary
print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

print(f"\nTotal player-seasons analyzed: {n_total}")
print(f"Pareto frontier (Layer 0): {len(frontier)} performances")

print("\n--- ALL-TIME FRONTIER (Layer 0) ---")
for p in frontier[:15]:
    print(f"  {p['name']} {p['season']} ({p['team']}): "
          f"{p['ppg']}/{p['rpg']}/{p['apg']}/{p['spg']}/{p['bpg']} TS:{p['ts_pct']}  "
          f"[dominates {p['dominance_pct']}%]")

if len(frontier) > 15:
    print(f"  ... and {len(frontier) - 15} more")

print("\n--- TOP 10 BY DOMINANCE % ---")
for i, p in enumerate(all_performances[:10]):
    print(f"  {i+1}. {p['name']} {p['season']}: {p['dominance_pct']}% "
          f"(dominates {p['dominates']:,}, dominated by {p['dominated_by']})")

print(f"\n--- ELITE DAG (Layer 0-{DAG_MAX_LAYER}) ---")
print(f"  Nodes: {len(dag_nodes)}")
print(f"  Edges: {len(dag_edges)}")

layer_counts = defaultdict(int)
for n in dag_nodes:
    layer_counts[n["layer"]] += 1
for layer in sorted(layer_counts.keys()):
    print(f"    Layer {layer}: {layer_counts[layer]} performances")

print()
print("=" * 70)
print("DONE")
print("=" * 70)
