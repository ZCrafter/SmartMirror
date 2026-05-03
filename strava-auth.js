#!/usr/bin/env node
/**
 * strava-auth.js
 * Run once to exchange your authorization code for a refresh token.
 *
 * Steps:
 *  1. Fill STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env
 *  2. Visit this URL in your browser (replace CLIENT_ID):
 *     https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read,activity:read_all
 *  3. After approving, copy the `code` param from the redirect URL
 *  4. Run: node scripts/strava-auth.js YOUR_CODE
 *  5. Copy the printed refresh_token into your .env
 */

const axios = require('axios');
require('dotenv').config();

const code = process.argv[2];
if (!code) {
  console.error('Usage: node scripts/strava-auth.js YOUR_AUTH_CODE');
  process.exit(1);
}

(async () => {
  try {
    const res = await axios.post('https://www.strava.com/oauth/token', {
      client_id:     process.env.STRAVA_CLIENT_ID,
      client_secret: process.env.STRAVA_CLIENT_SECRET,
      code,
      grant_type: 'authorization_code',
    });
    console.log('\n✅ Success! Add this to your .env:\n');
    console.log(`STRAVA_REFRESH_TOKEN=${res.data.refresh_token}`);
    console.log('\nFull response:', JSON.stringify(res.data, null, 2));
  } catch (err) {
    console.error('Error:', err.response?.data || err.message);
  }
})();
