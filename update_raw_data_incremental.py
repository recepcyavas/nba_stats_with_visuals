"""
================================================================================
UPDATE RAW DATA - INCREMENTAL VERSION
================================================================================

PURPOSE:
    Fast daily updates. Processes only NEW games since last run.
    Uses frozen team_records (vs_good/vs_bad splits don't change).

USAGE:
    - Weekly: Run update_raw.py (full rebuild, fresh good/bad splits)
    - Daily:  Run update_raw_incremental.py (fast, ~30 sec)

HOW IT WORKS:
    1. Load existing raw_state.json
    2. Find games in nba_pbp.db not yet processed
    3. Process only new games
    4. Merge into existing data (add counts, append lists)
    5. Save updated raw_state.json

FROZEN DATA (from weekly run):
    - team_records (determines vs_good/vs_bad classification)
    
UPDATED DATA (incremental):
    - margin_hist, leading_count, lineup_counts
    - game_count, wins, losses
    - threshold_data, runs, burst_freq, lead_changes
    - win_prob, checkpoints, comeback, blown_lead
    - game_shapes, timeout_analysis
    - OT margin_hist and leading_count (for OT timeline visualization)

================================================================================
"""

import sqlite3
import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "nba_pbp.db"
RAW_STATE_PATH = "raw_state.json"

TEAMS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764
}

TEAM_ID_TO_ABBREV = {v: k for k, v in TEAMS.items()}
CLUTCH_START = 2580  # 5 minutes left in Q4

# =============================================================================
# HELPER FUNCTIONS (same as update_raw.py)
# =============================================================================

def parse_clock(clock_str):
    """Parse NBA clock string like 'PT05M30.00S' to seconds remaining."""
    if not clock_str or not isinstance(clock_str, str):
        return 0
    c = clock_str.replace("PT", "").replace("S", "")
    if "M" in c:
        parts = c.split("M")
        return int(parts[0]) * 60 + float(parts[1])
    return float(c)


def to_elapsed(period, clock_str):
    """Convert period and clock to elapsed seconds from game start."""
    remaining = parse_clock(clock_str)
    if period <= 4:
        return int((period - 1) * 720 + (720 - remaining))
    else:
        return int(2880 + (period - 5) * 300 + (300 - remaining))


def get_processed_game_ids(raw_state):
    """Extract all game_ids that have been processed."""
    processed = set()
    
    # Get from game_shapes (most reliable)
    for g in raw_state.get("game_shapes", []):
        if "gid" in g:
            processed.add(g["gid"])
    
    return processed


# =============================================================================
# SINGLE GAME PROCESSING
# =============================================================================

def process_single_game(conn, game_id, home_team_id, away_team_id, game_date, team_records):
    """
    Process a single game and return data for both teams.
    Returns dict: {team_abbrev: game_data, ...}
    """
    # Get play-by-play data
    df = pd.read_sql_query("""
        SELECT period, clock, score_home, score_away
        FROM pbp
        WHERE game_id = ? AND score_home IS NOT NULL
        ORDER BY action_number
    """, conn, params=(game_id,))
    
    if len(df) == 0:
        return None, None
    
    df["elapsed"] = df.apply(lambda r: to_elapsed(r["period"], r["clock"]), axis=1)
    
    # Get lineup data
    lineups_df = pd.read_sql_query("""
        SELECT team_id, elapsed, player1_id, player2_id, player3_id, player4_id, player5_id
        FROM lineups WHERE game_id = ?
    """, conn, params=(game_id,))
    
    # Calculate opponent win percentages
    home_opp_record = team_records.get(str(away_team_id), {"wins": 0, "losses": 0})
    away_opp_record = team_records.get(str(home_team_id), {"wins": 0, "losses": 0})
    
    home_opp_total = home_opp_record["wins"] + home_opp_record["losses"]
    away_opp_total = away_opp_record["wins"] + away_opp_record["losses"]
    
    home_opp_win_pct = home_opp_record["wins"] / home_opp_total if home_opp_total > 0 else 0
    away_opp_win_pct = away_opp_record["wins"] / away_opp_total if away_opp_total > 0 else 0
    
    # Build timeline (home perspective: positive = home leading)
    g_dedup = df.groupby("elapsed").agg({
        "score_home": "last",
        "score_away": "last"
    })
    g_dedup["margin"] = g_dedup["score_home"] - g_dedup["score_away"]
    
    max_elapsed = int(g_dedup.index.max())
    final_margin_home = int(g_dedup["margin"].iloc[-1])
    
    # Build complete timeline (forward fill)
    timeline = pd.Series(index=range(max_elapsed + 1), dtype=float)
    timeline[0] = 0
    for e in g_dedup.index:
        timeline[e] = g_dedup.loc[e, "margin"]
    timeline = timeline.ffill().fillna(0)
    
    # Game properties
    went_to_ot = max_elapsed > 2880
    reg_end_margin = float(timeline[2880]) if 2880 in timeline.index else float(timeline.iloc[-1])
    ot_diff = final_margin_home - reg_end_margin if went_to_ot else 0.0
    
    # Regulation stats
    reg_timeline = timeline[timeline.index <= 2880]
    max_margin_reg = float(reg_timeline.max())  # Best for home
    min_margin_reg = float(reg_timeline.min())  # Worst for home
    
    # OT stats
    max_margin_ot = 0.0
    min_margin_ot = 0.0
    if went_to_ot:
        baseline_ot = reg_end_margin
        ot_timeline = timeline[timeline.index > 2880]
        if len(ot_timeline) > 0:
            relative_ot = ot_timeline - baseline_ot
            max_margin_ot = float(relative_ot.max())
            min_margin_ot = float(relative_ot.min())
    
    # Clutch check
    margin_at_clutch = float(timeline[CLUTCH_START]) if CLUTCH_START <= max_elapsed else float(timeline.iloc[-1])
    is_clutch = abs(margin_at_clutch) <= 5
    
    # Final scores
    final_row = g_dedup.iloc[-1]
    score_home = int(final_row["score_home"])
    score_away = int(final_row["score_away"])
    home_won = score_home > score_away
    
    # Build game shape data
    CHECKPOINTS = [6, 12, 18, 24, 30, 36, 42]
    cp_values = []
    for cp in CHECKPOINTS:
        cp_elapsed = cp * 60
        if cp_elapsed <= max_elapsed:
            cp_values.append(float(timeline[cp_elapsed]))
        else:
            cp_values.append(0.0)
    cp_values.append(float(final_margin_home))  # Final
    
    # Lead changes
    def count_lead_changes(tl):
        prev_sign = 0
        lc = 0
        for e in sorted(tl.index):
            m = tl[e]
            if m > 0:
                sign = 1
            elif m < 0:
                sign = -1
            else:
                continue
            if prev_sign != 0 and sign != prev_sign:
                lc += 1
            prev_sign = sign
        return lc
    
    lead_changes = count_lead_changes(timeline)
    
    game_shape = {
        "gid": game_id,
        "home": TEAM_ID_TO_ABBREV.get(home_team_id, "???"),
        "away": TEAM_ID_TO_ABBREV.get(away_team_id, "???"),
        "date": game_date,
        "cp": [round(x, 1) for x in cp_values],
        "home_won": home_won,
        "score": f"{score_home}-{score_away}",
        "lc": lead_changes,
        "max_home": round(max_margin_reg, 0),
        "max_away": round(-min_margin_reg, 0)
    }
    
    # Now build per-team data
    result = {}
    
    for team_id, is_home in [(home_team_id, True), (away_team_id, False)]:
        team_abbrev = TEAM_ID_TO_ABBREV.get(team_id, "???")
        
        # Flip margins for away team
        if is_home:
            team_timeline = timeline.copy()
            team_final_margin = final_margin_home
            team_won = home_won
            team_max_reg = max_margin_reg
            team_min_reg = min_margin_reg
            team_max_ot = max_margin_ot
            team_min_ot = min_margin_ot
            team_ot_diff = ot_diff
            opp_win_pct = home_opp_win_pct
            team_margin_at_clutch = margin_at_clutch
            team_reg_end_margin = reg_end_margin
        else:
            team_timeline = -timeline
            team_final_margin = -final_margin_home
            team_won = not home_won
            team_max_reg = -min_margin_reg  # Away's best = -home's worst
            team_min_reg = -max_margin_reg  # Away's worst = -home's best
            team_max_ot = -min_margin_ot
            team_min_ot = -max_margin_ot
            team_ot_diff = -ot_diff
            opp_win_pct = away_opp_win_pct
            team_margin_at_clutch = -margin_at_clutch
            team_reg_end_margin = -reg_end_margin
        
        # Determine filters
        is_vs_good = opp_win_pct > 0.5
        is_vs_bad = opp_win_pct < 0.5
        team_is_clutch = abs(team_margin_at_clutch) <= 5
        
        # Build margin histogram (absolute elapsed times)
        margin_hist = defaultdict(lambda: defaultdict(int))
        leading_count = defaultdict(int)
        
        for e in range(0, 2881, 10):
            if e <= max_elapsed:
                m = int(team_timeline[e])
                margin_hist[str(e)][str(m)] += 1
                if m > 0:
                    leading_count[str(e)] += 1
        
        # Clutch histogram (relative to clutch start)
        clutch_hist = defaultdict(lambda: defaultdict(int))
        clutch_leading = defaultdict(int)
        
        if team_is_clutch:
            baseline = team_margin_at_clutch
            for e in range(0, 301, 10):
                actual_e = CLUTCH_START + e
                if actual_e <= max_elapsed:
                    m = int(team_timeline[actual_e] - baseline)
                    clutch_hist[str(e)][str(m)] += 1
                    if m > 0:
                        clutch_leading[str(e)] += 1
        
        # OT margin histogram (relative elapsed, margins relative to reg end)
        ot_margin_hist = defaultdict(lambda: defaultdict(int))
        ot_leading_count = defaultdict(int)
        
        if went_to_ot:
            baseline_ot = team_reg_end_margin
            ot_elapsed_range = list(range(0, 301, 10))
            
            # Process each OT period
            ot_start = 2880
            while ot_start < max_elapsed:
                ot_end = min(ot_start + 300, max_elapsed)
                
                for rel_e in ot_elapsed_range:
                    actual_e = ot_start + rel_e
                    if actual_e <= ot_end and actual_e <= max_elapsed:
                        abs_margin = float(team_timeline[actual_e])
                        rel_margin = int(abs_margin - baseline_ot)
                        
                        ot_margin_hist[str(rel_e)][str(rel_margin)] += 1
                        if rel_margin > 0:
                            ot_leading_count[str(rel_e)] += 1
                
                ot_start += 300  # Next OT period
        
        # Lineup counts (individual player IDs)
        team_lineups = lineups_df[lineups_df["team_id"] == team_id]
        lineup_counts = defaultdict(lambda: defaultdict(int))
        lineup_counts_clutch = defaultdict(lambda: defaultdict(int))
        lineup_counts_ot = defaultdict(lambda: defaultdict(int))
        
        for _, row in team_lineups.iterrows():
            e = row["elapsed"]
            players = [row["player1_id"], row["player2_id"], row["player3_id"],
                      row["player4_id"], row["player5_id"]]
            
            # Main lineup
            if e <= 2880:
                key = str(e)
                for pid in players:
                    lineup_counts[key][str(int(pid))] += 1
            
            # Clutch lineup
            if team_is_clutch and CLUTCH_START <= e <= 2880:
                key = str(e - CLUTCH_START)
                for pid in players:
                    lineup_counts_clutch[key][str(int(pid))] += 1
            
            # OT lineup
            if e > 2880:
                for pid in players:
                    lineup_counts_ot["OT"][str(int(pid))] += 1
        
        # Threshold data
        threshold_time_at = {}
        for t in range(-25, 26):
            reg_tl = team_timeline[team_timeline.index <= 2880]
            if t >= 0:
                threshold_time_at[str(t)] = int((reg_tl >= t).sum())
            else:
                threshold_time_at[str(t)] = int((reg_tl <= t).sum())
        
        threshold_game = {
            "max": int(team_max_reg),
            "min": int(team_min_reg),
            "won": team_won,
            "time_at": threshold_time_at
        }
        
        # Runs data
        run_windows = {"1min": 60, "3min": 180, "6min": 360, "quarter": 720, "half": 1440}
        runs_data = {}
        
        for name, window in run_windows.items():
            max_e = min(2880, max_elapsed)
            best_run = 0.0
            worst_run = 0.0
            
            for start in range(0, max_e - window + 1, 10):
                end = start + window
                if end <= max_e:
                    run = float(team_timeline[end] - team_timeline[start])
                    best_run = max(best_run, run)
                    worst_run = min(worst_run, run)
            
            runs_data[name] = {
                "best": float(best_run),
                "worst": float(worst_run)
            }
        
        # Burst frequency
        BURST_WINDOWS = {
            "1min": {"window": 60, "thresholds": list(range(3, 9))},
            "3min": {"window": 180, "thresholds": list(range(6, 16))},
            "6min": {"window": 360, "thresholds": list(range(10, 21))}
        }
        
        burst_freq = {}
        for window_name, config in BURST_WINDOWS.items():
            burst_freq[window_name] = {}
            window = config["window"]
            
            for thresh in config["thresholds"]:
                gen = 0
                allowed = 0
                scan_end = min(2880, max_elapsed) - window
                
                i = 0
                while i <= scan_end:
                    if i + window <= max_elapsed:
                        diff = team_timeline[i + window] - team_timeline[i]
                        if diff >= thresh:
                            gen += 1
                            i += window
                        elif diff <= -thresh:
                            allowed += 1
                            i += window
                        else:
                            i += 10
                    else:
                        i += 10
                
                burst_freq[window_name][str(thresh)] = {"gen": gen, "allowed": allowed}
        
        # Win probability data
        win_prob = {}
        for minute in range(0, 49):
            e = minute * 60
            if e > max_elapsed:
                break
            
            current_margin = int(team_timeline[e])
            current_margin = max(-25, min(25, current_margin))
            
            for threshold in range(0, 26):
                if current_margin >= threshold:
                    key = f"{minute},{threshold}"
                    if key not in win_prob:
                        win_prob[key] = {"games": 0, "wins": 0}
                    win_prob[key]["games"] += 1
                    if team_won:
                        win_prob[key]["wins"] += 1
            
            for threshold in range(-1, -26, -1):
                if current_margin <= threshold:
                    key = f"{minute},{threshold}"
                    if key not in win_prob:
                        win_prob[key] = {"games": 0, "wins": 0}
                    win_prob[key]["games"] += 1
                    if team_won:
                        win_prob[key]["wins"] += 1
        
        # Checkpoints
        checkpoints = {}
        for cp in [6, 12, 18, 24, 30, 36, 42, 48]:
            cp_elapsed = cp * 60
            if cp_elapsed <= max_elapsed:
                checkpoints[str(cp)] = float(team_timeline[cp_elapsed])
            else:
                checkpoints[str(cp)] = 0.0
        checkpoints["final"] = float(team_final_margin)
        
        # Comeback / blown lead
        comeback = None
        blown_lead = None
        
        if team_won:
            if team_min_reg < 0:
                comeback = {"deficit": team_min_reg}
        else:
            if team_max_reg > 0:
                blown_lead = {"lead": team_max_reg}
        
        # Period stats
        period_defs = {
            "1": (0, 720),
            "2": (720, 1440),
            "3": (1440, 2160),
            "4": (2160, 2880),
            "1H": (0, 1440),
            "2H": (1440, 2880),
            "all": (0, 2880)
        }
        
        period_results = {}
        for pname, (start, end) in period_defs.items():
            if start > max_elapsed:
                continue
            
            actual_end = min(end, max_elapsed)
            baseline = 0 if start == 0 else float(team_timeline[start]) if start in team_timeline.index else 0
            
            if pname == "all":
                period_end_margin = team_final_margin
            else:
                period_end_margin = float(team_timeline[actual_end]) if actual_end in team_timeline.index else baseline
            
            period_diff = period_end_margin - baseline
            
            if period_diff > 0:
                p_result = "win"
            elif period_diff < 0:
                p_result = "loss"
            else:
                p_result = "tie"
            
            period_tl = team_timeline[(team_timeline.index >= start) & (team_timeline.index <= actual_end)]
            if len(period_tl) > 0:
                rel = period_tl - baseline
                p_max_lead = float(rel.max())
                p_min_margin = float(rel.min())
            else:
                p_max_lead = 0
                p_min_margin = 0
            
            period_results[pname] = {
                "result": p_result,
                "max_lead": p_max_lead,
                "min_margin": p_min_margin
            }
        
        # OT period
        if went_to_ot:
            ot_baseline = float(team_timeline[2880])
            ot_end_margin = team_final_margin
            ot_diff_val = ot_end_margin - ot_baseline
            
            if ot_diff_val > 0:
                ot_result = "win"
            elif ot_diff_val < 0:
                ot_result = "loss"
            else:
                ot_result = "tie"
            
            period_results["OT"] = {
                "result": ot_result,
                "max_lead": team_max_ot,
                "min_margin": team_min_ot
            }
        
        # Clutch period
        if team_is_clutch:
            clutch_baseline = team_margin_at_clutch
            clutch_end_margin = team_final_margin
            clutch_diff = clutch_end_margin - clutch_baseline
            
            if clutch_diff > 0:
                clutch_result = "win"
            elif clutch_diff < 0:
                clutch_result = "loss"
            else:
                clutch_result = "tie"
            
            clutch_tl = team_timeline[(team_timeline.index >= CLUTCH_START) & (team_timeline.index <= min(2880, max_elapsed))]
            if len(clutch_tl) > 0:
                rel = clutch_tl - clutch_baseline
                clutch_max_lead = float(rel.max())
                clutch_min_margin = float(rel.min())
            else:
                clutch_max_lead = 0
                clutch_min_margin = 0
            
            period_results["clutch"] = {
                "result": clutch_result,
                "max_lead": clutch_max_lead,
                "min_margin": clutch_min_margin
            }
        
        result[team_abbrev] = {
            "game_id": game_id,
            "won": team_won,
            "final_margin": team_final_margin,
            "is_vs_good": is_vs_good,
            "is_vs_bad": is_vs_bad,
            "is_clutch": team_is_clutch,
            "went_to_ot": went_to_ot,
            "ot_diff": team_ot_diff,
            "max_reg": team_max_reg,
            "min_reg": team_min_reg,
            "max_ot": team_max_ot,
            "min_ot": team_min_ot,
            "margin_hist": dict(margin_hist),
            "leading_count": dict(leading_count),
            "lineup_counts": dict(lineup_counts),
            "clutch_hist": dict(clutch_hist),
            "clutch_leading": dict(clutch_leading),
            "lineup_counts_clutch": dict(lineup_counts_clutch),
            "lineup_counts_ot": dict(lineup_counts_ot),
            "ot_margin_hist": dict(ot_margin_hist),
            "ot_leading_count": dict(ot_leading_count),
            "threshold_game": threshold_game,
            "runs": runs_data,
            "burst_freq": burst_freq,
            "lead_changes": lead_changes,
            "win_prob": win_prob,
            "checkpoints": checkpoints,
            "comeback": comeback,
            "blown_lead": blown_lead,
            "period_results": period_results,
            "margin_at_clutch": team_margin_at_clutch
        }
    
    return result, game_shape


# =============================================================================
# MERGE FUNCTIONS
# =============================================================================

def merge_histogram(existing, new):
    """Merge two histograms by adding counts."""
    for elapsed_str, margins in new.items():
        if elapsed_str not in existing:
            existing[elapsed_str] = {}
        for margin_str, count in margins.items():
            existing[elapsed_str][margin_str] = existing[elapsed_str].get(margin_str, 0) + count
    return existing


def merge_counts(existing, new):
    """Merge two count dicts by adding values."""
    for key, value in new.items():
        existing[key] = existing.get(key, 0) + value
    return existing


def merge_lineup_counts(existing, new):
    """Merge lineup counts."""
    for elapsed_str, players in new.items():
        if elapsed_str not in existing:
            existing[elapsed_str] = {}
        for pid_str, count in players.items():
            existing[elapsed_str][pid_str] = existing[elapsed_str].get(pid_str, 0) + count
    return existing


def merge_burst_freq(existing, new):
    """Merge burst frequency data."""
    for window_name, thresholds in new.items():
        if window_name not in existing:
            existing[window_name] = {}
        for thresh_str, data in thresholds.items():
            if thresh_str not in existing[window_name]:
                existing[window_name][thresh_str] = {"gen_sum": 0, "allowed_sum": 0}
            existing[window_name][thresh_str]["gen_sum"] += data["gen"]
            existing[window_name][thresh_str]["allowed_sum"] += data["allowed"]
    return existing


def merge_win_prob(existing, new):
    """Merge win probability data."""
    for key, data in new.items():
        if key not in existing:
            existing[key] = {"games": 0, "wins": 0}
        existing[key]["games"] += data["games"]
        existing[key]["wins"] += data["wins"]
    return existing


def merge_team_data(team_raw, game_data):
    """Merge a single game's data into team's raw data."""
    
    # Update game count and record
    team_raw["game_count"] = team_raw.get("game_count", 0) + 1
    if game_data["won"]:
        team_raw["wins"] = team_raw.get("wins", 0) + 1
    else:
        team_raw["losses"] = team_raw.get("losses", 0) + 1
    
    # Merge main histograms
    if "margin_hist" not in team_raw:
        team_raw["margin_hist"] = {}
    team_raw["margin_hist"] = merge_histogram(team_raw["margin_hist"], game_data["margin_hist"])
    
    if "leading_count" not in team_raw:
        team_raw["leading_count"] = {}
    team_raw["leading_count"] = merge_counts(team_raw["leading_count"], game_data["leading_count"])
    
    # Merge lineup counts
    if "lineup_counts" not in team_raw:
        team_raw["lineup_counts"] = {}
    team_raw["lineup_counts"] = merge_lineup_counts(team_raw["lineup_counts"], game_data["lineup_counts"])
    
    # Lead/deficit sums
    team_raw["max_lead_sum"] = team_raw.get("max_lead_sum", 0) + game_data["max_reg"]
    team_raw["min_margin_sum"] = team_raw.get("min_margin_sum", 0) + game_data["min_reg"]
    
    # OT contribution
    team_raw["total_ot_diff"] = team_raw.get("total_ot_diff", 0) + game_data["ot_diff"]
    
    # Merge vs_good filter
    if game_data["is_vs_good"]:
        if "vs_good" not in team_raw:
            team_raw["vs_good"] = {"game_count": 0, "wins": 0, "losses": 0, "margin_hist": {}, 
                                   "leading_count": {}, "lineup_counts": {}, "max_lead_sum": 0, 
                                   "min_margin_sum": 0, "total_ot_diff": 0}
        
        vg = team_raw["vs_good"]
        vg["game_count"] += 1
        if game_data["won"]:
            vg["wins"] += 1
        else:
            vg["losses"] += 1
        vg["margin_hist"] = merge_histogram(vg["margin_hist"], game_data["margin_hist"])
        vg["leading_count"] = merge_counts(vg["leading_count"], game_data["leading_count"])
        vg["lineup_counts"] = merge_lineup_counts(vg["lineup_counts"], game_data["lineup_counts"])
        vg["max_lead_sum"] += game_data["max_reg"]
        vg["min_margin_sum"] += game_data["min_reg"]
        vg["total_ot_diff"] += game_data["ot_diff"]
    
    # Merge vs_bad filter
    if game_data["is_vs_bad"]:
        if "vs_bad" not in team_raw:
            team_raw["vs_bad"] = {"game_count": 0, "wins": 0, "losses": 0, "margin_hist": {}, 
                                  "leading_count": {}, "lineup_counts": {}, "max_lead_sum": 0, 
                                  "min_margin_sum": 0, "total_ot_diff": 0}
        
        vb = team_raw["vs_bad"]
        vb["game_count"] += 1
        if game_data["won"]:
            vb["wins"] += 1
        else:
            vb["losses"] += 1
        vb["margin_hist"] = merge_histogram(vb["margin_hist"], game_data["margin_hist"])
        vb["leading_count"] = merge_counts(vb["leading_count"], game_data["leading_count"])
        vb["lineup_counts"] = merge_lineup_counts(vb["lineup_counts"], game_data["lineup_counts"])
        vb["max_lead_sum"] += game_data["max_reg"]
        vb["min_margin_sum"] += game_data["min_reg"]
        vb["total_ot_diff"] += game_data["ot_diff"]
    
    # Merge clutch data
    if game_data["is_clutch"]:
        if "clutch" not in team_raw:
            team_raw["clutch"] = {"game_count": 0, "wins": 0, "losses": 0, "margin_hist": {}, 
                                  "leading_count": {}, "lineup_counts": {}, "ot_games": 0, "ot_diff_sum": 0}
        
        cl = team_raw["clutch"]
        cl["game_count"] += 1
        if game_data["won"]:
            cl["wins"] += 1
        else:
            cl["losses"] += 1
        cl["margin_hist"] = merge_histogram(cl["margin_hist"], game_data["clutch_hist"])
        cl["leading_count"] = merge_counts(cl["leading_count"], game_data["clutch_leading"])
        cl["lineup_counts"] = merge_lineup_counts(cl["lineup_counts"], game_data["lineup_counts_clutch"])
        if game_data["went_to_ot"]:
            cl["ot_games"] += 1
            cl["ot_diff_sum"] += game_data["ot_diff"]
        
        # Clutch vs_good
        if game_data["is_vs_good"]:
            if "clutch_vs_good" not in team_raw:
                team_raw["clutch_vs_good"] = {"game_count": 0, "wins": 0, "losses": 0, "margin_hist": {},
                                              "leading_count": {}, "lineup_counts": {}, "ot_games": 0, "ot_diff_sum": 0}
            cvg = team_raw["clutch_vs_good"]
            cvg["game_count"] += 1
            if game_data["won"]:
                cvg["wins"] += 1
            else:
                cvg["losses"] += 1
            cvg["margin_hist"] = merge_histogram(cvg["margin_hist"], game_data["clutch_hist"])
            cvg["leading_count"] = merge_counts(cvg["leading_count"], game_data["clutch_leading"])
            cvg["lineup_counts"] = merge_lineup_counts(cvg["lineup_counts"], game_data["lineup_counts_clutch"])
            if game_data["went_to_ot"]:
                cvg["ot_games"] += 1
                cvg["ot_diff_sum"] += game_data["ot_diff"]
        
        # Clutch vs_bad
        if game_data["is_vs_bad"]:
            if "clutch_vs_bad" not in team_raw:
                team_raw["clutch_vs_bad"] = {"game_count": 0, "wins": 0, "losses": 0, "margin_hist": {},
                                             "leading_count": {}, "lineup_counts": {}, "ot_games": 0, "ot_diff_sum": 0}
            cvb = team_raw["clutch_vs_bad"]
            cvb["game_count"] += 1
            if game_data["won"]:
                cvb["wins"] += 1
            else:
                cvb["losses"] += 1
            cvb["margin_hist"] = merge_histogram(cvb["margin_hist"], game_data["clutch_hist"])
            cvb["leading_count"] = merge_counts(cvb["leading_count"], game_data["clutch_leading"])
            cvb["lineup_counts"] = merge_lineup_counts(cvb["lineup_counts"], game_data["lineup_counts_clutch"])
            if game_data["went_to_ot"]:
                cvb["ot_games"] += 1
                cvb["ot_diff_sum"] += game_data["ot_diff"]
    
    # Merge OT data (NOW WITH margin_hist and leading_count!)
    if game_data["went_to_ot"]:
        if "ot" not in team_raw:
            team_raw["ot"] = {
                "game_count": 0, "wins": 0, "losses": 0, "margin_sum": 0,
                "max_lead_sum": 0, "min_margin_sum": 0, "lineup_counts": {},
                "margin_hist": {}, "leading_count": {}
            }
        
        ot = team_raw["ot"]
        ot["game_count"] += 1
        if game_data["won"]:
            ot["wins"] += 1
        else:
            ot["losses"] += 1
        ot["margin_sum"] += game_data["ot_diff"]
        ot["max_lead_sum"] += game_data["max_ot"]
        ot["min_margin_sum"] += game_data["min_ot"]
        ot["lineup_counts"] = merge_lineup_counts(ot["lineup_counts"], game_data["lineup_counts_ot"])
        ot["margin_hist"] = merge_histogram(ot["margin_hist"], game_data["ot_margin_hist"])
        ot["leading_count"] = merge_counts(ot["leading_count"], game_data["ot_leading_count"])
        
        # OT vs_good
        if game_data["is_vs_good"]:
            if "ot_vs_good" not in team_raw:
                team_raw["ot_vs_good"] = {
                    "game_count": 0, "wins": 0, "losses": 0, "margin_sum": 0,
                    "max_lead_sum": 0, "min_margin_sum": 0, "lineup_counts": {},
                    "margin_hist": {}, "leading_count": {}
                }
            ovg = team_raw["ot_vs_good"]
            ovg["game_count"] += 1
            if game_data["won"]:
                ovg["wins"] += 1
            else:
                ovg["losses"] += 1
            ovg["margin_sum"] += game_data["ot_diff"]
            ovg["max_lead_sum"] += game_data["max_ot"]
            ovg["min_margin_sum"] += game_data["min_ot"]
            ovg["lineup_counts"] = merge_lineup_counts(ovg["lineup_counts"], game_data["lineup_counts_ot"])
            ovg["margin_hist"] = merge_histogram(ovg["margin_hist"], game_data["ot_margin_hist"])
            ovg["leading_count"] = merge_counts(ovg["leading_count"], game_data["ot_leading_count"])
        
        # OT vs_bad
        if game_data["is_vs_bad"]:
            if "ot_vs_bad" not in team_raw:
                team_raw["ot_vs_bad"] = {
                    "game_count": 0, "wins": 0, "losses": 0, "margin_sum": 0,
                    "max_lead_sum": 0, "min_margin_sum": 0, "lineup_counts": {},
                    "margin_hist": {}, "leading_count": {}
                }
            ovb = team_raw["ot_vs_bad"]
            ovb["game_count"] += 1
            if game_data["won"]:
                ovb["wins"] += 1
            else:
                ovb["losses"] += 1
            ovb["margin_sum"] += game_data["ot_diff"]
            ovb["max_lead_sum"] += game_data["max_ot"]
            ovb["min_margin_sum"] += game_data["min_ot"]
            ovb["lineup_counts"] = merge_lineup_counts(ovb["lineup_counts"], game_data["lineup_counts_ot"])
            ovb["margin_hist"] = merge_histogram(ovb["margin_hist"], game_data["ot_margin_hist"])
            ovb["leading_count"] = merge_counts(ovb["leading_count"], game_data["ot_leading_count"])
    
    # Merge threshold data
    if "threshold_data" not in team_raw:
        team_raw["threshold_data"] = {"games": []}
    team_raw["threshold_data"]["games"].append(game_data["threshold_game"])
    
    # Merge runs
    if "runs" not in team_raw:
        team_raw["runs"] = {}
    for window_name, data in game_data["runs"].items():
        if window_name not in team_raw["runs"]:
            team_raw["runs"][window_name] = {"best_sum": 0, "worst_sum": 0, "max_best": 0, "max_worst": 0, "game_count": 0}
        team_raw["runs"][window_name]["best_sum"] += data["best"]
        team_raw["runs"][window_name]["worst_sum"] += data["worst"]
        team_raw["runs"][window_name]["game_count"] += 1
        if data["best"] > team_raw["runs"][window_name]["max_best"]:
            team_raw["runs"][window_name]["max_best"] = data["best"]
        if data["worst"] < team_raw["runs"][window_name]["max_worst"]:
            team_raw["runs"][window_name]["max_worst"] = data["worst"]
    
    # Merge burst frequency
    if "burst_freq" not in team_raw:
        team_raw["burst_freq"] = {}
    team_raw["burst_freq"] = merge_burst_freq(team_raw["burst_freq"], game_data["burst_freq"])
    
    # Merge lead changes
    if "lead_changes" not in team_raw:
        team_raw["lead_changes"] = {"total": 0, "sum_sq": 0, "game_count": 0}
    team_raw["lead_changes"]["total"] += game_data["lead_changes"]
    team_raw["lead_changes"]["sum_sq"] += game_data["lead_changes"] ** 2
    team_raw["lead_changes"]["game_count"] += 1
    
    # Merge win probability
    if "win_prob" not in team_raw:
        team_raw["win_prob"] = {}
    team_raw["win_prob"] = merge_win_prob(team_raw["win_prob"], game_data["win_prob"])
    
    # Merge checkpoints
    if "checkpoints" not in team_raw:
        team_raw["checkpoints"] = {}
    for cp_str, value in game_data["checkpoints"].items():
        if cp_str not in team_raw["checkpoints"]:
            team_raw["checkpoints"][cp_str] = {"margin_sum": 0, "game_count": 0}
        team_raw["checkpoints"][cp_str]["margin_sum"] += value
        team_raw["checkpoints"][cp_str]["game_count"] += 1
    
    # Merge comeback
    if game_data["comeback"]:
        if "comeback" not in team_raw:
            team_raw["comeback"] = {"games": [], "worst_deficit_sum": 0, "max_deficit": 0, "wins_without_trailing": 0}
        team_raw["comeback"]["games"].append(game_data["game_id"])
        team_raw["comeback"]["worst_deficit_sum"] += game_data["comeback"]["deficit"]
        if game_data["comeback"]["deficit"] < team_raw["comeback"]["max_deficit"]:
            team_raw["comeback"]["max_deficit"] = game_data["comeback"]["deficit"]
    elif game_data["won"]:
        if "comeback" not in team_raw:
            team_raw["comeback"] = {"games": [], "worst_deficit_sum": 0, "max_deficit": 0, "wins_without_trailing": 0}
        team_raw["comeback"]["wins_without_trailing"] += 1
    
    # Merge blown lead
    if game_data["blown_lead"]:
        if "blown_lead" not in team_raw:
            team_raw["blown_lead"] = {"games": [], "best_lead_sum": 0, "max_lead": 0, "losses_without_leading": 0}
        team_raw["blown_lead"]["games"].append(game_data["game_id"])
        team_raw["blown_lead"]["best_lead_sum"] += game_data["blown_lead"]["lead"]
        if game_data["blown_lead"]["lead"] > team_raw["blown_lead"]["max_lead"]:
            team_raw["blown_lead"]["max_lead"] = game_data["blown_lead"]["lead"]
    elif not game_data["won"]:
        if "blown_lead" not in team_raw:
            team_raw["blown_lead"] = {"games": [], "best_lead_sum": 0, "max_lead": 0, "losses_without_leading": 0}
        team_raw["blown_lead"]["losses_without_leading"] += 1
    
    # Merge period stats
    if "period_stats" not in team_raw:
        team_raw["period_stats"] = {}
    
    for pname, pdata in game_data["period_results"].items():
        if pname not in team_raw["period_stats"]:
            team_raw["period_stats"][pname] = {"wins": 0, "losses": 0, "ties": 0, 
                                                "max_lead_sum": 0, "min_margin_sum": 0, "game_count": 0}
        
        ps = team_raw["period_stats"][pname]
        ps["game_count"] += 1
        if pdata["result"] == "win":
            ps["wins"] += 1
        elif pdata["result"] == "loss":
            ps["losses"] += 1
        else:
            ps["ties"] += 1
        ps["max_lead_sum"] += pdata["max_lead"]
        ps["min_margin_sum"] += pdata["min_margin"]
    
    return team_raw


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("UPDATE RAW DATA - INCREMENTAL")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load existing raw_state
    print(f"Loading {RAW_STATE_PATH}...")
    try:
        with open(RAW_STATE_PATH, "r") as f:
            raw_state = json.load(f)
        print(f"  Last updated: {raw_state['meta']['last_updated']}")
    except FileNotFoundError:
        print(f"  ERROR: {RAW_STATE_PATH} not found. Run update_raw.py first for initial build.")
        return
    
    # Get already processed game IDs
    processed_ids = get_processed_game_ids(raw_state)
    print(f"  Already processed: {len(processed_ids)} games")
    
    # Get frozen team records
    team_records = raw_state.get("team_records", {})
    print(f"  Frozen team records: {len(team_records)} teams")
    
    # Connect to database and find new games
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.execute("SELECT game_id, home_team_id, away_team_id, game_date FROM games ORDER BY game_date")
    all_games = cursor.fetchall()
    print(f"  Games in database: {len(all_games)}")
    
    new_games = [(gid, hid, aid, date) for gid, hid, aid, date in all_games if gid not in processed_ids]
    print(f"  New games to process: {len(new_games)}")
    
    if len(new_games) == 0:
        print("\nNo new games to process. Raw state is up to date.")
        conn.close()
        return
    
    # Process new games
    print(f"\nProcessing {len(new_games)} new games...")
    
    new_game_shapes = []
    
    for i, (game_id, home_id, away_id, game_date) in enumerate(new_games):
        print(f"  [{i+1}/{len(new_games)}] Game {game_id}...", end=" ", flush=True)
        
        team_data, game_shape = process_single_game(conn, game_id, home_id, away_id, game_date, team_records)
        
        if team_data is None:
            print("skipped (no data)")
            continue
        
        # Merge into each team's data
        for team_abbrev, gdata in team_data.items():
            if team_abbrev not in raw_state["teams"]:
                raw_state["teams"][team_abbrev] = {"team_id": TEAMS.get(team_abbrev, 0)}
            
            raw_state["teams"][team_abbrev] = merge_team_data(raw_state["teams"][team_abbrev], gdata)
        
        # Add game shape
        if game_shape:
            new_game_shapes.append(game_shape)
        
        print("done")
    
    conn.close()
    
    # Append new game shapes
    if "game_shapes" not in raw_state:
        raw_state["game_shapes"] = []
    raw_state["game_shapes"].extend(new_game_shapes)
    
    # Update meta
    raw_state["meta"]["last_updated"] = datetime.now().isoformat()
    raw_state["meta"]["total_games_processed"] = len(raw_state["game_shapes"])
    
    # Save
    print(f"\nSaving {RAW_STATE_PATH}...")
    with open(RAW_STATE_PATH, "w") as f:
        json.dump(raw_state, f)
    
    print(f"  Total games now: {raw_state['meta']['total_games_processed']}")
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  New games processed: {len(new_games)}")
    print(f"  New game shapes added: {len(new_game_shapes)}")
    print(f"  Total games in raw_state: {raw_state['meta']['total_games_processed']}")
    print()
    print("Note: vs_good/vs_bad splits use FROZEN team records.")
    print("Run update_raw.py (full rebuild) weekly to refresh splits.")
    print()
    print("DONE")


if __name__ == "__main__":
    main()
