const express = require('express');
const axios = require('axios');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const { execFile, spawn } = require('child_process');
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
            homeLogo: home?.team?.logo || `https://a.espncdn.com/i/teamlogos/${sport}/500/${String(home?.team?.abbreviation || '').toLowerCase()}.png`,
            awayLogo: away?.team?.logo || `https://a.espncdn.com/i/teamlogos/${sport}/500/${String(away?.team?.abbreviation || '').toLowerCase()}.png`,
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

// ─── Fitness data (Dreeve preferred, direct Strava kept as fallback) ─────────
//
// Dreeve pre-builds the activity table as JSON. Reading that local endpoint is
// both faster and more reliable than asking Strava again from this Raspberry
// Pi. Keep the old /api/strava/* routes so the kiosk page does not need a
// breaking change.
const DREEVE_URL = String(process.env.DREEVE_URL || '').trim().replace(/\/+$/, '');
const DREEVE_ACTIVITIES_PATH = String(
  process.env.DREEVE_ACTIVITIES_PATH || '/api/fragment/data/activities/data-table'
).trim();
const DREEVE_SPORT_TYPES = new Set(
  String(process.env.DREEVE_SPORT_TYPES || 'Walk')
    .split(',')
    .map(value => value.trim().toLowerCase())
    .filter(Boolean)
);
const DREEVE_CACHE_MS = Math.max(
  15000,
  Number(process.env.DREEVE_CACHE_SECONDS || 300) * 1000
);
let dreeveActivityCache = null;

function dreeveActivitiesUrl() {
  if (!DREEVE_URL) return null;
  const pathPart = DREEVE_ACTIVITIES_PATH.startsWith('/')
    ? DREEVE_ACTIVITIES_PATH
    : `/${DREEVE_ACTIVITIES_PATH}`;
  return `${DREEVE_URL}${pathPart}`;
}

function decodeBasicHtml(value) {
  return String(value || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

function dreeveActivityName(row) {
  const firstSpan = String(row?.markup || '').match(/<span[^>]*>([\s\S]*?)<\/span>/i);
  if (firstSpan) return decodeBasicHtml(firstSpan[1]);
  return String(row?.searchables || 'Walk').trim() || 'Walk';
}

function dateInMirrorTimezone(epochSeconds) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: process.env.SCHEDULE_TIMEZONE || 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(epochSeconds * 1000));
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function normalizeDreeveActivity(row) {
  const epochSeconds = Number(row?.sort?.['start-date'])
    || Math.floor(Number(row?.filterables?.['start-date'] || 0) / 1000);
  const distanceMeters = Number(row?.sort?.distance || 0);

  if (!epochSeconds) return null;
  return {
    date: dateInMirrorTimezone(epochSeconds),
    startTimestamp: epochSeconds,
    distance: (distanceMeters * 0.000621371).toFixed(2),
    distanceMeters,
    movingTime: Number(row?.sort?.['moving-time'] || 0),
    name: dreeveActivityName(row),
  };
}

async function fetchDreeveActivities({ force = false } = {}) {
  const url = dreeveActivitiesUrl();
  if (!url) throw new Error('DREEVE_URL is not set');

  if (!force && dreeveActivityCache && Date.now() - dreeveActivityCache.loadedAt < DREEVE_CACHE_MS) {
    return dreeveActivityCache.activities;
  }

  const response = await axios.get(url, {
    timeout: 15000,
    headers: { Accept: 'application/json' },
  });
  if (!Array.isArray(response.data)) {
    throw new Error(`Dreeve returned ${typeof response.data}, expected an activity array`);
  }

  const activities = response.data
    .filter(row => DREEVE_SPORT_TYPES.has(
      String(row?.filterables?.sportType || '').trim().toLowerCase()
    ))
    .map(normalizeDreeveActivity)
    .filter(Boolean);

  dreeveActivityCache = { loadedAt: Date.now(), activities };
  return activities;
}

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
    if (DREEVE_URL) {
      const activities = await fetchDreeveActivities();
      const now = new Date();
      const startOfYear = new Date(now.getFullYear(), 0, 1).getTime() / 1000;
      const fourWeeksAgo = now.getTime() / 1000 - 28 * 24 * 60 * 60;
      const ytdActs = activities.filter(activity => activity.startTimestamp >= startOfYear);
      const recentActs = activities.filter(activity => activity.startTimestamp >= fourWeeksAgo);
      const sum = (items, key) => items.reduce((total, item) => total + (item[key] || 0), 0);
      const miles = items => (sum(items, 'distanceMeters') * 0.000621371).toFixed(1);

      return res.json({
        source: 'dreeve',
        ytd: {
          distance: miles(ytdActs),
          count: ytdActs.length,
          movingTime: Math.round(sum(ytdActs, 'movingTime') / 3600),
        },
        allTime: {
          distance: miles(activities),
          count: activities.length,
        },
        recent: {
          distance: miles(recentActs),
          count: recentActs.length,
          movingTime: Math.round(sum(recentActs, 'movingTime') / 3600),
        },
      });
    }

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
    console.error(`${DREEVE_URL ? 'Dreeve' : 'Strava'} stats error:`, err.message);
    res.status(500).json({ error: err.message });
  }
});

// Strava recent activities heatmap data
app.get('/api/strava/activities', async (req, res) => {
  try {
    if (DREEVE_URL) {
      const oneYearAgo = Date.now() / 1000 - 365 * 24 * 60 * 60;
      const activities = (await fetchDreeveActivities())
        .filter(activity => activity.startTimestamp >= oneYearAgo)
        .map(({ date, distance, movingTime, name }) => ({
          date,
          distance,
          movingTime,
          name,
        }));
      return res.json({ source: 'dreeve', activities });
    }

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
    console.error(`${DREEVE_URL ? 'Dreeve' : 'Strava'} activities error:`, err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/fitness/status', async (req, res) => {
  if (!DREEVE_URL) {
    return res.json({
      source: 'strava',
      configured: Boolean(
        process.env.STRAVA_CLIENT_ID
        && process.env.STRAVA_CLIENT_SECRET
        && process.env.STRAVA_REFRESH_TOKEN
      ),
    });
  }

  try {
    const activities = await fetchDreeveActivities({ force: true });
    res.json({
      source: 'dreeve',
      configured: true,
      url: dreeveActivitiesUrl(),
      sportTypes: [...DREEVE_SPORT_TYPES],
      matchingActivities: activities.length,
    });
  } catch (err) {
    res.status(502).json({
      source: 'dreeve',
      configured: true,
      url: dreeveActivitiesUrl(),
      sportTypes: [...DREEVE_SPORT_TYPES],
      error: err.message,
    });
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
const CAPTURE_SCRIPT = path.join(__dirname, '../scripts/capture.py');

app.post('/api/selfie/capture', (req, res) => {
  const duringCountdown = req.body?.duringCountdown === true;
  const configuredDelay = Number(process.env.CAMERA_COUNTDOWN_DELAY_SECONDS || 4);
  const delaySeconds = duringCountdown
    ? Math.max(0, Math.min(10, configuredDelay))
    : 0;
  const args = [CAPTURE_SCRIPT, '--delay', String(delaySeconds)];

  execFile('/usr/bin/python3', args, (err, stdout, stderr) => {
    if (err) {
      console.error('Capture error:', stderr);
      return res.status(500).json({ error: 'Capture failed' });
    }
    res.json({ success: true, output: stdout });
  });
});

// The GPIO button cannot directly call browser JavaScript. It records a
// trigger here; the kiosk page polls the status endpoint and runs the same
// countdown workflow used by the keyboard shortcut.
let captureTriggerId = 0;
let lastClaimedTriggerId = 0;

app.post('/api/selfie/trigger', (req, res) => {
  captureTriggerId += 1;
  console.log(`Selfie sequence requested (trigger ${captureTriggerId})`);
  res.json({ success: true, triggerId: captureTriggerId });
});

app.get('/api/selfie/trigger/status', (req, res) => {
  // Old dashboard builds used this broadcast endpoint and could make every
  // open browser take a duplicate photo. Keep it inert so stale pages fail
  // safely until Chromium reloads the claim-based build.
  res.json({ triggerId: 0, deprecated: true });
});

// Atomically give each physical-button event to only one kiosk page. Without
// this claim, every open browser displaying the dashboard would see the same
// trigger and take its own photo.
app.post('/api/selfie/trigger/claim', (req, res) => {
  if (captureTriggerId <= lastClaimedTriggerId) {
    return res.json({ claimed: false, triggerId: captureTriggerId });
  }

  lastClaimedTriggerId = captureTriggerId;
  res.json({ claimed: true, triggerId: captureTriggerId });
});

// ─── WLED Lighting Control ────────────────────────────────────────────────────
// The weather renderer stays alive during a selfie so it retains its weather
// data and can resume immediately. A lock file tells it to pause DDP output
// while countdown_lights.py owns WLED and continuously holds the final white
// frame through the camera/Immich upload.

const COUNTDOWN_LIGHTS_SCRIPT = path.join(__dirname, '../scripts/countdown_lights.py');
const LIGHTS_DIR = path.join(__dirname, '../Lights/SmartMirror');
const LIGHTS_OVERRIDE_LOCK = '/run/smart-mirror-selfie-lighting.lock';

try {
  fs.unlinkSync(LIGHTS_OVERRIDE_LOCK);
} catch (err) {
  if (err.code !== 'ENOENT') console.error('Could not clear stale lighting lock:', err.message);
}

function runProcess(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile(command, args, options, (err, stdout, stderr) => {
      if (err) {
        console.error(`Command failed [${command} ${args.join(' ')}]:`, stderr || err.message);
        err.stdout = stdout;
        err.stderr = stderr;
        reject(err);
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

let lightsOverrideActive = false;
let countdownProcess = null;

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function pauseWeatherLights() {
  if (lightsOverrideActive) return;
  fs.writeFileSync(LIGHTS_OVERRIDE_LOCK, `${process.pid}\n`);
  lightsOverrideActive = true;
  // Allow at least a few weather-renderer frames for it to notice the lock.
  await delay(150);
}

async function stopCountdownProcess() {
  const child = countdownProcess;
  if (!child) return;

  countdownProcess = null;
  if (child.exitCode !== null) return;

  await new Promise(resolve => {
    const timeout = setTimeout(resolve, 750);
    child.once('exit', () => {
      clearTimeout(timeout);
      resolve();
    });
    child.kill('SIGTERM');
  });

  if (child.exitCode === null) {
    child.kill('SIGKILL');
    await delay(100);
  }
}

async function resumeWeatherLights() {
  await stopCountdownProcess();

  try {
    fs.unlinkSync(LIGHTS_OVERRIDE_LOCK);
  } catch (err) {
    if (err.code !== 'ENOENT') throw err;
  }
  lightsOverrideActive = false;
}

async function sendCountdownBrightness(brightness) {
  await runProcess('/usr/bin/python3', [COUNTDOWN_LIGHTS_SCRIPT, String(brightness)], {
    env: { ...process.env, SMART_MIRROR_DIR: LIGHTS_DIR },
  });
}

function startCountdownRamp(durationSeconds) {
  return new Promise((resolve, reject) => {
    if (countdownProcess && countdownProcess.exitCode === null) {
      reject(new Error('A selfie lighting ramp is already active'));
      return;
    }

    const child = spawn(
      '/usr/bin/python3',
      [COUNTDOWN_LIGHTS_SCRIPT, 'ramp', String(durationSeconds), '60'],
      {
        env: { ...process.env, SMART_MIRROR_DIR: LIGHTS_DIR },
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
    countdownProcess = child;

    child.stdout.on('data', data => console.log(`Selfie lights: ${data.toString().trim()}`));
    child.stderr.on('data', data => console.error(`Selfie lights: ${data.toString().trim()}`));
    child.once('spawn', resolve);
    child.once('error', err => {
      if (countdownProcess === child) countdownProcess = null;
      reject(err);
    });
    child.once('exit', (code, signal) => {
      if (countdownProcess === child) countdownProcess = null;
      if (code && signal !== 'SIGTERM') {
        console.error(`Selfie lighting process exited with code ${code}`);
      }
    });
  });
}

app.post('/api/lights/countdown', async (req, res) => {
  const { step, total } = req.body || {};
  const stepIndex  = step  ?? 0;
  const totalSteps = total ?? 5;

  // First call in a countdown sequence — pause the weather animation
  try {
    await pauseWeatherLights();

    // Compatibility endpoint for manual tests and older kiosk pages.
    const minBrightness = 60;
    const maxBrightness = 255;
    const brightness = Math.round(
      minBrightness + ((maxBrightness - minBrightness) * (stepIndex / totalSteps))
    );

    await sendCountdownBrightness(brightness);
    res.json({ success: true, brightness });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post('/api/lights/ramp', async (req, res) => {
  const requestedDuration = Number(req.body?.durationSeconds ?? 5);
  const durationSeconds = Math.max(1, Math.min(15, requestedDuration));

  if (lightsOverrideActive) {
    return res.status(409).json({ success: false, error: 'Selfie lighting already active' });
  }

  try {
    await pauseWeatherLights();
    await startCountdownRamp(durationSeconds);
    res.json({ success: true, durationSeconds });
  } catch (err) {
    await resumeWeatherLights().catch(restoreErr => {
      console.error('Failed to recover weather lighting:', restoreErr.message);
    });
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post('/api/lights/restore', async (req, res) => {
  try {
    // Resume the weather LED service — it will take back over the WLED connection
    await resumeWeatherLights();
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── Motion / Sleep State ──────────────────────────────────────────────────────
// DISPLAY_MODE selects one source of truth: always, schedule, or motion. The
// frontend polls /api/display/status and covers the dashboard with black while
// inactive. The weather-light process reads the same schedule from the root
// .env and sends black DDP frames outside the configured hours.
let motionState = {
  active: true,       // is someone currently in front of the mirror (within grace period)?
  lastMotionAt: Date.now(),
};
const MOTION_ENABLED = ['1', 'true', 'yes', 'on'].includes(
  String(process.env.MOTION_ENABLED || 'false').trim().toLowerCase()
);

const validDisplayModes = new Set(['always', 'schedule', 'motion']);
const requestedDisplayMode = String(process.env.DISPLAY_MODE || '').trim().toLowerCase();
if (requestedDisplayMode && !validDisplayModes.has(requestedDisplayMode)) {
  throw new Error('DISPLAY_MODE must be always, schedule, or motion');
}
// Preserve the old MOTION_ENABLED setting when DISPLAY_MODE has not yet been
// added to an existing installation.
const DISPLAY_MODE = requestedDisplayMode
  ? requestedDisplayMode
  : (MOTION_ENABLED ? 'motion' : 'always');
const SCHEDULE_TIMEZONE = String(process.env.SCHEDULE_TIMEZONE || 'America/New_York').trim();
const DAY_ORDER = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
const DAY_ALIASES = {
  sun: 'sun', sunday: 'sun',
  mon: 'mon', monday: 'mon',
  tue: 'tue', tues: 'tue', tuesday: 'tue',
  wed: 'wed', wednesday: 'wed',
  thu: 'thu', thur: 'thu', thurs: 'thu', thursday: 'thu',
  fri: 'fri', friday: 'fri',
  sat: 'sat', saturday: 'sat',
};

function parseScheduleDays(value) {
  const days = new Set();
  for (const part of String(value || '').split(',')) {
    const setting = part.trim().toLowerCase();
    if (!setting) continue;
    const normalized = DAY_ALIASES[setting];
    if (!normalized) throw new Error(`Unknown day in SCHEDULE_DAYS: ${part.trim()}`);
    if (normalized) days.add(normalized);
  }
  return days;
}

function parseTimeMinutes(value, settingName, allowEndOfDay = false) {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) throw new Error(`${settingName} must use 24-hour HH:MM format`);
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (allowEndOfDay && hours === 24 && minutes === 0) return 24 * 60;
  if (hours > 23 || minutes > 59) {
    throw new Error(`${settingName} is outside the valid 00:00-23:59 range`);
  }
  return hours * 60 + minutes;
}

function parseDailyWindows(value, settingName) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized || ['off', 'none'].includes(normalized)) return [];
  if (['all-day', 'allday', 'always'].includes(normalized)) return [[0, 24 * 60]];

  const windows = normalized.split(',').map((windowText, index) => {
    const parts = windowText.trim().split('-');
    if (parts.length !== 2) {
      throw new Error(`${settingName} window ${index + 1} must look like 05:00-09:00`);
    }
    const start = parseTimeMinutes(parts[0].trim(), `${settingName} start`);
    const end = parseTimeMinutes(parts[1].trim(), `${settingName} end`, true);
    if (start >= end) {
      throw new Error(
        `${settingName} window ${windowText.trim()} must end after it starts; split overnight hours across two days`
      );
    }
    return [start, end];
  });

  return windows.sort((a, b) => a[0] - b[0]);
}

function formatMinutes(minutes) {
  if (minutes === 24 * 60) return '24:00';
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function formatDailyWindows(windows) {
  if (!windows.length) return 'off';
  if (windows.length === 1 && windows[0][0] === 0 && windows[0][1] === 24 * 60) {
    return 'all-day';
  }
  return windows.map(([start, end]) => `${formatMinutes(start)}-${formatMinutes(end)}`).join(',');
}

function loadSchedule() {
  const perDayConfigured = DAY_ORDER.some(day =>
    Object.prototype.hasOwnProperty.call(process.env, `SCHEDULE_${day.toUpperCase()}`)
  );
  const windows = Object.fromEntries(DAY_ORDER.map(day => [day, []]));

  if (perDayConfigured) {
    for (const day of DAY_ORDER) {
      const settingName = `SCHEDULE_${day.toUpperCase()}`;
      windows[day] = parseDailyWindows(process.env[settingName] || 'off', settingName);
    }
    return { windows, source: 'per-day' };
  }

  // Backward compatibility for v3 .env files. Once any SCHEDULE_MON-style
  // setting is added, all seven per-day settings become the source of truth.
  const days = parseScheduleDays(process.env.SCHEDULE_DAYS || 'mon,tue,wed,thu,fri');
  const start = parseTimeMinutes(
    String(process.env.SCHEDULE_START || '05:00').trim(),
    'SCHEDULE_START'
  );
  const end = parseTimeMinutes(
    String(process.env.SCHEDULE_END || '21:00').trim(),
    'SCHEDULE_END'
  );

  for (const day of days) {
    if (start === end) {
      windows[day].push([0, 24 * 60]);
    } else if (start < end) {
      windows[day].push([start, end]);
    } else {
      windows[day].push([start, 24 * 60]);
      const nextDay = DAY_ORDER[(DAY_ORDER.indexOf(day) + 1) % DAY_ORDER.length];
      windows[nextDay].push([0, end]);
    }
  }
  return { windows, source: 'legacy' };
}

const { windows: SCHEDULE_WINDOWS, source: SCHEDULE_SOURCE } = loadSchedule();
const SCHEDULE_TEXT = Object.fromEntries(
  DAY_ORDER.map(day => [day, formatDailyWindows(SCHEDULE_WINDOWS[day])])
);

// Validate the timezone once at startup instead of silently leaving the mirror
// permanently asleep because of a typo.
new Intl.DateTimeFormat('en-US', { timeZone: SCHEDULE_TIMEZONE }).format(new Date());

function zonedClock(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: SCHEDULE_TIMEZONE,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return {
    day: values.weekday.toLowerCase(),
    minutes: Number(values.hour) * 60 + Number(values.minute),
  };
}

function isScheduleActive(date = new Date()) {
  const { day, minutes } = zonedClock(date);
  return SCHEDULE_WINDOWS[day].some(([start, end]) => minutes >= start && minutes < end);
}

function getDisplayStatus() {
  const graceMs = (parseInt(process.env.MOTION_GRACE_SECONDS, 10) || 45) * 1000;
  const msSinceMotion = Date.now() - motionState.lastMotionAt;
  let active = true;

  if (DISPLAY_MODE === 'schedule') {
    active = isScheduleActive();
  } else if (DISPLAY_MODE === 'motion') {
    active = msSinceMotion < graceMs;
    motionState.active = active;
  }

  return {
    active,
    mode: DISPLAY_MODE,
    timezone: SCHEDULE_TIMEZONE,
    schedule: {
      source: SCHEDULE_SOURCE,
      perDay: SCHEDULE_TEXT,
    },
    msSinceMotion,
    graceMs,
  };
}

app.post('/api/motion/event', (req, res) => {
  const { motion } = req.body || {};
  if (motion) {
    motionState.lastMotionAt = Date.now();
    motionState.active = true;
  }
  res.json({ success: true });
});

app.get('/api/display/status', (req, res) => res.json(getDisplayStatus()));

// Compatibility alias for old diagnostic commands and cached kiosk pages.
app.get('/api/motion/status', (req, res) => {
  res.json({ ...getDisplayStatus(), enabled: DISPLAY_MODE === 'motion' });
});

app.listen(PORT, () => {
  console.log(`Smart Mirror server running on port ${PORT}`);
  console.log(
    `Display mode: ${DISPLAY_MODE}`
    + (DISPLAY_MODE === 'schedule'
      ? ` (${SCHEDULE_SOURCE}, ${SCHEDULE_TIMEZONE})`
      : '')
  );
  if (DISPLAY_MODE === 'schedule') console.log('Schedule:', SCHEDULE_TEXT);
});
