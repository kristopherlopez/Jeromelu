/**
 * Scrape full NRL player list from supercoach.com.au
 *
 * - Launches Chrome (non-headless) with automation detection disabled
 * - Logs in via Google OAuth (user completes password + 2FA manually)
 * - Intercepts the players-cf API response containing all players
 * - Saves raw API data to scripts/scraped_players_api_raw.json
 */
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: ['--disable-blink-features=AutomationControlled'],
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  // Hide webdriver flag from detection
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  // Set up API interception for the players endpoint
  let playersApiData = null;
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('players-cf') && response.status() === 200) {
      try {
        const json = await response.json();
        if (Array.isArray(json) && json.length > 100) {
          playersApiData = json;
          console.log(`[API] Intercepted players-cf: ${json.length} players`);
        }
      } catch {}
    }
  });

  // Navigate to SuperCoach players page
  console.log('Navigating to supercoach.com.au...');
  await page.goto('https://www.supercoach.com.au/nrl/classic/players', {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForTimeout(5000);

  // Click Login
  console.log('Clicking Login...');
  const loginBtn = await page.$('text=Login')
    || await page.$('a:has-text("Login")')
    || await page.$('button:has-text("Login")')
    || await page.$('text=Log In');
  if (loginBtn) {
    await loginBtn.click();
    await page.waitForTimeout(3000);
  } else {
    console.log('No Login button found — may already be logged in');
  }

  // Click Google sign-in
  console.log('Clicking Google sign-in...');
  const googleBtn = await page.$('text=Google')
    || await page.$('a:has-text("Google")')
    || await page.$('button:has-text("Google")')
    || await page.$('[class*="google"]');

  if (googleBtn) {
    const [popup] = await Promise.all([
      context.waitForEvent('page', { timeout: 10000 }).catch(() => null),
      googleBtn.click(),
    ]);

    const authPage = popup || page;
    if (popup) await popup.waitForLoadState('domcontentloaded');
    await authPage.waitForTimeout(3000);

    // Fill email
    const emailInput = await authPage.$('input[type="email"]')
      || await authPage.$('#identifierId');
    if (emailInput) {
      console.log('Entering email...');
      await emailInput.fill('kristopher.lopez@gmail.com');
      await authPage.waitForTimeout(1000);

      const nextBtn = await authPage.$('#identifierNext')
        || await authPage.$('button:has-text("Next")');
      if (nextBtn) await nextBtn.click();
    }

    // Wait for user to complete password + 2FA
    console.log('');
    console.log('========================================');
    console.log('Complete password and 2FA in the browser');
    console.log('========================================');
    console.log('');

    if (popup) {
      await popup.waitForEvent('close', { timeout: 300000 }).catch(() => {
        console.error('Auth timeout — popup still open after 5 minutes');
      });
    } else {
      await page.waitForURL('**supercoach.com.au**', { timeout: 300000 }).catch(() => {
        console.error('Auth timeout — did not redirect back');
      });
    }
    console.log('Auth complete!');
  } else {
    console.log('No Google sign-in button found — may already be logged in');
  }

  await page.waitForTimeout(5000);

  // Navigate to players page to trigger the API call
  console.log('Loading players page...');
  await page.goto('https://www.supercoach.com.au/nrl/classic/players', {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });

  // Wait for the API response
  for (let i = 0; i < 30; i++) {
    if (playersApiData) break;
    await page.waitForTimeout(1000);
  }

  // Fallback: try fetching the API directly
  if (!playersApiData) {
    console.log('API not intercepted, trying direct fetch...');
    playersApiData = await page.evaluate(async () => {
      const res = await fetch('/2026/api/nrl/classic/v1/players-cf?embed=notes,odds,player_stats,positions&round=1&xredir=1');
      return res.json();
    }).catch(() => null);
  }

  if (playersApiData && playersApiData.length > 0) {
    fs.writeFileSync(
      'scripts/scraped_players_api_raw.json',
      JSON.stringify(playersApiData, null, 2)
    );
    console.log(`\nSaved ${playersApiData.length} players to scripts/scraped_players_api_raw.json`);
  } else {
    console.error('ERROR: Failed to get player data from API');
    process.exit(1);
  }

  await browser.close();
})();
