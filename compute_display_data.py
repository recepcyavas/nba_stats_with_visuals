"""
================================================================================
COMPUTE DISPLAY DATA
================================================================================

PURPOSE:
    Step 2 of pipeline. Reads raw_state.json and computes display_data.json
    with EXACT field names matching what generate_html_v21.py expects.

INPUT:
    raw_state.json - Aggregated raw data from update_raw.py

OUTPUT:
    display_data.json - Ready for HTML generation

--------------------------------------------------------------------------------
CRITICAL: OUTPUT STRUCTURE MUST MATCH V21 JS EXACTLY
--------------------------------------------------------------------------------

The v21 JavaScript accesses data like this:

    data[team].color                    - Team color hex
    data[team].periods                  - Main period data (all games)
    data[team].vs_good                  - Period data vs >0.500 teams
    data[team].vs_bad                   - Period data vs <0.500 teams
    data[team].clutch                   - Clutch data (all games)
    data[team].clutch_vs_good           - Clutch data vs >0.500 teams
    data[team].clutch_vs_bad            - Clutch data vs <0.500 teams
    data[team].lineups                  - Lineups (all games)
    data[team].lineups_vs_good          - Lineups vs >0.500 teams
    data[team].lineups_vs_bad           - Lineups vs <0.500 teams
    data[team].lineups_clutch           - Clutch lineups (all games)
    data[team].lineups_clutch_vs_good   - Clutch lineups vs >0.500 teams
    data[team].lineups_clutch_vs_bad    - Clutch lineups vs <0.500 teams
    data[team].thresholds               - Threshold analysis
    data[team].checkpoints              - Margin at checkpoints
    data[team].comeback                 - Comeback wins data
    data[team].blown_lead               - Blown lead losses data
    data[team].garbage_time             - Garbage time analysis
    data[team].runs                     - Best/worst runs
    data[team].win_prob                 - Win probability heatmap

PERIOD STRUCTURE (periods, vs_good, vs_bad):
    {
        "all": { "diff": [...], "games": N, "wins": N, "losses": N, 
                 "margin": N, "avg_lead": N, "avg_deficit": N },
        "1":   { ... },   # Q1
        "2":   { ... },   # Q2
        "3":   { ... },   # Q3
        "4":   { ... },   # Q4
        "1H":  { ... },   # 1st half
        "2H":  { ... },   # 2nd half
        "OT":  { "games": N, "wins": N, "losses": N, "margin": N }
    }

DIFF ARRAY FORMAT:
    [elapsed, mean, p25, p75, leading_pct, min, max]
    
    - elapsed: Seconds from period start (0-2880 for all, 0-720 for quarter, etc.)
    - mean: Average margin at this elapsed time
    - p25: 25th percentile margin
    - p75: 75th percentile margin
    - leading_pct: Percentage of games where team was leading
    - min: Minimum margin across all games
    - max: Maximum margin across all games

CLUTCH STRUCTURE:
    {
        "diff": [...],           # Elapsed 0-300 (last 5 minutes)
        "games": N,
        "wins": N,
        "losses": N,
        "margin": N,             # Final margin (includes OT contribution)
        "avg_lead": N,
        "avg_deficit": N,
        "ot_games": N,
        "ot_contribution": N
    }

LINEUP STRUCTURE:
    {
        "0": [[player_id, name], [player_id, name], ...],
        "10": [...],
        ...
        "OT": [...]
    }

THRESHOLDS STRUCTURE:
    {
        "-25": { "frequency": N, "time": N, "win_pct": N },
        ...
        "25": { "frequency": N, "time": N, "win_pct": N }
    }

RUNS STRUCTURE:
    {
        "1min": { "avg_best": N, "avg_worst": N },
        "3min": { ... },
        "6min": { ... },
        "quarter": { ... },
        "half": { ... }
    }

WIN_PROB STRUCTURE:
    {
        "0,0": [pct, n],
        "12,5": [pct, n],
        ...
    }

================================================================================
"""

import json
import numpy as np
from datetime import datetime
from collections import Counter

# Optional sklearn for clustering (graceful fallback if not installed)
try:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: sklearn not installed. Game clustering will be disabled.")

# =============================================================================
# CONFIGURATION
# =============================================================================

RAW_STATE_PATH = "raw_state.json"
DISPLAY_DATA_PATH = "display_data.json"

TEAM_COLORS = {
    "ATL": "#E03A3E", "BOS": "#007A33", "BKN": "#FFFFFF", "CHA": "#1D8CAB",
    "CHI": "#CE1141", "CLE": "#860038", "DAL": "#00538C", "DEN": "#FEC524",
    "DET": "#C8102E", "GSW": "#1D428A", "HOU": "#CE1141", "IND": "#FDBB30",
    "LAC": "#C8102E", "LAL": "#552583", "MEM": "#5D76A9", "MIA": "#98002E",
    "MIL": "#00471B", "MIN": "#236192", "NOP": "#C8102E", "NYK": "#F58426",
    "OKC": "#007AC1", "ORL": "#0077C0", "PHI": "#006BB6", "PHX": "#E56020",
    "POR": "#E03A3E", "SAC": "#5A2D81", "SAS": "#C4CED4", "TOR": "#CE1141",
    "UTA": "#4B7AB3", "WAS": "#E31837"
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def percentile_from_histogram(hist, p):
    """
    Compute percentile from a histogram {margin_str: count}.
    """
    if not hist:
        return 0
    
    total = sum(hist.values())
    if total == 0:
        return 0
    
    target = total * p / 100
    cumsum = 0
    
    for margin in sorted(int(k) for k in hist.keys()):
        cumsum += hist[str(margin)]
        if cumsum >= target:
            return margin
    
    return max(int(k) for k in hist.keys())


def mean_from_histogram(hist):
    """
    Compute mean from a histogram {margin_str: count}.
    """
    if not hist:
        return 0
    
    total = sum(hist.values())
    if total == 0:
        return 0
    
    weighted_sum = sum(int(m) * c for m, c in hist.items())
    return weighted_sum / total


def min_from_histogram(hist):
    """Get minimum margin from histogram."""
    if not hist:
        return 0
    return min(int(k) for k in hist.keys())


def max_from_histogram(hist):
    """Get maximum margin from histogram."""
    if not hist:
        return 0
    return max(int(k) for k in hist.keys())


def compute_lead_deficit_from_hist(period_hist):
    """
    Compute avg_lead and avg_deficit from a period's histogram data.
    avg_lead = max mean margin across all time points in period
    avg_deficit = min mean margin across all time points in period
    """
    if not period_hist:
        return 0, 0
    
    means = []
    for elapsed_str, hist in period_hist.items():
        if hist:
            mean = mean_from_histogram(hist)
            means.append(mean)
    
    if not means:
        return 0, 0
    
    avg_lead = max(means)
    avg_deficit = min(means)
    return avg_lead, avg_deficit


def compute_diff_array(margin_hist, leading_count, elapsed_range):
    """
    Compute diff array from margin histogram and leading counts.
    
    Returns: List of [elapsed, mean, p25, p75, leading_pct, min, max]
    """
    diff = []
    
    for e in elapsed_range:
        e_str = str(e)
        hist = margin_hist.get(e_str, {})
        lead_count = leading_count.get(e_str, 0)
        
        if hist:
            total = sum(hist.values())
            mean = round(mean_from_histogram(hist), 2)
            p25 = round(percentile_from_histogram(hist, 25), 2)
            p75 = round(percentile_from_histogram(hist, 75), 2)
            p_min = round(min_from_histogram(hist), 2)
            p_max = round(max_from_histogram(hist), 2)
            leading_pct = round(lead_count / total * 100, 1) if total > 0 else 0
            
            diff.append([e, mean, p25, p75, leading_pct, p_min, p_max])
    
    return diff


def compute_lineups(player_counts, elapsed_keys, player_names):
    """
    Convert player frequency counts to top 5 players per elapsed time.
    
    Returns: {"elapsed": [[player_id, name], ...], ...}
    """
    result = {}
    
    for key in elapsed_keys:
        key_str = str(key)
        counts = player_counts.get(key_str, {})
        
        if counts:
            # Sort by frequency, take top 5
            top5 = sorted(counts.items(), key=lambda x: -x[1])[:5]
            
            lineup = []
            for pid_str, _ in top5:
                pid = int(pid_str)
                name = player_names.get(str(pid), f"Player {pid}")
                lineup.append([pid, name])
            
            result[key_str] = lineup
    
    return result


def compute_period_stats(diff_array, game_count, wins, losses, ties=0, avg_lead=None, avg_deficit=None):
    """
    Compute period statistics from diff array.
    
    RULE: avg_lead and avg_deficit should be passed in from raw data
    (average of max lead per game, average of min margin per game).
    If not provided, fall back to computing from diff_array (less accurate).
    """
    if not diff_array:
        return {
            "diff": [],
            "games": game_count,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "margin": 0,
            "avg_lead": 0,
            "avg_deficit": 0
        }
    
    final_margin = diff_array[-1][1]  # mean at last elapsed
    
    # Use provided values or fall back to diff_array computation
    if avg_lead is None:
        leads = [d[1] for d in diff_array if d[1] > 0]
        avg_lead = np.mean(leads) if leads else 0
    if avg_deficit is None:
        deficits = [d[1] for d in diff_array if d[1] < 0]
        avg_deficit = np.mean(deficits) if deficits else 0
    
    return {
        "diff": diff_array,
        "games": game_count,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "margin": round(final_margin, 2),
        "avg_lead": round(avg_lead, 2),
        "avg_deficit": round(avg_deficit, 2)
    }


# =============================================================================
# MAIN COMPUTATION FUNCTIONS
# =============================================================================

def compute_periods(team_raw, player_names):
    """
    Compute periods structure with all period/half/quarter breakdowns.
    
    CRITICAL RULES:
    - Q1, 1H, all: baseline = 0 (margins are absolute)
    - Q2, Q3, Q4, 2H: baseline = margin at period start (margins are relative)
    - Elapsed times are RELATIVE to period start (0, 10, 20...)
    - Full game ("all") at elapsed 2880 gets OT contribution added
    """
    periods = {}
    
    # Period definitions: (start_elapsed, duration, needs_baseline_subtraction)
    period_defs = {
        "all": (0, 2880, False),
        "1":   (0, 720, False),
        "2":   (720, 720, True),   # Subtract baseline at 720
        "3":   (1440, 720, True),  # Subtract baseline at 1440
        "4":   (2160, 720, True),  # Subtract baseline at 2160
        "1H":  (0, 1440, False),
        "2H":  (1440, 1440, True)  # Subtract baseline at 1440
    }
    
    margin_hist = team_raw["margin_hist"]
    leading_count = team_raw["leading_count"]
    game_count = team_raw["game_count"]
    
    for period_name, (start, duration, needs_baseline) in period_defs.items():
        end = start + duration
        
        if needs_baseline:
            # PERIOD-RELATIVE COMPUTATION
            # For Q2/Q3/Q4/2H, we need to subtract baseline margin
            # Build new histogram with relative elapsed and relative margins
            
            # Get baseline histogram at period start
            baseline_hist = margin_hist.get(str(start), {})
            if not baseline_hist:
                # No data at period start, skip
                periods[period_name] = compute_period_stats([], game_count, team_raw["wins"], team_raw["losses"], ties=0)
                continue
            
            # Build relative histogram
            rel_margin_hist = {}
            rel_leading_count = {}
            
            for abs_e in range(start, end + 1, 10):
                rel_e = abs_e - start  # Relative elapsed (0, 10, 20...)
                abs_hist = margin_hist.get(str(abs_e), {})
                
                if not abs_hist:
                    continue
                
                # For each (baseline_margin, count) in baseline, and (current_margin, count) in current,
                # we need to compute relative margins. This is complex because we don't have per-game data.
                # APPROXIMATION: Subtract mean baseline from mean current
                # This is accurate for mean but not for percentiles.
                
                # Actually, we need to compute this properly. The histogram stores the distribution of 
                # margins across games at each elapsed time. To get period-relative, we'd need per-game
                # baseline subtraction, which we don't have in histogram form.
                
                # SOLUTION: Use the same histogram but shift the elapsed times to be relative
                # and compute baseline shift from mean
                rel_margin_hist[str(rel_e)] = abs_hist
                rel_leading_count[str(rel_e)] = leading_count.get(str(abs_e), 0)
            
            # Compute baseline mean to shift the histogram
            baseline_mean = mean_from_histogram(baseline_hist) if baseline_hist else 0
            
            # Shift all histogram values by baseline
            shifted_hist = {}
            shifted_leading = {}
            for rel_e_str, hist in rel_margin_hist.items():
                shifted_hist[rel_e_str] = {}
                lead_count = 0
                for margin_str, count in hist.items():
                    new_margin = int(margin_str) - int(baseline_mean)
                    shifted_hist[rel_e_str][str(new_margin)] = count
                    if new_margin > 0:
                        lead_count += count
                shifted_leading[rel_e_str] = lead_count
            
            elapsed_range = list(range(0, duration + 1, 10))
            diff_array = compute_diff_array(shifted_hist, shifted_leading, elapsed_range)
            
        else:
            # ABSOLUTE COMPUTATION (Q1, 1H, all)
            period_hist = {k: v for k, v in margin_hist.items() 
                           if start <= int(k) <= end}
            period_leading = {k: v for k, v in leading_count.items() 
                              if start <= int(k) <= end}
            
            elapsed_range = list(range(start, end + 1, 10))
            diff_array = compute_diff_array(period_hist, period_leading, elapsed_range)
        
        # Get per-period stats from raw data
        ps = team_raw.get("period_stats", {}).get(period_name, {})
        period_wins = ps.get("wins", team_raw["wins"] if period_name == "all" else 0)
        period_losses = ps.get("losses", team_raw["losses"] if period_name == "all" else 0)
        period_ties = ps.get("ties", 0)
        max_lead_sum = ps.get("max_lead_sum", team_raw.get("max_lead_sum", 0))
        min_margin_sum = ps.get("min_margin_sum", team_raw.get("min_margin_sum", 0))
        period_game_count = ps.get("game_count", game_count)
        
        avg_lead = max_lead_sum / period_game_count if period_game_count > 0 else 0
        avg_deficit = min_margin_sum / period_game_count if period_game_count > 0 else 0
        
        periods[period_name] = compute_period_stats(
            diff_array,
            game_count,
            period_wins,
            period_losses,
            ties=period_ties,
            avg_lead=avg_lead,
            avg_deficit=avg_deficit
        )
    
    # Add OT contribution to full game at elapsed 2880 (RULE 3)
    total_ot_diff = team_raw.get("total_ot_diff", 0)
    if game_count > 0 and "all" in periods and periods["all"]["diff"]:
        ot_contribution = total_ot_diff / game_count
        diff_array = periods["all"]["diff"]
        if diff_array:
            last_idx = len(diff_array) - 1
            diff_array[last_idx][1] = round(diff_array[last_idx][1] + ot_contribution, 2)
            # Also adjust percentiles
            diff_array[last_idx][2] = round(diff_array[last_idx][2] + ot_contribution, 2)
            diff_array[last_idx][3] = round(diff_array[last_idx][3] + ot_contribution, 2)
            periods["all"]["margin"] = diff_array[last_idx][1]
    
    # OT data
    ot_data = team_raw.get("ot", {})
    ot_games = ot_data.get("game_count", 0)
    
    # Get OT-specific stats from period_stats
    ot_ps = team_raw.get("period_stats", {}).get("OT", {})
    ot_max_lead_sum = ot_ps.get("max_lead_sum", 0)
    ot_min_margin_sum = ot_ps.get("min_margin_sum", 0)
    ot_ps_game_count = ot_ps.get("game_count", ot_games)
    
    if ot_games > 0:
        ot_margin = ot_data.get("margin_sum", 0) / ot_games
        ot_avg_lead = ot_max_lead_sum / ot_ps_game_count if ot_ps_game_count > 0 else 0
        ot_avg_deficit = ot_min_margin_sum / ot_ps_game_count if ot_ps_game_count > 0 else 0
        periods["OT"] = {
            "games": ot_games,
            "wins": ot_ps.get("wins", ot_data.get("wins", 0)),
            "losses": ot_ps.get("losses", ot_data.get("losses", 0)),
            "ties": ot_ps.get("ties", 0),
            "margin": round(ot_margin, 2),
            "avg_lead": round(ot_avg_lead, 2),
            "avg_deficit": round(ot_avg_deficit, 2)
        }
    else:
        periods["OT"] = {"games": 0, "wins": 0, "losses": 0, "ties": 0, "margin": 0, "avg_lead": 0, "avg_deficit": 0}
    
    return periods


def compute_filter_periods(filter_raw, ot_raw, player_names):
    """
    Compute periods structure for a filter (vs_good or vs_bad).
    Same logic as compute_periods but for filtered data.
    """
    periods = {}
    
    # Period definitions: (start_elapsed, duration, needs_baseline_subtraction)
    period_defs = {
        "all": (0, 2880, False),
        "1":   (0, 720, False),
        "2":   (720, 720, True),
        "3":   (1440, 720, True),
        "4":   (2160, 720, True),
        "1H":  (0, 1440, False),
        "2H":  (1440, 1440, True)
    }
    
    margin_hist = filter_raw.get("margin_hist", {})
    leading_count = filter_raw.get("leading_count", {})
    game_count = filter_raw.get("game_count", 0)
    
    for period_name, (start, duration, needs_baseline) in period_defs.items():
        end = start + duration
        
        if needs_baseline:
            # PERIOD-RELATIVE COMPUTATION
            baseline_hist = margin_hist.get(str(start), {})
            if not baseline_hist:
                periods[period_name] = compute_period_stats([], game_count, filter_raw.get("wins", 0), filter_raw.get("losses", 0), ties=0)
                continue
            
            rel_margin_hist = {}
            rel_leading_count = {}
            
            for abs_e in range(start, end + 1, 10):
                rel_e = abs_e - start
                abs_hist = margin_hist.get(str(abs_e), {})
                if not abs_hist:
                    continue
                rel_margin_hist[str(rel_e)] = abs_hist
                rel_leading_count[str(rel_e)] = leading_count.get(str(abs_e), 0)
            
            baseline_mean = mean_from_histogram(baseline_hist) if baseline_hist else 0
            
            shifted_hist = {}
            shifted_leading = {}
            for rel_e_str, hist in rel_margin_hist.items():
                shifted_hist[rel_e_str] = {}
                lead_count = 0
                for margin_str, count in hist.items():
                    new_margin = int(margin_str) - int(baseline_mean)
                    shifted_hist[rel_e_str][str(new_margin)] = count
                    if new_margin > 0:
                        lead_count += count
                shifted_leading[rel_e_str] = lead_count
            
            elapsed_range = list(range(0, duration + 1, 10))
            diff_array = compute_diff_array(shifted_hist, shifted_leading, elapsed_range)
            
            # Compute lead/deficit from shifted histogram for this period
            avg_lead, avg_deficit = compute_lead_deficit_from_hist(shifted_hist)
        else:
            period_hist = {k: v for k, v in margin_hist.items() 
                           if start <= int(k) <= end}
            period_leading = {k: v for k, v in leading_count.items() 
                              if start <= int(k) <= end}
            
            elapsed_range = list(range(start, end + 1, 10))
            diff_array = compute_diff_array(period_hist, period_leading, elapsed_range)
            
            # Compute lead/deficit from period histogram
            avg_lead, avg_deficit = compute_lead_deficit_from_hist(period_hist)
        
        periods[period_name] = compute_period_stats(
            diff_array,
            game_count,
            filter_raw.get("wins", 0),
            filter_raw.get("losses", 0),
            ties=0,
            avg_lead=avg_lead,
            avg_deficit=avg_deficit
        )
    
    # Add OT contribution to full game
    total_ot_diff = filter_raw.get("total_ot_diff", 0)
    if game_count > 0 and "all" in periods and periods["all"]["diff"]:
        ot_contribution = total_ot_diff / game_count
        diff_array = periods["all"]["diff"]
        if diff_array:
            last_idx = len(diff_array) - 1
            diff_array[last_idx][1] = round(diff_array[last_idx][1] + ot_contribution, 2)
            diff_array[last_idx][2] = round(diff_array[last_idx][2] + ot_contribution, 2)
            diff_array[last_idx][3] = round(diff_array[last_idx][3] + ot_contribution, 2)
            periods["all"]["margin"] = diff_array[last_idx][1]
    
    # OT for this filter
    ot_games = ot_raw.get("game_count", 0)
    if ot_games > 0:
        ot_margin = ot_raw.get("margin_sum", 0) / ot_games
        ot_avg_lead = ot_raw.get("max_lead_sum", 0) / ot_games
        ot_avg_deficit = ot_raw.get("min_margin_sum", 0) / ot_games
        
        # Build OT diff array from margin_hist
        ot_margin_hist = ot_raw.get("margin_hist", {})
        ot_leading_count = ot_raw.get("leading_count", {})
        ot_elapsed_range = list(range(0, 301, 10))
        ot_diff_array = compute_diff_array(ot_margin_hist, ot_leading_count, ot_elapsed_range)
        
        periods["OT"] = {
            "diff": ot_diff_array,
            "games": ot_games,
            "wins": ot_raw.get("wins", 0),
            "losses": ot_raw.get("losses", 0),
            "ties": 0,
            "margin": round(ot_margin, 2),
            "avg_lead": round(ot_avg_lead, 2),
            "avg_deficit": round(ot_avg_deficit, 2)
        }
    else:
        periods["OT"] = {"diff": [], "games": 0, "wins": 0, "losses": 0, "ties": 0, "margin": 0, "avg_lead": 0, "avg_deficit": 0}
    
    return periods


def compute_clutch(clutch_raw, player_names, clutch_stats=None):
    """
    Compute clutch data structure.
    Clutch uses elapsed 0-300 (relative to clutch start at 43:00).
    
    clutch_stats: optional period_stats["clutch"] for proper avg_lead/avg_deficit
    """
    clutch_elapsed = list(range(0, 301, 10))
    
    margin_hist = clutch_raw.get("margin_hist", {})
    leading_count = clutch_raw.get("leading_count", {})
    
    diff_array = compute_diff_array(margin_hist, leading_count, clutch_elapsed)
    
    game_count = clutch_raw.get("game_count", 0)
    wins = clutch_raw.get("wins", 0)
    losses = clutch_raw.get("losses", 0)
    ot_games = clutch_raw.get("ot_games", 0)
    ot_diff_sum = clutch_raw.get("ot_diff_sum", 0)
    
    # OT contribution: average OT diff * fraction of games that went to OT
    ot_contribution = 0
    if ot_games > 0 and game_count > 0:
        avg_ot_diff = ot_diff_sum / ot_games
        ot_contribution = avg_ot_diff * ot_games / game_count
    
    # Adjust final point in diff array for OT contribution
    if diff_array and len(diff_array) > 0:
        last_idx = len(diff_array) - 1
        diff_array[last_idx][1] = round(diff_array[last_idx][1] + ot_contribution, 2)
        diff_array[last_idx][2] = round(diff_array[last_idx][2] + ot_contribution, 2)
        diff_array[last_idx][3] = round(diff_array[last_idx][3] + ot_contribution, 2)
        # Update leading_pct to win percentage for final point
        if game_count > 0:
            diff_array[last_idx][4] = round(wins / game_count * 100, 1)
    
    final_margin = diff_array[-1][1] if diff_array else 0
    
    # Get avg_lead and avg_deficit from clutch_stats if available
    if clutch_stats and clutch_stats.get("game_count", 0) > 0:
        cs_game_count = clutch_stats["game_count"]
        avg_lead = clutch_stats.get("max_lead_sum", 0) / cs_game_count
        avg_deficit = clutch_stats.get("min_margin_sum", 0) / cs_game_count
        ties = clutch_stats.get("ties", 0)
    else:
        # Compute from histogram data
        avg_lead, avg_deficit = compute_lead_deficit_from_hist(margin_hist)
        ties = 0
    
    return {
        "diff": diff_array,
        "games": game_count,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "margin": round(final_margin, 2),
        "avg_lead": round(avg_lead, 2),
        "avg_deficit": round(avg_deficit, 2),
        "ot_games": ot_games,
        "ot_contribution": round(ot_contribution, 2)
    }


def compute_thresholds(team_raw):
    """
    Compute threshold analysis.
    """
    threshold_games = team_raw.get("threshold_data", {}).get("games", [])
    total_games = len(threshold_games)
    
    if total_games == 0:
        return {}
    
    thresholds = {}
    
    for t in range(-25, 26):
        t_str = str(t)
        
        if t >= 0:
            # Games that reached this margin or higher
            games_reached = [g for g in threshold_games if g["max"] >= t]
        else:
            # Games that fell to this margin or lower
            games_reached = [g for g in threshold_games if g["min"] <= t]
        
        frequency = len(games_reached) / total_games * 100
        
        # Time at this threshold
        total_time = sum(g["time_at"].get(t_str, 0) for g in threshold_games)
        total_possible = total_games * 2881  # All elapsed points
        time_pct = total_time / total_possible * 100 if total_possible > 0 else 0
        
        # Win percentage when reaching this threshold
        if games_reached:
            wins = sum(1 for g in games_reached if g["won"])
            win_pct = wins / len(games_reached) * 100
        else:
            win_pct = None
        
        thresholds[t_str] = {
            "frequency": round(frequency, 1),
            "time": round(time_pct, 2),
            "win_pct": round(win_pct, 1) if win_pct is not None else None
        }
    
    return thresholds


def compute_runs(team_raw):
    """
    Compute runs analysis.
    avg_best/avg_worst = average across all games
    max_best/max_worst = single game extremes
    """
    runs_raw = team_raw.get("runs", {})
    runs = {}
    
    for duration in ["1min", "3min", "6min", "quarter", "half"]:
        data = runs_raw.get(duration, {"best_sum": 0, "worst_sum": 0, "game_count": 0})
        game_count = data.get("game_count", 0)
        
        if game_count > 0:
            avg_best = data["best_sum"] / game_count
            avg_worst = data["worst_sum"] / game_count
        else:
            avg_best = 0
            avg_worst = 0
        
        runs[duration] = {
            "avg_best": round(avg_best, 1),
            "avg_worst": round(avg_worst, 1),
            "max_best": round(data.get("max_best", 0), 0),
            "max_worst": round(data.get("max_worst", 0), 0)
        }
    
    return runs


def compute_burst_freq(team_raw):
    """
    Compute burst frequency for scatter plot.
    Returns averages per game at each threshold.
    """
    burst_freq_raw = team_raw.get("burst_freq", {})
    game_count = team_raw.get("game_count", 0)
    
    if game_count == 0:
        return {}
    
    burst_freq = {}
    for window_name in ["1min", "3min", "6min"]:
        burst_freq[window_name] = {}
        window_data = burst_freq_raw.get(window_name, {})
        
        for thresh_str, data in window_data.items():
            gen_avg = data.get("gen_sum", 0) / game_count
            allowed_avg = data.get("allowed_sum", 0) / game_count
            
            burst_freq[window_name][thresh_str] = {
                "gen": round(gen_avg, 2),
                "allowed": round(allowed_avg, 2)
            }
    
    return burst_freq


def compute_lead_changes(team_raw):
    """
    Compute lead changes average and standard deviation.
    """
    lc_raw = team_raw.get("lead_changes", {})
    total = lc_raw.get("total", 0)
    sum_sq = lc_raw.get("sum_sq", 0)
    game_count = lc_raw.get("game_count", 0)
    
    if game_count == 0:
        return {"avg": 0, "std": 0, "games": 0}
    
    avg = total / game_count
    # Variance = E[X^2] - E[X]^2
    variance = (sum_sq / game_count) - (avg * avg)
    std = variance ** 0.5 if variance > 0 else 0
    
    return {
        "avg": round(avg, 2),
        "std": round(std, 2),
        "games": game_count
    }


def compute_garbage_time(team_raw):
    """
    Compute garbage time analysis.
    """
    instances = team_raw.get("garbage_time", {}).get("instances", [])
    game_count = team_raw.get("game_count", 0)
    
    if not instances or game_count == 0:
        return {
            "frequency_pct": 0,
            "total_instances": 0,
            "in_wins": 0,
            "in_losses": 0,
            "successful": 0,
            "failed": 0,
            "avg_start": 0,
            "avg_duration": 0,
            "avg_garbage_diff": 0
        }
    
    total = len(instances)
    in_wins = sum(1 for i in instances if i["won"])
    in_losses = total - in_wins
    successful = sum(1 for i in instances if i["successful"])
    failed = total - successful
    
    return {
        "frequency_pct": round(total / game_count * 100, 1),
        "total_instances": total,
        "in_wins": in_wins,
        "in_losses": in_losses,
        "successful": successful,
        "failed": failed,
        "avg_start": round(np.mean([i["start_min"] for i in instances]), 1),
        "avg_duration": round(np.mean([i["duration"] for i in instances]), 1),
        "avg_garbage_diff": round(np.mean([i["diff"] for i in instances]), 1)
    }


def compute_comeback_blown(team_raw):
    """
    Compute comeback wins and blown lead losses.
    
    Fields:
    - games: count of comeback wins / blown lead losses
    - avg_worst_deficit / avg_best_lead: average deficit/lead
    - max_deficit / max_lead: single largest comeback / blown lead
    - wins_without_trailing: wins where team never fell behind
    - losses_without_leading: losses where team never had a lead
    """
    comeback_raw = team_raw.get("comeback", {})
    blown_raw = team_raw.get("blown_lead", {})
    
    comeback_games = len(comeback_raw.get("games", []))
    comeback_deficit_sum = comeback_raw.get("worst_deficit_sum", 0)
    
    blown_games = len(blown_raw.get("games", []))
    blown_lead_sum = blown_raw.get("best_lead_sum", 0)
    
    comeback = {
        "games": comeback_games,
        "avg_worst_deficit": round(comeback_deficit_sum / comeback_games, 1) if comeback_games > 0 else 0,
        "max_deficit": comeback_raw.get("max_deficit", 0),
        "wins_without_trailing": comeback_raw.get("wins_without_trailing", 0)
    }
    
    blown_lead = {
        "games": blown_games,
        "avg_best_lead": round(blown_lead_sum / blown_games, 1) if blown_games > 0 else 0,
        "max_lead": blown_raw.get("max_lead", 0),
        "losses_without_leading": blown_raw.get("losses_without_leading", 0)
    }
    
    return comeback, blown_lead


def compute_checkpoints(team_raw):
    """
    Compute margin at checkpoints.
    Includes "final" which is actual game ending (with OT).
    """
    checkpoints_raw = team_raw.get("checkpoints", {})
    checkpoints = {}
    
    for cp in [6, 12, 18, 24, 30, 36, 42, 48]:
        cp_str = str(cp)
        data = checkpoints_raw.get(cp_str, {"margin_sum": 0, "game_count": 0})
        
        if data["game_count"] > 0:
            avg = data["margin_sum"] / data["game_count"]
        else:
            avg = 0
        
        checkpoints[cp] = round(avg, 1)
    
    # Add final margin (includes OT)
    final_data = checkpoints_raw.get("final", {"margin_sum": 0, "game_count": 0})
    if final_data["game_count"] > 0:
        checkpoints["final"] = round(final_data["margin_sum"] / final_data["game_count"], 1)
    else:
        checkpoints["final"] = 0
    
    return checkpoints


def compute_win_prob(team_raw):
    """
    Compute win probability heatmap.
    Format: {"minute,margin": [pct, n], ...}
    """
    win_prob_raw = team_raw.get("win_prob", {})
    win_prob = {}
    
    for key, data in win_prob_raw.items():
        games = data.get("games", 0)
        wins = data.get("wins", 0)
        
        if games > 0:
            pct = round(wins / games * 100, 1)
            win_prob[key] = [pct, games]
    
    return win_prob


# =============================================================================
# TEAM COMPUTATION
# =============================================================================

def compute_player_activity(player_counts, game_count, player_names, player_gp=None):
    """
    Compute on-court percentage over time for each player.
    Percentage is relative to games that player played in (using player_gp).
    
    Returns: {
        player_id: {
            "name": "Player Name",
            "gp": games_played,
            "data": [[elapsed, pct], ...]  // pct = on-court percentage given player played
        }
    }
    """
    if game_count == 0:
        return {}
    
    if player_gp is None:
        player_gp = {}
    
    # Collect all player IDs
    all_players = set()
    for time_counts in player_counts.values():
        all_players.update(time_counts.keys())
    
    # Build activity data per player
    result = {}
    elapsed_points = sorted([int(k) for k in player_counts.keys() if k != "OT"])
    
    for pid in all_players:
        # Get player's games played, fall back to team game_count
        gp = player_gp.get(pid, game_count)
        if gp == 0:
            gp = game_count  # Fallback
        
        data = []
        for e in elapsed_points:
            count = player_counts.get(str(e), {}).get(pid, 0)
            # Scale: count / player_gp * 100
            pct = round(count / gp * 100, 1)
            # Cap at 100% (can exceed if player_gp < team_games due to mid-season trade)
            pct = min(pct, 100.0)
            data.append([e, pct])
        
        result[pid] = {
            "name": player_names.get(pid, f"Player {pid}"),
            "gp": gp,
            "data": data
        }
    
    return result


def compute_team_display(team_abbrev, team_raw, player_names, player_gp=None):
    """
    Compute all display data for one team.
    Output structure matches EXACTLY what v21 JS expects.
    """
    # Main lineups elapsed keys
    main_elapsed_keys = list(range(0, 2881, 10)) + ["OT"]
    clutch_elapsed_keys = list(range(0, 301, 10))
    
    # Compute comeback and blown lead
    comeback, blown_lead = compute_comeback_blown(team_raw)
    
    display = {
        # Team color
        "color": TEAM_COLORS.get(team_abbrev, "#888888"),
        
        # Main period data (all games)
        "periods": compute_periods(team_raw, player_names),
        
        # Period data vs >0.500 teams
        "vs_good": compute_filter_periods(
            team_raw.get("vs_good", {}),
            team_raw.get("ot_vs_good", {}),
            player_names
        ),
        
        # Period data vs <0.500 teams
        "vs_bad": compute_filter_periods(
            team_raw.get("vs_bad", {}),
            team_raw.get("ot_vs_bad", {}),
            player_names
        ),
        
        # Clutch data (all games) - pass period_stats for proper lead/deficit
        "clutch": compute_clutch(
            team_raw.get("clutch", {}), 
            player_names,
            clutch_stats=team_raw.get("period_stats", {}).get("clutch", {})
        ),
        
        # Clutch data vs >0.500 teams
        "clutch_vs_good": compute_clutch(team_raw.get("clutch_vs_good", {}), player_names),
        
        # Clutch data vs <0.500 teams
        "clutch_vs_bad": compute_clutch(team_raw.get("clutch_vs_bad", {}), player_names),
        
        # Lineups (all games)
        "lineups": compute_lineups(
            team_raw.get("lineup_counts", {}),
            main_elapsed_keys,
            player_names
        ),
        
        # Lineups vs >0.500 teams
        "lineups_vs_good": compute_lineups(
            team_raw.get("vs_good", {}).get("lineup_counts", {}),
            main_elapsed_keys,
            player_names
        ),
        
        # Lineups vs <0.500 teams
        "lineups_vs_bad": compute_lineups(
            team_raw.get("vs_bad", {}).get("lineup_counts", {}),
            main_elapsed_keys,
            player_names
        ),
        
        # Clutch lineups (all games)
        "lineups_clutch": compute_lineups(
            team_raw.get("clutch", {}).get("lineup_counts", {}),
            clutch_elapsed_keys,
            player_names
        ),
        
        # Clutch lineups vs >0.500 teams
        "lineups_clutch_vs_good": compute_lineups(
            team_raw.get("clutch_vs_good", {}).get("lineup_counts", {}),
            clutch_elapsed_keys,
            player_names
        ),
        
        # Clutch lineups vs <0.500 teams
        "lineups_clutch_vs_bad": compute_lineups(
            team_raw.get("clutch_vs_bad", {}).get("lineup_counts", {}),
            clutch_elapsed_keys,
            player_names
        ),
        
        # Threshold analysis
        "thresholds": compute_thresholds(team_raw),
        
        # Runs
        "runs": compute_runs(team_raw),
        
        # Burst frequency
        "burst_freq": compute_burst_freq(team_raw),
        
        # Timeout analysis
        "timeout_analysis": team_raw.get("timeout_analysis", {}),
        
        # Lead changes
        "lead_changes": compute_lead_changes(team_raw),
        
        # Garbage time
        "garbage_time": compute_garbage_time(team_raw),
        
        # Comeback / blown lead
        "comeback": comeback,
        "blown_lead": blown_lead,
        
        # Checkpoints
        "checkpoints": compute_checkpoints(team_raw),
        
        # Win probability heatmap
        "win_prob": compute_win_prob(team_raw),
        
        # Player activity (on-court % over time)
        "player_activity": compute_player_activity(
            team_raw.get("lineup_counts", {}),
            team_raw.get("game_count", 0),
            player_names,
            player_gp
        )
    }
    
    # Add OT lineups to main lineups
    ot_lineup = compute_lineups(
        team_raw.get("ot", {}).get("lineup_counts", {}),
        ["OT"],
        player_names
    )
    if "OT" in ot_lineup:
        display["lineups"]["OT"] = ot_lineup["OT"]
    
    # Add OT lineups to filtered lineups
    ot_lineup_vs_good = compute_lineups(
        team_raw.get("ot_vs_good", {}).get("lineup_counts", {}),
        ["OT"],
        player_names
    )
    if "OT" in ot_lineup_vs_good:
        display["lineups_vs_good"]["OT"] = ot_lineup_vs_good["OT"]
    
    ot_lineup_vs_bad = compute_lineups(
        team_raw.get("ot_vs_bad", {}).get("lineup_counts", {}),
        ["OT"],
        player_names
    )
    if "OT" in ot_lineup_vs_bad:
        display["lineups_vs_bad"]["OT"] = ot_lineup_vs_bad["OT"]
    
    return display


# =============================================================================
# MAIN
# =============================================================================

# =============================================================================
# GAME SHAPE CLUSTERING
# =============================================================================

def compute_game_clusters(raw_state, k=5):
    """
    Cluster games by shape (margin progression).
    
    Returns dict with:
      - centroids: k x 8 array (cluster centers)
      - names: cluster labels based on shape
      - games: list of game dicts with cluster assignment and PCA coords
    """
    if not SKLEARN_AVAILABLE:
        return None
    
    game_shapes = raw_state.get("game_shapes", [])
    
    if len(game_shapes) < k:
        return None
    
    # Build feature matrix (orient from winner's perspective)
    X = []
    game_info = []
    
    for g in game_shapes:
        cp = g["cp"]  # 8 checkpoints from home perspective
        
        # Orient from winner's perspective
        if g["home_won"]:
            oriented_cp = cp  # Home won, keep as is
        else:
            oriented_cp = [-x for x in cp]  # Away won, flip sign
        
        X.append(oriented_cp)
        game_info.append(g)
    
    X = np.array(X)
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # K-means clustering
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    
    # Get centroids in original scale
    centroids_scaled = kmeans.cluster_centers_
    centroids = scaler.inverse_transform(centroids_scaled)
    
    # PCA for 2D visualization
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    
    # Name clusters based on centroid shapes (compares all at once for unique names)
    cluster_names = name_clusters(centroids)
    
    # Build games list with cluster info
    games = []
    for idx, g in enumerate(game_info):
        games.append({
            "home": g["home"],
            "away": g["away"],
            "date": g.get("date", ""),
            "cluster": int(labels[idx]),
            "pc1": round(float(X_pca[idx, 0]), 2),
            "pc2": round(float(X_pca[idx, 1]), 2),
            "home_won": g["home_won"],
            "score": g["score"],
            "lc": g["lc"],
            "max_home": int(g["max_home"]),
            "max_away": int(g["max_away"])
        })
    
    return {
        "k": k,
        "centroids": [[round(x, 1) for x in c] for c in centroids],
        "names": cluster_names,
        "games": games
    }


def name_clusters(centroids):
    """
    Name clusters by matching their shape characteristics.
    Returns list of names in same order as centroids.
    
    Target names (based on observed shapes):
    - Blowout: huge lead throughout, final ~28+
    - Nail-biter: close all game, final ~5-6
    - Late comeback: down 6-8 most of game, wins late
    - Controlled win: steady lead ~13, never trailed
    - Early rally: down early, takes control by halftime
    """
    k = len(centroids)
    names = [None] * k
    used = set()
    
    # Compute features for matching
    features = []
    for c in centroids:
        features.append({
            'start': np.mean(c[:2]),       # avg of 6min, 12min
            'mid': np.mean(c[2:5]),         # avg of 18, 24, 30min
            'final': c[-1],
            'min_val': min(c),
            'max_val': max(c)
        })
    
    # Match by characteristics (order matters - most distinctive first)
    
    # Blowout: highest final margin
    idx = max(range(k), key=lambda i: features[i]['final'] if names[i] is None else -999)
    if features[idx]['final'] > 20:
        names[idx] = "Blowout"
        used.add(idx)
    
    # Nail-biter: lowest final margin
    idx = min(range(k), key=lambda i: features[i]['final'] if names[i] is None else 999)
    if features[idx]['final'] < 8 and idx not in used:
        names[idx] = "Nail-biter"
        used.add(idx)
    
    # Late comeback: most negative mid-game, positive finish
    idx = min(range(k), key=lambda i: features[i]['mid'] if names[i] is None else 999)
    if features[idx]['mid'] < -3 and features[idx]['final'] > 0 and idx not in used:
        names[idx] = "Late comeback"
        used.add(idx)
    
    # Early rally: negative start, positive mid and end
    for i in range(k):
        if names[i] is None and features[i]['start'] < 0 and features[i]['mid'] > 0:
            names[i] = "Early rally"
            used.add(i)
            break
    
    # Controlled win: led throughout (min_val > 0), moderate final
    for i in range(k):
        if names[i] is None and features[i]['min_val'] > 0:
            names[i] = "Controlled win"
            used.add(i)
            break
    
    # Fallback for any remaining
    fallback_names = ["Steady win", "Comfortable win", "Grinding win", "Close win", "Tight game"]
    fallback_idx = 0
    for i in range(k):
        if names[i] is None:
            names[i] = fallback_names[fallback_idx % len(fallback_names)]
            fallback_idx += 1
    
    return names


def compute_timeout_rankings(display_data):
    """
    Compute timeout efficiency rankings for all teams.
    
    For each team, computes:
    - avg_before: average of curve values for t < 0
    - avg_after: average of curve values for t > 0
    - recovery: avg_after (how much they gain after TO)
    
    Returns rankings for my_to, opp_to, all_to modes.
    """
    rankings = {"my_to": [], "opp_to": [], "all_to": []}
    
    for team, team_data in display_data.items():
        if team.startswith("_"):
            continue
        
        ta = team_data.get("timeout_analysis", {})
        if not ta:
            continue
        
        time_points = ta.get("time_points", [])
        if not time_points:
            continue
        
        for mode in ["my_to", "opp_to", "all_to"]:
            mode_data = ta.get(mode, {})
            curve = mode_data.get("curve", [])
            count = mode_data.get("count", 0)
            
            if not curve or count == 0:
                continue
            
            # Split curve into before and after
            before_vals = []
            after_vals = []
            for i, t in enumerate(time_points):
                if t < 0:
                    before_vals.append(curve[i])
                elif t > 0:
                    after_vals.append(curve[i])
            
            avg_before = sum(before_vals) / len(before_vals) if before_vals else 0
            avg_after = sum(after_vals) / len(after_vals) if after_vals else 0
            
            rankings[mode].append({
                "team": team,
                "count": count,
                "avg_before": round(avg_before, 2),
                "avg_after": round(avg_after, 2),
                "recovery": round(avg_after - avg_before, 2)
            })
    
    # Sort by recovery (best at top)
    for mode in rankings:
        rankings[mode].sort(key=lambda x: x["recovery"], reverse=True)
    
    return rankings


def main():
    print("=" * 70)
    print("COMPUTE DISPLAY DATA")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load raw state
    print(f"Loading {RAW_STATE_PATH}...")
    try:
        with open(RAW_STATE_PATH, "r") as f:
            raw_state = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {RAW_STATE_PATH} not found. Run update_raw.py first.")
        return
    
    print(f"Raw state last updated: {raw_state['meta']['last_updated']}")
    print()
    
    # Get player names
    player_names = raw_state.get("player_names", {})
    print(f"Loaded {len(player_names)} player names")
    
    # Load player GP from player_stats.db
    player_gp = {}
    try:
        import sqlite3
        conn = sqlite3.connect("player_stats.db")
        cursor = conn.execute("SELECT PLAYER_ID, GP FROM player_season_stats")
        for row in cursor:
            player_gp[str(int(row[0]))] = int(row[1])
        conn.close()
        print(f"Loaded {len(player_gp)} player GP values")
    except Exception as e:
        print(f"Warning: Could not load player GP: {e}")
    
    # Compute display data for each team
    print("\nComputing display data...")
    display_data = {}
    
    for team_abbrev in TEAM_COLORS.keys():
        print(f"  {team_abbrev}...", end=" ", flush=True)
        
        team_raw = raw_state["teams"].get(team_abbrev)
        if team_raw:
            display_data[team_abbrev] = compute_team_display(team_abbrev, team_raw, player_names, player_gp)
            print("done")
        else:
            print("no data")
    
    # Compute league-wide win probability
    print("\nComputing league win probability...")
    league_win_prob = {}
    for team_abbrev, team_display in display_data.items():
        for key, value in team_display.get("win_prob", {}).items():
            if key not in league_win_prob:
                league_win_prob[key] = {"total_pct": 0, "total_games": 0}
            league_win_prob[key]["total_pct"] += value[0] * value[1]
            league_win_prob[key]["total_games"] += value[1]
    
    # Average the league win probability
    league_win_prob_final = {}
    for key, data in league_win_prob.items():
        if data["total_games"] > 0:
            avg_pct = data["total_pct"] / data["total_games"]
            league_win_prob_final[key] = [round(avg_pct, 1), data["total_games"]]
    
    display_data["_league"] = {"win_prob": league_win_prob_final}
    
    # Compute game shape clusters
    print("\nComputing game shape clusters...")
    clusters = compute_game_clusters(raw_state, k=5)
    if clusters:
        display_data["_clusters"] = clusters
        print(f"  Clustered {len(clusters['games'])} games into {clusters['k']} clusters")
        for i, name in enumerate(clusters["names"]):
            count = sum(1 for g in clusters["games"] if g["cluster"] == i)
            print(f"    Cluster {i}: {name} ({count} games)")
    else:
        print("  No game shapes data found")
    
    # Compute timeout efficiency rankings
    print("\nComputing timeout rankings...")
    timeout_rankings = compute_timeout_rankings(display_data)
    if timeout_rankings:
        display_data["_timeout_rankings"] = timeout_rankings
        print(f"  Computed rankings for {len(timeout_rankings['my_to'])} teams")
    else:
        print("  No timeout data found")
    
    # Save display data
    print(f"\nSaving {DISPLAY_DATA_PATH}...")
    with open(DISPLAY_DATA_PATH, "w") as f:
        json.dump(display_data, f)
    
    print(f"Saved display data ({len(display_data) - 1} teams + league)")
    
    # Verification
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    for team in ["OKC", "CLE", "BOS"]:
        if team in display_data:
            d = display_data[team]
            
            # Check periods structure
            periods = d.get("periods", {})
            all_diff = periods.get("all", {}).get("diff", [])
            print(f"\n{team}:")
            print(f"  periods.all.diff: {len(all_diff)} points, format: {all_diff[0] if all_diff else 'empty'}")
            print(f"  periods.1.diff: {len(periods.get('1', {}).get('diff', []))} points")
            print(f"  periods.OT: {periods.get('OT', {})}")
            
            # Check vs_good/vs_bad
            vs_good = d.get("vs_good", {})
            print(f"  vs_good.all.games: {vs_good.get('all', {}).get('games', 0)}")
            print(f"  vs_good.1.diff: {len(vs_good.get('1', {}).get('diff', []))} points")
            
            # Check clutch
            clutch = d.get("clutch", {})
            print(f"  clutch.games: {clutch.get('games', 0)}, margin: {clutch.get('margin', 0)}")
            
            # Check runs
            runs = d.get("runs", {})
            print(f"  runs.3min: {runs.get('3min', {})}")
            
            # Check win_prob
            win_prob = d.get("win_prob", {})
            print(f"  win_prob: {len(win_prob)} entries")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
