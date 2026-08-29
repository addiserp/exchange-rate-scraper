<?php
/**
 * Exchange-rate aggregator endpoint.
 * ------------------------------------------------------------
 * Most Ethiopian bank sites load their rate tables with JavaScript a
 * few seconds AFTER the page itself finishes loading. PHP's curl()
 * never runs JavaScript, so it can only ever see those banks'
 * "Loading..." placeholder — no amount of server-side waiting fixes
 * that, because there's no JS engine running at all on this end.
 *
 * The real fix lives in scripts/scrape_rates.py: it drives a real
 * (headless) browser, which DOES run each page's JavaScript, waits a
 * few seconds for the rate widgets to populate, then reads the actual
 * numbers. Run it on a schedule (cron) and it keeps
 * data/exchange-rates-cache.json fresh. THIS FILE'S JOB IS SIMPLE:
 * serve that cache. See scripts/scrape_rates.py's docstring for setup.
 *
 * This file ALSO does a quick curl-only refresh when "Refresh now" is
 * clicked (?refresh=1), which helps for any bank whose site happens
 * to render its rate in plain HTML without needing JavaScript — in
 * practice that turns out to be very few of them; most Ethiopian bank
 * sites need the JS wait, so scripts/scrape_rates.py running on a
 * schedule is what actually keeps this page populated. Either way,
 * the quick refresh only ever IMPROVES the cache — if a bank's curl
 * fetch fails or comes back empty, we keep whatever the last full
 * (Playwright) scrape had for that bank rather than overwriting a
 * good number with "Unavailable".
 * ------------------------------------------------------------
 */

header('Content-Type: application/json; charset=utf-8');

// ---------- configuration ----------
define('CACHE_FILE', __DIR__ . '/../data/exchange-rates-cache.json');
define('CONNECT_TIMEOUT', 6);
define('FETCH_TIMEOUT', 12);
define('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    . '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AddisERP-RateWidget/1.0 '
    . '(+https://www.addiserp.com/exchange-rate.html)');

// ---------- bank list ----------
// 'skip' => true banks are known not to be fetchable server-side
// (JS-rendered widgets, or robots.txt disallow) — we don't hit their
// server at all, we just show a direct link.
$BANKS = [
  ['name' => 'Abay Bank S.C',                         'url' => 'https://exchange.addisfortune.news/bank/abay-bank-sc'],
  ['name' => 'Addis International Bank S.C',          'url' => 'https://www.addisbanksc.com/'],
  ['name' => 'Ahadu Bank S.C',                         'url' => 'https://exchange.addisfortune.news/bank/ahadu-bank-sc'],
  ['name' => 'Amhara Bank S.C',                        'url' => 'https://www.amharabank.com/daily-exchange-rate/', 'skip' => true, 'reason' => 'Rates are loaded by JavaScript after the page loads, so a server can\'t read them'],
  ['name' => 'Awash Bank S.C',                         'url' => 'https://awashbank.com/exchange-historical/', 'skip' => true, 'reason' => 'Rates are loaded by JavaScript after the page loads, so a server can\'t read them'],
  ['name' => 'Bank of Abyssinia',                      'url' => 'https://www.bankofabyssinia.com/exchange-rate-2/'],
  ['name' => 'Berhan Bank S.C.',                       'url' => 'https://berhanbanksc.com/exchange-rates/'],
  ['name' => 'Bunna International Bank',               'url' => 'https://bunnabanksc.com/foreign-exchange/'],
  ['name' => 'Commercial Bank of Ethiopia',            'url' => 'https://combanketh.et/exchange-rates?srcPage=home', 'skip' => true, 'reason' => 'Rates are loaded by JavaScript after the page loads, so a server can\'t read them'],
  ['name' => 'Cooperative Bank of Oromia S.C.',        'url' => 'https://coopbankoromia.com.et/daily-exchange-rates/'],
  ['name' => 'Dashen Bank S.C',                        'url' => 'https://dashenbanksc.com/daily-exchange-rate/'],
  ['name' => 'Enat Bank S.C',                          'url' => 'https://www.enatbanksc.com/'],
  ['name' => 'Gadaa Bank S.C',                         'url' => 'https://gadaabank.com.et/foreign-exchange-remittances/'],
  ['name' => 'Global Bank Ethiopia S.C',               'url' => 'https://www.globalbankethiopia.com/remittance-forex/'],
  ['name' => 'Hibret Bank S.C. (United Bank)',         'url' => 'https://www.hibretbank.com.et/hibret-banks-daily-exchange-rate/'],
  ['name' => 'Lion International Bank S.C',            'url' => 'https://exchange.addisfortune.news/bank/anbesa-bank-1'],
  ['name' => 'National Bank of Ethiopia',              'url' => 'https://nbe.gov.et/'],
  ['name' => 'Nib International Bank S.C',             'url' => 'https://www.nibbanksc.com/exchange-rate/'],
  ['name' => 'Oromia International Bank S.C',          'url' => 'https://oromiabank.com/exchange-rates/', 'skip' => true, 'reason' => 'This bank\'s site blocks automated access (robots.txt)'],
  ['name' => 'Wegagen Bank S.C',                       'url' => 'https://www.wegagen.com/exchange-rate-cash-notes/'],
  ['name' => 'Zemen Bank S.C',                         'url' => 'https://zemenbank.com/exchange-rates/'],
];

// ---------- cache ----------
$force = isset($_GET['refresh']) && $_GET['refresh'] === '1';

$cacheFileExists = is_file(CACHE_FILE);
$existingCache = null;
$cacheReadError = null;

if ($cacheFileExists) {
    $raw = file_get_contents(CACHE_FILE);
    if ($raw === false) {
        $cacheReadError = 'File exists but could not be read (permissions?) at ' . CACHE_FILE;
    } else {
        $decoded = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE || !is_array($decoded) || !isset($decoded['banks'])) {
            $cacheReadError = 'File exists but is not valid rate-cache JSON (' . json_last_error_msg() . ') at ' . CACHE_FILE;
        } else {
            $existingCache = $decoded;
        }
    }
}

if ($cacheReadError !== null) {
    // Something is wrong with a file that DOES exist — this almost
    // always means scripts/scrape_rates.py successfully wrote good
    // data at some point and we now can't read it (wrong working
    // directory for php -S, a permissions mismatch between the user
    // that ran the Python script and the user running PHP, or a
    // half-written file caught mid-write). Fail loudly instead of
    // silently doing a full curl-only re-scrape that would overwrite
    // that good data with mostly "Unavailable" entries.
    error_log('[exchange-rates.php] ' . $cacheReadError);
    http_response_code(500);
    echo json_encode([
        'error'      => $cacheReadError,
        'hint'       => 'Check that data/exchange-rates-cache.json is readable by whatever user is '
            . 'running php -S (or your web server), and that scripts/scrape_rates.py finished writing '
            . 'it completely. This response was NOT saved over your cache file.',
        'fetched_at' => time(),
        'banks'      => [],
    ]);
    exit;
}

// Plain page load, and we already have a cache (however old — that's
// scripts/scrape_rates.py's job to keep fresh via cron): just serve
// it. Re-fetching with curl here would only degrade JS-rendered
// banks' data, not improve it.
if (!$force && $existingCache !== null) {
    $existingCache['from_cache'] = true;
    echo json_encode($existingCache);
    exit;
}

// ---------- parallel fetch ----------
function fetch_all_banks(array $banks): array
{
    $mh = curl_multi_init();
    $handles = [];

    foreach ($banks as $i => $bank) {
        if (!empty($bank['skip'])) {
            continue;
        }
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL            => $bank['url'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS      => 5,
            CURLOPT_CONNECTTIMEOUT => CONNECT_TIMEOUT,
            CURLOPT_TIMEOUT        => FETCH_TIMEOUT,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_USERAGENT      => USER_AGENT,
            CURLOPT_HTTPHEADER     => ['Accept-Language: en-US,en;q=0.9'],
            CURLOPT_ENCODING       => '', // accept gzip/deflate automatically
        ]);
        curl_multi_add_handle($mh, $ch);
        $handles[$i] = $ch;
    }

    $running = null;
    do {
        $status = curl_multi_exec($mh, $running);
        if ($running) {
            curl_multi_select($mh, 1.0);
        }
    } while ($running > 0 && $status === CURLM_OK);

    $results = [];
    foreach ($handles as $i => $ch) {
        $results[$i] = [
            'body'      => curl_multi_getcontent($ch),
            'error'     => curl_error($ch),
            'http_code' => curl_getinfo($ch, CURLINFO_HTTP_CODE),
        ];
        curl_multi_remove_handle($mh, $ch);
        curl_close($ch);
    }
    curl_multi_close($mh);

    return $results;
}

// ---------- generic table parser ----------
/**
 * Looks for a table row that mentions the given currency code
 * (e.g. "USD") and pulls the first two decimal-looking numbers out
 * of that row as [buy, sell]. Works for the common
 * "Currency | Buying | Selling" table layout used by most of these
 * bank sites' WordPress/CMS themes.
 */
function extract_currency_rate(string $html, string $code): ?array
{
    if ($html === '') {
        return null;
    }

    libxml_use_internal_errors(true);
    $doc = new DOMDocument();
    $doc->loadHTML('<?xml encoding="utf-8" ?>' . $html);
    libxml_clear_errors();

    $xpath = new DOMXPath($doc);
    $rows = $xpath->query('//tr');
    if (!$rows) {
        return null;
    }

    foreach ($rows as $row) {
        $cells = $xpath->query('.//td|.//th', $row);
        $texts = [];
        foreach ($cells as $cell) {
            $texts[] = trim(preg_replace('/\s+/', ' ', $cell->textContent));
        }
        if (!$texts) {
            continue;
        }
        $rowText = implode(' | ', $texts);

        // Match the currency code as a whole word, e.g. "USD" but not "USDT".
        if (!preg_match('/\b' . preg_quote($code, '/') . '\b/i', $rowText)) {
            continue;
        }

        $numbers = [];
        foreach ($texts as $t) {
            $clean = str_replace(',', '', $t);
            if (preg_match('/^-?\d+(\.\d{2,4})?$/', $clean)) {
                $val = (float) $clean;
                // Real ETB buy/sell rates for USD/EUR are realistically
                // between ~1 and ~1000 today; this filters out stray
                // "1" unit multiplier columns and spread/percent columns.
                if ($val > 1 && $val < 100000) {
                    $numbers[] = $val;
                }
            }
        }

        if (count($numbers) >= 2) {
            return ['buy' => $numbers[0], 'sell' => $numbers[1]];
        }
    }

    return null;
}

// ---------- quick curl-only pass ----------
$fetchResults = fetch_all_banks($BANKS);

// Index the existing (Playwright-scraped) cache by bank name so we
// can merge into it instead of replacing it wholesale.
$existingByName = [];
if ($existingCache !== null) {
    foreach ($existingCache['banks'] as $b) {
        $existingByName[$b['name']] = $b;
    }
}

$out = [];
foreach ($BANKS as $i => $bank) {
    $previous = $existingByName[$bank['name']] ?? null;

    if (!empty($bank['skip'])) {
        $out[] = $previous ?? [
            'name'   => $bank['name'],
            'url'    => $bank['url'],
            'status' => 'unavailable',
            'reason' => $bank['reason'] ?? 'Not available for automated fetching',
            'usd'    => null,
            'eur'    => null,
        ];
        continue;
    }

    $r = $fetchResults[$i] ?? null;
    $usd = $eur = null;

    if ($r && $r['error'] === '' && $r['http_code'] < 400 && $r['body'] !== '') {
        $usd = extract_currency_rate($r['body'], 'USD');
        $eur = extract_currency_rate($r['body'], 'EUR');
    }

    if ($usd || $eur) {
        // Curl succeeded this time — use the fresh figures.
        $out[] = [
            'name'   => $bank['name'],
            'url'    => $bank['url'],
            'status' => 'ok',
            'usd'    => $usd,
            'eur'    => $eur,
        ];
    } elseif ($previous && $previous['status'] === 'ok') {
        // Curl couldn't get it (often because this bank needs
        // JavaScript) but we still have a good number from the last
        // scripts/scrape_rates.py run — keep that instead of
        // regressing to "Unavailable".
        $out[] = $previous;
    } else {
        $out[] = [
            'name'   => $bank['name'],
            'url'    => $bank['url'],
            'status' => 'unavailable',
            'reason' => 'This bank\'s rate needs JavaScript to load — run scripts/scrape_rates.py '
                . 'to fetch it with a headless browser',
            'usd'    => null,
            'eur'    => null,
        ];
    }
}

$result = [
    'fetched_at'     => time(),
    'fetched_at_iso' => date('c'),
    'from_cache'     => false,
    'source'         => 'curl-quick-refresh',
    'banks'          => $out,
];

@mkdir(dirname(CACHE_FILE), 0755, true);
$tmpFile = dirname(CACHE_FILE) . '/.exchange-rates-cache.tmp-' . bin2hex(random_bytes(6));
if (@file_put_contents($tmpFile, json_encode($result)) !== false) {
    @rename($tmpFile, CACHE_FILE);
}

echo json_encode($result);
