const express = require('express');
const axios = require('axios');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

// ─── NHL / NFL Score API ──────────────────────────────────────────────────────
// Uses free ESPN API — no key required
const TEAMS = {
  nhl: { id: '13', name: 'Florida Panthers', abbr: 'FLA', league: 'nhl' },
  nfl: { id: '6',  name: 'Dallas Cowboys',   abbr: 'DAL', league: 'nfl' },
};

async function fetchUpcomingGames() {
  const games = [];
  const now = new Date();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  for (const [sport, team] of Object.entries(TEAMS)) {
    try {
      const season = sport === 'nfl' ? '2025' : '20252026';
      const url = `https://site.api.espn.com/apis/site/v2/sports/${sport === 'nhl' ? 'hockey' : 'football'}/${sport}/teams/${team.id}/schedule?season=${season}`;
      const res = await axios.get(url, { timeout: 5000 });
      const events = res.data?.events || [];

      for (const event of events) {
        const gameDate = new Date(event.date);
        const diffMs = gameDate - now;
        // Within next 7 days OR currently live
        if (diffMs > -3 * 60 * 60 * 1000 && diffMs < sevenDaysMs) {
          const comp = event.competitions?.[0];
          const home = comp?.competitors?.find(c => c.homeAway === 'home');
          const away = comp?.competitors?.find(c => c.homeAway === 'away');
          const status = comp?.status;

          games.push({
            sport,
            league: sport.toUpperCase(),
            teamName: team.name,
            homeTeam: home?.team?.abbreviation || '',
            awayTeam: away?.team?.abbreviation || '',
            homeScore: home?.score || '0',
            awayScore: away?.score || '0',
            homeLogo: home?.team?.logo || '',
            awayLogo: away?.team?.logo || '',
            date: event.date,
            displayDate: gameDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
            displayTime: gameDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
            statusType: status?.type?.name || 'scheduled', // scheduled | in-progress | final
            statusDetail: status?.displayClock || '',
            period: status?.period || 0,
            isLive: status?.type?.name === 'in-progress',
            isFinal: status?.type?.name === 'STATUS_FINAL',
          });
        }
      }
    } catch (err) {
      console.error(`Error fetching ${sport} schedule:`, err.message);
    }
  }

  return games;
}

app.get('/api/games', async (req, res) => {
  try {
    const games = await fetchUpcomingGames();
    res.json({ games });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Strava OAuth + Stats ─────────────────────────────────────────────────────
let stravaTokenCache = null;

async function refreshStravaToken() {
  if (
    stravaTokenCache &&
    stravaTokenCache.expires_at > Date.now() / 1000 + 300
  ) {
    return stravaTokenCache.access_token;
  }

  const res = await axios.post('https://www.strava.com/oauth/token', {
    client_id: process.env.STRAVA_CLIENT_ID,
    client_secret: process.env.STRAVA_CLIENT_SECRET,
    refresh_token: process.env.STRAVA_REFRESH_TOKEN,
    grant_type: 'refresh_token',
  });

  stravaTokenCache = res.data;
  return stravaTokenCache.access_token;
}

app.get('/api/strava/stats', async (req, res) => {
  try {
    const token = await refreshStravaToken();
    const athleteRes = await axios.get('https://www.strava.com/api/v3/athlete', {
      headers: { Authorization: `Bearer ${token}` },
    });

    const statsRes = await axios.get(
      `https://www.strava.com/api/v3/athletes/${athleteRes.data.id}/stats`,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    const stats = statsRes.data;
    const ytdWalk = stats.ytd_walk_totals || {};
    const allWalk = stats.all_walk_totals || {};
    const recentWalk = stats.recent_walk_totals || {};

    res.json({
      athlete: {
        name: athleteRes.data.firstname,
        avatar: athleteRes.data.profile,
      },
      ytd: {
        distance: (ytdWalk.distance / 1000).toFixed(1),
        count: ytdWalk.count || 0,
        movingTime: Math.round((ytdWalk.moving_time || 0) / 3600),
        elevation: Math.round(ytdWalk.elevation_gain || 0),
      },
      allTime: {
        distance: (allWalk.distance / 1000).toFixed(1),
        count: allWalk.count || 0,
      },
      recent: {
        distance: ((recentWalk.distance || 0) / 1000).toFixed(1),
        count: recentWalk.count || 0,
        movingTime: Math.round((recentWalk.moving_time || 0) / 3600),
      },
    });
  } catch (err) {
    console.error('Strava error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// Strava recent activities heatmap data
app.get('/api/strava/activities', async (req, res) => {
  try {
    const token = await refreshStravaToken();
    const after = Math.floor(Date.now() / 1000) - 365 * 24 * 60 * 60; // last year

    const activitiesRes = await axios.get('https://www.strava.com/api/v3/athlete/activities', {
      headers: { Authorization: `Bearer ${token}` },
      params: { after, per_page: 200, type: 'Walk' },
    });

    const activities = activitiesRes.data.map(a => ({
      date: a.start_date_local.split('T')[0],
      distance: (a.distance / 1000).toFixed(2),
      movingTime: a.moving_time,
      name: a.name,
    }));

    res.json({ activities });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Selfie / Immich Integration ──────────────────────────────────────────────
app.get('/api/selfies', async (req, res) => {
  try {
    const immichUrl = process.env.IMMICH_URL;
    const immichKey = process.env.IMMICH_API_KEY;
    const albumId   = process.env.IMMICH_ALBUM_ID;

    if (!immichUrl || !immichKey || !albumId) {
      return res.json({ selfies: [] });
    }

    const albumRes = await axios.get(`${immichUrl}/api/albums/${albumId}`, {
      headers: { 'x-api-key': immichKey },
    });

    const assets = albumRes.data.assets || [];
    const now = new Date();

    // Find closest photo to N months ago
    function findClosest(assets, monthsAgo) {
      const target = new Date(now);
      target.setMonth(target.getMonth() - monthsAgo);
      let best = null;
      let bestDiff = Infinity;
      for (const a of assets) {
        const d = new Date(a.fileCreatedAt);
        const diff = Math.abs(d - target);
        if (diff < bestDiff) {
          bestDiff = diff;
          best = a;
        }
      }
      // Only return if within 2 weeks of target
      if (best && bestDiff < 14 * 24 * 60 * 60 * 1000) return best;
      return null;
    }

    const milestones = [1, 6, 12];
    const selfies = milestones.map(months => {
      const asset = findClosest(assets, months);
      return {
        monthsAgo: months,
        id: asset?.id || null,
        url: asset ? `${immichUrl}/api/assets/${asset.id}/thumbnail?size=preview` : null,
        date: asset?.fileCreatedAt || null,
      };
    });

    res.json({ selfies });
  } catch (err) {
    console.error('Immich error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// Trigger webcam capture via Python script, save to Immich
app.post('/api/selfie/capture', (req, res) => {
  exec('python3 /home/pi/mirror/scripts/capture.py', (err, stdout, stderr) => {
    if (err) {
      console.error('Capture error:', stderr);
      return res.status(500).json({ error: 'Capture failed' });
    }
    res.json({ success: true, output: stdout });
  });
});

app.listen(PORT, () => {
  console.log(`Smart Mirror server running on port ${PORT}`);
});
