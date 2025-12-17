"""
================================================================================
FETCH PLAYER BOX SCORES
================================================================================

PURPOSE:
    Fetches individual player statistics for each game played in the season.
    Stores in player_box_scores.db for downstream analysis including:
    - Season averages
    - Risk-adjusted stats (mean - downside deviation)
    - Max/min performances
    - Near triple-double tracking
    - IPM (Involvement Per Minute)
    - Ethical Hoops Score

SOURCE:
    NBA Stats API - PlayerGameLogs endpoint
    One API call returns all player-game rows for the season (~8000+ rows)

OUTPUT:
    player_box_scores.db with tables:
        - players: Player ID disambiguation (full name, display name, team, fouls)
        - box_scores: One row per player per game with all stats
        - fetch_meta: Tracks last fetch time for incremental updates

FOUL DATA:
    Tech/flagrant/ejection data synced from espn_wp.db (player_fouls table).
    Joined by nba_player_id, with fallback accent-normalized name matching.

INCREMENTAL LOGIC:
    1. Fetch all player game logs for the season (single API call)
    2. Compare against existing game_ids in database
    3. Insert only new rows
    4. Update player table with any new players
    5. Sync foul data from ESPN

USAGE:
    python fetch_player_box_scores.py              # Incremental update
    python fetch_player_box_scores.py --rebuild    # Full rebuild (drops tables)

================================================================================
"""

import sqlite3
import pandas as pd
import sys
import re
import os
import unicodedata
from datetime import datetime
from nba_api.stats.endpoints import PlayerGameLogs

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "player_box_scores.db"
ESPN_DB_PATH = "espn_wp.db"
SEASON = "2025-26"
SEASON_TYPE = "Regular Season"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.nba.com/',
}

# Columns to keep from PlayerGameLogs
KEEP_COLUMNS = [
    'PLAYER_ID', 'PLAYER_NAME', 'NICKNAME',
    'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME',
    'GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL',
    'MIN',
    'PTS', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA',
    'OREB', 'DREB', 'REB',
    'AST', 'TOV',
    'STL', 'BLK', 'BLKA',
    'PF', 'PFD',
    'PLUS_MINUS',
    'DD2', 'TD3',
]


# =============================================================================
# NAME NORMALIZATION (handles accents, suffixes)
# =============================================================================

def normalize_name(name):
    """
    Normalize player name for matching.
    Handles: accents (Jokić→jokic), suffixes (Jr./III), periods, spacing.
    """
    if not name:
        return ""
    name = name.lower().strip()
    # Strip accents: Jokić → jokic, Dončić → doncic, Schröder → schroder
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    # Remove Jr., Sr., III, II, IV, etc.
    name = re.sub(r'\s+(jr\.?|sr\.?|iii|ii|iv)$', '', name, flags=re.IGNORECASE)
    # Remove periods and extra spaces
    name = re.sub(r'\.', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

def ensure_schema(conn):
    """Create tables if they don't exist."""
    
    # Players table - includes foul data
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY,
            player_name TEXT,
            nickname TEXT,
            team_id INTEGER,
            team_abbreviation TEXT,
            team_name TEXT,
            technical_fouls INTEGER DEFAULT 0,
            flagrant_fouls INTEGER DEFAULT 0,
            ejections INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    
    # Add foul columns if missing (for existing DBs)
    for col in ['technical_fouls', 'flagrant_fouls', 'ejections']:
        try:
            conn.execute(f"ALTER TABLE players ADD COLUMN {col} INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    
    # Box scores - one row per player per game
    conn.execute("""
        CREATE TABLE IF NOT EXISTS box_scores (
            player_id INTEGER,
            game_id TEXT,
            game_date TEXT,
            team_id INTEGER,
            team_abbreviation TEXT,
            matchup TEXT,
            wl TEXT,
            min REAL,
            pts INTEGER,
            fgm INTEGER,
            fga INTEGER,
            fg3m INTEGER,
            fg3a INTEGER,
            ftm INTEGER,
            fta INTEGER,
            oreb INTEGER,
            dreb INTEGER,
            reb INTEGER,
            ast INTEGER,
            tov INTEGER,
            stl INTEGER,
            blk INTEGER,
            blka INTEGER,
            pf INTEGER,
            pfd INTEGER,
            plus_minus INTEGER,
            dd2 INTEGER,
            td3 INTEGER,
            PRIMARY KEY (player_id, game_id)
        )
    """)
    
    # Fetch metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetch_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_box_player ON box_scores(player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_box_game ON box_scores(game_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_box_date ON box_scores(game_date)")
    
    conn.commit()


def drop_tables(conn):
    """Drop all tables for rebuild."""
    conn.execute("DROP TABLE IF EXISTS box_scores")
    conn.execute("DROP TABLE IF EXISTS players")
    conn.execute("DROP TABLE IF EXISTS fetch_meta")
    conn.commit()


# =============================================================================
# FETCH FUNCTIONS
# =============================================================================

def get_existing_game_ids(conn):
    """Get set of (player_id, game_id) tuples already in database."""
    try:
        cursor = conn.execute("SELECT player_id, game_id FROM box_scores")
        return set((row[0], row[1]) for row in cursor.fetchall())
    except:
        return set()


def fetch_player_game_logs():
    """Fetch all player game logs for the season."""
    print(f"  Fetching PlayerGameLogs for {SEASON}...")
    
    pgl = PlayerGameLogs(
        season_nullable=SEASON,
        season_type_nullable=SEASON_TYPE,
        headers=HEADERS,
        timeout=120
    )
    
    df = pgl.get_data_frames()[0]
    print(f"  Received {len(df)} rows, {df['PLAYER_ID'].nunique()} players, {df['GAME_ID'].nunique()} games")
    
    df = df[KEEP_COLUMNS].copy()
    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE']).dt.strftime('%Y-%m-%d')
    
    return df


# =============================================================================
# STORAGE FUNCTIONS
# =============================================================================

def store_players(conn, df):
    """Update players table with latest info."""
    players_df = df.sort_values('GAME_DATE', ascending=False).drop_duplicates('PLAYER_ID')
    now = datetime.now().isoformat()
    
    for _, row in players_df.iterrows():
        # Check if player exists (to preserve foul data)
        existing = conn.execute(
            "SELECT technical_fouls, flagrant_fouls, ejections FROM players WHERE player_id = ?",
            (int(row['PLAYER_ID']),)
        ).fetchone()
        
        techs, flags, ejects = (0, 0, 0) if not existing else existing
        
        conn.execute("""
            INSERT OR REPLACE INTO players 
            (player_id, player_name, nickname, team_id, team_abbreviation, team_name,
             technical_fouls, flagrant_fouls, ejections, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(row['PLAYER_ID']),
            row['PLAYER_NAME'],
            row['NICKNAME'],
            int(row['TEAM_ID']),
            row['TEAM_ABBREVIATION'],
            row['TEAM_NAME'],
            techs, flags, ejects,
            now
        ))
    
    conn.commit()
    print(f"  Updated {len(players_df)} players")


def store_box_scores(conn, df, existing_keys):
    """Store new box scores (skip existing)."""
    new_rows = []
    
    for _, row in df.iterrows():
        key = (int(row['PLAYER_ID']), row['GAME_ID'])
        if key in existing_keys:
            continue
        
        new_rows.append({
            'player_id': int(row['PLAYER_ID']),
            'game_id': row['GAME_ID'],
            'game_date': row['GAME_DATE'],
            'team_id': int(row['TEAM_ID']),
            'team_abbreviation': row['TEAM_ABBREVIATION'],
            'matchup': row['MATCHUP'],
            'wl': row['WL'],
            'min': row['MIN'] if pd.notna(row['MIN']) else 0,
            'pts': int(row['PTS']) if pd.notna(row['PTS']) else 0,
            'fgm': int(row['FGM']) if pd.notna(row['FGM']) else 0,
            'fga': int(row['FGA']) if pd.notna(row['FGA']) else 0,
            'fg3m': int(row['FG3M']) if pd.notna(row['FG3M']) else 0,
            'fg3a': int(row['FG3A']) if pd.notna(row['FG3A']) else 0,
            'ftm': int(row['FTM']) if pd.notna(row['FTM']) else 0,
            'fta': int(row['FTA']) if pd.notna(row['FTA']) else 0,
            'oreb': int(row['OREB']) if pd.notna(row['OREB']) else 0,
            'dreb': int(row['DREB']) if pd.notna(row['DREB']) else 0,
            'reb': int(row['REB']) if pd.notna(row['REB']) else 0,
            'ast': int(row['AST']) if pd.notna(row['AST']) else 0,
            'tov': int(row['TOV']) if pd.notna(row['TOV']) else 0,
            'stl': int(row['STL']) if pd.notna(row['STL']) else 0,
            'blk': int(row['BLK']) if pd.notna(row['BLK']) else 0,
            'blka': int(row['BLKA']) if pd.notna(row['BLKA']) else 0,
            'pf': int(row['PF']) if pd.notna(row['PF']) else 0,
            'pfd': int(row['PFD']) if pd.notna(row['PFD']) else 0,
            'plus_minus': int(row['PLUS_MINUS']) if pd.notna(row['PLUS_MINUS']) else 0,
            'dd2': int(row['DD2']) if pd.notna(row['DD2']) else 0,
            'td3': int(row['TD3']) if pd.notna(row['TD3']) else 0,
        })
    
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        new_df.to_sql('box_scores', conn, if_exists='append', index=False)
        conn.commit()
    
    print(f"  Inserted {len(new_rows)} new box scores (skipped {len(df) - len(new_rows)} existing)")
    return len(new_rows)


def update_meta(conn):
    """Update fetch metadata."""
    now = datetime.now().isoformat()
    conn.execute("INSERT OR REPLACE INTO fetch_meta (key, value) VALUES (?, ?)", ('last_fetch', now))
    conn.execute("INSERT OR REPLACE INTO fetch_meta (key, value) VALUES (?, ?)", ('season', SEASON))
    conn.commit()


# =============================================================================
# FOUL DATA SYNC FROM ESPN
# =============================================================================

def sync_fouls_from_espn(conn):
    """
    Copy tech/flagrant/ejection data from espn_wp.db into players table.
    Joins on nba_player_id, with fallback accent-normalized name matching.
    """
    if not os.path.exists(ESPN_DB_PATH):
        print(f"  ESPN DB not found ({ESPN_DB_PATH}), skipping foul sync")
        return 0
    
    espn_conn = sqlite3.connect(ESPN_DB_PATH)
    
    # Check if player_fouls table exists
    table_exists = espn_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_fouls'"
    ).fetchone()
    
    if not table_exists:
        print(f"  player_fouls table not found in ESPN DB, skipping foul sync")
        espn_conn.close()
        return 0
    
    # Get foul data from ESPN
    espn_fouls = espn_conn.execute("""
        SELECT nba_player_id, player_name, technical_fouls, flagrant_fouls, ejections
        FROM player_fouls WHERE season = ?
    """, (SEASON,)).fetchall()
    espn_conn.close()
    
    if not espn_fouls:
        print(f"  No foul data found for {SEASON}")
        return 0
    
    # Build lookups
    fouls_by_id = {}
    fouls_by_name = {}
    
    for row in espn_fouls:
        nba_id, name, techs, flags, ejects = row
        foul_data = (techs or 0, flags or 0, ejects or 0)
        
        if nba_id:
            fouls_by_id[nba_id] = foul_data
        
        # Always add normalized name as fallback
        norm_name = normalize_name(name)
        if norm_name:
            fouls_by_name[norm_name] = foul_data
    
    # Get all players from box scores DB
    players = conn.execute("SELECT player_id, player_name FROM players").fetchall()
    
    updated = 0
    matched_by_id = 0
    matched_by_name = 0
    
    for player_id, player_name in players:
        techs, flags, ejects = 0, 0, 0
        
        # Try matching by NBA player ID first
        if player_id in fouls_by_id:
            techs, flags, ejects = fouls_by_id[player_id]
            matched_by_id += 1
        else:
            # Fallback to normalized name matching
            norm_name = normalize_name(player_name)
            if norm_name in fouls_by_name:
                techs, flags, ejects = fouls_by_name[norm_name]
                matched_by_name += 1
        
        conn.execute("""
            UPDATE players 
            SET technical_fouls = ?, flagrant_fouls = ?, ejections = ?
            WHERE player_id = ?
        """, (techs, flags, ejects, player_id))
        
        if techs > 0 or flags > 0:
            updated += 1
    
    conn.commit()
    
    print(f"  Synced fouls: {matched_by_id} by ID, {matched_by_name} by name fallback")
    print(f"  Players with techs/flagrants: {updated}")
    
    # Show any unmatched players with fouls
    box_ids = set(p[0] for p in players)
    box_names = set(normalize_name(p[1]) for p in players)
    
    unmatched = []
    for row in espn_fouls:
        nba_id, name, techs, flags, ejects = row
        if (techs or 0) > 0 or (flags or 0) > 0:
            id_match = nba_id in box_ids
            name_match = normalize_name(name) in box_names
            if not id_match and not name_match:
                unmatched.append((name, techs or 0, flags or 0))
    
    if unmatched:
        print(f"  WARNING: {len(unmatched)} ESPN players with fouls not matched:")
        for name, t, f in unmatched:
            print(f"    {name}: {t}T {f}F")
    
    return updated


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("FETCH PLAYER BOX SCORES")
    print("=" * 70)
    print(f"Season: {SEASON}")
    print(f"Database: {DB_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    rebuild = '--rebuild' in sys.argv
    
    conn = sqlite3.connect(DB_PATH)
    
    if rebuild:
        print("REBUILD MODE - dropping existing tables")
        drop_tables(conn)
    
    ensure_schema(conn)
    
    existing_keys = get_existing_game_ids(conn)
    print(f"  Existing box scores: {len(existing_keys)}")
    
    # Fetch from API
    df = fetch_player_game_logs()
    
    # Store data
    print()
    print("Storing data...")
    store_players(conn, df)
    new_count = store_box_scores(conn, df, existing_keys)
    update_meta(conn)
    
    # Sync foul data from ESPN
    print()
    print("Syncing foul data from ESPN...")
    sync_fouls_from_espn(conn)
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total_box = conn.execute("SELECT COUNT(*) FROM box_scores").fetchone()[0]
    total_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    total_games = conn.execute("SELECT COUNT(DISTINCT game_id) FROM box_scores").fetchone()[0]
    
    print(f"  Total box scores: {total_box}")
    print(f"  Total players: {total_players}")
    print(f"  Total games: {total_games}")
    print(f"  New this fetch: {new_count}")
    
    # Foul stats
    players_with_techs = conn.execute("SELECT COUNT(*) FROM players WHERE technical_fouls > 0").fetchone()[0]
    total_techs = conn.execute("SELECT SUM(technical_fouls) FROM players").fetchone()[0] or 0
    total_flags = conn.execute("SELECT SUM(flagrant_fouls) FROM players").fetchone()[0] or 0
    print(f"  Players with techs: {players_with_techs} (total: {total_techs} T, {total_flags} F)")
    
    # Top offenders
    print()
    print("  Tech/Flagrant Leaders:")
    for row in conn.execute("""
        SELECT player_name, team_abbreviation, technical_fouls, flagrant_fouls
        FROM players 
        WHERE technical_fouls > 0 OR flagrant_fouls > 0
        ORDER BY technical_fouls + flagrant_fouls * 2 DESC
        LIMIT 10
    """).fetchall():
        name, team, techs, flags = row
        print(f"    {techs}T {flags}F  {name} ({team})")
    
    # Sample top scorer
    print()
    print("  Sample (top scorer today):")
    sample = conn.execute("""
        SELECT player_id, game_date, matchup, pts, reb, ast, stl, blk, dd2, td3
        FROM box_scores ORDER BY game_date DESC, pts DESC LIMIT 1
    """).fetchone()
    
    if sample:
        player_name = conn.execute(
            "SELECT player_name FROM players WHERE player_id = ?", (sample[0],)
        ).fetchone()[0]
        print(f"    {player_name}: {sample[3]} PTS, {sample[4]} REB, {sample[5]} AST")
        print(f"    Game: {sample[2]} on {sample[1]}")
    
    conn.close()
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
