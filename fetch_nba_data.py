"""
================================================================================
NBA DATA FETCHER
================================================================================

Single script that fetches NBA game data from two sources into two databases.

OUTPUT 1: nba_pbp.db
    Source: NBA Live API (nba_api package)
    Tables:
        - games: game_id, home_team_id, away_team_id, game_date
        - pbp: play-by-play with scores and possession
        - timeouts: extracted timeout events
    
OUTPUT 2: espn_wp.db
    Source: ESPN public API (unofficial)
    Tables:
        - espn_games: ESPN game IDs, teams, scores, fetch status, NBA IDs
        - wp_plays: win probability at each play

ID LINKING:
    ESPN games are linked to NBA games via nba_game_id column.
    Team IDs are standardized to NBA format (home_nba_team_id, away_nba_team_id).
    ESPN abbrev differences handled: GS->GSW, NO->NOP, NY->NYK, SA->SAS, UTAH->UTA, WSH->WAS

INCREMENTAL LOGIC:
    Both fetchers find the last game date in their DB, then search
    date-by-date forward to today. Stops after 5 consecutive empty days.

USAGE:
    python fetch_data.py              # Fetch both (incremental)
    python fetch_data.py --nba        # NBA PBP only
    python fetch_data.py --espn       # ESPN WP only
    python fetch_data.py --backfill   # Full season backfill
    python fetch_data.py --link-ids   # Update existing ESPN games with NBA IDs

================================================================================
"""

import sqlite3
import pandas as pd
import requests
import time
import sys
from datetime import datetime, timedelta

from nba_api.live.nba.endpoints import playbyplay
from nba_api.stats.endpoints import scoreboardv2

# Headers for stats API requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.nba.com/',
}

# NBA Team ID mapping (official NBA team IDs)
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

# ESPN abbreviation -> NBA abbreviation (handles mismatches)
ESPN_TO_NBA_ABBREV = {
    "ATL": "ATL", "BKN": "BKN", "BOS": "BOS", "CHA": "CHA",
    "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN",
    "DET": "DET", "GS": "GSW", "HOU": "HOU", "IND": "IND",
    "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA",
    "MIL": "MIL", "MIN": "MIN", "NO": "NOP", "NY": "NYK",
    "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHX": "PHX",
    "POR": "POR", "SA": "SAS", "SAC": "SAC", "TOR": "TOR",
    "UTAH": "UTA", "WSH": "WAS"
}


# =============================================================================
# CONFIGURATION
# =============================================================================

NBA_DB_PATH = "nba_pbp.db"
ESPN_DB_PATH = "espn_wp.db"

SEASON = "2025-26"
SEASON_START = "20251021"  # Oct 21, 2025

MAX_EMPTY_DAYS = 5
API_DELAY = 0.4


# =============================================================================
# SHARED HELPERS
# =============================================================================

def parse_nba_clock(clock_str):
    """Parse NBA clock string (PT11M30.00S) to seconds remaining."""
    if not clock_str or not isinstance(clock_str, str):
        return 0
    c = clock_str.replace("PT", "").replace("S", "")
    if "M" in c:
        parts = c.split("M")
        return int(parts[0]) * 60 + float(parts[1])
    return float(c)


def to_elapsed(period, clock_seconds):
    """Convert period + clock to elapsed seconds from game start."""
    if period <= 4:
        return int((period - 1) * 720 + (720 - clock_seconds))
    else:
        return int(2880 + (period - 5) * 300 + (300 - clock_seconds))


# =============================================================================
# PART 1: NBA PLAY-BY-PLAY → nba_pbp.db
# =============================================================================

def nba_ensure_schema(conn):
    """Create NBA PBP tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            home_team_id INTEGER,
            away_team_id INTEGER,
            game_date TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pbp (
            game_id TEXT,
            action_number INTEGER,
            period INTEGER,
            clock TEXT,
            score_home INTEGER,
            score_away INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            possession INTEGER,
            PRIMARY KEY (game_id, action_number)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS timeouts (
            game_id TEXT,
            period INTEGER,
            clock TEXT,
            elapsed INTEGER,
            team_id INTEGER,
            timeout_type TEXT,
            description TEXT,
            PRIMARY KEY (game_id, period, clock, team_id)
        )
    """)
    try:
        conn.execute("ALTER TABLE pbp ADD COLUMN possession INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def nba_get_existing_ids(conn):
    """Get set of game IDs already in DB."""
    try:
        cursor = conn.execute("SELECT game_id FROM games")
        return set(r[0] for r in cursor.fetchall())
    except:
        return set()


def nba_get_last_date(conn):
    """Get last game date in DB."""
    try:
        cursor = conn.execute("SELECT MAX(game_date) FROM games")
        result = cursor.fetchone()[0]
        if result:
            return datetime.strptime(result, "%Y-%m-%d").date()
    except:
        pass
    return datetime.strptime(SEASON_START, "%Y%m%d").date()


def nba_find_games_by_date(date_str, existing_ids):
    """
    Find games for a date using ScoreboardV2.
    Returns list of game_ids not in existing_ids.
    
    Note: GAME_STATUS_ID is unreliable (often shows 1 for finished games).
    We'll try to fetch and check if we get real data.
    
    Note: Game IDs are NOT sequential by date. A game scheduled earlier
    might have a higher ID than one scheduled later.
    """
    new_games = []
    try:
        sb = scoreboardv2.ScoreboardV2(game_date=date_str, headers=HEADERS, timeout=60)
        df = sb.game_header.get_data_frame()
        
        for _, row in df.iterrows():
            gid = row['GAME_ID']
            if gid not in existing_ids:
                new_games.append({
                    'game_id': gid,
                    'home_team_id': row['HOME_TEAM_ID'],
                    'away_team_id': row['VISITOR_TEAM_ID'],
                    'game_date': date_str
                })
    except Exception as e:
        print(f"      ScoreboardV2 error: {e}")
    
    return new_games


def nba_fetch_game(game_info):
    """Fetch PBP for a single game. Returns (pbp_rows, timeout_rows, msg)."""
    game_id = game_info['game_id']
    try:
        pbp = playbyplay.PlayByPlay(game_id=game_id)
        actions = pbp.get_dict()['game']['actions']
        
        if len(actions) < 50:
            return None, None, f"Too few actions ({len(actions)})"
        
        pbp_rows = []
        timeout_rows = []
        
        for a in actions:
            score_home = int(a["scoreHome"]) if a["scoreHome"] != '' else 0
            score_away = int(a["scoreAway"]) if a["scoreAway"] != '' else 0
            possession = a.get("possession", 0) or 0
            
            pbp_rows.append({
                "game_id": game_id,
                "action_number": a["actionNumber"],
                "period": a["period"],
                "clock": a["clock"],
                "score_home": score_home,
                "score_away": score_away,
                "home_team_id": game_info["home_team_id"],
                "away_team_id": game_info["away_team_id"],
                "possession": possession
            })
            
            action_type = a.get("actionType", "").lower()
            if "timeout" in action_type:
                timeout_rows.append({
                    "game_id": game_id,
                    "period": a.get("period"),
                    "clock": a.get("clock"),
                    "elapsed": to_elapsed(a.get("period", 1), parse_nba_clock(a.get("clock", "PT12M00.00S"))),
                    "team_id": a.get("teamId"),
                    "timeout_type": a.get("subType", action_type),
                    "description": a.get("description", "")
                })
        
        poss_count = sum(1 for r in pbp_rows if r["possession"])
        poss_pct = (poss_count / len(pbp_rows) * 100) if pbp_rows else 0
        return pbp_rows, timeout_rows, f"{len(actions)} actions, {len(timeout_rows)} TO, poss={poss_pct:.0f}%"
    
    except Exception as e:
        return None, None, str(e)


def nba_store_game(conn, game_info, pbp_rows, timeout_rows):
    """Store game data in DB."""
    df = pd.DataFrame(pbp_rows)
    df.to_sql("pbp", conn, if_exists="append", index=False)
    
    for t in timeout_rows:
        conn.execute("""
            INSERT OR IGNORE INTO timeouts 
            (game_id, period, clock, elapsed, team_id, timeout_type, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (t["game_id"], t["period"], t["clock"], t["elapsed"],
              t["team_id"], t["timeout_type"], t["description"]))
    
    conn.execute("INSERT OR REPLACE INTO games VALUES (?, ?, ?, ?)",
                 (game_info["game_id"], game_info["home_team_id"],
                  game_info["away_team_id"], game_info["game_date"]))
    conn.commit()


def run_nba_fetch():
    """Main NBA PBP fetch routine."""
    print("=" * 60)
    print("PART 1: NBA PLAY-BY-PLAY → nba_pbp.db")
    print("=" * 60)
    
    conn = sqlite3.connect(NBA_DB_PATH)
    nba_ensure_schema(conn)
    
    existing_ids = nba_get_existing_ids(conn)
    last_date = nba_get_last_date(conn)
    today = datetime.now().date()
    
    # Don't check today - games won't be finished yet
    # Stop at yesterday
    yesterday = today - timedelta(days=1)
    
    print(f"  Existing games: {len(existing_ids)}")
    print(f"  Searching: {last_date} → {yesterday}")
    
    # Find missing games by scanning dates
    new_games = []
    empty_days = 0
    current = last_date
    
    while current <= yesterday:
        date_str = current.strftime("%Y-%m-%d")
        day_games = nba_find_games_by_date(date_str, existing_ids)
        
        if day_games:
            print(f"    {date_str}: {len(day_games)} new game(s)")
            new_games.extend(day_games)
            empty_days = 0
        else:
            empty_days += 1
        
        if empty_days >= MAX_EMPTY_DAYS and current > last_date:
            break
        
        current += timedelta(days=1)
        time.sleep(API_DELAY)
    
    if not new_games:
        print(f"  No new games. Total in DB: {len(existing_ids)}")
        conn.close()
        return
    
    print(f"\n  Fetching {len(new_games)} game(s)...")
    success = 0
    for i, g in enumerate(new_games, 1):
        print(f"    [{i}/{len(new_games)}] {g['game_id']}...", end=" ")
        pbp, timeouts, msg = nba_fetch_game(g)
        if pbp:
            nba_store_game(conn, g, pbp, timeouts)
            print(msg)
            success += 1
        else:
            print(f"FAILED: {msg}")
        time.sleep(API_DELAY)
    
    final = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    conn.close()
    print(f"  Done. Total games: {final}")


# =============================================================================
# PART 2: ESPN WIN PROBABILITY → espn_wp.db
# =============================================================================

def espn_ensure_schema(conn):
    """Create ESPN tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS espn_games (
            espn_game_id TEXT PRIMARY KEY,
            date TEXT,
            home_abbrev TEXT,
            away_abbrev TEXT,
            home_espn_team_id INTEGER,
            away_espn_team_id INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT,
            wp_fetched INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            nba_game_id TEXT,
            home_nba_team_id INTEGER,
            away_nba_team_id INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wp_plays (
            espn_game_id TEXT,
            play_id TEXT,
            sequence INTEGER,
            period INTEGER,
            clock INTEGER,
            elapsed INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            home_wp REAL,
            play_type TEXT,
            play_text TEXT,
            player_id TEXT,
            player_name TEXT,
            team_id INTEGER,
            PRIMARY KEY (espn_game_id, play_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wp_game ON wp_plays(espn_game_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wp_elapsed ON wp_plays(espn_game_id, elapsed)")
    
    # Add NBA columns if they don't exist (for existing DBs)
    for col in ['nba_game_id TEXT', 'home_nba_team_id INTEGER', 'away_nba_team_id INTEGER']:
        try:
            conn.execute(f"ALTER TABLE espn_games ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    
    conn.commit()


def espn_get_fetched_ids(conn):
    """Get game IDs that already have WP data."""
    try:
        cursor = conn.execute("SELECT espn_game_id FROM espn_games WHERE wp_fetched = 1")
        return set(row[0] for row in cursor.fetchall())
    except:
        return set()


def espn_get_last_date(conn):
    """Get last game date in ESPN DB."""
    try:
        cursor = conn.execute("SELECT MAX(date) FROM espn_games")
        result = cursor.fetchone()[0]
        if result:
            return result  # Already YYYYMMDD format
    except:
        pass
    return SEASON_START


def espn_fetch_scoreboard(date_str):
    """Fetch ESPN scoreboard for a date (YYYYMMDD)."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        games = []
        for event in data.get('events', []):
            comp = event['competitions'][0]
            teams = comp['competitors']
            home = next(t for t in teams if t['homeAway'] == 'home')
            away = next(t for t in teams if t['homeAway'] == 'away')
            
            games.append({
                'espn_game_id': event['id'],
                'date': date_str,
                'home_abbrev': home['team']['abbreviation'],
                'away_abbrev': away['team']['abbreviation'],
                'home_espn_team_id': int(home['team']['id']),
                'away_espn_team_id': int(away['team']['id']),
                'home_score': int(home.get('score', 0) or 0),
                'away_score': int(away.get('score', 0) or 0),
                'status': comp['status']['type']['name']
            })
        return games
    except Exception as e:
        print(f"      Error: {e}")
        return []


def espn_fetch_wp(espn_game_id):
    """Fetch win probability data for a game."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espn_game_id}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        return data.get('winprobability', []), data.get('plays', [])
    except Exception as e:
        print(f"      Error: {e}")
        return None, None


def espn_parse_clock(clock_dict):
    """Parse ESPN clock dict to seconds remaining."""
    if not clock_dict:
        return 0
    display = clock_dict.get('displayValue', '0:00')
    try:
        parts = display.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(float(parts[1]))
        return int(float(display))
    except:
        return 0


def espn_extract_player(play):
    """Extract player info from play. Returns (player_id, player_name)."""
    participants = play.get('participants', [])
    player_id = participants[0].get('athlete', {}).get('id') if participants else None
    
    text = play.get('text', '') or ''
    player_name = None
    if text:
        actions = [' makes ', ' misses ', ' shooting foul', ' personal foul',
                   ' turnover', ' rebound', ' blocks ', ' steals', ' free throw',
                   ' layup', ' dunk', ' jump shot', ' three point', ' two point']
        text_lower = text.lower()
        for action in actions:
            if action in text_lower:
                idx = text_lower.index(action)
                if idx > 0:
                    player_name = text[:idx].strip()
                    break
    return player_id, player_name


def espn_store_game(conn, game, nba_game_lookup=None):
    """Store ESPN game metadata with NBA ID mapping."""
    # Convert ESPN abbrevs to NBA team IDs
    home_nba_abbrev = ESPN_TO_NBA_ABBREV.get(game['home_abbrev'])
    away_nba_abbrev = ESPN_TO_NBA_ABBREV.get(game['away_abbrev'])
    home_nba_team_id = TEAMS.get(home_nba_abbrev) if home_nba_abbrev else None
    away_nba_team_id = TEAMS.get(away_nba_abbrev) if away_nba_abbrev else None
    
    # Look up NBA game ID by date + teams
    nba_game_id = None
    if nba_game_lookup and home_nba_team_id and away_nba_team_id:
        key = (game['date'], home_nba_team_id, away_nba_team_id)
        nba_game_id = nba_game_lookup.get(key)
    
    conn.execute("""
        INSERT OR REPLACE INTO espn_games 
        (espn_game_id, date, home_abbrev, away_abbrev, 
         home_espn_team_id, away_espn_team_id, home_score, away_score, status,
         nba_game_id, home_nba_team_id, away_nba_team_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (game['espn_game_id'], game['date'], game['home_abbrev'], game['away_abbrev'],
          game['home_espn_team_id'], game['away_espn_team_id'],
          game['home_score'], game['away_score'], game['status'],
          nba_game_id, home_nba_team_id, away_nba_team_id))


def espn_store_wp(conn, espn_game_id, wp_list, plays_list):
    """Store win probability plays."""
    wp_lookup = {w['playId']: w['homeWinPercentage'] for w in wp_list}
    
    rows = []
    for play in plays_list:
        play_id = str(play['id'])
        period = play.get('period', {}).get('number', 1)
        clock = espn_parse_clock(play.get('clock'))
        elapsed = to_elapsed(period, clock)
        player_id, player_name = espn_extract_player(play)
        
        rows.append({
            'espn_game_id': espn_game_id,
            'play_id': play_id,
            'sequence': play.get('sequenceNumber'),
            'period': period,
            'clock': clock,
            'elapsed': elapsed,
            'home_score': play.get('homeScore', 0),
            'away_score': play.get('awayScore', 0),
            'home_wp': wp_lookup.get(play_id),
            'play_type': play.get('type', {}).get('text', ''),
            'play_text': (play.get('text', '') or '')[:200],
            'player_id': player_id,
            'player_name': player_name,
            'team_id': play.get('team', {}).get('id')
        })
    
    if rows:
        df = pd.DataFrame(rows)
        df.to_sql('wp_plays', conn, if_exists='append', index=False)
    
    conn.execute("UPDATE espn_games SET wp_fetched = 1 WHERE espn_game_id = ?", (espn_game_id,))
    conn.commit()


def espn_update_nba_ids():
    """Update existing ESPN games with NBA IDs (for existing DB migration)."""
    print("\n" + "=" * 60)
    print("UPDATING ESPN GAMES WITH NBA IDs")
    print("=" * 60)
    
    espn_conn = sqlite3.connect(ESPN_DB_PATH)
    espn_ensure_schema(espn_conn)
    
    # Build NBA game lookup
    nba_game_lookup = {}
    try:
        nba_conn = sqlite3.connect(NBA_DB_PATH)
        for row in nba_conn.execute("SELECT game_id, game_date, home_team_id, away_team_id FROM games").fetchall():
            gid, gdate, home, away = row
            date_key = gdate.replace("-", "")
            nba_game_lookup[(date_key, home, away)] = gid
        nba_conn.close()
        print(f"  NBA games loaded: {len(nba_game_lookup)}")
    except Exception as e:
        print(f"  Error loading NBA games: {e}")
        espn_conn.close()
        return
    
    # Get all ESPN games
    espn_games = espn_conn.execute("""
        SELECT espn_game_id, date, home_abbrev, away_abbrev 
        FROM espn_games
    """).fetchall()
    
    updated = 0
    for eg in espn_games:
        espn_id, espn_date, home_abbrev, away_abbrev = eg
        
        home_nba_abbrev = ESPN_TO_NBA_ABBREV.get(home_abbrev)
        away_nba_abbrev = ESPN_TO_NBA_ABBREV.get(away_abbrev)
        
        if not home_nba_abbrev or not away_nba_abbrev:
            continue
        
        home_nba_team_id = TEAMS.get(home_nba_abbrev)
        away_nba_team_id = TEAMS.get(away_nba_abbrev)
        
        key = (espn_date, home_nba_team_id, away_nba_team_id)
        nba_game_id = nba_game_lookup.get(key)
        
        espn_conn.execute("""
            UPDATE espn_games 
            SET nba_game_id = ?, home_nba_team_id = ?, away_nba_team_id = ?
            WHERE espn_game_id = ?
        """, (nba_game_id, home_nba_team_id, away_nba_team_id, espn_id))
        
        if nba_game_id:
            updated += 1
    
    espn_conn.commit()
    
    # Verify
    total = espn_conn.execute("SELECT COUNT(*) FROM espn_games").fetchone()[0]
    with_nba = espn_conn.execute("SELECT COUNT(*) FROM espn_games WHERE nba_game_id IS NOT NULL").fetchone()[0]
    espn_conn.close()
    
    print(f"  Updated: {updated} games with NBA game IDs")
    print(f"  Total: {total} ESPN games, {with_nba} linked to NBA")


def run_espn_fetch(backfill=False):
    """Main ESPN WP fetch routine."""
    print("\n" + "=" * 60)
    print("PART 2: ESPN WIN PROBABILITY → espn_wp.db")
    print("=" * 60)
    
    conn = sqlite3.connect(ESPN_DB_PATH)
    espn_ensure_schema(conn)
    
    # Build NBA game lookup from nba_pbp.db for ID matching
    nba_game_lookup = {}
    try:
        nba_conn = sqlite3.connect(NBA_DB_PATH)
        for row in nba_conn.execute("SELECT game_id, game_date, home_team_id, away_team_id FROM games").fetchall():
            gid, gdate, home, away = row
            # Convert '2025-12-10' to '20251210' to match ESPN format
            date_key = gdate.replace("-", "")
            nba_game_lookup[(date_key, home, away)] = gid
        nba_conn.close()
        print(f"  NBA game lookup: {len(nba_game_lookup)} games")
    except Exception as e:
        print(f"  Warning: Could not load NBA games for ID matching: {e}")
    
    fetched_ids = espn_get_fetched_ids(conn)
    
    if backfill:
        start_date = SEASON_START
    else:
        last = espn_get_last_date(conn)
        start_dt = datetime.strptime(last, "%Y%m%d") + timedelta(days=1)
        start_date = start_dt.strftime("%Y%m%d")
    
    today = datetime.now()
    end_date = today.strftime("%Y%m%d")
    
    if start_date > end_date:
        print("  Database is up to date.")
        conn.close()
        return
    
    print(f"  Fetched games: {len(fetched_ids)}")
    print(f"  Searching: {start_date} → {end_date}")
    
    current = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    empty_days = 0
    total_wp = 0
    
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        games = espn_fetch_scoreboard(date_str)
        
        if games:
            print(f"\n  [{date_str}] {len(games)} games")
            empty_days = 0
            
            for game in games:
                gid = game['espn_game_id']
                espn_store_game(conn, game, nba_game_lookup)
                
                if gid in fetched_ids:
                    print(f"    {gid}: {game['away_abbrev']}@{game['home_abbrev']} - skip")
                    continue
                
                if game['status'] != 'STATUS_FINAL':
                    print(f"    {gid}: {game['away_abbrev']}@{game['home_abbrev']} - {game['status']}")
                    continue
                
                wp, plays = espn_fetch_wp(gid)
                if wp and plays:
                    espn_store_wp(conn, gid, wp, plays)
                    print(f"    {gid}: {game['away_abbrev']}@{game['home_abbrev']} - {len(plays)} plays ✓")
                    total_wp += 1
                else:
                    print(f"    {gid}: {game['away_abbrev']}@{game['home_abbrev']} - no WP")
                
                time.sleep(API_DELAY)
            
            conn.commit()
        else:
            empty_days += 1
            if empty_days >= MAX_EMPTY_DAYS:
                break
        
        current += timedelta(days=1)
        time.sleep(API_DELAY)
    
    game_count = conn.execute("SELECT COUNT(*) FROM espn_games").fetchone()[0]
    wp_count = conn.execute("SELECT COUNT(*) FROM espn_games WHERE wp_fetched = 1").fetchone()[0]
    play_count = conn.execute("SELECT COUNT(*) FROM wp_plays").fetchone()[0]
    conn.close()
    
    print(f"\n  Done. Games: {game_count}, With WP: {wp_count}, Plays: {play_count}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print(f"NBA DATA FETCHER - Season {SEASON}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Parse args
    args = sys.argv[1:]
    
    # Special mode: just update ESPN games with NBA IDs
    if '--link-ids' in args:
        espn_update_nba_ids()
        print("\n" + "=" * 60)
        print("ALL DONE")
        print("=" * 60)
        return
    
    do_nba = '--nba' in args or not any(a in args for a in ['--nba', '--espn'])
    do_espn = '--espn' in args or not any(a in args for a in ['--nba', '--espn'])
    backfill = '--backfill' in args
    
    if do_nba:
        run_nba_fetch()
    
    if do_espn:
        run_espn_fetch(backfill=backfill)
    
    print("\n" + "=" * 60)
    print("ALL DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
