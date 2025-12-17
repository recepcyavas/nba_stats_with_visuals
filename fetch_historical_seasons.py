"""
================================================================================
FETCH HISTORICAL SEASON AVERAGES (1996-97 to 2025-26)
================================================================================

MODE:
    - Default: Only fetches current season (2025-26)
    - --full:  Fetches all seasons from 1996-97 (for initial setup)

================================================================================
"""

import sqlite3
import sys
import time
from datetime import datetime
from nba_api.stats.endpoints import LeagueDashPlayerStats

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = "historical_seasons.db"
CURRENT_SEASON = "2025-26"

# ALL seasons from 1996-97 to 2025-26 (only used with --full flag)
ALL_SEASONS = [
    "2025-26", "2024-25", "2023-24", "2022-23", "2021-22",
    "2020-21", "2019-20", "2018-19", "2017-18", "2016-17",
    "2015-16", "2014-15", "2013-14", "2012-13", "2011-12",
    "2010-11", "2009-10", "2008-09", "2007-08", "2006-07",
    "2005-06", "2004-05", "2003-04", "2002-03", "2001-02",
    "2000-01", "1999-00", "1998-99", "1997-98", "1996-97",
]

REQUEST_DELAY = 1.0  # seconds between API calls
MIN_GP = 1
MIN_MPG = 5.0


# =============================================================================
# DATABASE
# =============================================================================

def ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS season_averages (
            player_id INTEGER,
            season TEXT,
            name TEXT,
            team TEXT,
            gp INTEGER,
            mpg REAL,
            ppg REAL,
            rpg REAL,
            apg REAL,
            spg REAL,
            bpg REAL,
            ts_pct REAL,
            PRIMARY KEY (player_id, season)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_season ON season_averages(season)")
    conn.commit()


def season_exists(conn, season):
    result = conn.execute(
        "SELECT COUNT(*) FROM season_averages WHERE season = ?", (season,)
    ).fetchone()
    return result[0] > 0


def delete_season(conn, season):
    conn.execute("DELETE FROM season_averages WHERE season = ?", (season,))
    conn.commit()


# =============================================================================
# FETCH
# =============================================================================

def fetch_season(season):
    print(f"  Fetching {season}...", end=" ", flush=True)
    
    try:
        stats = LeagueDashPlayerStats(
            season=season,
            season_type_all_star="Regular Season",
            per_mode_detailed="PerGame",
            timeout=120
        )
        df = stats.get_data_frames()[0]
    except Exception as e:
        print(f"ERROR: {e}")
        return []
    
    players = []
    
    for _, row in df.iterrows():
        gp = row.get('GP', 0) or 0
        mpg = row.get('MIN', 0) or 0
        
        if gp < MIN_GP or mpg < MIN_MPG:
            continue
        
        # Compute TS%
        pts = row.get('PTS', 0) or 0
        fga = row.get('FGA', 0) or 0
        fta = row.get('FTA', 0) or 0
        
        ts_denom = 2 * (fga + 0.44 * fta)
        ts_pct = (pts / ts_denom * 100) if ts_denom > 0 else 0
        
        players.append({
            "player_id": int(row['PLAYER_ID']),
            "season": season,
            "name": row['PLAYER_NAME'],
            "team": row['TEAM_ABBREVIATION'],
            "gp": int(gp),
            "mpg": round(mpg, 1),
            "ppg": round(pts, 1),
            "rpg": round(row.get('REB', 0) or 0, 1),
            "apg": round(row.get('AST', 0) or 0, 1),
            "spg": round(row.get('STL', 0) or 0, 1),
            "bpg": round(row.get('BLK', 0) or 0, 1),
            "ts_pct": round(ts_pct, 1),
        })
    
    print(f"{len(players)} players")
    return players


def store_season(conn, players):
    if not players:
        return
    conn.executemany("""
        INSERT OR REPLACE INTO season_averages 
        (player_id, season, name, team, gp, mpg, ppg, rpg, apg, spg, bpg, ts_pct)
        VALUES (:player_id, :season, :name, :team, :gp, :mpg, :ppg, :rpg, :apg, :spg, :bpg, :ts_pct)
    """, players)
    conn.commit()


# =============================================================================
# MAIN
# =============================================================================

def main():
    full_mode = "--full" in sys.argv
    
    print("=" * 70)
    print("FETCH HISTORICAL SEASON AVERAGES")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print(f"Mode: {'FULL (all seasons)' if full_mode else 'UPDATE (current season only)'}")
    print(f"Filters: GP >= {MIN_GP}, MPG >= {MIN_MPG}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    
    # Determine which seasons to fetch
    if full_mode:
        seasons_to_fetch = ALL_SEASONS
    else:
        seasons_to_fetch = [CURRENT_SEASON]
    
    fetched = 0
    skipped = 0
    
    for i, season in enumerate(seasons_to_fetch):
        prefix = f"[{i+1}/{len(seasons_to_fetch)}]"
        
        # In full mode: skip historical seasons that exist, always refresh current
        # In update mode: always refresh current season
        if season_exists(conn, season):
            if season == CURRENT_SEASON:
                print(f"{prefix} {season}: Refreshing current season...")
                delete_season(conn, season)
            elif full_mode:
                count = conn.execute(
                    "SELECT COUNT(*) FROM season_averages WHERE season = ?", (season,)
                ).fetchone()[0]
                print(f"{prefix} {season}: Already have {count} players, skipping")
                skipped += 1
                continue
        
        print(prefix, end=" ")
        players = fetch_season(season)
        
        if players:
            store_season(conn, players)
            fetched += 1
        
        if i < len(seasons_to_fetch) - 1:
            time.sleep(REQUEST_DELAY)
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    cursor = conn.execute("""
        SELECT season, COUNT(*) as players 
        FROM season_averages 
        GROUP BY season 
        ORDER BY season DESC
        LIMIT 10
    """)
    
    total_players = 0
    print("Recent seasons:")
    for row in cursor:
        print(f"  {row[0]}: {row[1]} players")
        total_players += row[1]
    
    total_seasons = conn.execute("SELECT COUNT(DISTINCT season) FROM season_averages").fetchone()[0]
    total_all = conn.execute("SELECT COUNT(*) FROM season_averages").fetchone()[0]
    
    print()
    print(f"Total: {total_seasons} seasons, {total_all} player-seasons")
    print(f"This run: {fetched} fetched, {skipped} skipped")
    
    conn.close()
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
