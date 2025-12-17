"""
================================================================================
FETCH PLAYER FOULS - FOX SPORTS
================================================================================

PURPOSE:
    Scrapes technical and flagrant foul data from Fox Sports player pages.
    More accurate than ESPN API which has known data gaps.

SOURCE:
    Fox Sports player stats pages
    URL pattern: foxsports.com/nba/{firstname}-{lastname}-player-stats?category=misc&seasonType=reg
    
    2025-26 row cells:
        Cell 10 = Flagrant fouls
        Cell 11 = Technical fouls

OUTPUT:
    Updates both databases:
        - player_box_scores.db (players table)
        - espn_wp.db (player_fouls table)

USAGE:
    python fetch_player_fouls_fox.py              # Update all players
    python fetch_player_fouls_fox.py --test       # Test with 5 players only
    python fetch_player_fouls_fox.py --player "Stephen Curry"  # Single player

NOTES:
    - Uses 1 second delay between requests to avoid rate limiting
    - ~500 players = ~8-10 minutes
    - Failed lookups logged to fox_fouls_errors.log

================================================================================
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import unicodedata
import re
import time
import sys
import os
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

BOX_SCORES_DB = "player_box_scores.db"
ESPN_DB = "espn_wp.db"
SEASON = "2025-26"
REQUEST_DELAY = 1.0  # seconds between requests (be nice to Fox)
ERROR_LOG = "fox_fouls_errors.log"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# =============================================================================
# NAME TO URL SLUG CONVERSION
# =============================================================================

def name_to_slug(name):
    """
    Convert player name to Fox Sports URL slug.
    
    Examples:
        Nikola Jokić → nikola-jokic
        Luka Dončić → luka-doncic
        Kelly Oubre Jr. → kelly-oubre-jr
        Shai Gilgeous-Alexander → shai-gilgeous-alexander
        Royce O'Neale → royce-oneale
    """
    if not name:
        return ""
    
    # Lowercase
    slug = name.lower().strip()
    
    # Strip accents: Jokić → jokic
    slug = unicodedata.normalize('NFD', slug)
    slug = ''.join(c for c in slug if unicodedata.category(c) != 'Mn')
    
    # Remove apostrophes: O'Neale → oneale
    slug = slug.replace("'", "")
    
    # Remove periods: Jr. → Jr
    slug = slug.replace(".", "")
    
    # Replace spaces with hyphens
    slug = slug.replace(" ", "-")
    
    # Clean up multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Remove trailing hyphens
    slug = slug.strip('-')
    
    return slug


def build_fox_url(player_name):
    """Build Fox Sports URL for player."""
    slug = name_to_slug(player_name)
    return f"https://www.foxsports.com/nba/{slug}-player-stats?category=misc&seasonType=reg"


# =============================================================================
# SCRAPING
# =============================================================================

def fetch_fouls_from_fox(player_name):
    """
    Fetch tech and flagrant foul counts from Fox Sports.
    
    Returns:
        (tech, flag, error) tuple
        - On success: (int, int, None)
        - On failure: (None, None, error_message)
    """
    url = build_fox_url(player_name)
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        
        if resp.status_code == 404:
            return (None, None, f"404 Not Found: {url}")
        
        if resp.status_code != 200:
            return (None, None, f"HTTP {resp.status_code}: {url}")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find all table rows
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if cells and len(cells) >= 12 and SEASON in cells[0].text:
                # Cell 10 = FLAG, Cell 11 = TECH
                flag_text = cells[10].text.strip()
                tech_text = cells[11].text.strip()
                
                # Handle "-" or empty values
                flag = int(flag_text) if flag_text.isdigit() else 0
                tech = int(tech_text) if tech_text.isdigit() else 0
                
                return (tech, flag, None)
        
        # No 2025-26 row found (player hasn't played this season)
        return (None, None, f"No {SEASON} data found")
        
    except requests.exceptions.Timeout:
        return (None, None, f"Timeout: {url}")
    except requests.exceptions.RequestException as e:
        return (None, None, f"Request error: {str(e)}")
    except Exception as e:
        return (None, None, f"Parse error: {str(e)}")


# =============================================================================
# DATABASE UPDATES
# =============================================================================

def get_all_players():
    """Get all players from box scores DB."""
    conn = sqlite3.connect(BOX_SCORES_DB)
    players = conn.execute("""
        SELECT player_id, player_name, technical_fouls, flagrant_fouls 
        FROM players
        ORDER BY player_name
    """).fetchall()
    conn.close()
    return players


def update_box_scores_db(player_id, tech, flag):
    """Update fouls in player_box_scores.db."""
    conn = sqlite3.connect(BOX_SCORES_DB)
    conn.execute("""
        UPDATE players 
        SET technical_fouls = ?, flagrant_fouls = ?
        WHERE player_id = ?
    """, (tech, flag, player_id))
    conn.commit()
    conn.close()


def update_espn_db(player_name, tech, flag):
    """Update fouls in espn_wp.db (if table exists)."""
    if not os.path.exists(ESPN_DB):
        return
    
    conn = sqlite3.connect(ESPN_DB)
    
    # Check if table exists
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_fouls'"
    ).fetchone()
    
    if table_exists:
        # Try to update by name
        conn.execute("""
            UPDATE player_fouls 
            SET technical_fouls = ?, flagrant_fouls = ?
            WHERE player_name = ? AND season = ?
        """, (tech, flag, player_name, SEASON))
        conn.commit()
    
    conn.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("FETCH PLAYER FOULS - FOX SPORTS")
    print("=" * 70)
    print(f"Season: {SEASON}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Delay: {REQUEST_DELAY}s between requests")
    print()
    
    # Parse arguments
    test_mode = '--test' in sys.argv
    single_player = None
    if '--player' in sys.argv:
        idx = sys.argv.index('--player')
        if idx + 1 < len(sys.argv):
            single_player = sys.argv[idx + 1]
    
    # Get players
    players = get_all_players()
    print(f"Total players in DB: {len(players)}")
    
    if single_player:
        players = [(p[0], p[1], p[2], p[3]) for p in players if single_player.lower() in p[1].lower()]
        print(f"Filtered to: {len(players)} matching '{single_player}'")
    elif test_mode:
        players = players[:5]
        print(f"TEST MODE: Processing only {len(players)} players")
    
    print()
    print("-" * 70)
    
    # Track results
    success_count = 0
    error_count = 0
    changed_count = 0
    errors = []
    
    for i, (player_id, player_name, old_tech, old_flag) in enumerate(players):
        # Progress
        print(f"[{i+1}/{len(players)}] {player_name}...", end=" ", flush=True)
        
        # Fetch from Fox
        tech, flag, error = fetch_fouls_from_fox(player_name)
        
        if error:
            print(f"ERROR: {error}")
            errors.append((player_name, error))
            error_count += 1
        else:
            # Check if changed
            old_tech = old_tech or 0
            old_flag = old_flag or 0
            changed = (tech != old_tech) or (flag != old_flag)
            
            if changed:
                print(f"UPDATED: {old_tech}T {old_flag}F → {tech}T {flag}F")
                changed_count += 1
            else:
                print(f"OK: {tech}T {flag}F")
            
            # Update databases
            update_box_scores_db(player_id, tech, flag)
            update_espn_db(player_name, tech, flag)
            success_count += 1
        
        # Delay between requests (skip on last one)
        if i < len(players) - 1:
            time.sleep(REQUEST_DELAY)
    
    # Write error log
    if errors:
        with open(ERROR_LOG, 'w') as f:
            f.write(f"Fox Sports Foul Fetch Errors - {datetime.now().isoformat()}\n")
            f.write(f"Season: {SEASON}\n")
            f.write("-" * 50 + "\n")
            for name, err in errors:
                f.write(f"{name}: {err}\n")
        print(f"\nErrors logged to {ERROR_LOG}")
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total processed: {len(players)}")
    print(f"  Successful: {success_count}")
    print(f"  Changed: {changed_count}")
    print(f"  Errors: {error_count}")
    
    if changed_count > 0:
        print()
        print("Run compute_player_stats.py to recalculate Ethical Hoops scores.")
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
