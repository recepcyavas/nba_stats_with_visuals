"""
================================================================================
FETCH HISTORICAL BOX SCORES
================================================================================

PURPOSE:
    Fetches all player box scores from 1996-97 to 2025-26.
    One-time fetch, stores in SQLite for Pareto analysis.

SOURCE:
    NBA Stats API - PlayerGameLogs endpoint
    30 API calls (one per season)

OUTPUT:
    historical_box_scores.db
        - box_scores: ~780k rows with PTS, REB, AST, STL, BLK, FGA, FTA
        - fetch_meta: tracks progress for resumable fetching

COMPUTED FIELDS:
    - stockpg: STL + BLK
    - ts_pct: PTS / (2 * (FGA + 0.44 * FTA)) * 100

USAGE:
    python fetch_historical_box_scores.py           # Fetch all (skip completed)
    python fetch_historical_box_scores.py --rebuild # Drop and re-fetch all

================================================================================
"""

import sqlite3
import time
import sys
from datetime import datetime
from nba_api.stats.endpoints import PlayerGameLogs

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "historical_box_scores.db"

# Seasons to fetch (1996-97 to 2025-26)
SEASONS = [f"{y}-{str(y+1)[-2:]}" for y in range(1996, 2026)]

# Columns to keep
KEEP_COLUMNS = [
    'SEASON_YEAR', 'PLAYER_ID', 'PLAYER_NAME', 'TEAM_ABBREVIATION',
    'GAME_ID', 'GAME_DATE', 'MATCHUP', 'MIN',
    'PTS', 'REB', 'AST', 'STL', 'BLK', 'FGA', 'FTA',
    'OREB', 'DREB', 'FGM', 'FG3M', 'FG3A', 'FTM',  # Extra for potential future use
    'TOV', 'PF', 'PLUS_MINUS', 'DD2', 'TD3'
]

# Rate limiting
DELAY_BETWEEN_CALLS = 1.5  # seconds


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

def ensure_schema(conn):
    """Create tables if they don't exist."""
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS box_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season TEXT,
            player_id INTEGER,
            player_name TEXT,
            team TEXT,
            game_id TEXT,
            game_date TEXT,
            matchup TEXT,
            min REAL,
            pts INTEGER,
            reb INTEGER,
            ast INTEGER,
            stl INTEGER,
            blk INTEGER,
            fga INTEGER,
            fta INTEGER,
            fgm INTEGER,
            fg3m INTEGER,
            fg3a INTEGER,
            ftm INTEGER,
            oreb INTEGER,
            dreb INTEGER,
            tov INTEGER,
            pf INTEGER,
            plus_minus INTEGER,
            dd2 INTEGER,
            td3 INTEGER,
            stockpg REAL,
            ts_pct REAL,
            UNIQUE(player_id, game_id)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetch_meta (
            season TEXT PRIMARY KEY,
            fetched_at TEXT,
            row_count INTEGER
        )
    """)
    
    # Indexes for fast queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_season ON box_scores(season)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_player ON box_scores(player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pts ON box_scores(pts DESC)")
    
    conn.commit()


def drop_tables(conn):
    """Drop all tables for rebuild."""
    conn.execute("DROP TABLE IF EXISTS box_scores")
    conn.execute("DROP TABLE IF EXISTS fetch_meta")
    conn.commit()


def get_fetched_seasons(conn):
    """Get list of already-fetched seasons."""
    try:
        cursor = conn.execute("SELECT season FROM fetch_meta")
        return set(row[0] for row in cursor.fetchall())
    except:
        return set()


# =============================================================================
# FETCH FUNCTIONS
# =============================================================================

def compute_ts_pct(pts, fga, fta):
    """Compute True Shooting Percentage."""
    if pts is None or fga is None or fta is None:
        return None
    denominator = 2 * (fga + 0.44 * fta)
    if denominator == 0:
        return None
    return round((pts / denominator) * 100, 1)


def fetch_season(season):
    """Fetch all box scores for a single season."""
    print(f"  Fetching {season}...", end=" ", flush=True)
    
    pgl = PlayerGameLogs(
        season_nullable=season,
        season_type_nullable="Regular Season",
        timeout=120
    )
    
    df = pgl.get_data_frames()[0]
    print(f"{len(df):,} rows")
    
    return df


def process_and_store(conn, df, season):
    """Process dataframe and store in database."""
    
    rows_inserted = 0
    
    for _, row in df.iterrows():
        # Compute derived fields
        stl = row['STL'] if row['STL'] is not None else 0
        blk = row['BLK'] if row['BLK'] is not None else 0
        stockpg = stl + blk
        
        pts = row['PTS'] if row['PTS'] is not None else 0
        fga = row['FGA'] if row['FGA'] is not None else 0
        fta = row['FTA'] if row['FTA'] is not None else 0
        ts_pct = compute_ts_pct(pts, fga, fta)
        
        try:
            conn.execute("""
                INSERT OR IGNORE INTO box_scores (
                    season, player_id, player_name, team, game_id, game_date, matchup, min,
                    pts, reb, ast, stl, blk, fga, fta, fgm, fg3m, fg3a, ftm, oreb, dreb,
                    tov, pf, plus_minus, dd2, td3, stockpg, ts_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                season,
                int(row['PLAYER_ID']),
                row['PLAYER_NAME'],
                row['TEAM_ABBREVIATION'],
                row['GAME_ID'],
                str(row['GAME_DATE'])[:10],  # Just date part
                row['MATCHUP'],
                row['MIN'] if row['MIN'] is not None else 0,
                pts,
                int(row['REB']) if row['REB'] is not None else 0,
                int(row['AST']) if row['AST'] is not None else 0,
                stl,
                blk,
                fga,
                fta,
                int(row['FGM']) if row['FGM'] is not None else 0,
                int(row['FG3M']) if row['FG3M'] is not None else 0,
                int(row['FG3A']) if row['FG3A'] is not None else 0,
                int(row['FTM']) if row['FTM'] is not None else 0,
                int(row['OREB']) if row['OREB'] is not None else 0,
                int(row['DREB']) if row['DREB'] is not None else 0,
                int(row['TOV']) if row['TOV'] is not None else 0,
                int(row['PF']) if row['PF'] is not None else 0,
                int(row['PLUS_MINUS']) if row['PLUS_MINUS'] is not None else 0,
                int(row['DD2']) if row['DD2'] is not None else 0,
                int(row['TD3']) if row['TD3'] is not None else 0,
                stockpg,
                ts_pct
            ))
            rows_inserted += 1
        except Exception as e:
            print(f"    Error inserting row: {e}")
    
    conn.commit()
    
    # Record completion
    conn.execute("""
        INSERT OR REPLACE INTO fetch_meta (season, fetched_at, row_count)
        VALUES (?, ?, ?)
    """, (season, datetime.now().isoformat(), rows_inserted))
    conn.commit()
    
    return rows_inserted


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("FETCH HISTORICAL BOX SCORES")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print(f"Seasons: {SEASONS[0]} to {SEASONS[-1]} ({len(SEASONS)} total)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    rebuild = '--rebuild' in sys.argv
    
    conn = sqlite3.connect(DB_PATH)
    
    if rebuild:
        print("REBUILD MODE - dropping existing tables")
        drop_tables(conn)
    
    ensure_schema(conn)
    
    fetched = get_fetched_seasons(conn)
    remaining = [s for s in SEASONS if s not in fetched]
    
    print(f"Already fetched: {len(fetched)} seasons")
    print(f"Remaining: {len(remaining)} seasons")
    print()
    
    if not remaining:
        print("All seasons already fetched!")
    else:
        print("Starting fetch...")
        print("-" * 70)
        
        total_rows = 0
        
        for i, season in enumerate(remaining):
            print(f"[{i+1}/{len(remaining)}]", end=" ")
            
            try:
                df = fetch_season(season)
                rows = process_and_store(conn, df, season)
                total_rows += rows
                print(f"    Stored {rows:,} rows")
            except Exception as e:
                print(f"    ERROR: {e}")
            
            # Rate limiting (skip on last iteration)
            if i < len(remaining) - 1:
                time.sleep(DELAY_BETWEEN_CALLS)
        
        print("-" * 70)
        print(f"Fetched {total_rows:,} new rows")
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total = conn.execute("SELECT COUNT(*) FROM box_scores").fetchone()[0]
    seasons_done = conn.execute("SELECT COUNT(*) FROM fetch_meta").fetchone()[0]
    
    print(f"  Total box scores: {total:,}")
    print(f"  Seasons fetched: {seasons_done}/{len(SEASONS)}")
    
    # Sample top performances
    print()
    print("  Top 5 scoring games all-time:")
    for row in conn.execute("""
        SELECT player_name, season, matchup, pts, reb, ast, stockpg, ts_pct
        FROM box_scores ORDER BY pts DESC LIMIT 5
    """).fetchall():
        name, season, matchup, pts, reb, ast, stk, ts = row
        print(f"    {pts} PTS - {name} ({season}) {matchup} [{reb}r {ast}a {stk}stk {ts}%TS]")
    
    conn.close()
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
