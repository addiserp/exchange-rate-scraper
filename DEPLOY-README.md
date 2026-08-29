# AddisERP Solution PLC — Website

A static, dependency-free website (plain HTML/CSS/JS + one PHP script for
the contact form). No build step, no Node, no database — this is the
simplest possible thing to host on shared hosting through a Plesk panel
(e.g. ethiotelecom hosting).

## What's in this folder

```
index.html              Homepage
services.html            The two packages + payment integration + add-ons
clients.html              Track record / client list + testimonial
about.html                 Company profile, staff, org chart
contact.html                Lead form
contact-handler.php          Processes the form (PHP mail(), no libraries)
thanks.html                   Shown after a successful submission
404.html                       Custom not-found page
robots.txt / sitemap.xml        Basic SEO files
.htaccess                        Apache config (caching, compression, friendly URLs)
assets/css/main.css               All styling (one file)
assets/js/main.js                  Nav menu + light scroll-reveal (no libraries)
assets/img/favicon.svg              Site icon
```

Fonts (Space Grotesk / IBM Plex Sans / IBM Plex Mono) load from Google
Fonts via `<link>` tags already in each page's `<head>` — nothing to
install.

## Deploying on Plesk (step by step)

1. **Log in to Plesk** and open **Websites & Domains** for your domain
   (e.g. `addiserp.com`).
2. Click **File Manager**, then open the domain's document root
   (usually `httpdocs/`).
3. **Delete or back up** any default `index.html` placeholder Plesk put there.
4. **Upload** every file and folder from this package into `httpdocs/`,
   keeping the folder structure exactly as-is (the `assets/` folder must
   sit next to `index.html`).
   - Easiest: zip this whole folder, upload the zip through File Manager,
     then use its "Extract" option — or use an FTP client (FileZilla) with
     the FTP credentials shown in Plesk under **Websites & Domains → FTP Access**.
5. In Plesk, go to **Websites & Domains → SSL/TLS Certificates** and issue
   a free "Let's Encrypt" certificate for the domain, then enable
   **"Permanent SEO-safe 301 redirect from HTTP to HTTPS."**
   (Once that's on, you can uncomment the HTTPS redirect lines at the top
   of `.htaccess`.)
6. **Set the homepage**: Plesk automatically serves `index.html` at the
   domain root — no extra config needed.

## Making the contact form work

1. Open `contact-handler.php` and change this line near the top to your
   real inbox:
   ```php
   $to_email = "info@addiserp.com";
   ```
2. In Plesk, go to **Websites & Domains → PHP Settings** for the domain
   and confirm the `mail()` function is **enabled** (some hosts disable it
   by default for anti-spam reasons — if so, see the note inside
   `contact-handler.php` about switching to SMTP with PHPMailer).
3. Test it: open the live `contact.html` page, submit the form, and check
   that the message arrives at the inbox you configured.
4. If mail() is blocked by your host, create a real mailbox in
   **Plesk → Mail** and use its SMTP credentials with PHPMailer instead —
   instructions are in the comment block at the bottom of
   `contact-handler.php`.

## Before you go live — things to fill in

- [ ] Replace `info@addiserp.com` in `contact-handler.php` with your real inbox
- [ ] Add a real phone number / email / Telegram to `contact.html` and the
      footer on every page (search for "available on request")
- [ ] Swap `addiserp.com` in `robots.txt` and `sitemap.xml` for your actual domain
- [ ] Confirm final client reference contact details before publishing them
      publicly on `clients.html` (currently references are described by
      company + project only, with contact details available on request)
- [ ] Add your Chapa and Telebirr merchant details when you're ready to
      accept payments through the site itself (this version showcases the
      integration; wiring up live checkout is a follow-on step your dev
      team or AddisERP can handle against the Chapa/Telebirr APIs)

## Exchange Rate page (new)

`exchange-rate.html` shows USD/EUR buy/sell rates pulled from each
bank's own website. It has two moving parts:

### 1. The real scraper — runs on GitHub Actions, not your host

Almost every Ethiopian bank site loads its rate table with JavaScript
a few seconds *after* the page finishes loading. A plain server-side
fetch (PHP `curl`, or anything that doesn't run JS) only ever sees a
"Loading..." placeholder for those banks — waiting longer doesn't
help, because there's no JS engine running at all. The only real fix
is a headless browser that actually runs the page's JavaScript and
waits, which needs more than typical shared PHP hosting provides.

Since this site is on shared hosting, the scraper runs for free on
**GitHub Actions** on a schedule, and pushes its results to your site
over plain HTTPS. Nothing runs locally or needs to stay turned on.

**One-time setup:**
1. Push this whole folder to a GitHub repository (public repos get
   unlimited free Actions minutes; private repos get 2,000 min/month
   free — see the schedule note inside `.github/workflows/scrape-rates.yml`
   if you go private, since this job takes several minutes per run).
2. On the **server** (not in git): copy
   `config/upload-token.example.php` to `config/upload-token.php`,
   generate a real secret (`openssl rand -hex 32` or any long random
   string) and put it in there. Upload just that one file via
   FTP/SFTP/File Manager. It's in `.gitignore` on purpose — never
   commit it.
3. In your GitHub repo: **Settings → Secrets and variables → Actions
   → New repository secret**, add two secrets:
   - `RATES_UPLOAD_URL` = `https://www.yourdomain.com/api/upload-rates.php`
   - `RATES_UPLOAD_TOKEN` = the exact same string you put on the server
4. That's it. The workflow runs on its schedule (every 30 min by
   default — adjust the `cron:` line in the workflow file), scrapes
   all ~20 bank sites with a real headless browser, and POSTs the
   result to `api/upload-rates.php` on your server, which atomically
   replaces `data/exchange-rates-cache.json`.
5. To test it right away instead of waiting for the schedule: in
   GitHub, go to **Actions → Update exchange rates → Run workflow**.
6. Watch the run in the **Actions** tab — the "Upload the fresh rates"
   step prints exactly what the server responded with, so if something's
   wrong (bad token, wrong URL, `data/` not writable) you'll see the
   real error message there.

**If GitHub Actions doesn't work out** (e.g. your host blocks incoming
requests from GitHub's IP ranges, or you'd rather not use GitHub at
all), the fallback is running `scripts/scrape_rates.py` on a schedule
somewhere you control — your own Ubuntu machine via cron is the
simplest version of that, though it only updates while that machine
is on. See the "Run it manually" section below either way, since it's
useful for testing regardless of which scheduling method you use.

**Manual run / local testing**, on any machine with Python:
```bash
cd addiserp-site-new
pip install --break-system-packages -r scripts/requirements.txt
python3 -m playwright install --with-deps chromium
python3 scripts/scrape_rates.py
```
This writes straight to your local `data/exchange-rates-cache.json` —
no upload involved, useful for testing the scraper itself or for the
"run it on your own machine" fallback.

### 2. `api/exchange-rates.php` (serves the cache, does a light quick-refresh)

- **PHP extensions**: `curl` and `dom` (also called `xml`/`libxml`)
  must be enabled — Plesk: **Websites & Domains → PHP Settings**.
- On a normal page load, it just serves whatever
  `data/exchange-rates-cache.json` currently has (written by the
  Python scraper above) — fast, no outbound requests.
- Clicking **"Refresh now"** on the page triggers a quick PHP `curl`
  pass, which only helps the rare bank whose site shows a rate without
  needing JavaScript. It's designed to never make things worse: if
  curl can't get a bank's rate, it leaves that bank's last known good
  figure (from the Python scraper) in place rather than replacing it
  with "Unavailable".
- **A writable `data/` folder** is required either way (already
  included, with a `.htaccess` blocking direct web access to it).
- If `data/exchange-rates-cache.json` doesn't exist yet at all (i.e.
  you haven't run the Python scraper even once), the PHP endpoint
  falls back to a curl-only fetch for every bank so the page isn't
  completely empty — but most banks will show "Unavailable" until you
  run `scripts/scrape_rates.py` at least once.
- Bank site HTML changes over time without notice. If a bank that used
  to work stops working, check its current markup and adjust
  `extract_currency_rate()` — the same parsing logic lives in both
  `api/exchange-rates.php` (PHP) and `scripts/scrape_rates.py`
  (Python), so update both if you change the heuristic.

## Editing content later

Everything is plain HTML — open any `.html` file in a text editor and
edit the text directly. All five pages share the same header/footer
markup and the same `assets/css/main.css`, so styling changes in one
place apply everywhere.
