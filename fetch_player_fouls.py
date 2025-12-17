"""
================================================================================
ESPN PLAYER FOULS FETCHER
================================================================================

Fetches technical and flagrant foul data from ESPN's hidden API.

ESPN has season-level tech/flagrant stats at:
    https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/stats

The "miscellaneous" category contains: TECH, FLAG, EJECT, DD2, TD3, etc.

OUTPUT: espn_wp.db (adds player_fouls table)
    - nba_player_id: NBA player ID (for joining with boxscore data)
    - espn_player_id: ESPN athlete ID
    - player_name: Display name
    - team_abbrev: Current team (NBA format: GSW not GS)
    - season: e.g., "2025-26"
    - technical_fouls, flagrant_fouls, ejections, games_played

ID LINKING:
    Players matched to NBA IDs via name normalization (handles Jr., accents, etc.)
    Uses nba_api.stats.static.players for the lookup.

USAGE:
    python fetch_player_fouls.py              # Fetch all players
    python fetch_player_fouls.py --refresh    # Force refresh all

================================================================================
"""
import sqlite3
import requests
import time
import sys
import re
from datetime import datetime

# =============================================================================
# CONFIGURATION (matches fetch_data.py patterns)
# =============================================================================

ESPN_DB_PATH = "espn_wp.db"
SEASON = "2025-26"
SEASON_YEAR = 2026  # ESPN uses end year (2025-26 season = 2026)
API_DELAY = 0.3

# ESPN team IDs for roster endpoint
ESPN_TEAM_IDS = {
    "ATL": 1, "BOS": 2, "BKN": 17, "CHA": 30, "CHI": 4,
    "CLE": 5, "DAL": 6, "DEN": 7, "DET": 8, "GSW": 9,
    "HOU": 10, "IND": 11, "LAC": 12, "LAL": 13, "MEM": 29,
    "MIA": 14, "MIL": 15, "MIN": 16, "NOP": 3, "NYK": 18,
    "OKC": 25, "ORL": 19, "PHI": 20, "PHX": 21, "POR": 22,
    "SAC": 23, "SAS": 24, "TOR": 28, "UTA": 26, "WAS": 27
}

# ESPN abbreviation -> NBA abbreviation (from fetch_data.py)
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

# NBA Team ID mapping (from fetch_data.py)
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


# =============================================================================
# DATABASE (into espn_wp.db alongside wp_plays)
# =============================================================================

def ensure_schema(conn):
    """Create player_fouls table in espn_wp.db."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_fouls (
            espn_player_id TEXT PRIMARY KEY,
            nba_player_id INTEGER,
            player_name TEXT,
            team_abbrev TEXT,
            nba_team_id INTEGER,
            season TEXT,
            technical_fouls INTEGER DEFAULT 0,
            flagrant_fouls INTEGER DEFAULT 0,
            ejections INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fouls_nba_id ON player_fouls(nba_player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fouls_team ON player_fouls(team_abbrev)")
    conn.commit()


def get_existing_players(conn):
    """Get dict of espn_player_id -> last updated timestamp."""
    try:
        cursor = conn.execute("SELECT espn_player_id, updated_at FROM player_fouls WHERE season = ?", (SEASON,))
        return {row[0]: row[1] for row in cursor.fetchall()}
    except:
        return {}


# =============================================================================
# ESPN API FUNCTIONS
# =============================================================================

def fetch_team_roster(nba_team_abbrev):
    """Fetch roster for a team from ESPN. Takes NBA abbrev (GSW), uses ESPN team ID."""
    espn_team_id = ESPN_TEAM_IDS.get(nba_team_abbrev)
    if not espn_team_id:
        return []
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{espn_team_id}/roster"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        players = []
        
        for athlete in data.get('athletes', []):
            players.append({
                'espn_id': athlete['id'],
                'name': athlete['displayName'],
                'team_abbrev': nba_team_abbrev  # Store in NBA format
            })
        
        return players
    except Exception as e:
        print(f"    Error fetching {nba_team_abbrev} roster: {e}")
        return []


def fetch_player_stats(espn_player_id):
    """
    Fetch player stats from ESPN.
    Returns dict with tech/flagrant/ejection counts for current season, or None.
    """
    url = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{espn_player_id}/stats"
    params = {"region": "us", "lang": "en", "contentorigin": "espn"}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        result = {'technical_fouls': 0, 'flagrant_fouls': 0, 'ejections': 0, 'games_played': 0}
        
        for cat in data.get('categories', []):
            cat_name = cat.get('name')
            labels = cat.get('labels', [])
            
            # Get games played from averages
            if cat_name == 'averages' and 'GP' in labels:
                gp_idx = labels.index('GP')
                for stat_row in cat.get('statistics', []):
                    if stat_row.get('season', {}).get('year') == SEASON_YEAR:
                        stats = stat_row.get('stats', [])
                        if gp_idx < len(stats):
                            result['games_played'] = int(stats[gp_idx])
                        break
            
            # Get techs/flagrants from miscellaneous
            if cat_name == 'miscellaneous':
                tech_idx = labels.index('TECH') if 'TECH' in labels else None
                flag_idx = labels.index('FLAG') if 'FLAG' in labels else None
                eject_idx = labels.index('EJECT') if 'EJECT' in labels else None
                
                for stat_row in cat.get('statistics', []):
                    if stat_row.get('season', {}).get('year') == SEASON_YEAR:
                        stats = stat_row.get('stats', [])
                        if tech_idx is not None and tech_idx < len(stats):
                            result['technical_fouls'] = int(stats[tech_idx])
                        if flag_idx is not None and flag_idx < len(stats):
                            result['flagrant_fouls'] = int(stats[flag_idx])
                        if eject_idx is not None and eject_idx < len(stats):
                            result['ejections'] = int(stats[eject_idx])
                        break
        
        # Only return if player has played this season
        if result['games_played'] > 0:
            return result
        return None
        
    except Exception as e:
        return None


# =============================================================================
# NAME MATCHING FOR NBA IDs
# =============================================================================

def normalize_name(name):
    """Normalize player name for matching."""
    if not name:
        return ""
    # Remove accents, lowercase, remove suffixes
    name = name.lower().strip()
    # Remove Jr., Sr., III, II, etc.
    name = re.sub(r'\s+(jr\.?|sr\.?|iii|ii|iv)$', '', name, flags=re.IGNORECASE)
    # Remove periods and extra spaces
    name = re.sub(r'\.', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def build_nba_player_lookup():
    """
    Build NBA player ID lookup from nba_api.
    Returns dict: normalized_name -> nba_player_id
    """
    try:
        from nba_api.stats.static import players
        all_players = players.get_active_players()
        
        lookup = {}
        for p in all_players:
            norm_name = normalize_name(p['full_name'])
            lookup[norm_name] = p['id']
        
        return lookup
    except Exception as e:
        print(f"  Warning: Could not load NBA players: {e}")
        return {}


# =============================================================================
# MAIN FETCH LOGIC
# =============================================================================

def run_fetch(force_refresh=False):
    """Main fetch routine."""
    print("=" * 60)
    print(f"ESPN PLAYER FOULS FETCHER - Season {SEASON}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    conn = sqlite3.connect(ESPN_DB_PATH)
    ensure_schema(conn)
    
    existing = get_existing_players(conn)
    print(f"  Existing players in DB: {len(existing)}")
    
    # Build NBA player lookup for ID matching
    print("  Loading NBA player lookup...")
    nba_lookup = build_nba_player_lookup()
    print(f"  NBA players loaded: {len(nba_lookup)}")
    
    # Fetch all team rosters (iterate NBA abbrevs)
    print("\n  Fetching team rosters...")
    all_players = []
    for team_abbrev in sorted(ESPN_TEAM_IDS.keys()):
        roster = fetch_team_roster(team_abbrev)
        all_players.extend(roster)
        print(f"    {team_abbrev}: {len(roster)} players")
        time.sleep(API_DELAY)
    
    print(f"\n  Total players: {len(all_players)}")
    
    # Fetch stats for each player
    print("\n  Fetching player stats...")
    updated = 0
    skipped = 0
    no_stats = 0
    
    for i, player in enumerate(all_players, 1):
        espn_id = player['espn_id']
        name = player['name']
        team = player['team_abbrev']  # Already in NBA format
        
        # Skip if recently updated (unless force refresh)
        if not force_refresh and espn_id in existing:
            skipped += 1
            continue
        
        # Match to NBA player ID
        norm_name = normalize_name(name)
        nba_id = nba_lookup.get(norm_name)
        nba_team_id = TEAMS.get(team)
        
        # Fetch stats (single call gets both GP and techs)
        stats = fetch_player_stats(espn_id)
        
        if stats:
            conn.execute("""
                INSERT OR REPLACE INTO player_fouls 
                (espn_player_id, nba_player_id, player_name, team_abbrev, nba_team_id,
                 season, technical_fouls, flagrant_fouls, ejections, games_played, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                espn_id, nba_id, name, team, nba_team_id,
                SEASON,
                stats['technical_fouls'],
                stats['flagrant_fouls'],
                stats['ejections'],
                stats['games_played'],
                datetime.now().isoformat()
            ))
            
            if stats['technical_fouls'] > 0 or stats['flagrant_fouls'] > 0:
                print(f"    [{i}/{len(all_players)}] {name} ({team}): {stats['technical_fouls']}T {stats['flagrant_fouls']}F")
            
            updated += 1
        else:
            # Player has no stats this season (rookie, injured, etc.)
            no_stats += 1
        
        if i % 50 == 0:
            conn.commit()
            print(f"    Progress: {i}/{len(all_players)} ({updated} updated, {no_stats} no stats)")
        
        time.sleep(API_DELAY)
    
    conn.commit()
    
    # Summary
    total = conn.execute("SELECT COUNT(*) FROM player_fouls WHERE season = ?", (SEASON,)).fetchone()[0]
    with_techs = conn.execute("SELECT COUNT(*) FROM player_fouls WHERE season = ? AND technical_fouls > 0", (SEASON,)).fetchone()[0]
    with_flags = conn.execute("SELECT COUNT(*) FROM player_fouls WHERE season = ? AND flagrant_fouls > 0", (SEASON,)).fetchone()[0]
    total_techs = conn.execute("SELECT SUM(technical_fouls) FROM player_fouls WHERE season = ?", (SEASON,)).fetchone()[0] or 0
    total_flags = conn.execute("SELECT SUM(flagrant_fouls) FROM player_fouls WHERE season = ?", (SEASON,)).fetchone()[0] or 0
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Players updated: {updated}")
    print(f"  Players skipped (already in DB): {skipped}")
    print(f"  Players with no stats: {no_stats}")
    print(f"  Total in DB: {total}")
    print(f"  Players with techs: {with_techs} (total: {total_techs})")
    print(f"  Players with flagrants: {with_flags} (total: {total_flags})")
    
    # Show tech leaders
    print("\n  Tech Leaders:")
    for row in conn.execute("""
        SELECT player_name, team_abbrev, technical_fouls, flagrant_fouls, games_played
        FROM player_fouls WHERE season = ? AND technical_fouls > 0
        ORDER BY technical_fouls DESC LIMIT 10
    """, (SEASON,)).fetchall():
        name, team, techs, flags, gp = row
        print(f"    {techs:2d}T {flags}F  {name} ({team}) - {gp} GP")
    
    conn.close()
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    force = '--refresh' in sys.argv
    run_fetch(force_refresh=force)
