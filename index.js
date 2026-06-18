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
  nhl: { id: '26', name: 'Florida Panthers', abbr: 'FLA', league: 'nhl' },
  nfl: { id: '6',  name: 'Dallas Cowboys',   abbr: 'DAL', league: 'nfl' },
};

async function fetchUpcomingGames() {
  const games = [];
  const now = new Date();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  for (const [sport, team] of Object.entries(TEAMS)) {
    try {
      const now2 = new Date();
      const yr = now2.getFullYear();
      // NHL season spans two years; if before August use current/prev, else current/next
      const nhlSeason = now2.getMonth() < 7 ? `${yr-1}${yr}` : `${yr}${yr+1}`;
      const season = sport === 'nfl' ? String(yr) : nhlSeason;
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

    // Calculate stats from activities directly — Strava walk_totals are unreliable
    const oneYearAgo = Math.floor(Date.now() / 1000) - 365 * 24 * 60 * 60;
    const [yearRes, allRes] = await Promise.all([
      axios.get('https://www.strava.com/api/v3/athlete/activities', {
        headers: { Authorization: `Bearer ${token}` },
        params: { after: oneYearAgo, per_page: 200, sport_type: 'Walk' },
      }),
      axios.get('https://www.strava.com/api/v3/athlete/activities', {
        headers: { Authorization: `Bearer ${token}` },
        params: { per_page: 200, sport_type: 'Walk' },
      }),
    ]);

    const yearActs = yearRes.data || [];
    const allActs  = allRes.data  || [];
    const toMiles  = m => (m * 0.000621371);
    const now      = new Date();
    const startOfYear  = new Date(now.getFullYear(), 0, 1);
    const fourWeeksAgo = new Date(now - 28 * 24 * 60 * 60 * 1000);

    const ytdActs    = yearActs.filter(a => new Date(a.start_date) >= startOfYear);
    const recentActs = yearActs.filter(a => new Date(a.start_date) >= fourWeeksAgo);

    const sum = (arr, key) => arr.reduce((s, a) => s + (a[key] || 0), 0);

    res.json({
      athlete: { name: athleteRes.data.firstname, avatar: athleteRes.data.profile },
      ytd: {
        distance: toMiles(sum(ytdActs, 'distance')).toFixed(1),
        count:    ytdActs.length,
        movingTime: Math.round(sum(ytdActs, 'moving_time') / 3600),
      },
      allTime: {
        distance: toMiles(sum(allActs, 'distance')).toFixed(1),
        count:    allActs.length,
      },
      recent: {
        distance: toMiles(sum(recentActs, 'distance')).toFixed(1),
        count:    recentActs.length,
        movingTime: Math.round(sum(recentActs, 'moving_time') / 3600),
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
      distance: (a.distance * 0.000621371).toFixed(2),
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
        url: asset ? `/api/selfie/thumb/${asset.id}` : null,
        date: asset?.fileCreatedAt || null,
      };
    });

    res.json({ selfies });
  } catch (err) {
    console.error('Immich error:', err.message);
    res.status(500).json({ error: err.message });
  }
});


// ─── Selfie thumbnail proxy (avoids CORS + handles Immich auth via header) ───
app.get('/api/selfie/thumb/:id', async (req, res) => {
  try {
    const immichUrl = process.env.IMMICH_URL;
    const immichKey = process.env.IMMICH_API_KEY;
    const response  = await axios.get(
      `${immichUrl}/api/assets/${req.params.id}/thumbnail?size=preview`,
      {
        headers:      { 'x-api-key': immichKey },
        responseType: 'stream',
        timeout:      10000,
      }
    );
    res.set('Content-Type', response.headers['content-type'] || 'image/jpeg');
    res.set('Cache-Control', 'public, max-age=86400');
    response.data.pipe(res);
  } catch (err) {
    console.error('Thumb proxy error:', err.message);
    res.status(500).send('Image unavailable');
  }
});

// Trigger webcam capture via Python script, save to Immich
app.post('/api/selfie/capture', (req, res) => {
  const scriptPath = path.join(__dirname, '../scripts/capture.py');
  exec(`python3 ${scriptPath}`, (err, stdout, stderr) => {
    if (err) {
      console.error('Capture error:', stderr);
      return res.status(500).json({ error: 'Capture failed' });
    }
    res.json({ success: true, output: stdout });
  });
});

// ─── WLED Lighting Control ────────────────────────────────────────────────────
const WLED_URL = process.env.WLED_URL; // e.g. http://192.168.1.50

async function wledSetState(state) {
  if (!WLED_URL) {
    console.log('WLED_URL not set in .env — skipping lighting control');
    return;
  }
  try {
    await axios.post(`${WLED_URL}/json/state`, state, { timeout: 3000 });
  } catch (err) {
    console.error('WLED control error:', err.message);
  }
}

// Solid white at a given brightness (0-255), used during countdown ramp
async function wledCountdownStep(stepIndex, totalSteps) {
  // Ramp brightness from ~25% to 100% as countdown approaches 0
  const minBrightness = 60;
  const maxBrightness = 255;
  const brightness = Math.round(
    minBrightness + ((maxBrightness - minBrightness) * (stepIndex / totalSteps))
  );
  await wledSetState({
    on: true,
    bri: brightness,
    seg: [{ col: [[255, 255, 255]], fx: 0 }], // fx:0 = solid color, no effect
  });
}

// Restore the default WLED preset/state (whatever you've already configured)
async function wledRestoreDefault() {
  // If you saved your default look as a WLED preset, call it by ID here.
  // Find your preset ID in the WLED UI under Presets, then set WLED_DEFAULT_PRESET in .env
  const presetId = process.env.WLED_DEFAULT_PRESET;
  if (presetId) {
    await wledSetState({ ps: parseInt(presetId, 10) });
  } else {
    // Fallback: just turn on, let WLED's own boot-default segment/effect take over
    await wledSetState({ on: true });
  }
}

app.post('/api/lights/countdown', async (req, res) => {
  const { step, total } = req.body || {};
  await wledCountdownStep(step ?? 0, total ?? 5);
  res.json({ success: true });
});

app.post('/api/lights/restore', async (req, res) => {
  await wledRestoreDefault();
  res.json({ success: true });
});

// ─── Motion / Sleep State ──────────────────────────────────────────────────────
// The motion.py daemon POSTs here whenever the PIR sensor changes state.
// The frontend polls /api/motion/status to decide whether to show the dashboard
// or go to sleep (black screen).
let motionState = {
  active: true,       // is someone currently in front of the mirror (within grace period)?
  lastMotionAt: Date.now(),
};

app.post('/api/motion/event', (req, res) => {
  const { motion } = req.body || {};
  if (motion) {
    motionState.lastMotionAt = Date.now();
    motionState.active = true;
  }
  res.json({ success: true });
});

app.get('/api/motion/status', (req, res) => {
  const GRACE_MS = (parseInt(process.env.MOTION_GRACE_SECONDS, 10) || 45) * 1000;
  const msSinceMotion = Date.now() - motionState.lastMotionAt;
  motionState.active = msSinceMotion < GRACE_MS;
  res.json({
    active: motionState.active,
    msSinceMotion,
    graceMs: GRACE_MS,
  });
});

app.listen(PORT, () => {
  console.log(`Smart Mirror server running on port ${PORT}`);
});
