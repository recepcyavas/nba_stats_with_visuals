"""
================================================================================
COMPUTE PARETO FRONTIER
================================================================================

PURPOSE:
    Compute Pareto-optimal performances in NBA history.
    A performance is Pareto-optimal if no other performance dominates it
    (i.e., is >= in ALL stats and > in at least one).

MODES:
    1. playeravg  - Season averages (one entry per player-season)
    2. gamebygame - Individual game performances (one entry per player-game)

DIMENSIONS:
    6D (Full):
        - PPG, RPG, APG, SPG, BPG, TS%
        - 63 subsets for sub-Pareto analysis
    
    3D (Traditional):
        - PPG, RPG, APG
        - 7 subsets for sub-Pareto analysis

SUB-PARETO ANALYSIS:
    For each dimension mode, we check membership in all possible sub-frontiers.
    For each frontier member we report:
    - pareto_count: Number of sub-frontiers they belong to
    - min_pareto_dim: SMALLEST subset dimension where still Pareto-optimal
    - min_pareto_vars: The variables forming that smallest unbeatable combo

PARETO DAG (Directed Acyclic Graph):
    Computes hierarchical dominance structure for ALL players:
    
    - Layer 0: Pareto frontier (dominated by nobody)
    - Layer 1: Dominated only by Layer 0 players
    - Layer 2: Dominated by Layer 0 or 1 players
    - etc.
    
    Direct dominance edges connect adjacent layers only:
    - Parent (layer L-1) dominates Child (layer L)
    - A player can have multiple parents (DAG, not tree)

OUTPUT STRUCTURE:
    pareto.json:
    {
        "meta": { ... },
        "playeravg": {
            "2025-26": {
                "6d": { "none": [...], "min15": [...] },
                "3d": { "none": [...], "min15": [...] }
            }
        },
        "gamebygame": { ... same structure ... },
        "dag": {
            "2025-26": {
                "6d": {
                    "none": {
                        "stats": { "total_players", "max_layer", "layer_sizes" },
                        "nodes": [ { player info with layer } ],
                        "edges": [ [parent_id, child_id], ... ]
                    }
                }
            }
        }
    }

USAGE:
    python compute_pareto.py

================================================================================
"""

import json
import sqlite3
import numpy as np
from datetime import datetime
from pathlib import Path
from itertools import combinations
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

CURRENT_SEASON = "2025-26"

# Input/Output paths
PLAYER_STATS_PATH = "player_computed_stats.json"
BOX_SCORES_DB_PATH = "player_box_scores.db"
PARETO_OUTPUT_PATH = "pareto.json"

# DAG configuration
DAG_TOP_N = 150  # Only include top N players in DAG by layer/PPG (reduces clutter)

# Dimension configurations
DIMENSIONS = {
    "6d": {
        "name": "Full (6D)",
        "variables": ["PPG", "RPG", "APG", "SPG", "BPG", "TS%"],
        "description": "Points, Rebounds, Assists, Steals, Blocks, True Shooting %"
    },
    "3d": {
        "name": "Traditional (3D)",
        "variables": ["PPG", "RPG", "APG"],
        "description": "Points, Rebounds, Assists"
    }
}

# Field mappings for playeravg mode (from player_computed_stats.json)
PLAYERAVG_FIELD_MAP = {
    "PPG": "ppg",
    "RPG": "rpg",
    "APG": "apg",
    "SPG": "spg",
    "BPG": "bpg",
    "TS%": "ts_pct"
}


# =============================================================================
# GENERATE ALL SUBSETS
# =============================================================================

def generate_all_subsets(variables: list) -> list:
    """
    Generate all non-empty subsets of variables.
    
    For n variables: 2^n - 1 subsets
        - 6 variables: 63 subsets
        - 3 variables: 7 subsets
    
    Returns:
        List of tuples, sorted by size (ascending), then alphabetically.
    """
    all_subsets = []
    for size in range(1, len(variables) + 1):
        for subset in combinations(variables, size):
            all_subsets.append(subset)
    return all_subsets


# Precompute subsets for each dimension
SUBSETS_BY_DIM = {
    dim_key: generate_all_subsets(dim_config["variables"])
    for dim_key, dim_config in DIMENSIONS.items()
}


# =============================================================================
# PARETO DOMINANCE LOGIC
# =============================================================================

def dominates(a: dict, b: dict, variables: list) -> bool:
    """
    Check if performance 'a' dominates performance 'b'.
    
    Dominance (Pareto): a >= b in ALL variables, and a > b in at least ONE.
    
    Special case for 1D: a dominates b if a > b (strict).
    
    Note: Identical performances do NOT dominate each other.
    Both would be on the Pareto frontier.
    """
    if len(variables) == 1:
        return a.get(variables[0], 0) > b.get(variables[0], 0)
    
    geq_all = all(a.get(v, 0) >= b.get(v, 0) for v in variables)
    gt_any = any(a.get(v, 0) > b.get(v, 0) for v in variables)
    return geq_all and gt_any


def compute_pareto_frontier(performances: list, variables: list) -> list:
    """
    Compute the Pareto frontier from a list of performances.
    
    Algorithm:
        1. Sort by first variable (descending) for efficiency
        2. Iterate through each performance
        3. Add to frontier if not dominated by current frontier members
        4. Remove any frontier members dominated by new addition
    
    Complexity: O(n * f) where n = input size, f = frontier size
    """
    if not performances:
        return []
    
    sorted_perfs = sorted(
        performances, 
        key=lambda x: x.get(variables[0], 0), 
        reverse=True
    )
    
    frontier = []
    
    for candidate in sorted_perfs:
        is_dominated = False
        for f in frontier:
            if dominates(f, candidate, variables):
                is_dominated = True
                break
        
        if not is_dominated:
            frontier = [f for f in frontier if not dominates(candidate, f, variables)]
            frontier.append(candidate)
    
    return frontier


def is_on_frontier(perf: dict, frontier: list, variables: list) -> bool:
    """Check if performance is a member of the given frontier."""
    perf_key = (perf.get("player_id"), perf.get("game_id"))
    for f in frontier:
        f_key = (f.get("player_id"), f.get("game_id"))
        if perf_key == f_key:
            return True
    return False


# =============================================================================
# PARETO DAG (LAYERED DOMINANCE STRUCTURE)
# =============================================================================

def compute_pareto_layers(performances: list, variables: list) -> dict:
    """
    Compute Pareto layers using non-dominated sorting (NSGA-II style peeling).
    
    Algorithm:
        Layer 0 = Pareto frontier of all performances
        Layer 1 = Pareto frontier of (all - Layer 0)
        Layer 2 = Pareto frontier of (all - Layer 0 - Layer 1)
        ... until empty
    
    Args:
        performances: List of performance dicts
        variables: List of variable names for dominance comparison
    
    Returns:
        Dict mapping player_id -> layer number (0 = frontier)
    
    Complexity: O(L × n × f_avg) where L = number of layers
    """
    remaining = performances.copy()
    layers = {}
    layer = 0
    
    while remaining:
        frontier = compute_pareto_frontier(remaining, variables)
        frontier_ids = {p["player_id"] for p in frontier}
        
        for p in frontier:
            layers[p["player_id"]] = layer
        
        remaining = [p for p in remaining if p["player_id"] not in frontier_ids]
        layer += 1
    
    return layers


def compute_dominance_dag(performances: list, variables: list, top_n: int = None) -> dict:
    """
    Compute complete Pareto DAG with layers and direct dominance edges.
    
    Direct dominance: A is a direct parent of B if:
        1. A dominates B
        2. There is NO intermediate C where A dominates C AND C dominates B
           (transitive reduction - keeps only minimal edges)
    
    This allows edges to skip layers when no intermediate path exists,
    ensuring accurate ancestor/descendant counts.
    
    Args:
        performances: List of performance dicts
        variables: List of variable names
        top_n: If set, only include top N players by layer (lower layers first, then PPG within layer)
    
    Returns:
        Dict with structure:
        {
            "stats": {
                "total_players": int,
                "max_layer": int,
                "layer_sizes": [int, ...]
            },
            "nodes": [
                {"id": player_id, "name": str, "team": str, "layer": int, 
                 "PPG": float, "RPG": float, ...},
                ...
            ],
            "edges": [[parent_id, child_id], ...]
        }
    
    Complexity: O(n²) for dominance matrix, O(n³) for transitive reduction
    """
    if not performances:
        return {"stats": {}, "nodes": [], "edges": []}
    
    print("    Computing Pareto layers...")
    layers = compute_pareto_layers(performances, variables)
    
    # Group performances by layer
    by_layer = defaultdict(list)
    for p in performances:
        by_layer[layers[p["player_id"]]].append(p)
    
    max_layer = max(layers.values())
    layer_sizes = [len(by_layer[i]) for i in range(max_layer + 1)]
    
    print(f"    Layers: {max_layer + 1} (sizes: {layer_sizes[:5]}{'...' if max_layer > 4 else ''})")
    
    # -------------------------------------------------------------------------
    # FILTER TO TOP N (if specified)
    # Sort by: layer (asc), then PPG (desc) within layer
    # -------------------------------------------------------------------------
    if top_n and top_n < len(performances):
        print(f"    Filtering to top {top_n} players by layer/PPG...")
        
        # Sort all performances by layer, then PPG
        sorted_perfs = sorted(performances, key=lambda p: (layers[p["player_id"]], -p.get("PPG", 0)))
        performances = sorted_perfs[:top_n]
        
        # Rebuild layers dict for filtered set
        layers = {p["player_id"]: layers[p["player_id"]] for p in performances}
        
        # Rebuild by_layer
        by_layer = defaultdict(list)
        for p in performances:
            by_layer[layers[p["player_id"]]].append(p)
        
        max_layer = max(layers.values()) if layers else 0
        layer_sizes = [len(by_layer[i]) for i in range(max_layer + 1)]
        
        print(f"    After filter: {len(performances)} players, {max_layer + 1} layers")
    
    # Build nodes list
    nodes = []
    perf_by_id = {}  # For quick lookup
    for p in performances:
        perf_by_id[p["player_id"]] = p
        node = {
            "id": p["player_id"],
            "name": p["name"],
            "team": p["team"],
            "layer": layers[p["player_id"]],
            "gp": p.get("gp"),
            "mpg": p.get("mpg"),
        }
        # Add all stat variables
        for v in variables:
            node[v] = p.get(v, 0)
        nodes.append(node)
    
    # -------------------------------------------------------------------------
    # STEP 1: Build full dominance matrix
    # dominance[a_id] = set of all player_ids that a dominates
    # -------------------------------------------------------------------------
    print("    Building dominance matrix...")
    dominance = {p["player_id"]: set() for p in performances}
    
    for a in performances:
        a_layer = layers[a["player_id"]]
        for b in performances:
            b_layer = layers[b["player_id"]]
            # Only check if a is in a lower layer (potential dominator)
            if a_layer < b_layer:
                if dominates(a, b, variables):
                    dominance[a["player_id"]].add(b["player_id"])
    
    total_dominance_pairs = sum(len(v) for v in dominance.values())
    print(f"    Total dominance pairs: {total_dominance_pairs}")
    
    # -------------------------------------------------------------------------
    # STEP 2: Transitive reduction
    # Edge A→B is direct iff there's no C where A dominates C AND C dominates B
    # -------------------------------------------------------------------------
    print("    Computing transitive reduction (direct edges)...")
    edges = []
    
    for a_id, dominated_by_a in dominance.items():
        for b_id in dominated_by_a:
            # Check if any intermediate C exists
            has_intermediate = False
            for c_id in dominated_by_a:
                if c_id != b_id and b_id in dominance.get(c_id, set()):
                    # A→C→B path exists, so A→B is not a direct edge
                    has_intermediate = True
                    break
            
            if not has_intermediate:
                edges.append([a_id, b_id])
    
    print(f"    Direct edges (transitive reduction): {len(edges)}")
    
    # Stats summary
    stats = {
        "total_players": len(performances),
        "max_layer": max_layer,
        "layer_sizes": layer_sizes,
        "total_edges": len(edges),
        "avg_parents_per_child": round(len(edges) / (len(performances) - layer_sizes[0]), 2) if len(performances) > layer_sizes[0] else 0
    }
    
    return {
        "stats": stats,
        "nodes": nodes,
        "edges": edges
    }


# =============================================================================
# SUB-PARETO ANALYSIS (Optimized)
# =============================================================================

def precompute_all_frontiers(all_performances: list, subsets: list) -> dict:
    """
    Precompute Pareto frontiers for all variable subsets.
    
    This is the expensive step: O(S × n × f_avg) where S = number of subsets.
    But we only do it ONCE, not once per frontier member.
    """
    print(f"    Precomputing {len(subsets)} sub-frontiers...")
    
    subset_frontiers = {}
    for i, subset in enumerate(subsets):
        if (i + 1) % 20 == 0:
            print(f"      {i+1}/{len(subsets)} subsets done...")
        
        variables = list(subset)
        frontier = compute_pareto_frontier(all_performances, variables)
        subset_frontiers[subset] = frontier
    
    print(f"    All {len(subsets)} sub-frontiers precomputed.")
    return subset_frontiers


def compute_sub_pareto_stats(perf: dict, precomputed_frontiers: dict) -> dict:
    """
    For a given performance, compute sub-Pareto statistics.
    
    Returns:
        dict with pareto_count, min_pareto_dim, min_pareto_vars
    """
    pareto_memberships = []
    
    for subset, frontier in precomputed_frontiers.items():
        if is_on_frontier(perf, frontier, list(subset)):
            pareto_memberships.append(subset)
    
    pareto_count = len(pareto_memberships)
    
    if pareto_memberships:
        min_subset = min(pareto_memberships, key=len)
        min_pareto_dim = len(min_subset)
        min_pareto_vars = list(min_subset)
    else:
        min_pareto_dim = 0
        min_pareto_vars = []
    
    return {
        "pareto_count": pareto_count,
        "min_pareto_dim": min_pareto_dim,
        "min_pareto_vars": min_pareto_vars
    }


def enrich_frontier_with_sub_pareto(frontier: list, all_performances: list, subsets: list) -> list:
    """
    Add sub-Pareto statistics to each frontier member.
    """
    precomputed = precompute_all_frontiers(all_performances, subsets)
    
    total = len(frontier)
    enriched = []
    
    print(f"    Checking membership for {total} frontier members...")
    for i, perf in enumerate(frontier):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"      {i+1}/{total} members processed...")
        
        sub_stats = compute_sub_pareto_stats(perf, precomputed)
        enriched_perf = {**perf, **sub_stats}
        enriched.append(enriched_perf)
    
    return enriched


# =============================================================================
# PLAYERAVG MODE
# =============================================================================

def load_player_stats(path: str = PLAYER_STATS_PATH) -> dict:
    """Load player computed stats from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def extract_playeravg_performance(player: dict, field_map: dict = PLAYERAVG_FIELD_MAP) -> dict:
    """Extract standardized performance dict from player data."""
    perf = {
        "player_id": player.get("player_id"),
        "game_id": None,
        "name": player.get("name"),
        "team": player.get("team"),
        "gp": player.get("gp"),
        "mpg": player.get("mpg"),
    }
    
    for var_name, field_name in field_map.items():
        value = player.get(field_name, 0)
        perf[var_name] = round(value, 1) if value else 0.0
    
    return perf


def compute_playeravg_frontier(
    season: str = CURRENT_SEASON,
    filter_type: str = "none",
    dim_key: str = "6d",
    min_mpg: float = 15.0,
    player_stats_path: str = PLAYER_STATS_PATH
) -> tuple:
    """
    Compute Pareto frontier for player season averages with sub-Pareto analysis.
    
    Returns:
        Tuple of (frontier_list, all_performances_list)
    """
    dim_config = DIMENSIONS[dim_key]
    variables = dim_config["variables"]
    subsets = SUBSETS_BY_DIM[dim_key]
    
    print(f"  Loading player stats from {player_stats_path}...")
    data = load_player_stats(player_stats_path)
    players = list(data.get("players", {}).values())
    print(f"  Total players: {len(players)}")
    
    if filter_type == "min15":
        players = [p for p in players if (p.get("mpg") or 0) >= min_mpg]
        print(f"  After MPG >= {min_mpg} filter: {len(players)}")
    
    performances = [extract_playeravg_performance(p) for p in players]
    
    print(f"  Computing {dim_key.upper()} Pareto frontier ({len(variables)} variables)...")
    frontier = compute_pareto_frontier(performances, variables)
    print(f"  Frontier size: {len(frontier)}")
    
    print(f"  Computing sub-Pareto stats ({len(subsets)} subsets)...")
    frontier = enrich_frontier_with_sub_pareto(frontier, performances, subsets)
    
    # Sort by min_pareto_dim (asc), then pareto_count (desc), then PPG (desc)
    frontier = sorted(frontier, key=lambda x: (x.get("min_pareto_dim", 99), -x.get("pareto_count", 0), -x.get("PPG", 0)))
    
    return frontier, performances


def compute_playeravg_dag(
    performances: list,
    dim_key: str = "6d",
    top_n: int = None
) -> dict:
    """
    Compute Pareto DAG for player season averages.
    
    Args:
        performances: List of player performance dicts
        dim_key: Dimension key ("6d" or "3d")
        top_n: If set, only include top N players by layer (lower layers first, then PPG)
    
    Returns:
        DAG dict with stats, nodes, edges
    """
    variables = DIMENSIONS[dim_key]["variables"]
    
    print(f"  Computing DAG for {len(performances)} players ({dim_key.upper()})...")
    dag = compute_dominance_dag(performances, variables, top_n=top_n)
    
    return dag


# =============================================================================
# GAMEBYGAME MODE
# =============================================================================

def load_box_scores(db_path: str = BOX_SCORES_DB_PATH) -> list:
    """Load all box scores from player_box_scores.db."""
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            b.player_id,
            p.player_name,
            b.team_abbreviation,
            b.game_id,
            b.game_date,
            b.matchup,
            b.min,
            b.pts,
            b.reb,
            b.ast,
            b.stl,
            b.blk,
            b.fga,
            b.fta
        FROM box_scores b
        JOIN players p ON b.player_id = p.player_id
        WHERE b.min > 0
    """
    
    cursor = conn.execute(query)
    columns = ['player_id', 'player_name', 'team_abbreviation', 'game_id', 
               'game_date', 'matchup', 'min', 'pts', 'reb', 'ast', 'stl', 
               'blk', 'fga', 'fta']
    
    games = []
    for row in cursor.fetchall():
        game = dict(zip(columns, row))
        games.append(game)
    
    conn.close()
    return games


def calculate_ts_pct(pts: int, fga: int, fta: int) -> float:
    """Calculate True Shooting Percentage."""
    denominator = 2 * (fga + 0.44 * fta)
    if denominator == 0:
        return 0.0
    return (pts / denominator) * 100


def extract_gamebygame_performance(game: dict) -> dict:
    """Extract standardized performance dict from game data."""
    pts = game.get('pts', 0) or 0
    fga = game.get('fga', 0) or 0
    fta = game.get('fta', 0) or 0
    
    ts_pct = calculate_ts_pct(pts, fga, fta)
    
    return {
        "player_id": game.get("player_id"),
        "game_id": game.get("game_id"),
        "name": game.get("player_name"),
        "team": game.get("team_abbreviation"),
        "date": game.get("game_date"),
        "matchup": game.get("matchup"),
        "min": round(game.get("min", 0) or 0, 1),
        "PPG": pts,
        "RPG": game.get("reb", 0) or 0,
        "APG": game.get("ast", 0) or 0,
        "SPG": game.get("stl", 0) or 0,
        "BPG": game.get("blk", 0) or 0,
        "TS%": round(ts_pct, 1),
    }


def compute_gamebygame_frontier(
    season: str = CURRENT_SEASON,
    filter_type: str = "none",
    dim_key: str = "6d",
    min_min: float = 15.0,
    db_path: str = BOX_SCORES_DB_PATH
) -> list:
    """
    Compute Pareto frontier for individual game performances.
    
    Note: DAG not computed for gamebygame (too many nodes/edges).
    """
    dim_config = DIMENSIONS[dim_key]
    variables = dim_config["variables"]
    subsets = SUBSETS_BY_DIM[dim_key]
    
    print(f"  Loading box scores from {db_path}...")
    games = load_box_scores(db_path)
    print(f"  Total games with MIN > 0: {len(games)}")
    
    if filter_type == "min15":
        games = [g for g in games if (g.get("min") or 0) >= min_min]
        print(f"  After MIN >= {min_min} filter: {len(games)}")
    
    performances = [extract_gamebygame_performance(g) for g in games]
    
    print(f"  Computing {dim_key.upper()} Pareto frontier ({len(variables)} variables)...")
    frontier = compute_pareto_frontier(performances, variables)
    print(f"  Frontier size: {len(frontier)}")
    
    print(f"  Computing sub-Pareto stats ({len(subsets)} subsets)...")
    frontier = enrich_frontier_with_sub_pareto(frontier, performances, subsets)
    
    frontier = sorted(frontier, key=lambda x: (x.get("min_pareto_dim", 99), -x.get("pareto_count", 0), -x.get("PPG", 0)))
    
    return frontier


# =============================================================================
# FILE I/O
# =============================================================================

def load_pareto_file(path: str = PARETO_OUTPUT_PATH) -> dict:
    """Load existing pareto.json or create new structure."""
    if Path(path).exists():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Check if old format (no dimension nesting) — migrate if needed
            needs_migration = False
            for mode in ["playeravg", "gamebygame"]:
                if mode in data:
                    for season, season_data in data[mode].items():
                        if "none" in season_data and not isinstance(season_data.get("6d"), dict):
                            needs_migration = True
                            break
            
            if needs_migration:
                print("  Migrating old pareto.json format to new dimension-nested format...")
                return create_new_structure()
            
            return data
    
    return create_new_structure()


def create_new_structure() -> dict:
    """Create a fresh pareto.json structure."""
    return {
        "meta": {
            "dimensions": {
                dim_key: {
                    "name": dim_config["name"],
                    "variables": dim_config["variables"],
                    "total_subsets": len(SUBSETS_BY_DIM[dim_key])
                }
                for dim_key, dim_config in DIMENSIONS.items()
            },
            "last_updated": None,
            "seasons": []
        },
        "playeravg": {},
        "gamebygame": {},
        "dag": {}  # New: DAG data for playeravg mode
    }


def save_pareto_file(data: dict, path: str = PARETO_OUTPUT_PATH):
    """Save pareto.json with proper formatting."""
    data["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {path}")


def update_pareto_file(
    season: str,
    mode: str,
    dim_key: str,
    filter_type: str,
    frontier: list,
    path: str = PARETO_OUTPUT_PATH
):
    """Update pareto.json with new frontier data."""
    data = load_pareto_file(path)
    
    if season not in data[mode]:
        data[mode][season] = {}
    
    if dim_key not in data[mode][season]:
        data[mode][season][dim_key] = {}
    
    data[mode][season][dim_key][filter_type] = frontier
    
    if season not in data["meta"]["seasons"]:
        data["meta"]["seasons"].append(season)
        data["meta"]["seasons"] = sorted(data["meta"]["seasons"], reverse=True)
    
    save_pareto_file(data, path)


def update_dag_file(
    season: str,
    dim_key: str,
    filter_type: str,
    dag: dict,
    path: str = PARETO_OUTPUT_PATH
):
    """Update pareto.json with DAG data."""
    data = load_pareto_file(path)
    
    if "dag" not in data:
        data["dag"] = {}
    
    if season not in data["dag"]:
        data["dag"][season] = {}
    
    if dim_key not in data["dag"][season]:
        data["dag"][season][dim_key] = {}
    
    data["dag"][season][dim_key][filter_type] = dag
    
    save_pareto_file(data, path)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("COMPUTE PARETO FRONTIER + DAG")
    print("=" * 70)
    print(f"Season: {CURRENT_SEASON}")
    print()
    
    for dim_key, dim_config in DIMENSIONS.items():
        print(f"Dimension: {dim_config['name']}")
        print(f"  Variables: {dim_config['variables']}")
        print(f"  Subsets: {len(SUBSETS_BY_DIM[dim_key])}")
    
    # -------------------------------------------------------------------------
    # PLAYERAVG MODE (with DAG)
    # -------------------------------------------------------------------------
    print(f"\n{'='*70}")
    print("PLAYERAVG MODE (with DAG)")
    print("=" * 70)
    
    for dim_key in DIMENSIONS.keys():
        print(f"\n[{dim_key.upper()}] {DIMENSIONS[dim_key]['name']}")
        print("-" * 40)
        
        for filter_type in ["none", "min15"]:
            print(f"\n  Filter: {filter_type}")
            
            # Compute frontier (returns performances too for DAG)
            frontier, performances = compute_playeravg_frontier(
                season=CURRENT_SEASON,
                filter_type=filter_type,
                dim_key=dim_key
            )
            
            # Save frontier
            update_pareto_file(
                season=CURRENT_SEASON,
                mode="playeravg",
                dim_key=dim_key,
                filter_type=filter_type,
                frontier=frontier
            )
            
            # Compute and save DAG (only for 'none' filter with top_n limit)
            if filter_type == "none":
                dag = compute_playeravg_dag(performances, dim_key, top_n=DAG_TOP_N)
                update_dag_file(
                    season=CURRENT_SEASON,
                    dim_key=dim_key,
                    filter_type=filter_type,
                    dag=dag
                )
                
                print(f"\n  DAG Summary:")
                print(f"    Total players: {dag['stats']['total_players']}")
                print(f"    Max layer: {dag['stats']['max_layer']}")
                print(f"    Layer sizes: {dag['stats']['layer_sizes'][:6]}{'...' if dag['stats']['max_layer'] > 5 else ''}")
                print(f"    Total edges: {dag['stats']['total_edges']}")
                print(f"    Avg parents/child: {dag['stats']['avg_parents_per_child']}")
            
            # Print frontier summary
            total_subsets = len(SUBSETS_BY_DIM[dim_key])
            print(f"\n  Frontier Top 5 ({filter_type}):")
            for i, p in enumerate(frontier[:5]):
                vars_str = "/".join(str(p.get(v, 0)) for v in DIMENSIONS[dim_key]["variables"])
                print(f"    {i+1}. {p['name']} ({p['team']}): {vars_str}")
                print(f"       pareto_count={p['pareto_count']}/{total_subsets}, "
                      f"min_dim={p['min_pareto_dim']}")
    
    # -------------------------------------------------------------------------
    # GAMEBYGAME MODE (no DAG — too many nodes)
    # -------------------------------------------------------------------------
    print(f"\n{'='*70}")
    print("GAMEBYGAME MODE (frontier only, no DAG)")
    print("=" * 70)
    
    for dim_key in DIMENSIONS.keys():
        print(f"\n[{dim_key.upper()}] {DIMENSIONS[dim_key]['name']}")
        print("-" * 40)
        
        for filter_type in ["none", "min15"]:
            print(f"\n  Filter: {filter_type}")
            frontier = compute_gamebygame_frontier(
                season=CURRENT_SEASON,
                filter_type=filter_type,
                dim_key=dim_key
            )
            
            update_pareto_file(
                season=CURRENT_SEASON,
                mode="gamebygame",
                dim_key=dim_key,
                filter_type=filter_type,
                frontier=frontier
            )
            
            total_subsets = len(SUBSETS_BY_DIM[dim_key])
            print(f"\n  Top 5 ({filter_type}):")
            for i, p in enumerate(frontier[:5]):
                vars_str = "/".join(str(p.get(v, 0)) for v in DIMENSIONS[dim_key]["variables"])
                print(f"    {i+1}. {p['name']} ({p['team']}) {p['date']}: {vars_str}")
                print(f"       pareto_count={p['pareto_count']}/{total_subsets}, "
                      f"min_dim={p['min_pareto_dim']}")
    
    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    data = load_pareto_file()
    
    for dim_key in DIMENSIONS.keys():
        print(f"\n{dim_key.upper()} ({DIMENSIONS[dim_key]['name']}):")
        
        for mode in ["playeravg", "gamebygame"]:
            for filter_type in ["none", "min15"]:
                count = len(data[mode].get(CURRENT_SEASON, {}).get(dim_key, {}).get(filter_type, []))
                suffix = ""
                if mode == "playeravg":
                    dag_stats = data.get("dag", {}).get(CURRENT_SEASON, {}).get(dim_key, {}).get(filter_type, {}).get("stats", {})
                    if dag_stats:
                        suffix = f" | DAG: {dag_stats.get('max_layer', 0)+1} layers, {dag_stats.get('total_edges', 0)} edges"
                print(f"  {mode}/{filter_type}: {count} Pareto-optimal{suffix}")
    
    print(f"\nOutput: {PARETO_OUTPUT_PATH}")
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
