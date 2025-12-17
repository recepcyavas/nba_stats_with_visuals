"""
================================================================================
FETCH PLAYER TRACKING STATS
================================================================================

PURPOSE:
    Fetches hustle stats and tracking data (touches, passes, etc.)
    These are season averages per player, not game-by-game logs.
    Should be run daily to get updated averages.

SOURCE:
    NBA Stats API:
    - LeagueHustleStatsPlayer: deflections, screen assists, contested shots, etc.
    - LeagueDashPtStats (Possessions): touches, time of possession
    - LeagueDashPtStats (Passing): secondary assists, potential assists

OUTPUT:
    player_box_scores.db with new table:
    - player_tracking: One row per player with all tracking/hustle stats

NOTE:
    These are PerGame averages. Table is replaced on each fetch (not incremental).

================================================================================
"""

import sqlite3
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import LeagueHustleStatsPlayer, LeagueDashPtStats

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "player_box_scores.db"
SEASON = "2025-26"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.nba.com/',
}

# Columns to keep from each endpoint
HUSTLE_COLUMNS = [
    'PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION', 'G', 'MIN',
    'CONTESTED_SHOTS', 'CONTESTED_SHOTS_2PT', 'CONTESTED_SHOTS_3PT',
    'DEFLECTIONS',
    'CHARGES_DRAWN',
    'SCREEN_ASSISTS', 'SCREEN_AST_PTS',
    'OFF_LOOSE_BALLS_RECOVERED', 'DEF_LOOSE_BALLS_RECOVERED', 'LOOSE_BALLS_RECOVERED',
    'OFF_BOXOUTS', 'DEF_BOXOUTS', 'BOX_OUTS',
]

POSSESSIONS_COLUMNS = [
    'PLAYER_ID',
    'TOUCHES', 'FRONT_CT_TOUCHES', 'TIME_OF_POSS', 
    'AVG_SEC_PER_TOUCH', 'AVG_DRIB_PER_TOUCH',
    'ELBOW_TOUCHES', 'POST_TOUCHES', 'PAINT_TOUCHES',
]

PASSING_COLUMNS = [
    'PLAYER_ID',
    'PASSES_MADE', 'PASSES_RECEIVED',
    'SECONDARY_AST', 'POTENTIAL_AST',
    'AST_POINTS_CREATED',
]


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

def ensure_schema(conn):
    """Create player_tracking table if it doesn't exist."""
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_tracking (
            player_id INTEGER PRIMARY KEY,
            player_name TEXT,
            team_id INTEGER,
            team_abbreviation TEXT,
            gp INTEGER,
            min_pg REAL,
            
            -- Hustle stats (per game)
            contested_shots REAL,
            contested_shots_2pt REAL,
            contested_shots_3pt REAL,
            deflections REAL,
            charges_drawn REAL,
            screen_assists REAL,
            screen_ast_pts REAL,
            off_loose_balls_recovered REAL,
            def_loose_balls_recovered REAL,
            loose_balls_recovered REAL,
            off_boxouts REAL,
            def_boxouts REAL,
            box_outs REAL,
            
            -- Possession tracking (per game)
            touches REAL,
            front_ct_touches REAL,
            time_of_poss REAL,
            avg_sec_per_touch REAL,
            avg_drib_per_touch REAL,
            elbow_touches REAL,
            post_touches REAL,
            paint_touches REAL,
            
            -- Passing tracking (per game)
            passes_made REAL,
            passes_received REAL,
            secondary_ast REAL,
            potential_ast REAL,
            ast_points_created REAL,
            
            -- Metadata
            updated_at TEXT
        )
    """)
    
    conn.commit()


# =============================================================================
# FETCH FUNCTIONS
# =============================================================================

def fetch_hustle_stats():
    """Fetch LeagueHustleStatsPlayer data."""
    print("  Fetching LeagueHustleStatsPlayer...")
    
    hustle = LeagueHustleStatsPlayer(
        season=SEASON,
        season_type_all_star='Regular Season',
        per_mode_time='PerGame',
        headers=HEADERS,
        timeout=60
    )
    
    df = hustle.get_data_frames()[0]
    df = df[HUSTLE_COLUMNS].copy()
    
    print(f"    Got {len(df)} players")
    return df


def fetch_possessions_stats():
    """Fetch LeagueDashPtStats with pt_measure_type=Possessions."""
    print("  Fetching LeagueDashPtStats (Possessions)...")
    
    tracking = LeagueDashPtStats(
        season=SEASON,
        season_type_all_star='Regular Season',
        per_mode_simple='PerGame',
        player_or_team='Player',
        pt_measure_type='Possessions',
        headers=HEADERS,
        timeout=60
    )
    
    df = tracking.get_data_frames()[0]
    df = df[POSSESSIONS_COLUMNS].copy()
    
    print(f"    Got {len(df)} players")
    return df


def fetch_passing_stats():
    """Fetch LeagueDashPtStats with pt_measure_type=Passing."""
    print("  Fetching LeagueDashPtStats (Passing)...")
    
    tracking = LeagueDashPtStats(
        season=SEASON,
        season_type_all_star='Regular Season',
        per_mode_simple='PerGame',
        player_or_team='Player',
        pt_measure_type='Passing',
        headers=HEADERS,
        timeout=60
    )
    
    df = tracking.get_data_frames()[0]
    df = df[PASSING_COLUMNS].copy()
    
    print(f"    Got {len(df)} players")
    return df


# =============================================================================
# MERGE AND STORE
# =============================================================================

def merge_data(hustle_df, possessions_df, passing_df):
    """Merge all dataframes on PLAYER_ID."""
    print("\nMerging dataframes...")
    
    # Start with hustle (has player info)
    merged = hustle_df.copy()
    
    # Merge possessions
    merged = merged.merge(possessions_df, on='PLAYER_ID', how='left')
    
    # Merge passing
    merged = merged.merge(passing_df, on='PLAYER_ID', how='left')
    
    print(f"  Merged: {len(merged)} players")
    return merged


def store_tracking(conn, df):
    """Store tracking data (replaces existing)."""
    print("\nStoring to player_tracking table...")
    
    # Clear existing data
    conn.execute("DELETE FROM player_tracking")
    
    now = datetime.now().isoformat()
    
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO player_tracking (
                player_id, player_name, team_id, team_abbreviation, gp, min_pg,
                contested_shots, contested_shots_2pt, contested_shots_3pt,
                deflections, charges_drawn,
                screen_assists, screen_ast_pts,
                off_loose_balls_recovered, def_loose_balls_recovered, loose_balls_recovered,
                off_boxouts, def_boxouts, box_outs,
                touches, front_ct_touches, time_of_poss,
                avg_sec_per_touch, avg_drib_per_touch,
                elbow_touches, post_touches, paint_touches,
                passes_made, passes_received,
                secondary_ast, potential_ast, ast_points_created,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(row['PLAYER_ID']),
            row['PLAYER_NAME'],
            int(row['TEAM_ID']) if pd.notna(row['TEAM_ID']) else None,
            row['TEAM_ABBREVIATION'],
            int(row['G']) if pd.notna(row['G']) else 0,
            float(row['MIN']) if pd.notna(row['MIN']) else 0,
            
            float(row['CONTESTED_SHOTS']) if pd.notna(row['CONTESTED_SHOTS']) else 0,
            float(row['CONTESTED_SHOTS_2PT']) if pd.notna(row['CONTESTED_SHOTS_2PT']) else 0,
            float(row['CONTESTED_SHOTS_3PT']) if pd.notna(row['CONTESTED_SHOTS_3PT']) else 0,
            float(row['DEFLECTIONS']) if pd.notna(row['DEFLECTIONS']) else 0,
            float(row['CHARGES_DRAWN']) if pd.notna(row['CHARGES_DRAWN']) else 0,
            float(row['SCREEN_ASSISTS']) if pd.notna(row['SCREEN_ASSISTS']) else 0,
            float(row['SCREEN_AST_PTS']) if pd.notna(row['SCREEN_AST_PTS']) else 0,
            float(row['OFF_LOOSE_BALLS_RECOVERED']) if pd.notna(row['OFF_LOOSE_BALLS_RECOVERED']) else 0,
            float(row['DEF_LOOSE_BALLS_RECOVERED']) if pd.notna(row['DEF_LOOSE_BALLS_RECOVERED']) else 0,
            float(row['LOOSE_BALLS_RECOVERED']) if pd.notna(row['LOOSE_BALLS_RECOVERED']) else 0,
            float(row['OFF_BOXOUTS']) if pd.notna(row['OFF_BOXOUTS']) else 0,
            float(row['DEF_BOXOUTS']) if pd.notna(row['DEF_BOXOUTS']) else 0,
            float(row['BOX_OUTS']) if pd.notna(row['BOX_OUTS']) else 0,
            
            float(row['TOUCHES']) if pd.notna(row['TOUCHES']) else 0,
            float(row['FRONT_CT_TOUCHES']) if pd.notna(row['FRONT_CT_TOUCHES']) else 0,
            float(row['TIME_OF_POSS']) if pd.notna(row['TIME_OF_POSS']) else 0,
            float(row['AVG_SEC_PER_TOUCH']) if pd.notna(row['AVG_SEC_PER_TOUCH']) else 0,
            float(row['AVG_DRIB_PER_TOUCH']) if pd.notna(row['AVG_DRIB_PER_TOUCH']) else 0,
            float(row['ELBOW_TOUCHES']) if pd.notna(row['ELBOW_TOUCHES']) else 0,
            float(row['POST_TOUCHES']) if pd.notna(row['POST_TOUCHES']) else 0,
            float(row['PAINT_TOUCHES']) if pd.notna(row['PAINT_TOUCHES']) else 0,
            
            float(row['PASSES_MADE']) if pd.notna(row['PASSES_MADE']) else 0,
            float(row['PASSES_RECEIVED']) if pd.notna(row['PASSES_RECEIVED']) else 0,
            float(row['SECONDARY_AST']) if pd.notna(row['SECONDARY_AST']) else 0,
            float(row['POTENTIAL_AST']) if pd.notna(row['POTENTIAL_AST']) else 0,
            float(row['AST_POINTS_CREATED']) if pd.notna(row['AST_POINTS_CREATED']) else 0,
            
            now
        ))
    
    conn.commit()
    print(f"  Stored {len(df)} players")


# =============================================================================
# ANALYSIS
# =============================================================================

def print_stats_summary(df):
    """Print mean/std/min/max for key columns to help with weight decisions."""
    print("\n" + "=" * 70)
    print("STATS SUMMARY (for weight normalization)")
    print("=" * 70)
    
    # Filter to top 100 by minutes
    df_top100 = df.nlargest(100, 'MIN')
    print(f"\nFiltered to top 100 by MPG (min MPG in top 100: {df_top100['MIN'].min():.1f})")
    
    stats_cols = [
        # Hustle
        ('CONTESTED_SHOTS', 'Contested Shots'),
        ('DEFLECTIONS', 'Deflections'),
        ('CHARGES_DRAWN', 'Charges Drawn'),
        ('SCREEN_ASSISTS', 'Screen Assists'),
        ('LOOSE_BALLS_RECOVERED', 'Loose Balls Recovered'),
        ('BOX_OUTS', 'Box Outs'),
        
        # Possessions
        ('TOUCHES', 'Touches'),
        ('FRONT_CT_TOUCHES', 'Front Court Touches'),
        ('TIME_OF_POSS', 'Time of Possession'),
        ('ELBOW_TOUCHES', 'Elbow Touches'),
        ('POST_TOUCHES', 'Post Touches'),
        ('PAINT_TOUCHES', 'Paint Touches'),
        
        # Passing
        ('PASSES_MADE', 'Passes Made'),
        ('SECONDARY_AST', 'Secondary Assists'),
        ('POTENTIAL_AST', 'Potential Assists'),
    ]
    
    print(f"\n{'Stat':<25} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8}")
    print("-" * 60)
    
    for col, name in stats_cols:
        if col in df_top100.columns:
            mean = df_top100[col].mean()
            std = df_top100[col].std()
            min_val = df_top100[col].min()
            max_val = df_top100[col].max()
            print(f"{name:<25} {mean:>8.2f} {std:>8.2f} {min_val:>8.2f} {max_val:>8.2f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("FETCH PLAYER TRACKING STATS")
    print("=" * 70)
    print(f"Season: {SEASON}")
    print(f"Database: {DB_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    
    # Fetch from API
    print("Fetching data from NBA API...")
    hustle_df = fetch_hustle_stats()
    possessions_df = fetch_possessions_stats()
    passing_df = fetch_passing_stats()
    
    # Merge
    merged_df = merge_data(hustle_df, possessions_df, passing_df)
    
    # Store
    store_tracking(conn, merged_df)
    
    # Analysis
    print_stats_summary(merged_df)
    
    # Verify
    count = conn.execute("SELECT COUNT(*) FROM player_tracking").fetchone()[0]
    print(f"\nVerified: {count} players in player_tracking table")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
