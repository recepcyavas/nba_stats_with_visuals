"""
================================================================================
UPDATE RAW DATA
================================================================================

PURPOSE:
    Step 1 of pipeline. Reads play-by-play data from nba_pbp.db and aggregates
    into raw_state.json.

INPUT:
    nba_pbp.db - SQLite database with tables: games, pbp, players, lineups

OUTPUT:
    raw_state.json - Aggregated raw data

================================================================================
CRITICAL RULES - READ CAREFULLY
================================================================================

RULE 1: MARGIN_HIST USES ABSOLUTE ELAPSED TIMES
    margin_hist keys are absolute elapsed times (0, 10, 20, ... 2880)
    margin_hist values are absolute margins (cumulative from game start)
    compute_display.py handles period-relative conversion

RULE 2: WIN PROBABILITY - CHECK CURRENT MARGIN (NOT MAX/MIN SO FAR)
    At minute t, check CURRENT margin at that exact time:
    - For threshold >= 0: count if current_margin >= threshold
    - For threshold < 0: count if current_margin <= threshold
    
    This means at minute 36 with margin -3:
    - Count for thresholds -1, -2, -3 (since -3 <= all of them)
    - NOT counted for 0, +1, etc. (since -3 is not >= 0)
    
    Cells must be mutually exclusive at same time!
    A game at margin -3 at minute 36 cannot be in BOTH +0 AND -3 cells.

RULE 3: WIN IS DETERMINED BY FINAL GAME OUTCOME (INCLUDES OT)
    won = final_margin > 0
    final_margin is the margin at the END of the game, including OT if played.
    Do NOT use margin at 48:00 to determine win.

RULE 4: OT CONTRIBUTION DATA
    Store total_ot_diff so compute_display.py can add OT contribution
    to the final point of full game data.

RULE 5: LEAD AND DEFICIT RAW DATA
    Store max_lead_sum and min_margin_sum per filter:
    - max_lead_sum = sum of (max margin during regulation) per game
    - min_margin_sum = sum of (min margin during regulation) per game
    avg_lead = max_lead_sum / game_count
    avg_deficit = min_margin_sum / game_count

RULE 6: JSON SERIALIZATION
    All numpy types must be converted: bool(), float(), int()

RULE 7: OT MARGIN_HIST FOR TIMELINE VISUALIZATION
    OT margin_hist uses relative elapsed (0-300 per OT period).
    Margins are relative to regulation end baseline.
    Multiple OT periods are combined.

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
# HELPER FUNCTIONS
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


def get_player_names(conn):
    """Load player names from database."""
    df = pd.read_sql_query("SELECT person_id, name FROM players", conn)
    return dict(zip(df["person_id"], df["name"]))


# =============================================================================
# DATA COLLECTION
# =============================================================================

def collect_team_data(conn, team_abbrev, team_id, team_records, player_names):
    """Collect all raw data for one team."""
    
    # Get all play-by-play data
    df = pd.read_sql_query("""
        SELECT p.game_id, p.period, p.clock, p.score_home, p.score_away,
               g.home_team_id, g.away_team_id
        FROM pbp p
        JOIN games g ON p.game_id = g.game_id
        WHERE (g.home_team_id = ? OR g.away_team_id = ?)
          AND p.score_home IS NOT NULL
    """, conn, params=(team_id, team_id))
    
    if len(df) == 0:
        return None
    
    df["elapsed"] = df.apply(lambda r: to_elapsed(r["period"], r["clock"]), axis=1)
    df["margin"] = df.apply(
        lambda r: (r["score_home"] - r["score_away"]) if r["home_team_id"] == team_id 
                  else (r["score_away"] - r["score_home"]),
        axis=1
    )
    
    # Get lineup data
    lineups_df = pd.read_sql_query("""
        SELECT game_id, elapsed, player1_id, player2_id, player3_id, player4_id, player5_id
        FROM lineups WHERE team_id = ?
    """, conn, params=(team_id,))
    
    # Calculate opponent win percentages
    opponent_win_pct = {}
    for gid, g in df.groupby("game_id"):
        home_id = g["home_team_id"].iloc[0]
        away_id = g["away_team_id"].iloc[0]
        opp_id = away_id if home_id == team_id else home_id
        opp_record = team_records.get(opp_id, {"wins": 0, "losses": 0})
        total = opp_record["wins"] + opp_record["losses"]
        opponent_win_pct[gid] = opp_record["wins"] / total if total > 0 else 0
    
    # -------------------------------------------------------------------------
    # Process each game - build timeline
    # -------------------------------------------------------------------------
    game_data = {}
    for gid, g in df.groupby("game_id"):
        g_dedup = g.groupby("elapsed")["margin"].last()
        max_elapsed = int(g_dedup.index.max())
        final_margin = float(g_dedup.iloc[-1])  # RULE 3: This includes OT
        
        # Build complete timeline (forward fill)
        timeline = pd.Series(index=range(max_elapsed + 1), dtype=float)
        timeline[0] = 0
        for e, m in g_dedup.items():
            timeline[e] = m
        timeline = timeline.ffill().fillna(0)
        
        # Margin at clutch start
        margin_at_clutch = float(timeline[CLUTCH_START]) if CLUTCH_START <= max_elapsed else float(timeline.iloc[-1])
        
        # OT detection
        went_to_ot = max_elapsed > 2880
        reg_end_margin = float(timeline[2880]) if 2880 in timeline.index else float(timeline.iloc[-1])
        ot_diff = final_margin - reg_end_margin if went_to_ot else 0.0
        
        # Regulation stats (RULE 5: for avg_lead/avg_deficit)
        reg_timeline = timeline[timeline.index <= 2880]
        max_margin_reg = float(reg_timeline.max())
        min_margin_reg = float(reg_timeline.min())
        
        # OT stats (for OT lead/deficit)
        max_margin_ot = 0.0
        min_margin_ot = 0.0
        if went_to_ot:
            baseline_ot = reg_end_margin
            ot_timeline = timeline[timeline.index > 2880]
            if len(ot_timeline) > 0:
                relative_ot = ot_timeline - baseline_ot
                max_margin_ot = float(relative_ot.max())
                min_margin_ot = float(relative_ot.min())
        
        game_data[gid] = {
            "timeline": timeline,
            "final_margin": final_margin,
            "max_elapsed": max_elapsed,
            "won": bool(final_margin > 0),  # RULE 3: Includes OT result
            "opponent_win_pct": opponent_win_pct[gid],
            "is_clutch": abs(margin_at_clutch) <= 5,
            "margin_at_clutch": margin_at_clutch,
            "went_to_ot": went_to_ot,
            "ot_diff": float(ot_diff),
            "reg_end_margin": reg_end_margin,
            "max_margin_reg": max_margin_reg,
            "min_margin_reg": min_margin_reg,
            "max_margin_ot": max_margin_ot,
            "min_margin_ot": min_margin_ot
        }
    
    # Split games by filter
    all_game_ids = list(game_data.keys())
    games_vs_good = [gid for gid, gd in game_data.items() if gd["opponent_win_pct"] > 0.5]
    games_vs_bad = [gid for gid, gd in game_data.items() if gd["opponent_win_pct"] < 0.5]
    clutch_all = [gid for gid, gd in game_data.items() if gd["is_clutch"]]
    clutch_vs_good = [gid for gid in games_vs_good if game_data[gid]["is_clutch"]]
    clutch_vs_bad = [gid for gid in games_vs_bad if game_data[gid]["is_clutch"]]
    ot_all = [gid for gid, gd in game_data.items() if gd["went_to_ot"]]
    ot_vs_good = [gid for gid in games_vs_good if game_data[gid]["went_to_ot"]]
    ot_vs_bad = [gid for gid in games_vs_bad if game_data[gid]["went_to_ot"]]
    
    # -------------------------------------------------------------------------
    # Build margin histograms and leading counts
    # Keys are ABSOLUTE elapsed times, values are ABSOLUTE margins
    # -------------------------------------------------------------------------
    
    def build_margin_hist_and_leading(game_ids, elapsed_range):
        """Build margin histogram and leading count."""
        margin_hist = defaultdict(lambda: defaultdict(int))
        leading_count = defaultdict(int)
        
        for gid in game_ids:
            timeline = game_data[gid]["timeline"]
            for e in elapsed_range:
                if e <= game_data[gid]["max_elapsed"]:
                    m = int(timeline[e])
                    margin_hist[str(e)][str(m)] += 1
                    if m > 0:
                        leading_count[str(e)] += 1
        
        return dict(margin_hist), dict(leading_count)
    
    # Main period data (elapsed 0-2880)
    main_elapsed = list(range(0, 2881, 10))
    margin_hist_all, leading_all = build_margin_hist_and_leading(all_game_ids, main_elapsed)
    margin_hist_vs_good, leading_vs_good = build_margin_hist_and_leading(games_vs_good, main_elapsed)
    margin_hist_vs_bad, leading_vs_bad = build_margin_hist_and_leading(games_vs_bad, main_elapsed)
    
    # Clutch data (elapsed 0-300 relative to clutch start)
    clutch_elapsed = list(range(0, 301, 10))
    
    def build_clutch_hist(game_ids):
        """Build clutch histogram with margin relative to clutch start."""
        margin_hist = defaultdict(lambda: defaultdict(int))
        leading_count = defaultdict(int)
        
        for gid in game_ids:
            gd = game_data[gid]
            baseline = gd["margin_at_clutch"]
            timeline = gd["timeline"]
            
            for e in clutch_elapsed:
                actual_e = CLUTCH_START + e
                if actual_e <= gd["max_elapsed"]:
                    m = int(timeline[actual_e] - baseline)
                    margin_hist[str(e)][str(m)] += 1
                    if m > 0:
                        leading_count[str(e)] += 1
        
        return dict(margin_hist), dict(leading_count)
    
    clutch_hist_all, clutch_leading_all = build_clutch_hist(clutch_all)
    clutch_hist_vs_good, clutch_leading_vs_good = build_clutch_hist(clutch_vs_good)
    clutch_hist_vs_bad, clutch_leading_vs_bad = build_clutch_hist(clutch_vs_bad)
    
    # -------------------------------------------------------------------------
    # OT histogram (RULE 7: relative elapsed, margins relative to reg end)
    # -------------------------------------------------------------------------
    
    def build_ot_hist(game_ids):
        """
        Build OT histogram with margin relative to regulation end.
        
        OT elapsed is relative (0 = start of OT, 10, 20, ... up to 300 per period).
        Multiple OT periods are combined - if a game has 2OT, both contribute.
        Margins are relative to regulation end (baseline = margin at elapsed 2880).
        """
        margin_hist = defaultdict(lambda: defaultdict(int))
        leading_count = defaultdict(int)
        
        ot_elapsed_range = list(range(0, 301, 10))  # 0 to 300 in 10s increments
        
        for gid in game_ids:
            gd = game_data[gid]
            if not gd["went_to_ot"]:
                continue
            
            timeline = gd["timeline"]
            max_elapsed = gd["max_elapsed"]
            baseline = gd["reg_end_margin"]  # Margin at end of regulation (2880)
            
            # Process each OT period
            ot_start = 2880
            while ot_start < max_elapsed:
                ot_end = min(ot_start + 300, max_elapsed)
                
                for rel_e in ot_elapsed_range:
                    actual_e = ot_start + rel_e
                    if actual_e <= ot_end and actual_e <= max_elapsed:
                        # Margin relative to regulation end
                        abs_margin = float(timeline[actual_e]) if actual_e in timeline.index else baseline
                        rel_margin = int(abs_margin - baseline)
                        
                        margin_hist[str(rel_e)][str(rel_margin)] += 1
                        if rel_margin > 0:
                            leading_count[str(rel_e)] += 1
                
                ot_start += 300  # Next OT period
        
        return dict(margin_hist), dict(leading_count)
    
    ot_hist_all, ot_leading_all = build_ot_hist(ot_all)
    ot_hist_vs_good, ot_leading_vs_good = build_ot_hist(ot_vs_good)
    ot_hist_vs_bad, ot_leading_vs_bad = build_ot_hist(ot_vs_bad)
    
    # -------------------------------------------------------------------------
    # Build lineup counts
    # -------------------------------------------------------------------------
    
    def build_lineup_counts(game_ids, is_clutch=False, is_ot=False):
        """Build lineup counts per elapsed time (individual player IDs)."""
        counts = defaultdict(lambda: defaultdict(int))
        game_lineups = lineups_df[lineups_df["game_id"].isin(game_ids)]
        
        for _, row in game_lineups.iterrows():
            e = row["elapsed"]
            
            if is_ot:
                if e <= 2880:
                    continue
                key = "OT"
            elif is_clutch:
                if e < CLUTCH_START or e > 2880:
                    continue
                key = str(e - CLUTCH_START)
            else:
                key = str(e)
            
            # Store INDIVIDUAL player IDs (not lineup strings)
            players = [
                row["player1_id"], row["player2_id"], row["player3_id"],
                row["player4_id"], row["player5_id"]
            ]
            for pid in players:
                counts[key][str(int(pid))] += 1
        
        return {k: dict(v) for k, v in counts.items()}
    
    lineup_counts_all = build_lineup_counts(all_game_ids)
    lineup_counts_vs_good = build_lineup_counts(games_vs_good)
    lineup_counts_vs_bad = build_lineup_counts(games_vs_bad)
    lineup_counts_clutch = build_lineup_counts(clutch_all, is_clutch=True)
    lineup_counts_clutch_vs_good = build_lineup_counts(clutch_vs_good, is_clutch=True)
    lineup_counts_clutch_vs_bad = build_lineup_counts(clutch_vs_bad, is_clutch=True)
    lineup_counts_ot = build_lineup_counts(ot_all, is_ot=True)
    lineup_counts_ot_vs_good = build_lineup_counts(ot_vs_good, is_ot=True)
    lineup_counts_ot_vs_bad = build_lineup_counts(ot_vs_bad, is_ot=True)
    
    # -------------------------------------------------------------------------
    # Compute max_lead_sum and min_margin_sum (RULE 5)
    # -------------------------------------------------------------------------
    
    def compute_lead_deficit_sums(game_ids):
        """Sum of max margins and min margins across games."""
        max_sum = sum(game_data[gid]["max_margin_reg"] for gid in game_ids)
        min_sum = sum(game_data[gid]["min_margin_reg"] for gid in game_ids)
        return float(max_sum), float(min_sum)
    
    max_lead_sum_all, min_margin_sum_all = compute_lead_deficit_sums(all_game_ids)
    max_lead_sum_vs_good, min_margin_sum_vs_good = compute_lead_deficit_sums(games_vs_good)
    max_lead_sum_vs_bad, min_margin_sum_vs_bad = compute_lead_deficit_sums(games_vs_bad)
    
    # -------------------------------------------------------------------------
    # Build threshold data
    # -------------------------------------------------------------------------
    
    threshold_games = []
    for gid in all_game_ids:
        gd = game_data[gid]
        timeline = gd["timeline"]
        reg_timeline = timeline[timeline.index <= 2880]
        
        time_at = {}
        for t in range(-25, 26):
            if t >= 0:
                time_at[str(t)] = int((reg_timeline >= t).sum())
            else:
                time_at[str(t)] = int((reg_timeline <= t).sum())
        
        threshold_games.append({
            "max": int(reg_timeline.max()),
            "min": int(reg_timeline.min()),
            "won": gd["won"],
            "time_at": time_at
        })
    
    # -------------------------------------------------------------------------
    # Build runs data
    # -------------------------------------------------------------------------
    
    run_windows = {"1min": 60, "3min": 180, "6min": 360, "quarter": 720, "half": 1440}
    runs_data = {}
    
    for name, window in run_windows.items():
        best_sum = 0.0
        worst_sum = 0.0
        max_best = 0.0  # Single game extreme (best)
        max_worst = 0.0  # Single game extreme (worst)
        
        for gid in all_game_ids:
            timeline = game_data[gid]["timeline"]
            max_e = min(2880, game_data[gid]["max_elapsed"])
            
            best_run = 0.0
            worst_run = 0.0
            
            for start in range(0, max_e - window + 1, 10):
                end = start + window
                if end <= max_e:
                    run = float(timeline[end] - timeline[start])
                    best_run = max(best_run, run)
                    worst_run = min(worst_run, run)
            
            best_sum += best_run
            worst_sum += worst_run
            
            # Track single game extremes
            if best_run > max_best:
                max_best = best_run
            if worst_run < max_worst:
                max_worst = worst_run
        
        runs_data[name] = {
            "best_sum": float(best_sum),
            "worst_sum": float(worst_sum),
            "max_best": float(max_best),
            "max_worst": float(max_worst),
            "game_count": len(all_game_ids)
        }
    
    # -------------------------------------------------------------------------
    # Build burst frequency data
    # -------------------------------------------------------------------------
    
    BURST_WINDOWS = {
        "1min": {"window": 60, "thresholds": list(range(3, 9))},      # +3 to +8
        "3min": {"window": 180, "thresholds": list(range(6, 16))},    # +6 to +15
        "6min": {"window": 360, "thresholds": list(range(10, 21))}    # +10 to +20
    }
    SCAN_STEP = 10
    
    def count_bursts_greedy(timeline, window, threshold, max_elapsed):
        generated = 0
        allowed = 0
        scan_end = min(2880, max_elapsed) - window
        
        i = 0
        while i <= scan_end:
            if i + window <= max_elapsed:
                start_val = timeline[i] if i in timeline.index else 0
                end_val = timeline[i + window] if (i + window) in timeline.index else start_val
                diff = end_val - start_val
                
                if diff >= threshold:
                    generated += 1
                    i += window
                elif diff <= -threshold:
                    allowed += 1
                    i += window
                else:
                    i += SCAN_STEP
            else:
                i += SCAN_STEP
        return generated, allowed
    
    burst_freq = {}
    for window_name, config in BURST_WINDOWS.items():
        burst_freq[window_name] = {}
        for thresh in config["thresholds"]:
            burst_freq[window_name][str(thresh)] = {"gen_sum": 0, "allowed_sum": 0}
    
    for gid in all_game_ids:
        timeline = game_data[gid]["timeline"]
        max_elapsed = game_data[gid]["max_elapsed"]
        
        for window_name, config in BURST_WINDOWS.items():
            window = config["window"]
            for thresh in config["thresholds"]:
                gen, allowed = count_bursts_greedy(timeline, window, thresh, max_elapsed)
                burst_freq[window_name][str(thresh)]["gen_sum"] += gen
                burst_freq[window_name][str(thresh)]["allowed_sum"] += allowed
    
    # -------------------------------------------------------------------------
    # Build lead changes data
    # -------------------------------------------------------------------------
    
    def count_lead_changes(timeline):
        prev_sign = 0
        lead_changes = 0
        for elapsed in sorted(timeline.index):
            margin = timeline[elapsed]
            if margin > 0:
                sign = 1
            elif margin < 0:
                sign = -1
            else:
                continue  # Tie, skip
            if prev_sign != 0 and sign != prev_sign:
                lead_changes += 1
            prev_sign = sign
        return lead_changes
    
    lead_changes_total = 0
    lead_changes_sum_sq = 0
    
    for gid in all_game_ids:
        timeline = game_data[gid]["timeline"]
        lc = count_lead_changes(timeline)
        lead_changes_total += lc
        lead_changes_sum_sq += lc * lc
    
    lead_changes_data = {
        "total": lead_changes_total,
        "sum_sq": lead_changes_sum_sq,
        "game_count": len(all_game_ids)
    }
    
    # -------------------------------------------------------------------------
    # Build garbage time data
    # -------------------------------------------------------------------------
    
    mpg_data = {}
    try:
        with open("player_mpg.json", "r") as f:
            mpg_data = json.load(f)
    except:
        pass
    
    garbage_instances = []
    for gid in all_game_ids:
        gd = game_data[gid]
        game_lineups = lineups_df[lineups_df["game_id"] == gid]
        
        in_garbage = False
        garbage_start = None
        
        for _, row in game_lineups.iterrows():
            e = row["elapsed"]
            if e < 2160 or e > 2880:
                continue
            
            lineup = [row["player1_id"], row["player2_id"], row["player3_id"],
                     row["player4_id"], row["player5_id"]]
            avg_mpg = np.mean([mpg_data.get(str(int(p)), 20) for p in lineup])
            
            timeline = gd["timeline"]
            margin = float(timeline[e]) if e in timeline.index else 0
            
            if not in_garbage:
                if abs(margin) >= 10 and avg_mpg < 15:
                    in_garbage = True
                    garbage_start = e
            else:
                if e >= 2760 and avg_mpg > 25:
                    duration = (e - garbage_start) / 60
                    diff = float(timeline[e] - timeline[garbage_start])
                    garbage_instances.append({
                        "game_id": gid, "won": gd["won"],
                        "start_min": garbage_start / 60,
                        "duration": duration, "diff": diff, "successful": False
                    })
                    in_garbage = False
        
        if in_garbage:
            end_e = min(2880, gd["max_elapsed"])
            duration = (end_e - garbage_start) / 60
            timeline = gd["timeline"]
            diff = float(timeline[end_e] - timeline[garbage_start])
            garbage_instances.append({
                "game_id": gid, "won": gd["won"],
                "start_min": garbage_start / 60,
                "duration": duration, "diff": diff, "successful": True
            })
    
    # -------------------------------------------------------------------------
    # Build comeback/blown lead data
    # -------------------------------------------------------------------------
    
    comeback_games = []
    comeback_deficit_sum = 0.0
    max_comeback_deficit = 0.0  # Most negative (largest deficit overcome)
    wins_without_trailing = 0
    
    blown_games = []
    blown_lead_sum = 0.0
    max_blown_lead = 0.0  # Most positive (largest lead squandered)
    losses_without_leading = 0
    
    for gid in all_game_ids:
        gd = game_data[gid]
        min_margin = gd["min_margin_reg"]
        max_margin = gd["max_margin_reg"]
        
        if gd["won"]:
            if min_margin < 0:
                # Comeback win
                comeback_games.append(gid)
                comeback_deficit_sum += min_margin
                if min_margin < max_comeback_deficit:
                    max_comeback_deficit = min_margin
            else:
                # Win without ever trailing
                wins_without_trailing += 1
        else:
            if max_margin > 0:
                # Blown lead loss
                blown_games.append(gid)
                blown_lead_sum += max_margin
                if max_margin > max_blown_lead:
                    max_blown_lead = max_margin
            else:
                # Loss without ever leading
                losses_without_leading += 1
    
    # -------------------------------------------------------------------------
    # Build period stats (per-period record, lead, deficit)
    # Includes regular periods, OT, and clutch
    # -------------------------------------------------------------------------
    
    # Period definitions: (start_elapsed, end_elapsed)
    period_defs = {
        "1": (0, 720),
        "2": (720, 1440),
        "3": (1440, 2160),
        "4": (2160, 2880),
        "1H": (0, 1440),
        "2H": (1440, 2880),
        "all": (0, 2880)  # For "all", we use final_margin which includes OT
    }
    
    # Initialize all periods including OT and clutch
    all_period_names = list(period_defs.keys()) + ["OT", "clutch"]
    period_stats = {p: {"wins": 0, "losses": 0, "ties": 0, "max_lead_sum": 0.0, "min_margin_sum": 0.0, "game_count": 0}
                    for p in all_period_names}
    
    for gid in all_game_ids:
        gd = game_data[gid]
        timeline = gd["timeline"]
        max_elapsed = gd["max_elapsed"]
        final_margin = gd["final_margin"]
        
        # Process regular periods
        for period_name, (start, end) in period_defs.items():
            if start > max_elapsed:
                continue
            
            actual_end = min(end, max_elapsed)
            
            # Baseline at period start
            baseline = 0 if start == 0 else float(timeline[start]) if start in timeline.index else 0
            
            # Period end margin (use final_margin for "all" to include OT)
            if period_name == "all":
                period_end_margin = final_margin
            else:
                period_end_margin = float(timeline[actual_end]) if actual_end in timeline.index else baseline
            
            # Period result
            period_diff = period_end_margin - baseline
            
            if period_diff > 0:
                period_stats[period_name]["wins"] += 1
            elif period_diff < 0:
                period_stats[period_name]["losses"] += 1
            else:
                period_stats[period_name]["ties"] += 1
            
            # Max lead and min margin during period (relative to baseline)
            period_timeline = timeline[(timeline.index >= start) & (timeline.index <= actual_end)]
            if len(period_timeline) > 0:
                relative_margins = period_timeline - baseline
                period_stats[period_name]["max_lead_sum"] += float(relative_margins.max())
                period_stats[period_name]["min_margin_sum"] += float(relative_margins.min())
            
            period_stats[period_name]["game_count"] += 1
        
        # Process OT (only for games that went to OT)
        if max_elapsed > 2880:
            baseline_ot = float(timeline[2880]) if 2880 in timeline.index else 0
            ot_end_margin = final_margin
            ot_diff = ot_end_margin - baseline_ot
            
            if ot_diff > 0:
                period_stats["OT"]["wins"] += 1
            elif ot_diff < 0:
                period_stats["OT"]["losses"] += 1
            else:
                period_stats["OT"]["ties"] += 1
            
            ot_timeline = timeline[timeline.index > 2880]
            if len(ot_timeline) > 0:
                relative_margins = ot_timeline - baseline_ot
                period_stats["OT"]["max_lead_sum"] += float(relative_margins.max())
                period_stats["OT"]["min_margin_sum"] += float(relative_margins.min())
            
            period_stats["OT"]["game_count"] += 1
        
        # Process clutch (only for clutch games: margin <= 5 at CLUTCH_START)
        if CLUTCH_START <= max_elapsed:
            margin_at_clutch = float(timeline[CLUTCH_START])
            if abs(margin_at_clutch) <= 5:
                baseline_clutch = margin_at_clutch
                clutch_end = min(2880, max_elapsed)
                
                # Clutch result uses final_margin (includes OT if played)
                clutch_diff = final_margin - baseline_clutch
                
                if clutch_diff > 0:
                    period_stats["clutch"]["wins"] += 1
                elif clutch_diff < 0:
                    period_stats["clutch"]["losses"] += 1
                else:
                    period_stats["clutch"]["ties"] += 1
                
                clutch_timeline = timeline[(timeline.index >= CLUTCH_START) & (timeline.index <= clutch_end)]
                if len(clutch_timeline) > 0:
                    relative_margins = clutch_timeline - baseline_clutch
                    period_stats["clutch"]["max_lead_sum"] += float(relative_margins.max())
                    period_stats["clutch"]["min_margin_sum"] += float(relative_margins.min())
                
                period_stats["clutch"]["game_count"] += 1
    
    # -------------------------------------------------------------------------
    # Build checkpoint data
    # -------------------------------------------------------------------------
    
    checkpoints = {}
    for cp in [6, 12, 18, 24, 30, 36, 42, 48]:
        cp_elapsed = cp * 60
        margin_sum = 0.0
        count = 0
        
        for gid in all_game_ids:
            timeline = game_data[gid]["timeline"]
            if cp_elapsed in timeline.index:
                margin_sum += float(timeline[cp_elapsed])
                count += 1
        
        checkpoints[str(cp)] = {"margin_sum": float(margin_sum), "game_count": count}
    
    # Add final margin (actual game ending, includes OT)
    final_margin_sum = sum(game_data[gid]["final_margin"] for gid in all_game_ids)
    checkpoints["final"] = {"margin_sum": float(final_margin_sum), "game_count": len(all_game_ids)}
    
    # -------------------------------------------------------------------------
    # Build win probability data (RULE 2: CURRENT margin, not max/min so far)
    # -------------------------------------------------------------------------
    
    win_prob = defaultdict(lambda: {"games": 0, "wins": 0})
    
    for gid in all_game_ids:
        gd = game_data[gid]
        timeline = gd["timeline"]
        won = gd["won"]  # RULE 3: Includes OT result
        
        for minute in range(0, 49):
            e = minute * 60
            if e > gd["max_elapsed"]:
                break
            
            # RULE 2: Get CURRENT margin at this exact minute (NOT max/min so far!)
            current_margin = int(timeline[e])
            
            # Clamp to display range
            current_margin = max(-25, min(25, current_margin))
            
            # For positive thresholds: count if CURRENT margin >= threshold
            for threshold in range(0, 26):
                if current_margin >= threshold:
                    key = f"{minute},{threshold}"
                    win_prob[key]["games"] += 1
                    if won:
                        win_prob[key]["wins"] += 1
            
            # For negative thresholds: count if CURRENT margin <= threshold
            for threshold in range(-1, -26, -1):
                if current_margin <= threshold:
                    key = f"{minute},{threshold}"
                    win_prob[key]["games"] += 1
                    if won:
                        win_prob[key]["wins"] += 1
    
    # -------------------------------------------------------------------------
    # Compute OT totals for OT contribution (RULE 4)
    # -------------------------------------------------------------------------
    
    total_ot_diff = float(sum(game_data[gid]["ot_diff"] for gid in all_game_ids))
    total_ot_diff_vs_good = float(sum(game_data[gid]["ot_diff"] for gid in games_vs_good))
    total_ot_diff_vs_bad = float(sum(game_data[gid]["ot_diff"] for gid in games_vs_bad))
    
    # -------------------------------------------------------------------------
    # Assemble return data (KEEP ORIGINAL FIELD NAMES)
    # -------------------------------------------------------------------------
    
    wins_all = sum(1 for gd in game_data.values() if gd["won"])
    losses_all = len(game_data) - wins_all
    wins_vs_good = sum(1 for gid in games_vs_good if game_data[gid]["won"])
    wins_vs_bad = sum(1 for gid in games_vs_bad if game_data[gid]["won"])
    wins_clutch = sum(1 for gid in clutch_all if game_data[gid]["won"])
    wins_clutch_vs_good = sum(1 for gid in clutch_vs_good if game_data[gid]["won"])
    wins_clutch_vs_bad = sum(1 for gid in clutch_vs_bad if game_data[gid]["won"])
    wins_ot = sum(1 for gid in ot_all if game_data[gid]["won"])
    wins_ot_vs_good = sum(1 for gid in ot_vs_good if game_data[gid]["won"])
    wins_ot_vs_bad = sum(1 for gid in ot_vs_bad if game_data[gid]["won"])
    
    return {
        "team_id": team_id,
        "game_count": len(all_game_ids),
        "wins": wins_all,
        "losses": losses_all,
        
        # Main margin histogram (absolute elapsed, absolute margins)
        "margin_hist": margin_hist_all,
        "leading_count": leading_all,
        "lineup_counts": lineup_counts_all,
        
        # Lead/deficit sums for avg calculation (RULE 5)
        "max_lead_sum": max_lead_sum_all,
        "min_margin_sum": min_margin_sum_all,
        
        # OT contribution data (RULE 4)
        "total_ot_diff": total_ot_diff,
        
        # vs_good filter
        "vs_good": {
            "game_ids": games_vs_good,
            "game_count": len(games_vs_good),
            "wins": wins_vs_good,
            "losses": len(games_vs_good) - wins_vs_good,
            "margin_hist": margin_hist_vs_good,
            "leading_count": leading_vs_good,
            "lineup_counts": lineup_counts_vs_good,
            "max_lead_sum": max_lead_sum_vs_good,
            "min_margin_sum": min_margin_sum_vs_good,
            "total_ot_diff": total_ot_diff_vs_good
        },
        
        # vs_bad filter
        "vs_bad": {
            "game_ids": games_vs_bad,
            "game_count": len(games_vs_bad),
            "wins": wins_vs_bad,
            "losses": len(games_vs_bad) - wins_vs_bad,
            "margin_hist": margin_hist_vs_bad,
            "leading_count": leading_vs_bad,
            "lineup_counts": lineup_counts_vs_bad,
            "max_lead_sum": max_lead_sum_vs_bad,
            "min_margin_sum": min_margin_sum_vs_bad,
            "total_ot_diff": total_ot_diff_vs_bad
        },
        
        # Clutch data
        "clutch": {
            "game_ids": clutch_all,
            "game_count": len(clutch_all),
            "wins": wins_clutch,
            "losses": len(clutch_all) - wins_clutch,
            "margin_hist": clutch_hist_all,
            "leading_count": clutch_leading_all,
            "lineup_counts": lineup_counts_clutch,
            "ot_games": sum(1 for gid in clutch_all if game_data[gid]["went_to_ot"]),
            "ot_diff_sum": float(sum(game_data[gid]["ot_diff"] for gid in clutch_all if game_data[gid]["went_to_ot"]))
        },
        
        "clutch_vs_good": {
            "game_ids": clutch_vs_good,
            "game_count": len(clutch_vs_good),
            "wins": wins_clutch_vs_good,
            "losses": len(clutch_vs_good) - wins_clutch_vs_good,
            "margin_hist": clutch_hist_vs_good,
            "leading_count": clutch_leading_vs_good,
            "lineup_counts": lineup_counts_clutch_vs_good,
            "ot_games": sum(1 for gid in clutch_vs_good if game_data[gid]["went_to_ot"]),
            "ot_diff_sum": float(sum(game_data[gid]["ot_diff"] for gid in clutch_vs_good if game_data[gid]["went_to_ot"]))
        },
        
        "clutch_vs_bad": {
            "game_ids": clutch_vs_bad,
            "game_count": len(clutch_vs_bad),
            "wins": wins_clutch_vs_bad,
            "losses": len(clutch_vs_bad) - wins_clutch_vs_bad,
            "margin_hist": clutch_hist_vs_bad,
            "leading_count": clutch_leading_vs_bad,
            "lineup_counts": lineup_counts_clutch_vs_bad,
            "ot_games": sum(1 for gid in clutch_vs_bad if game_data[gid]["went_to_ot"]),
            "ot_diff_sum": float(sum(game_data[gid]["ot_diff"] for gid in clutch_vs_bad if game_data[gid]["went_to_ot"]))
        },
        
        # OT data (NOW WITH margin_hist and leading_count for timeline!)
        "ot": {
            "game_count": len(ot_all),
            "wins": wins_ot,
            "losses": len(ot_all) - wins_ot,
            "margin_sum": float(sum(game_data[gid]["ot_diff"] for gid in ot_all)),
            "max_lead_sum": float(sum(game_data[gid]["max_margin_ot"] for gid in ot_all)),
            "min_margin_sum": float(sum(game_data[gid]["min_margin_ot"] for gid in ot_all)),
            "lineup_counts": lineup_counts_ot,
            "margin_hist": ot_hist_all,
            "leading_count": ot_leading_all
        },
        
        "ot_vs_good": {
            "game_count": len(ot_vs_good),
            "wins": wins_ot_vs_good,
            "losses": len(ot_vs_good) - wins_ot_vs_good,
            "margin_sum": float(sum(game_data[gid]["ot_diff"] for gid in ot_vs_good)),
            "max_lead_sum": float(sum(game_data[gid]["max_margin_ot"] for gid in ot_vs_good)),
            "min_margin_sum": float(sum(game_data[gid]["min_margin_ot"] for gid in ot_vs_good)),
            "lineup_counts": lineup_counts_ot_vs_good,
            "margin_hist": ot_hist_vs_good,
            "leading_count": ot_leading_vs_good
        },
        
        "ot_vs_bad": {
            "game_count": len(ot_vs_bad),
            "wins": wins_ot_vs_bad,
            "losses": len(ot_vs_bad) - wins_ot_vs_bad,
            "margin_sum": float(sum(game_data[gid]["ot_diff"] for gid in ot_vs_bad)),
            "max_lead_sum": float(sum(game_data[gid]["max_margin_ot"] for gid in ot_vs_bad)),
            "min_margin_sum": float(sum(game_data[gid]["min_margin_ot"] for gid in ot_vs_bad)),
            "lineup_counts": lineup_counts_ot_vs_bad,
            "margin_hist": ot_hist_vs_bad,
            "leading_count": ot_leading_vs_bad
        },
        
        # Other data
        "threshold_data": {"games": threshold_games},
        "runs": runs_data,
        "burst_freq": burst_freq,
        "lead_changes": lead_changes_data,
        "garbage_time": {"instances": garbage_instances},
        "comeback": {
            "games": comeback_games,
            "worst_deficit_sum": float(comeback_deficit_sum),
            "max_deficit": float(max_comeback_deficit),
            "wins_without_trailing": wins_without_trailing
        },
        "blown_lead": {
            "games": blown_games,
            "best_lead_sum": float(blown_lead_sum),
            "max_lead": float(max_blown_lead),
            "losses_without_leading": losses_without_leading
        },
        "period_stats": period_stats,
        "checkpoints": checkpoints,
        "win_prob": dict(win_prob)
    }


# =============================================================================
# GAME SHAPES COLLECTION
# =============================================================================

def collect_game_shapes(conn):
    """
    Collect per-game shape data for clustering.
    Returns list of game dicts with checkpoints, lead changes, etc.
    """
    TEAM_ID_TO_ABBREV = {v: k for k, v in TEAMS.items()}
    CHECKPOINTS = [6, 12, 18, 24, 30, 36, 42]  # 48 replaced by final
    
    def count_lead_changes_game(timeline):
        prev_sign = 0
        lc = 0
        for elapsed in sorted(timeline.index):
            margin = timeline[elapsed]
            if margin > 0:
                sign = 1
            elif margin < 0:
                sign = -1
            else:
                continue
            if prev_sign != 0 and sign != prev_sign:
                lc += 1
            prev_sign = sign
        return lc
    
    # Get all games
    games_df = pd.read_sql_query("SELECT * FROM games", conn)
    
    # Get all PBP
    pbp_df = pd.read_sql_query("""
        SELECT game_id, period, clock, score_home, score_away, home_team_id, away_team_id
        FROM pbp
        WHERE score_home IS NOT NULL
    """, conn)
    
    pbp_df["elapsed"] = pbp_df.apply(lambda r: to_elapsed(r["period"], r["clock"]), axis=1)
    pbp_df["margin"] = pbp_df["score_home"] - pbp_df["score_away"]
    
    game_shapes = []
    
    for _, game in games_df.iterrows():
        gid = game["game_id"]
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]
        
        home_abbrev = TEAM_ID_TO_ABBREV.get(home_id, "???")
        away_abbrev = TEAM_ID_TO_ABBREV.get(away_id, "???")
        
        g_pbp = pbp_df[pbp_df["game_id"] == gid]
        if len(g_pbp) == 0:
            continue
        
        g_dedup = g_pbp.groupby("elapsed").agg({
            "margin": "last",
            "score_home": "last",
            "score_away": "last"
        })
        
        max_elapsed = int(g_dedup.index.max())
        
        timeline = pd.Series(index=range(max_elapsed + 1), dtype=float)
        timeline[0] = 0
        for e in g_dedup.index:
            timeline[e] = g_dedup.loc[e, "margin"]
        timeline = timeline.ffill().fillna(0)
        
        # Checkpoints
        cp_values = []
        for cp in CHECKPOINTS:
            cp_elapsed = cp * 60
            if cp_elapsed <= max_elapsed:
                cp_values.append(float(timeline[cp_elapsed]))
            else:
                cp_values.append(0.0)
        
        final_margin = float(timeline.iloc[-1])
        cp_values.append(final_margin)
        
        # Final scores
        final_row = g_dedup.iloc[-1]
        home_score = int(final_row["score_home"])
        away_score = int(final_row["score_away"])
        home_won = home_score > away_score
        
        # Lead changes
        lc = count_lead_changes_game(timeline)
        
        # Max leads
        max_home_lead = float(timeline.max())
        max_away_lead = float(-timeline.min())
        
        game_shapes.append({
            "gid": gid,
            "home": home_abbrev,
            "away": away_abbrev,
            "date": game["game_date"],
            "cp": [round(x, 1) for x in cp_values],
            "home_won": home_won,
            "score": f"{home_score}-{away_score}",
            "lc": lc,
            "max_home": round(max_home_lead, 0),
            "max_away": round(max_away_lead, 0)
        })
    
    return game_shapes


# =============================================================================
# TIMEOUT ANALYSIS COLLECTION
# =============================================================================

def collect_timeout_analysis(conn, teams_data):
    """
    Compute timeout analysis curves for each team.
    Shows avg margin trajectory around timeouts (-120s to +120s).
    """
    WINDOW = 120  # seconds before/after
    STEP = 10     # interval
    
    # Check if timeouts table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeouts'")
    if cursor.fetchone() is None:
        print("  No timeouts table found, skipping")
        return {}
    
    # Load timeouts (full only, not challenges)
    timeouts_df = pd.read_sql("""
        SELECT t.game_id, t.elapsed, t.team_id, g.home_team_id, g.away_team_id
        FROM timeouts t
        JOIN games g ON t.game_id = g.game_id
        WHERE t.timeout_type = 'full'
    """, conn)
    
    if len(timeouts_df) == 0:
        print("  No timeout data found, skipping")
        return {}
    
    print(f"  Loaded {len(timeouts_df)} full timeouts")
    
    # Load PBP for margin curves
    pbp_df = pd.read_sql("""
        SELECT game_id, period, clock, score_home, score_away, home_team_id
        FROM pbp WHERE score_home IS NOT NULL
    """, conn)
    pbp_df["elapsed"] = pbp_df.apply(lambda r: to_elapsed(r["period"], r["clock"]), axis=1)
    pbp_df["margin"] = pbp_df["score_home"] - pbp_df["score_away"]
    
    # Build game timelines
    game_timelines = {}
    for gid, g in pbp_df.groupby("game_id"):
        g_dedup = g.groupby("elapsed")["margin"].last()
        max_e = int(g_dedup.index.max())
        timeline = pd.Series(index=range(max_e + 1), dtype=float)
        timeline[0] = 0
        for e, m in g_dedup.items():
            timeline[e] = m
        timeline = timeline.ffill().fillna(0)
        game_timelines[gid] = timeline
    
    def compute_curve(to_df, team_id):
        """Compute avg margin curve around timeouts from team's perspective."""
        time_points = list(range(-WINDOW, WINDOW + 1, STEP))
        sums = {t: 0.0 for t in time_points}
        counts = {t: 0 for t in time_points}
        
        for _, row in to_df.iterrows():
            gid = row["game_id"]
            to_elapsed_val = row["elapsed"]
            
            if gid not in game_timelines:
                continue
            
            timeline = game_timelines[gid]
            max_e = len(timeline) - 1
            
            to_idx = min(int(to_elapsed_val), max_e)
            margin_at_to = timeline[to_idx]
            
            is_home = (row["home_team_id"] == team_id)
            sign = 1 if is_home else -1
            margin_at_to_adj = margin_at_to * sign
            
            for t in time_points:
                idx = int(to_elapsed_val + t)
                if 0 <= idx <= max_e:
                    margin_at_t = timeline[idx] * sign
                    
                    if t < 0:
                        diff = margin_at_to_adj - margin_at_t
                    elif t > 0:
                        diff = margin_at_t - margin_at_to_adj
                    else:
                        diff = 0
                    
                    sums[t] += diff
                    counts[t] += 1
        
        curve = []
        for t in time_points:
            avg = sums[t] / counts[t] if counts[t] > 0 else 0
            curve.append(round(avg, 2))
        
        return {"count": len(to_df), "curve": curve}
    
    # Process each team
    result = {}
    for team_abbrev, team_id in TEAMS.items():
        my_to = timeouts_df[timeouts_df["team_id"] == team_id]
        opp_to = timeouts_df[
            (timeouts_df["team_id"] != team_id) & 
            ((timeouts_df["home_team_id"] == team_id) | (timeouts_df["away_team_id"] == team_id))
        ]
        all_to = timeouts_df[
            (timeouts_df["home_team_id"] == team_id) | (timeouts_df["away_team_id"] == team_id)
        ]
        
        my_curve = compute_curve(my_to, team_id)
        opp_curve = compute_curve(opp_to, team_id)
        all_curve = compute_curve(all_to, team_id)
        
        result[team_abbrev] = {
            "my_to": my_curve,
            "opp_to": opp_curve,
            "all_to": all_curve,
            "time_points": list(range(-WINDOW, WINDOW + 1, STEP))
        }
    
    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("UPDATE RAW DATA")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    conn = sqlite3.connect(DB_PATH)
    
    print("Loading player names...")
    player_names = get_player_names(conn)
    print(f"Loaded {len(player_names)} players")
    
    print("\nCalculating team records...")
    team_records = {}
    
    for team_abbrev, team_id in TEAMS.items():
        df = pd.read_sql_query("""
            SELECT p.game_id, p.period, p.clock, p.score_home, p.score_away,
                   g.home_team_id, g.away_team_id
            FROM pbp p
            JOIN games g ON p.game_id = g.game_id
            WHERE (g.home_team_id = ? OR g.away_team_id = ?)
              AND p.score_home IS NOT NULL
        """, conn, params=(team_id, team_id))
        
        if len(df) == 0:
            team_records[team_id] = {"wins": 0, "losses": 0}
            continue
        
        df["elapsed"] = df.apply(lambda r: to_elapsed(r["period"], r["clock"]), axis=1)
        df["margin"] = df.apply(
            lambda r: (r["score_home"] - r["score_away"]) if r["home_team_id"] == team_id 
                      else (r["score_away"] - r["score_home"]),
            axis=1
        )
        
        wins = losses = 0
        for gid, g in df.groupby("game_id"):
            final_margin = g.groupby("elapsed")["margin"].last().iloc[-1]
            if final_margin > 0:
                wins += 1
            elif final_margin < 0:
                losses += 1
        
        team_records[team_id] = {"wins": wins, "losses": losses}
    
    print(f"Records calculated for {len(team_records)} teams")
    
    print("\nCollecting team data...")
    teams_data = {}
    
    for i, (team_abbrev, team_id) in enumerate(TEAMS.items()):
        print(f"  [{i+1}/30] {team_abbrev}...", end=" ", flush=True)
        team_data = collect_team_data(conn, team_abbrev, team_id, team_records, player_names)
        if team_data:
            teams_data[team_abbrev] = team_data
            print(f"done ({team_data['game_count']} games)")
        else:
            print("no data")
    
    conn.close()
    
    # Collect game shapes for clustering
    print("\nCollecting game shapes...")
    conn2 = sqlite3.connect(DB_PATH)
    game_shapes = collect_game_shapes(conn2)
    conn2.close()
    print(f"Collected {len(game_shapes)} game shapes")
    
    # Collect timeout analysis
    print("\nCollecting timeout analysis...")
    conn3 = sqlite3.connect(DB_PATH)
    timeout_analysis = collect_timeout_analysis(conn3, teams_data)
    conn3.close()
    
    # Add timeout analysis to each team's data
    for team_abbrev, ta in timeout_analysis.items():
        if team_abbrev in teams_data:
            teams_data[team_abbrev]["timeout_analysis"] = ta
    
    raw_state = {
        "meta": {
            "last_updated": datetime.now().isoformat(),
            "total_games_processed": sum(t["game_count"] for t in teams_data.values()) // 2
        },
        "team_records": {str(k): v for k, v in team_records.items()},
        "player_names": {str(k): v for k, v in player_names.items()},
        "teams": teams_data,
        "game_shapes": game_shapes
    }
    
    print(f"\nSaving {RAW_STATE_PATH}...")
    with open(RAW_STATE_PATH, "w") as f:
        json.dump(raw_state, f)
    
    print(f"Saved raw state ({len(teams_data)} teams)")
    print("\nDone!")


if __name__ == "__main__":
    main()
