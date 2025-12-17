"""
================================================================================
COMPUTE PLAYER STATS
================================================================================

PURPOSE:
    Computes derived player statistics from raw box scores including:
    - Basic averages (per game and per minute)
    - Advanced shooting metrics
    - Max/min performances
    - Risk-adjusted stats (Sortino-style)
    - Custom metrics: IPM (Involvement Per Minute), Ethical Hoops
    - Achievement counts (double-doubles, triple-doubles, near triple-doubles)

INPUT:
    player_box_scores.db (from fetch_player_box_scores.py)
        - players: player_id, player_name, team_abbreviation, etc.
        - box_scores: one row per player per game with all stats
        - player_tracking: hustle stats and tracking data (touches, deflections, etc.)
                          from fetch_player_tracking.py

OUTPUT:
    player_computed_stats.json
        - One entry per player with all computed statistics
        - Ready for filtering UI and display

================================================================================
FORMULA DOCUMENTATION
================================================================================

1. BASIC AVERAGES
-----------------
    PPG = SUM(PTS) / GP
    RPG = SUM(REB) / GP
    APG = SUM(AST) / GP
    (etc. for all counting stats)

2. PER-MINUTE STATS
-------------------
    PTS_PER_MIN = SUM(PTS) / SUM(MIN)
    REB_PER_MIN = SUM(REB) / SUM(MIN)
    (etc.)

3. ADVANCED SHOOTING
--------------------
    FG_PCT = SUM(FGM) / SUM(FGA)
    
    FG3_PCT = SUM(FG3M) / SUM(FG3A)
    
    FT_PCT = SUM(FTM) / SUM(FTA)
    
    TS_PCT (True Shooting %) = PTS / (2 × (FGA + 0.44 × FTA))
        - Accounts for 3-pointers and free throws
        - 0.44 factor estimates possessions used by FTs
    
    EFG_PCT (Effective FG%) = (FGM + 0.5 × FG3M) / FGA
        - Weights 3-pointers at 1.5× value of 2-pointers
    
    FG3A_RATE = FG3A / FGA
        - Proportion of shots from 3-point range
    
    FTA_RATE = FTA / FGA
        - Free throw attempts per field goal attempt

4. RISK-ADJUSTED STATS (Sortino-Style)
--------------------------------------
    Downside Deviation = sqrt(mean((min(X - threshold, 0))²))
        - Only considers games BELOW threshold
        - Threshold = player's mean for that stat
    
    Risk-Adjusted Stat = Mean - Downside Deviation
        - Penalizes inconsistency on the downside
        - Does NOT penalize upside variance (explosions are good)
    
    Example:
        Player A: [20, 22, 18, 21, 19] → mean=20, low variance → high risk-adj
        Player B: [10, 15, 20, 25, 30] → mean=20, high downside → lower risk-adj
        Player C: [20, 20, 20, 20, 70] → mean=30, explosion helps → high risk-adj

5. IPM (Involvement Per Minute)
-------------------------------
    Measures total "touches" or "involvement" in the game per minute played.
    Combines box score stats with Second Spectrum tracking data.
    
    BOX SCORE COMPONENT:
    
    FG_MISS = FGA - FGM
    FT_MISS = FTA - FTM
    
    Any IPM (everything counts as involvement, even mistakes):
    
        Any IPM_box = (0.5×PTS + 0.5×FG_MISS + 0.25×FT_MISS 
                       + REB + AST + STL + BLK + TOV + 0.5×PF) / MIN
    
    Net IPM (good stuff positive, bad stuff negative - alternative to PER/LEBRON/EPM):
    
        Net IPM_box = (0.5×PTS - 0.5×FG_MISS - 0.25×FT_MISS 
                       + REB + AST + STL + BLK - TOV - 0.5×PF) / MIN
    
    TRACKING COMPONENT (per game, converted to per minute):
    
        Tracking IPM = (0.05×TOUCHES + 0.5×DEFLECTIONS + 0.1×CONTESTED_SHOTS
                        + 0.5×SCREEN_ASSISTS + 0.5×LOOSE_BALLS + 0.5×SECONDARY_AST) / MPG
    
        Calibrated so avg top-100 player gets ~6 per game from tracking (~3 from touches)
    
    FINAL IPM = (IPM_box + Tracking_IPM) × minutes_scale
    
    Interpretation:
        - High Any IPM = high-usage player (ball-dominant, active)
        - High Net IPM = efficient high-usage player (doing the right things)
        - Gap between Any and Net = inefficiency (misses, turnovers, fouls)
        - Net IPM is a transparent all-in-one metric: add good stuff, subtract bad stuff
    
    MINUTES ADJUSTMENT (Logarithmic with Power):
    
        Bench players with few minutes can have inflated IPM due to small
        sample size. We apply a soft penalty based on minutes played:
        
        scale = (log(1 + MPG) / log(1 + MPG_max))^p
        
        IPM_adj = IPM_raw × scale
        
        Where:
            - MPG = player's minutes per game
            - MPG_max = highest MPG in league (reference player)
            - p = 1.5 (harshness parameter, higher = harsher penalty)
        
        Example (MPG_max = 37.3):
            - 6.8 MPG:  scale = (log(7.8)/log(38.3))^1.5 = 0.56^1.5 = 0.42
            - 35.0 MPG: scale = (log(36)/log(38.3))^1.5 = 0.98^1.5 = 0.97
        
        This ensures low-minute players don't dominate the leaderboard
        while barely affecting high-minute starters.

6. ETHICAL HOOPS
----------------
    Inspired by Jarrett Allen's "ethical basketball" quote.
    Rewards real basketball, penalizes foul-baiting and free throw hunting.
    
    BOX SCORE COMPONENT:
    
    Ethical_box = PTS - 0.5×FTM - 1.5×FTA
                  + 0.9×AST 
                  + 0.9×OREB + 0.7×DREB
                  + 1.5×BLK + 1.5×STL
                  - 1.2×PF
    
    TRACKING COMPONENT (hustle stats):
    
    Ethical_tracking = 0.4×DEFLECTIONS + 0.1×CONTESTED_SHOTS
                       + 0.5×SCREEN_ASSISTS + 0.4×BOX_OUTS
                       + 1.5×CHARGES_DRAWN
    
    Calibrated so avg top-100 player gets ~2.2 per game from tracking
    
    FINAL Ethical = Ethical_box + Ethical_tracking
    
    Breakdown:
        Box Score:
        - PTS: Full credit for points scored
        - FTM penalty (-0.5): Made FTs still needed ref's whistle
        - FTA penalty (-1.5): Attempting FTs = hunting fouls
        - AST (+0.9): Team play bonus (moderated to prevent PG dominance)
        - OREB (+0.9): Hustle play
        - DREB (+0.7): Expected, less credit
        - BLK (+1.5): Rim protection, clean defense
        - STL (+1.5): Active hands, not flopping (same as blocks)
        - PF (-1.2): Undisciplined play (harsher penalty)
        
        Tracking (hustle):
        - DEFLECTIONS (+0.4): Active hands on defense
        - CONTESTED_SHOTS (+0.1): Effort defense
        - SCREEN_ASSISTS (+0.5): Selfless off-ball work
        - BOX_OUTS (+0.4): Doing the dirty work
        - CHARGES_DRAWN (+1.5): Taking contact (max = BLK weight)
    
    Example outcomes:
        - Pure shooter (0 FTA): Ethical ≈ PTS + bonuses
        - Foul merchant (high FTA): Ethical << PTS
        - Rim protector (high BLK, OREB): Big ethical bonus
        - Glue guy (screens, box outs): Gets recognition from tracking

7. ACHIEVEMENT COUNTS
---------------------
    Double-Double (DD2): Built-in flag from NBA API
        - 10+ in two of: PTS, REB, AST, STL, BLK
    
    Triple-Double (TD3): Built-in flag from NBA API
        - 10+ in three of: PTS, REB, AST, STL, BLK
    
    Near Triple-Double: Custom definition
        - At least 2 stats >= 10
        - At least 3 stats >= 9
        - NOT a triple-double (td3 = 0)
        - Example: 25 PTS, 10 REB, 9 AST = near triple-double
    
    Other achievements:
        - games_30plus: PTS >= 30
        - games_40plus: PTS >= 40
        - games_20_10: PTS >= 20 AND (REB >= 10 OR AST >= 10)
        - games_20_10_5: PTS >= 20 AND REB >= 10 AND AST >= 5

================================================================================
"""

import sqlite3
import json
import numpy as np
from datetime import datetime
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "player_box_scores.db"
OUTPUT_PATH = "player_computed_stats.json"

# Minimum games played to include player
MIN_GAMES = 1

# Minimum minutes per game to include (filters DNPs)
MIN_MPG = 5.0

# =============================================================================
# IPM WEIGHTS
# =============================================================================

IPM_WEIGHTS = {
    'pts': 0.5,
    'fg_miss_any': 0.5,   # For Any IPM (involvement)
    'fg_miss_net': -0.5,  # For Net IPM (efficiency)
    'ft_miss_any': 0.25,  # For Any IPM
    'ft_miss_net': -0.25, # For Net IPM
    'reb': 1.0,
    'ast': 1.0,
    'stl': 1.0,
    'blk': 1.0,
    'tov_any': 1.0,      # For Any IPM
    'tov_net': -1.0,     # For Net IPM
    'pf_any': 0.5,       # For Any IPM
    'pf_net': -0.5,      # For Net IPM
}

# IPM Minutes Adjustment
IPM_ADJUSTMENT_POWER = 1.5  # Harshness of penalty for low-minute players

# =============================================================================
# ETHICAL HOOPS WEIGHTS
# =============================================================================

ETHICAL_WEIGHTS = {
    'pts': 1.0,
    'ftm': -0.5,
    'fta': -1.5,
    'ast': 0.9,
    'oreb': 0.9,
    'dreb': 0.7,
    'blk': 1.5,
    'stl': 1.5,
    'pf': -1.2,
}

# =============================================================================
# TRACKING WEIGHTS (from player_tracking table - hustle/Second Spectrum data)
# =============================================================================

# These are per-game stats. Weights calibrated so avg top-100 player gets:
# - IPM tracking contribution: ~6 per game (~3 from touches, ~3 from hustle)
# - Ethical tracking contribution: ~4 per game

TRACKING_WEIGHTS_IPM = {
    'touches': 0.05,                   # 63 avg × 0.05 = 3.15
    'deflections': 0.5,                # 2.3 avg × 0.5 = 1.15
    'contested_shots': 0.1,            # 5.0 avg × 0.1 = 0.50
    'screen_assists': 0.5,             # 0.88 avg × 0.5 = 0.44
    'loose_balls_recovered': 0.5,      # 0.69 avg × 0.5 = 0.35
    'secondary_ast': 0.5,              # 0.58 avg × 0.5 = 0.29
}
# Total: ~5.88 per game for avg top-100 player

TRACKING_WEIGHTS_ETHICAL = {
    'deflections': 0.4,                # 2.3 avg × 0.4 = 0.92
    'contested_shots': 0.1,            # 5.0 avg × 0.1 = 0.50
    'screen_assists': 0.5,             # 0.88 avg × 0.5 = 0.44
    'box_outs': 0.4,                   # 0.76 avg × 0.4 = 0.30
    'charges_drawn': 1.5,              # 0.05 avg × 1.5 = 0.08
}
# Total: ~2.24 per game for avg top-100 player

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def safe_divide(numerator, denominator, default=0.0):
    """Safe division, returns default if denominator is 0."""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def load_tracking_data(conn):
    """
    Load tracking stats from player_tracking table.
    Returns dict of player_id -> tracking stats.
    """
    try:
        cursor = conn.execute("""
            SELECT 
                player_id, touches, deflections, contested_shots,
                screen_assists, loose_balls_recovered, box_outs,
                charges_drawn, secondary_ast
            FROM player_tracking
        """)
        
        tracking = {}
        for row in cursor.fetchall():
            tracking[row[0]] = {
                'touches': row[1] or 0,
                'deflections': row[2] or 0,
                'contested_shots': row[3] or 0,
                'screen_assists': row[4] or 0,
                'loose_balls_recovered': row[5] or 0,
                'box_outs': row[6] or 0,
                'charges_drawn': row[7] or 0,
                'secondary_ast': row[8] or 0,
            }
        
        print(f"Loaded tracking data for {len(tracking)} players")
        return tracking
    
    except Exception as e:
        print(f"Warning: Could not load tracking data: {e}")
        return {}


def compute_tracking_ipm_contribution(tracking_stats, mpg):
    """
    Compute tracking contribution to IPM.
    
    Args:
        tracking_stats: Dict with per-game tracking stats
        mpg: Minutes per game (to convert to per-minute)
    
    Returns:
        Per-minute tracking contribution
    """
    if not tracking_stats or mpg <= 0:
        return 0
    
    per_game = (
        TRACKING_WEIGHTS_IPM['touches'] * tracking_stats.get('touches', 0) +
        TRACKING_WEIGHTS_IPM['deflections'] * tracking_stats.get('deflections', 0) +
        TRACKING_WEIGHTS_IPM['contested_shots'] * tracking_stats.get('contested_shots', 0) +
        TRACKING_WEIGHTS_IPM['screen_assists'] * tracking_stats.get('screen_assists', 0) +
        TRACKING_WEIGHTS_IPM['loose_balls_recovered'] * tracking_stats.get('loose_balls_recovered', 0) +
        TRACKING_WEIGHTS_IPM['secondary_ast'] * tracking_stats.get('secondary_ast', 0)
    )
    
    # Convert to per-minute
    return per_game / mpg


def compute_tracking_ethical_contribution(tracking_stats):
    """
    Compute tracking contribution to Ethical Hoops.
    
    Args:
        tracking_stats: Dict with per-game tracking stats
    
    Returns:
        Per-game tracking contribution
    """
    if not tracking_stats:
        return 0
    
    return (
        TRACKING_WEIGHTS_ETHICAL['deflections'] * tracking_stats.get('deflections', 0) +
        TRACKING_WEIGHTS_ETHICAL['contested_shots'] * tracking_stats.get('contested_shots', 0) +
        TRACKING_WEIGHTS_ETHICAL['screen_assists'] * tracking_stats.get('screen_assists', 0) +
        TRACKING_WEIGHTS_ETHICAL['box_outs'] * tracking_stats.get('box_outs', 0) +
        TRACKING_WEIGHTS_ETHICAL['charges_drawn'] * tracking_stats.get('charges_drawn', 0)
    )


def downside_deviation(values, threshold=None):
    """
    Compute downside deviation (Sortino-style).
    Only penalizes values below threshold.
    
    Args:
        values: List of values
        threshold: Threshold for downside (default: mean of values)
    
    Returns:
        Downside deviation (always >= 0)
    """
    if not values or len(values) < 2:
        return 0.0
    
    arr = np.array(values)
    if threshold is None:
        threshold = np.mean(arr)
    
    # Only consider downside (below threshold)
    downside = np.minimum(arr - threshold, 0)
    downside_sq = downside ** 2
    
    return np.sqrt(np.mean(downside_sq))


def compute_ipm_game(row, mode='any'):
    """
    Compute IPM for a single game.
    
    Args:
        row: Dict with game stats
        mode: 'any' or 'net'
    
    Returns:
        IPM value (or None if no minutes)
    """
    minutes = row.get('min', 0)
    if minutes <= 0:
        return None
    
    pts = row.get('pts', 0)
    fgm = row.get('fgm', 0)
    fga = row.get('fga', 0)
    ftm = row.get('ftm', 0)
    fta = row.get('fta', 0)
    reb = row.get('reb', 0)
    ast = row.get('ast', 0)
    stl = row.get('stl', 0)
    blk = row.get('blk', 0)
    tov = row.get('tov', 0)
    pf = row.get('pf', 0)
    
    fg_miss = fga - fgm
    ft_miss = fta - ftm
    
    # Base involvement (always positive)
    involvement = (
        IPM_WEIGHTS['pts'] * pts +
        IPM_WEIGHTS['reb'] * reb +
        IPM_WEIGHTS['ast'] * ast +
        IPM_WEIGHTS['stl'] * stl +
        IPM_WEIGHTS['blk'] * blk
    )
    
    if mode == 'any':
        # Any IPM: everything counts as involvement (even mistakes)
        involvement += IPM_WEIGHTS['fg_miss_any'] * fg_miss
        involvement += IPM_WEIGHTS['ft_miss_any'] * ft_miss
        involvement += IPM_WEIGHTS['tov_any'] * tov
        involvement += IPM_WEIGHTS['pf_any'] * pf
    else:  # net
        # Net IPM: good stuff positive, bad stuff negative
        involvement += IPM_WEIGHTS['fg_miss_net'] * fg_miss
        involvement += IPM_WEIGHTS['ft_miss_net'] * ft_miss
        involvement += IPM_WEIGHTS['tov_net'] * tov
        involvement += IPM_WEIGHTS['pf_net'] * pf
    
    return involvement / minutes


def compute_ethical_game(row):
    """
    Compute Ethical Hoops score for a single game.
    
    Args:
        row: Dict with game stats
    
    Returns:
        Ethical Hoops score
    """
    pts = row.get('pts', 0)
    ftm = row.get('ftm', 0)
    fta = row.get('fta', 0)
    ast = row.get('ast', 0)
    oreb = row.get('oreb', 0)
    dreb = row.get('dreb', 0)
    blk = row.get('blk', 0)
    stl = row.get('stl', 0)
    pf = row.get('pf', 0)
    
    ethical = (
        ETHICAL_WEIGHTS['pts'] * pts +
        ETHICAL_WEIGHTS['ftm'] * ftm +
        ETHICAL_WEIGHTS['fta'] * fta +
        ETHICAL_WEIGHTS['ast'] * ast +
        ETHICAL_WEIGHTS['oreb'] * oreb +
        ETHICAL_WEIGHTS['dreb'] * dreb +
        ETHICAL_WEIGHTS['blk'] * blk +
        ETHICAL_WEIGHTS['stl'] * stl +
        ETHICAL_WEIGHTS['pf'] * pf
    )
    
    return ethical


def is_near_triple_double(row):
    """
    Check if game is a near triple-double.
    
    Definition:
        - At least 2 stats >= 10
        - At least 3 stats >= 9
        - NOT a triple-double (td3 = 0)
    
    Args:
        row: Dict with game stats
    
    Returns:
        True if near triple-double
    """
    if row.get('td3', 0) == 1:
        return False
    
    stats = [
        row.get('pts', 0),
        row.get('reb', 0),
        row.get('ast', 0),
        row.get('stl', 0),
        row.get('blk', 0),
    ]
    
    at_least_10 = sum(1 for s in stats if s >= 10)
    at_least_9 = sum(1 for s in stats if s >= 9)
    
    return at_least_10 >= 2 and at_least_9 >= 3


# =============================================================================
# MAIN COMPUTATION
# =============================================================================

def compute_player_stats(conn):
    """
    Compute all statistics for all players.
    
    Args:
        conn: SQLite connection to player_box_scores.db
    
    Returns:
        Dict of player_id -> computed stats
    """
    print("Loading box scores...")
    
    # Load all box scores
    cursor = conn.execute("""
        SELECT 
            b.player_id, b.game_id, b.game_date, b.team_abbreviation,
            b.matchup, b.wl, b.min,
            b.pts, b.fgm, b.fga, b.fg3m, b.fg3a, b.ftm, b.fta,
            b.oreb, b.dreb, b.reb, b.ast, b.tov, b.stl, b.blk, b.blka,
            b.pf, b.pfd, b.plus_minus, b.dd2, b.td3,
            p.player_name, p.team_abbreviation as current_team,
            p.technical_fouls, p.flagrant_fouls
        FROM box_scores b
        JOIN players p ON b.player_id = p.player_id
        ORDER BY b.player_id, b.game_date
    """)
    
    columns = [desc[0] for desc in cursor.description]
    
    # Group by player
    player_games = defaultdict(list)
    for row in cursor.fetchall():
        row_dict = dict(zip(columns, row))
        player_games[row_dict['player_id']].append(row_dict)
    
    print(f"Loaded {sum(len(g) for g in player_games.values())} box scores for {len(player_games)} players")
    
    # Load tracking data (hustle stats, touches, etc.)
    tracking_data = load_tracking_data(conn)
    
    # Compute stats for each player
    results = {}
    
    for player_id, games in player_games.items():
        if len(games) < MIN_GAMES:
            continue
        
        # Get player info from most recent game
        latest = games[-1]
        player_name = latest['player_name']
        team = latest['current_team']
        
        # Filter out DNPs (0 minutes)
        games_played = [g for g in games if g.get('min', 0) > 0]
        gp = len(games_played)
        
        if gp < MIN_GAMES:
            continue
        
        # Check minimum MPG
        total_min = sum(g.get('min', 0) for g in games_played)
        mpg = total_min / gp if gp > 0 else 0
        
        if mpg < MIN_MPG:
            continue
        
        # ---------------------------------------------------------------------
        # TOTALS
        # ---------------------------------------------------------------------
        totals = {
            'min': sum(g.get('min', 0) for g in games_played),
            'pts': sum(g.get('pts', 0) for g in games_played),
            'fgm': sum(g.get('fgm', 0) for g in games_played),
            'fga': sum(g.get('fga', 0) for g in games_played),
            'fg3m': sum(g.get('fg3m', 0) for g in games_played),
            'fg3a': sum(g.get('fg3a', 0) for g in games_played),
            'ftm': sum(g.get('ftm', 0) for g in games_played),
            'fta': sum(g.get('fta', 0) for g in games_played),
            'oreb': sum(g.get('oreb', 0) for g in games_played),
            'dreb': sum(g.get('dreb', 0) for g in games_played),
            'reb': sum(g.get('reb', 0) for g in games_played),
            'ast': sum(g.get('ast', 0) for g in games_played),
            'tov': sum(g.get('tov', 0) for g in games_played),
            'stl': sum(g.get('stl', 0) for g in games_played),
            'blk': sum(g.get('blk', 0) for g in games_played),
            'blka': sum(g.get('blka', 0) for g in games_played),
            'pf': sum(g.get('pf', 0) for g in games_played),
            'pfd': sum(g.get('pfd', 0) for g in games_played),
            'plus_minus': sum(g.get('plus_minus', 0) for g in games_played),
        }
        
        # ---------------------------------------------------------------------
        # BASIC AVERAGES (per game)
        # ---------------------------------------------------------------------
        avg = {
            'ppg': round(totals['pts'] / gp, 1),
            'rpg': round(totals['reb'] / gp, 1),
            'apg': round(totals['ast'] / gp, 1),
            'spg': round(totals['stl'] / gp, 1),
            'bpg': round(totals['blk'] / gp, 1),
            'topg': round(totals['tov'] / gp, 1),
            'pfpg': round(totals['pf'] / gp, 1),
            'mpg': round(totals['min'] / gp, 1),
            'orebpg': round(totals['oreb'] / gp, 1),
            'drebpg': round(totals['dreb'] / gp, 1),
            'fgmpg': round(totals['fgm'] / gp, 1),
            'fgapg': round(totals['fga'] / gp, 1),
            'fg3mpg': round(totals['fg3m'] / gp, 1),
            'fg3apg': round(totals['fg3a'] / gp, 1),
            'ftmpg': round(totals['ftm'] / gp, 1),
            'ftapg': round(totals['fta'] / gp, 1),
            'pfdpg': round(totals['pfd'] / gp, 1),
            'plus_minus_pg': round(totals['plus_minus'] / gp, 1),
        }
        
        # ---------------------------------------------------------------------
        # PER-MINUTE STATS
        # ---------------------------------------------------------------------
        per_min = {}
        if totals['min'] > 0:
            per_min = {
                'pts_per_min': round(totals['pts'] / totals['min'], 3),
                'reb_per_min': round(totals['reb'] / totals['min'], 3),
                'ast_per_min': round(totals['ast'] / totals['min'], 3),
                'stl_per_min': round(totals['stl'] / totals['min'], 3),
                'blk_per_min': round(totals['blk'] / totals['min'], 3),
                'tov_per_min': round(totals['tov'] / totals['min'], 3),
            }
        
        # ---------------------------------------------------------------------
        # ADVANCED SHOOTING
        # ---------------------------------------------------------------------
        shooting = {
            'fg_pct': round(safe_divide(totals['fgm'], totals['fga']) * 100, 1),
            'fg3_pct': round(safe_divide(totals['fg3m'], totals['fg3a']) * 100, 1),
            'ft_pct': round(safe_divide(totals['ftm'], totals['fta']) * 100, 1),
            'ts_pct': round(safe_divide(
                totals['pts'],
                2 * (totals['fga'] + 0.44 * totals['fta'])
            ) * 100, 1),
            'efg_pct': round(safe_divide(
                totals['fgm'] + 0.5 * totals['fg3m'],
                totals['fga']
            ) * 100, 1),
            'fg3a_rate': round(safe_divide(totals['fg3a'], totals['fga']) * 100, 1),
            'fta_rate': round(safe_divide(totals['fta'], totals['fga']) * 100, 1),
        }
        
        # ---------------------------------------------------------------------
        # MAX / MIN
        # ---------------------------------------------------------------------
        max_min = {
            'pts_max': max(g.get('pts', 0) for g in games_played),
            'pts_min': min(g.get('pts', 0) for g in games_played),
            'reb_max': max(g.get('reb', 0) for g in games_played),
            'reb_min': min(g.get('reb', 0) for g in games_played),
            'ast_max': max(g.get('ast', 0) for g in games_played),
            'ast_min': min(g.get('ast', 0) for g in games_played),
            'stl_max': max(g.get('stl', 0) for g in games_played),
            'blk_max': max(g.get('blk', 0) for g in games_played),
            'min_max': max(g.get('min', 0) for g in games_played),
            'min_min': min(g.get('min', 0) for g in games_played),
        }
        
        # ---------------------------------------------------------------------
        # RISK-ADJUSTED (Sortino-style)
        # ---------------------------------------------------------------------
        pts_values = [g.get('pts', 0) for g in games_played]
        reb_values = [g.get('reb', 0) for g in games_played]
        ast_values = [g.get('ast', 0) for g in games_played]
        
        risk_adj = {
            'pts_risk_adj': round(np.mean(pts_values) - downside_deviation(pts_values), 1),
            'reb_risk_adj': round(np.mean(reb_values) - downside_deviation(reb_values), 1),
            'ast_risk_adj': round(np.mean(ast_values) - downside_deviation(ast_values), 1),
            'pts_std': round(np.std(pts_values), 1),
            'reb_std': round(np.std(reb_values), 1),
            'ast_std': round(np.std(ast_values), 1),
        }
        
        # ---------------------------------------------------------------------
        # IPM (per game values, then average) - RAW VALUES FIRST
        # Adjustment applied after all players computed (need max MPG)
        # ---------------------------------------------------------------------
        any_ipm_values = [compute_ipm_game(g, 'any') for g in games_played]
        net_ipm_values = [compute_ipm_game(g, 'net') for g in games_played]
        
        any_ipm_values = [v for v in any_ipm_values if v is not None]
        net_ipm_values = [v for v in net_ipm_values if v is not None]
        
        ipm = {
            'any_ipm_raw': round(np.mean(any_ipm_values), 3) if any_ipm_values else 0,
            'net_ipm_raw': round(np.mean(net_ipm_values), 3) if net_ipm_values else 0,
            'any_ipm_max': round(max(any_ipm_values), 3) if any_ipm_values else 0,
            'net_ipm_max': round(max(net_ipm_values), 3) if net_ipm_values else 0,
            # Adjusted values will be added in second pass
            'any_ipm': 0,
            'net_ipm': 0,
        }
        
        # ---------------------------------------------------------------------
        # ETHICAL HOOPS (per game values, then average)
        # ---------------------------------------------------------------------
        ethical_values = [compute_ethical_game(g) for g in games_played]
        
        # Get foul counts (player-level, stored in each game row from JOIN)
        techs = games[0].get('technical_fouls', 0) or 0
        flags = games[0].get('flagrant_fouls', 0) or 0
        
        # Foul penalty added to total: -4 per TECH, -10 per FLAG
        foul_penalty_total = -4 * techs - 10 * flags
        ethical_total = sum(ethical_values) + foul_penalty_total
        
        ethical = {
            'ethical_total': round(ethical_total, 1),
            'ethical_avg': round(ethical_total / gp, 1),
            'ethical_per_min': round(ethical_total / totals['min'], 3) if totals['min'] > 0 else 0,
            'ethical_max': round(max(ethical_values), 1),
            'ethical_min': round(min(ethical_values), 1),
            'technical_fouls': techs,
            'flagrant_fouls': flags,
            'foul_penalty': round(foul_penalty_total / gp, 2),
        }
        
        # ---------------------------------------------------------------------
        # ACHIEVEMENTS
        # ---------------------------------------------------------------------
        achievements = {
            'double_doubles': sum(g.get('dd2', 0) for g in games_played),
            'triple_doubles': sum(g.get('td3', 0) for g in games_played),
            'near_triple_doubles': sum(1 for g in games_played if is_near_triple_double(g)),
            'games_30plus': sum(1 for g in games_played if g.get('pts', 0) >= 30),
            'games_40plus': sum(1 for g in games_played if g.get('pts', 0) >= 40),
            'games_50plus': sum(1 for g in games_played if g.get('pts', 0) >= 50),
            'games_20_10': sum(1 for g in games_played 
                              if g.get('pts', 0) >= 20 and (g.get('reb', 0) >= 10 or g.get('ast', 0) >= 10)),
            'games_20_10_5': sum(1 for g in games_played 
                                if g.get('pts', 0) >= 20 and g.get('reb', 0) >= 10 and g.get('ast', 0) >= 5),
        }
        
        # ---------------------------------------------------------------------
        # RECORD
        # ---------------------------------------------------------------------
        wins = sum(1 for g in games_played if g.get('wl') == 'W')
        losses = gp - wins
        
        record = {
            'gp': gp,
            'wins': wins,
            'losses': losses,
            'win_pct': round(safe_divide(wins, gp) * 100, 1),
        }
        
        # ---------------------------------------------------------------------
        # COMBINE ALL
        # ---------------------------------------------------------------------
        results[player_id] = {
            'player_id': player_id,
            'name': player_name,
            'team': team,
            **record,
            **avg,
            **per_min,
            **shooting,
            **max_min,
            **risk_adj,
            **ipm,
            **ethical,
            **achievements,
            'totals': totals,
        }
    
    # -------------------------------------------------------------------------
    # SECOND PASS: Apply IPM minutes adjustment and add tracking contributions
    # -------------------------------------------------------------------------
    print("Applying IPM minutes adjustment and tracking contributions...")
    
    # Find max MPG
    mpg_max = max(p['mpg'] for p in results.values())
    print(f"  Max MPG: {mpg_max}")
    
    players_with_tracking = 0
    
    # Apply adjustment to each player
    for player_id, stats in results.items():
        mpg = stats['mpg']
        
        # Logarithmic scale with power
        # scale = (log(1 + MPG) / log(1 + MPG_max))^p
        if mpg_max > 0 and mpg > 0:
            scale = (np.log(1 + mpg) / np.log(1 + mpg_max)) ** IPM_ADJUSTMENT_POWER
        else:
            scale = 0
        
        stats['ipm_scale'] = round(scale, 3)
        
        # Get tracking data for this player
        tracking = tracking_data.get(player_id, {})
        
        if tracking:
            players_with_tracking += 1
            
            # Compute tracking contributions
            tracking_ipm = compute_tracking_ipm_contribution(tracking, mpg)
            tracking_ethical = compute_tracking_ethical_contribution(tracking)
            
            # Store tracking contribution details
            stats['tracking_ipm_raw'] = round(tracking_ipm, 3)
            stats['tracking_ethical'] = round(tracking_ethical, 1)
            
            # Add tracking to IPM (both any and net get same bonus since all positive)
            stats['any_ipm'] = round((stats['any_ipm_raw'] + tracking_ipm) * scale, 3)
            stats['net_ipm'] = round((stats['net_ipm_raw'] + tracking_ipm) * scale, 3)
            
            # Add tracking to Ethical Hoops
            stats['ethical_avg'] = round(stats['ethical_avg'] + tracking_ethical, 1)
            stats['ethical_per_min'] = round((stats['ethical_avg']) / mpg, 3) if mpg > 0 else 0
        else:
            # No tracking data - just apply scale to box score IPM
            stats['tracking_ipm_raw'] = 0
            stats['tracking_ethical'] = 0
            stats['any_ipm'] = round(stats['any_ipm_raw'] * scale, 3)
            stats['net_ipm'] = round(stats['net_ipm_raw'] * scale, 3)
    
    print(f"  Added tracking data for {players_with_tracking} players")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("COMPUTE PLAYER STATS")
    print("=" * 70)
    print(f"Input: {DB_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    # Compute all stats
    results = compute_player_stats(conn)
    
    conn.close()
    
    print(f"\nComputed stats for {len(results)} players")
    
    # Prepare output
    output = {
        'meta': {
            'generated': datetime.now().isoformat(),
            'source': DB_PATH,
            'player_count': len(results),
            'min_games': MIN_GAMES,
            'min_mpg': MIN_MPG,
            'ipm_weights': IPM_WEIGHTS,
            'ipm_adjustment_power': IPM_ADJUSTMENT_POWER,
            'ethical_weights': ETHICAL_WEIGHTS,
            'foul_penalty': {'tech': -4, 'flag': -10},
        },
        'players': results,
    }
    
    # Save to JSON
    print(f"\nSaving to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Summary
    print()
    print("=" * 70)
    print("TOP 10 BY PPG")
    print("=" * 70)
    top_ppg = sorted(results.values(), key=lambda x: x['ppg'], reverse=True)[:10]
    for i, p in enumerate(top_ppg, 1):
        print(f"{i:2d}. {p['name']:<25} {p['team']} - {p['ppg']} PPG ({p['gp']} GP)")
    
    print()
    print("=" * 70)
    print("TOP 10 BY ETHICAL HOOPS (with foul penalties)")
    print("=" * 70)
    top_ethical = sorted(results.values(), key=lambda x: x['ethical_avg'], reverse=True)[:10]
    for i, p in enumerate(top_ethical, 1):
        foul_str = ""
        if p.get('technical_fouls', 0) > 0 or p.get('flagrant_fouls', 0) > 0:
            foul_str = f" [{p.get('technical_fouls', 0)}T {p.get('flagrant_fouls', 0)}F = {p.get('foul_penalty', 0)} pen]"
        print(f"{i:2d}. {p['name']:<22} {p['team']} - {p['ethical_avg']} ETH ({p['ppg']} PPG){foul_str}")
    
    # Show biggest foul impact
    print()
    print("BIGGEST FOUL PENALTIES:")
    by_penalty = sorted(results.values(), key=lambda x: x.get('foul_penalty', 0))[:5]
    for p in by_penalty:
        if p.get('foul_penalty', 0) < 0:
            print(f"  {p['name']:<22} {p['team']} - {p.get('technical_fouls', 0)}T {p.get('flagrant_fouls', 0)}F = {p['foul_penalty']} pen")
    
    print()
    print("=" * 70)
    print("TOP 10 BY NET IPM (Adjusted)")
    print("=" * 70)
    top_ipm = sorted(results.values(), key=lambda x: x['net_ipm'], reverse=True)[:10]
    for i, p in enumerate(top_ipm, 1):
        print(f"{i:2d}. {p['name']:<25} {p['team']} - {p['net_ipm']:.3f} IPM (raw: {p['net_ipm_raw']:.3f}, scale: {p['ipm_scale']:.2f}, {p['mpg']} MPG)")
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
