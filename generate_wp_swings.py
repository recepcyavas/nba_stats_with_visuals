"""
================================================================================
GENERATE WP SWINGS HTML
================================================================================

PURPOSE:
    Generates standalone HTML dashboard for Win Probability Swings analysis.
    Shows biggest game-changing plays with YouTube video links.

INPUT:
    unified_display.json - requires _wp_swings and _wp_swings_youtube sections

OUTPUT:
    wp_swings_dashboard.html

================================================================================
"""

import json

INPUT_PATH = "unified_display.json"
OUTPUT_PATH = "wp_swings_dashboard.html"


def generate_html():
    print("=" * 60)
    print("GENERATE WP SWINGS HTML")
    print("=" * 60)
    
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    wp_swings = data.get("_wp_swings", {})
    wp_youtube = data.get("_wp_swings_youtube", {})
    game_excitement = data.get("_game_excitement", {})
    
    plays = wp_youtube.get("plays", [])
    leaderboard = wp_swings.get("player_leaderboard", [])
    excitement_games = game_excitement.get("games", [])
    
    print(f"Loaded {len(plays)} WP swings with YouTube links")
    print(f"Loaded {len(leaderboard)} players in leaderboard")
    print(f"Loaded {len(excitement_games)} games with excitement index")
    
    # Escape for safe JavaScript embedding
    def js_escape(obj):
        s = json.dumps(obj, ensure_ascii=True)
        # Escape </script> to prevent breaking out of script tag
        s = s.replace('</script>', '<\\/script>')
        return s
    
    plays_json = js_escape(plays)
    leaderboard_json = js_escape(leaderboard)
    excitement_json = js_escape(excitement_games)
    
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>NBA Win Probability Swings 2025-26</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%); 
            color: white; 
            min-height: 100vh;
            padding: 30px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 2.5rem;
            background: linear-gradient(90deg, #007AC1, #4ade80);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .header .subtitle {
            color: #888;
            font-size: 1.1rem;
        }
        
        .main-container {
            display: flex;
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .swings-container {
            flex: 1;
        }
        
        .sidebar {
            width: 350px;
            flex-shrink: 0;
        }
        
        /* Swing Cards */
        .swing-card {
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 15px;
            display: flex;
            gap: 18px;
            align-items: center;
            border-left: 5px solid #007AC1;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .swing-card:hover {
            transform: translateX(8px);
            box-shadow: 0 8px 30px rgba(0,122,193,0.25);
            border-left-color: #4ade80;
        }
        
        .swing-rank {
            font-size: 1.8rem;
            font-weight: 800;
            color: #007AC1;
            min-width: 50px;
            text-align: center;
        }
        
        .swing-delta {
            min-width: 90px;
            text-align: center;
        }
        .swing-delta-value {
            font-size: 1.5rem;
            font-weight: 700;
        }
        .swing-delta-value.positive { color: #4ade80; }
        .swing-delta-value.negative { color: #f87171; }
        .swing-delta-label {
            font-size: 0.7rem;
            color: #666;
            text-transform: uppercase;
        }
        
        .swing-headshot {
            width: 70px;
            height: 52px;
            border-radius: 6px;
            overflow: hidden;
            background: #0a1628;
            flex-shrink: 0;
        }
        .swing-headshot img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .swing-info {
            flex: 1;
        }
        .swing-play {
            font-size: 1rem;
            color: #fff;
            margin-bottom: 6px;
            line-height: 1.4;
        }
        .swing-play .player-name {
            color: #4ade80;
            font-weight: 600;
        }
        .swing-meta {
            font-size: 0.8rem;
            color: #888;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        .swing-meta span {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .swing-wp {
            text-align: center;
            min-width: 130px;
        }
        .swing-wp-label {
            font-size: 0.7rem;
            color: #666;
            margin-bottom: 5px;
            text-transform: uppercase;
        }
        .swing-wp-bar {
            width: 120px;
            height: 28px;
            background: #0a1628;
            border-radius: 6px;
            position: relative;
            overflow: hidden;
            border: 1px solid #333;
        }
        .swing-wp-fill {
            height: 100%;
            border-radius: 5px;
            transition: width 0.5s ease;
        }
        .swing-wp-fill.positive { background: linear-gradient(90deg, #166534, #4ade80); }
        .swing-wp-fill.negative { background: linear-gradient(90deg, #991b1b, #f87171); }
        .swing-wp-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 0.8rem;
            font-weight: 700;
            color: #fff;
            text-shadow: 0 1px 3px rgba(0,0,0,0.8);
            white-space: nowrap;
        }
        
        .swing-youtube a {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: linear-gradient(135deg, #ff0000, #cc0000);
            color: white;
            padding: 10px 16px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s;
        }
        .swing-youtube a:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(255,0,0,0.4);
        }
        .swing-youtube .yt-icon {
            font-size: 1.1rem;
        }
        
        /* Sidebar */
        .sidebar-section {
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .sidebar-section h3 {
            color: #007AC1;
            font-size: 1.1rem;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #007AC1;
        }
        
        .leaderboard-item {
            display: flex;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #2a3a5a;
            transition: background 0.2s;
        }
        .leaderboard-item:hover {
            background: rgba(0,122,193,0.1);
            margin: 0 -10px;
            padding: 12px 10px;
            border-radius: 6px;
        }
        .leaderboard-item:last-child { border-bottom: none; }
        
        .lb-rank {
            width: 35px;
            font-size: 1rem;
            font-weight: 700;
            color: #007AC1;
        }
        .lb-rank.top3 { color: #fbbf24; }
        
        .lb-name {
            flex: 1;
            font-size: 0.95rem;
            color: #fff;
        }
        
        .lb-stats {
            text-align: right;
        }
        .lb-score {
            font-size: 1.1rem;
            font-weight: 700;
            color: #4ade80;
        }
        .lb-plays {
            font-size: 0.75rem;
            color: #888;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        .stat-box {
            background: #0a1628;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #4ade80;
        }
        .stat-label {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            margin-top: 4px;
        }
        
        /* Filter Buttons */
        .filter-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-btn {
            background: #0f3460;
            color: #ccc;
            border: 2px solid #333;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        .filter-btn:hover { border-color: #007AC1; color: #fff; }
        .filter-btn.active { 
            background: #007AC1; 
            border-color: #007AC1; 
            color: #fff;
        }
        
        /* Tabs */
        .tab-nav {
            display: flex;
            gap: 0;
            margin-bottom: 25px;
            border-bottom: 2px solid #333;
        }
        .tab-btn {
            background: transparent;
            color: #888;
            border: none;
            padding: 12px 24px;
            font-size: 1rem;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }
        .tab-btn:hover { color: #fff; }
        .tab-btn.active {
            color: #007AC1;
            border-bottom-color: #007AC1;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Excitement cards */
        .excitement-card {
            display: flex;
            align-items: center;
            gap: 15px;
            background: linear-gradient(135deg, #16213e 0%, #1a2744 100%);
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 12px;
            border: 1px solid #2a3a5a;
        }
        .excitement-rank {
            font-size: 1.1rem;
            font-weight: 700;
            color: #007AC1;
            min-width: 45px;
        }
        .excitement-rank.top3 { color: #fbbf24; }
        .excitement-score {
            min-width: 100px;
            text-align: center;
        }
        .excitement-value {
            font-size: 1.4rem;
            font-weight: 700;
            color: #4ade80;
        }
        .excitement-label {
            font-size: 0.65rem;
            color: #666;
            text-transform: uppercase;
        }
        .excitement-info { flex: 1; }
        .excitement-matchup {
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 4px;
        }
        .excitement-meta {
            font-size: 0.8rem;
            color: #888;
            display: flex;
            gap: 12px;
        }
        .excitement-bar {
            width: 120px;
            height: 8px;
            background: #0a1628;
            border-radius: 4px;
            overflow: hidden;
        }
        .excitement-fill {
            height: 100%;
            background: linear-gradient(90deg, #166534, #4ade80);
            border-radius: 4px;
        }
        .excitement-stats {
            text-align: right;
            min-width: 100px;
        }
        .excitement-stats div {
            font-size: 0.8rem;
            color: #888;
        }
        .excitement-stats span {
            color: #4ade80;
            font-weight: 600;
        }
        
        /* Excitement sidebar */
        .excitement-summary .stat-box {
            text-align: center;
        }
        
        /* WP Chart Tooltip */
        .wp-chart-tooltip {
            display: none;
            position: fixed;
            background: #0a1628;
            border: 2px solid #007AC1;
            border-radius: 12px;
            padding: 15px;
            z-index: 1000;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
        .wp-chart-tooltip.visible { display: block; }
        .wp-chart-header {
            text-align: center;
            margin-bottom: 10px;
            font-size: 0.9rem;
            color: #888;
        }
        .wp-chart-header strong {
            color: #fff;
            font-size: 1rem;
        }
        .wp-chart-canvas {
            display: block;
        }
        .wp-chart-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            margin-top: 5px;
        }
        .wp-chart-labels .home-label { color: #4ade80; }
        .wp-chart-labels .away-label { color: #f87171; }
        
        /* Responsive */
        @media (max-width: 1100px) {
            .main-container { flex-direction: column; }
            .sidebar { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏀 Win Probability Analysis</h1>
        <div class="subtitle">NBA 2025-26 • Game-changing plays & excitement rankings</div>
    </div>
    
    <div class="tab-nav">
        <button class="tab-btn active" data-tab="swings">⚡ WP Swings</button>
        <button class="tab-btn" data-tab="excitement">🔥 Game Excitement</button>
    </div>
    
    <!-- WP SWINGS TAB -->
    <div id="tab-swings" class="tab-content active">
    <div class="main-container">
        <div class="swings-container">
            <div class="filter-bar">
                <button class="filter-btn active" data-filter="all">All Plays</button>
                <button class="filter-btn" data-filter="positive">Home Team ↑</button>
                <button class="filter-btn" data-filter="negative">Away Team ↑</button>
                <button class="filter-btn" data-filter="buzzer">Buzzer Beaters</button>
            </div>
            <div id="swings-list"></div>
        </div>
        
        <div class="sidebar">
            <div class="sidebar-section">
                <h3>📊 Summary Stats</h3>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value" id="stat-total">0</div>
                        <div class="stat-label">Total Plays</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="stat-max">0%</div>
                        <div class="stat-label">Max Swing</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="stat-videos">0</div>
                        <div class="stat-label">With Video</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="stat-ot">0</div>
                        <div class="stat-label">In OT</div>
                    </div>
                </div>
            </div>
            
            <div class="sidebar-section">
                <h3>🏆 Clutch Player Leaderboard</h3>
                <div id="leaderboard"></div>
            </div>
        </div>
    </div>
    </div><!-- end tab-swings -->
    
    <!-- GAME EXCITEMENT TAB -->
    <div id="tab-excitement" class="tab-content">
    <div class="main-container">
        <div class="swings-container">
            <div class="filter-bar">
                <button class="filter-btn active" data-filter="all-exc">All Games</button>
                <button class="filter-btn" data-filter="top50">Top 50</button>
                <button class="filter-btn" data-filter="bottom50">Bottom 50</button>
                <button class="filter-btn" data-filter="overtime">Overtime</button>
            </div>
            <div id="excitement-list"></div>
        </div>
        
        <div class="sidebar">
            <div class="sidebar-section excitement-summary">
                <h3>📊 Excitement Stats</h3>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value" id="exc-total">0</div>
                        <div class="stat-label">Games</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="exc-avg">0</div>
                        <div class="stat-label">Avg bit-min</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="exc-max">0</div>
                        <div class="stat-label">Max</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="exc-ot">0</div>
                        <div class="stat-label">OT Games</div>
                    </div>
                </div>
            </div>
            
            <div class="sidebar-section">
                <h3>📈 Distribution</h3>
                <div id="exc-distribution"></div>
            </div>
        </div>
    </div>
    </div><!-- end tab-excitement -->
    
    <!-- WP Chart Tooltip -->
    <div id="wp-chart-tooltip" class="wp-chart-tooltip">
        <div class="wp-chart-header"><strong id="chart-matchup"></strong><br><span id="chart-date"></span></div>
        <canvas id="wp-chart-canvas" class="wp-chart-canvas" width="350" height="180"></canvas>
        <div class="wp-chart-labels">
            <span class="away-label" id="chart-away-label"></span>
            <span style="color:#666">Win Probability</span>
            <span class="home-label" id="chart-home-label"></span>
        </div>
    </div>
    
    <script>
var plays = ''' + plays_json + ''';
var leaderboard = ''' + leaderboard_json + ''';
var excitementGames = ''' + excitement_json + ''';
var currentFilter = 'all';
var currentExcFilter = 'all-exc';

function highlightPlayer(text) {
    if (!text) return '';
    var parts = text.split(/ makes | blocks /);
    if (parts.length > 1) {
        var action = text.includes(' makes ') ? ' makes ' : ' blocks ';
        return '<span class="player-name">' + parts[0] + '</span>' + action + parts.slice(1).join(action);
    }
    return text;
}

function renderSwings() {
    var container = document.getElementById('swings-list');
    var filtered = plays;
    
    if (currentFilter === 'positive') {
        filtered = plays.filter(p => p.wp_delta > 0);
    } else if (currentFilter === 'negative') {
        filtered = plays.filter(p => p.wp_delta < 0);
    } else if (currentFilter === 'buzzer') {
        filtered = plays.filter(function(p) {
            if (!p.time_display) return false;
            var match = p.time_display.match(/(\d+):(\d+)/);
            if (!match) return false;
            var mins = parseInt(match[1]);
            var secs = parseInt(match[2]);
            var totalSecs = mins * 60 + secs;
            
            // Regulation buzzer: 47:59 (2879s) or 48:00 (2880s)
            if (totalSecs === 2879 || totalSecs === 2880) return true;
            
            // OT buzzer: last second of each OT
            if (p.period > 4) {
                var otEndSecs = (48 + (p.period - 4) * 5) * 60;
                if (totalSecs === otEndSecs - 1 || totalSecs === otEndSecs) return true;
            }
            return false;
        });
    }
    
    if (!filtered.length) {
        container.innerHTML = '<p style="color: #888; text-align: center; padding: 40px;">No plays match this filter</p>';
        return;
    }
    
    var html = '';
    filtered.forEach(function(p, idx) {
        var deltaClass = p.wp_delta > 0 ? 'positive' : 'negative';
        var deltaStr = (p.wp_delta > 0 ? '+' : '') + (p.wp_delta * 100).toFixed(1) + '%';
        var wpBefore = Math.round(p.wp_before * 100);
        var wpAfter = Math.round(p.wp_after * 100);
        var fillClass = p.wp_delta > 0 ? 'positive' : 'negative';
        
        html += '<div class="swing-card">';
        html += '<div class="swing-rank">#' + p.rank + '</div>';
        html += '<div class="swing-delta">';
        html += '<div class="swing-delta-value ' + deltaClass + '">' + deltaStr + '</div>';
        html += '<div class="swing-delta-label">WP Swing</div>';
        html += '</div>';
        // Player headshot
        if (p.player_id) {
            html += "<div class=\\"swing-headshot\\">";
            html += "<img src=\\"https://cdn.nba.com/headshots/nba/latest/1040x760/" + p.player_id + ".png\\">";
            html += "</div>";
        }
        html += '<div class="swing-info">';
        html += '<div class="swing-play">' + highlightPlayer(p.play_text || 'Unknown') + '</div>';
        html += '<div class="swing-meta">';
        html += '<span>🏟️ ' + (p.matchup || '') + '</span>';
        html += '<span>📅 ' + (p.date || '') + '</span>';
        html += '<span>⏱️ ' + (p.time_display || '') + '</span>';
        html += '<span>📊 ' + (p.score_at_play || '') + '</span>';
        html += '</div>';
        html += '</div>';
        html += '<div class="swing-wp">';
        html += '<div class="swing-wp-label">Win Probability</div>';
        html += '<div class="swing-wp-bar">';
        html += '<div class="swing-wp-fill ' + fillClass + '" style="width: ' + wpAfter + '%;"></div>';
        html += '<div class="swing-wp-text">' + wpBefore + '% → ' + wpAfter + '%</div>';
        html += '</div>';
        html += '</div>';
        if (p.youtube_url) {
            html += '<div class="swing-youtube">';
            html += '<a href="' + p.youtube_url + '" target="_blank"><span class="yt-icon">▶</span> Watch</a>';
            html += '</div>';
        }
        html += '</div>';
    });
    
    container.innerHTML = html;
}

function renderLeaderboard() {
    var container = document.getElementById('leaderboard');
    
    if (!leaderboard.length) {
        container.innerHTML = '<p style="color: #888;">No data available</p>';
        return;
    }
    
    var html = '';
    leaderboard.slice(0, 15).forEach(function(p, i) {
        var rankClass = i < 3 ? 'top3' : '';
        html += '<div class="leaderboard-item">';
        html += '<div class="lb-rank ' + rankClass + '">' + (i + 1) + '</div>';
        html += '<div class="lb-name">' + p.player + '</div>';
        html += '<div class="lb-stats">';
        html += '<div class="lb-score">' + p.weighted_score.toFixed(2) + '</div>';
        html += '<div class="lb-plays">' + p.clutch_plays + ' play' + (p.clutch_plays > 1 ? 's' : '') + ' • max ' + (p.max_swing * 100).toFixed(0) + '%</div>';
        html += '</div>';
        html += '</div>';
    });
    
    container.innerHTML = html;
}

function updateStats() {
    document.getElementById('stat-total').textContent = plays.length;
    
    var maxSwing = plays.reduce(function(max, p) {
        return Math.abs(p.wp_delta) > max ? Math.abs(p.wp_delta) : max;
    }, 0);
    document.getElementById('stat-max').textContent = (maxSwing * 100).toFixed(1) + '%';
    
    var withVideo = plays.filter(function(p) { return p.youtube_url; }).length;
    document.getElementById('stat-videos').textContent = withVideo;
    
    var inOT = plays.filter(function(p) { return p.period > 4; }).length;
    document.getElementById('stat-ot').textContent = inOT;
}

// ==================== EXCITEMENT TAB ====================

function renderExcitement() {
    var container = document.getElementById('excitement-list');
    var filtered = excitementGames;
    
    if (currentExcFilter === 'top50') {
        filtered = excitementGames.slice(0, 50);
    } else if (currentExcFilter === 'bottom50') {
        filtered = excitementGames.slice(-50).reverse();
    } else if (currentExcFilter === 'overtime') {
        filtered = excitementGames.filter(function(g) { return g.game_length > 50; });
    }
    
    if (!filtered.length) {
        container.innerHTML = '<p style="color: #888; text-align: center; padding: 40px;">No games match this filter</p>';
        return;
    }
    
    var maxExc = excitementGames[0].excitement_raw;
    var html = '';
    
    filtered.forEach(function(g, idx) {
        var rankClass = g.rank <= 3 ? 'top3' : '';
        var barWidth = Math.min(100, (g.excitement_raw / maxExc) * 100);
        
        // Convert game length to OT display
        var otDisplay = 'No OT';
        if (g.game_length > 50) {
            var numOT = Math.round((g.game_length - 48) / 5);
            otDisplay = numOT + ' OT';
        }
        
        html += '<div class="excitement-card" data-rank="' + g.rank + '">';
        html += '<div class="excitement-rank ' + rankClass + '">#' + g.rank + '</div>';
        html += '<div class="excitement-score">';
        html += '<div class="excitement-value">' + g.excitement_raw.toFixed(1) + '</div>';
        html += '<div class="excitement-label">bit-minutes</div>';
        html += '</div>';
        html += '<div class="excitement-info">';
        html += '<div class="excitement-matchup">' + g.matchup + '</div>';
        html += '<div class="excitement-meta">';
        html += '<span>📅 ' + g.date + '</span> ';
        html += '<span>🏁 ' + g.final_score + '</span> ';
        html += '<span>⏱️ ' + otDisplay + '</span>';
        html += '</div>';
        html += '</div>';
        html += '<div class="excitement-bar"><div class="excitement-fill" style="width:' + barWidth + '%"></div></div>';
        html += '<div class="excitement-stats">';
        html += '<div><span>' + g.lead_changes + '</span> lead changes</div>';
        html += '<div><span>' + g.time_close.toFixed(0) + '</span> min close</div>';
        html += '</div>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    
    // Add hover listeners for WP chart
    container.querySelectorAll('.excitement-card').forEach(function(card) {
        card.addEventListener('mouseenter', function(e) {
            var rank = parseInt(this.dataset.rank);
            showWPChart(e, rank);
        });
        card.addEventListener('mousemove', function(e) {
            var rank = parseInt(this.dataset.rank);
            showWPChart(e, rank);
        });
        card.addEventListener('mouseleave', function() {
            hideWPChart();
        });
    });
}

function updateExcStats() {
    document.getElementById('exc-total').textContent = excitementGames.length;
    
    var sum = excitementGames.reduce(function(s, g) { return s + g.excitement_raw; }, 0);
    var avg = sum / excitementGames.length;
    document.getElementById('exc-avg').textContent = avg.toFixed(1);
    
    document.getElementById('exc-max').textContent = excitementGames[0].excitement_raw.toFixed(1);
    
    var otGames = excitementGames.filter(function(g) { return g.game_length > 50; }).length;
    document.getElementById('exc-ot').textContent = otGames;
    
    // Distribution
    var brackets = [[0,20,'😴'],[20,30,''],[30,40,''],[40,50,'🔥'],[50,100,'🔥🔥']];
    var distHtml = '';
    brackets.forEach(function(b) {
        var count = excitementGames.filter(function(g) { return g.excitement_raw >= b[0] && g.excitement_raw < b[1]; }).length;
        var pct = (count / excitementGames.length * 100).toFixed(0);
        var barW = count / excitementGames.length * 200;
        distHtml += '<div style="margin:8px 0;font-size:0.85rem;">';
        distHtml += '<span style="color:#888;width:60px;display:inline-block;">' + b[0] + '-' + b[1] + '</span>';
        distHtml += '<span style="background:#007AC1;height:12px;width:' + barW + 'px;display:inline-block;border-radius:3px;margin:0 8px;"></span>';
        distHtml += '<span style="color:#4ade80;">' + count + '</span> <span style="color:#666;">(' + pct + '%)</span> ' + b[2];
        distHtml += '</div>';
    });
    document.getElementById('exc-distribution').innerHTML = distHtml;
}

// ==================== EVENT HANDLERS ====================

// Tab switching
document.querySelectorAll('.tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
        document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
        this.classList.add('active');
        document.getElementById('tab-' + this.dataset.tab).classList.add('active');
    });
});

// Filter buttons for swings tab
document.querySelectorAll('#tab-swings .filter-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('#tab-swings .filter-btn').forEach(function(b) { b.classList.remove('active'); });
        this.classList.add('active');
        currentFilter = this.dataset.filter;
        renderSwings();
    });
});

// Filter buttons for excitement tab
document.querySelectorAll('#tab-excitement .filter-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('#tab-excitement .filter-btn').forEach(function(b) { b.classList.remove('active'); });
        this.classList.add('active');
        currentExcFilter = this.dataset.filter;
        renderExcitement();
    });
});

// ==================== WP CHART TOOLTIP ====================

var chartTooltip = document.getElementById('wp-chart-tooltip');
var chartCanvas = document.getElementById('wp-chart-canvas');
var chartCtx = chartCanvas.getContext('2d');

function drawWPChart(game) {
    var timeline = game.wp_timeline || [];
    if (timeline.length < 2) return;
    
    var W = chartCanvas.width;
    var H = chartCanvas.height;
    var pad = {top: 20, right: 30, bottom: 25, left: 15};
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;
    
    // Clear
    chartCtx.fillStyle = '#0a1628';
    chartCtx.fillRect(0, 0, W, H);
    
    // Find time range
    var maxTime = Math.max(48, timeline[timeline.length - 1][0]);
    
    function toX(t) { return pad.left + (t / maxTime) * plotW; }
    function toY(wp) { return pad.top + (1 - wp) * plotH; }
    var y50 = toY(0.5);
    
    // Build expanded timeline with crossing points
    var expanded = [];
    for (var i = 0; i < timeline.length; i++) {
        var t = timeline[i][0], wp = timeline[i][1];
        if (i > 0) {
            var prevT = timeline[i-1][0], prevWp = timeline[i-1][1];
            if ((prevWp - 0.5) * (wp - 0.5) < 0) {
                var tCross = prevT + (0.5 - prevWp) / (wp - prevWp) * (t - prevT);
                expanded.push([tCross, 0.5]);
            }
        }
        expanded.push([t, wp]);
    }
    
    // Draw center line
    chartCtx.strokeStyle = '#444';
    chartCtx.lineWidth = 1;
    chartCtx.setLineDash([4, 4]);
    chartCtx.beginPath();
    chartCtx.moveTo(pad.left, y50);
    chartCtx.lineTo(W - pad.right, y50);
    chartCtx.stroke();
    chartCtx.setLineDash([]);
    
    // Green fill (home): area above 0.5
    chartCtx.fillStyle = 'rgba(74, 222, 128, 0.4)';
    chartCtx.beginPath();
    chartCtx.moveTo(toX(expanded[0][0]), y50);
    for (var i = 0; i < expanded.length; i++) {
        chartCtx.lineTo(toX(expanded[i][0]), toY(Math.max(expanded[i][1], 0.5)));
    }
    chartCtx.lineTo(toX(expanded[expanded.length-1][0]), y50);
    chartCtx.closePath();
    chartCtx.fill();
    
    // Red fill (away): area below 0.5
    chartCtx.fillStyle = 'rgba(248, 113, 113, 0.4)';
    chartCtx.beginPath();
    chartCtx.moveTo(toX(expanded[0][0]), y50);
    for (var i = 0; i < expanded.length; i++) {
        chartCtx.lineTo(toX(expanded[i][0]), toY(Math.min(expanded[i][1], 0.5)));
    }
    chartCtx.lineTo(toX(expanded[expanded.length-1][0]), y50);
    chartCtx.closePath();
    chartCtx.fill();
    
    // Draw WP line on top
    chartCtx.strokeStyle = '#fff';
    chartCtx.lineWidth = 2;
    chartCtx.beginPath();
    chartCtx.moveTo(toX(timeline[0][0]), toY(timeline[0][1]));
    for (var i = 1; i < timeline.length; i++) {
        chartCtx.lineTo(toX(timeline[i][0]), toY(timeline[i][1]));
    }
    chartCtx.stroke();
    
    // X-axis labels
    chartCtx.fillStyle = '#666';
    chartCtx.font = '10px sans-serif';
    chartCtx.textAlign = 'center';
    chartCtx.fillText('0', toX(0), H - 5);
    chartCtx.fillText('12', toX(12), H - 5);
    chartCtx.fillText('24', toX(24), H - 5);
    chartCtx.fillText('36', toX(36), H - 5);
    chartCtx.fillText('48', toX(48), H - 5);
    if (maxTime > 53) {
        chartCtx.fillText('OT', toX(53), H - 5);
    }
    
    // Y-axis labels on right
    chartCtx.textAlign = 'left';
    chartCtx.fillStyle = '#4ade80';
    chartCtx.fillText(game.home_team, W - pad.right + 5, pad.top + 8);
    chartCtx.fillStyle = '#f87171';
    chartCtx.fillText(game.away_team, W - pad.right + 5, H - pad.bottom);
    
    // Update header
    document.getElementById('chart-matchup').textContent = game.matchup;
    document.getElementById('chart-date').textContent = game.date + ' \\u2022 ' + game.final_score;
    document.getElementById('chart-home-label').textContent = game.home_team + ' \\u2191';
    document.getElementById('chart-away-label').textContent = '\\u2193 ' + game.away_team;
}

function showWPChart(e, gameIndex) {
    var game = excitementGames.find(function(g) { return g.rank === gameIndex; });
    if (!game || !game.wp_timeline) return;
    
    drawWPChart(game);
    
    // Position tooltip
    var x = e.clientX + 20;
    var y = e.clientY - 100;
    
    // Keep on screen
    if (x + 380 > window.innerWidth) x = e.clientX - 390;
    if (y < 10) y = 10;
    if (y + 230 > window.innerHeight) y = window.innerHeight - 240;
    
    chartTooltip.style.left = x + 'px';
    chartTooltip.style.top = y + 'px';
    chartTooltip.classList.add('visible');
}

function hideWPChart() {
    chartTooltip.classList.remove('visible');
}

// Init
renderSwings();
renderLeaderboard();
updateStats();
renderExcitement();
updateExcStats();
    </script>
</body>
</html>'''
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Saved {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    generate_html()
