<?php
/**
 * Receives the exchange-rate cache JSON pushed by the GitHub Actions
 * workflow (.github/workflows/scrape-rates.yml) after it runs
 * scripts/scrape_rates.py on GitHub's servers (which CAN run a
 * headless browser — your shared host can't).
 *
 * This exists so you don't need FTP/SFTP credentials wired into
 * GitHub: the workflow just does an HTTPS POST here with a secret
 * bearer token, same as calling any other API.
 *
 * SETUP (do this once, directly on the server — never commit the
 * real token to git):
 *   1. Copy config/upload-token.example.php to config/upload-token.php
 *   2. Put a long random string in it (e.g. `openssl rand -hex 32`)
 *   3. Upload config/upload-token.php to the server via FTP/SFTP/File
 *      Manager (it's in .gitignore, so it won't come from git)
 *   4. Put that same string in your GitHub repo's secret
 *      RATES_UPLOAD_TOKEN (Settings → Secrets and variables → Actions)
 */

header('Content-Type: application/json; charset=utf-8');

define('CACHE_FILE', __DIR__ . '/../data/exchange-rates-cache.json');
define('TOKEN_CONFIG', __DIR__ . '/../config/upload-token.php');
define('MAX_BODY_BYTES', 200 * 1024); // rate data is tiny; this is generous

function respond(int $code, array $body): void
{
    http_response_code($code);
    echo json_encode($body);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    respond(405, ['error' => 'Use POST']);
}

if (!is_file(TOKEN_CONFIG)) {
    respond(500, [
        'error' => 'Server is not configured yet.',
        'hint'  => 'Copy config/upload-token.example.php to config/upload-token.php on the server '
            . 'and set a real token in it (see the comment at the top of this file).',
    ]);
}

require TOKEN_CONFIG; // defines UPLOAD_TOKEN

if (!defined('UPLOAD_TOKEN') || UPLOAD_TOKEN === '' || UPLOAD_TOKEN === 'change-me') {
    respond(500, ['error' => 'config/upload-token.php exists but UPLOAD_TOKEN isn\'t set to a real value.']);
}

$authHeader = $_SERVER['HTTP_AUTHORIZATION']
    ?? apache_request_headers()['Authorization']
    ?? '';
$providedToken = preg_match('/^Bearer\s+(.+)$/i', $authHeader, $m) ? $m[1] : '';

if ($providedToken === '' || !hash_equals(UPLOAD_TOKEN, $providedToken)) {
    respond(401, ['error' => 'Missing or incorrect bearer token']);
}

$raw = file_get_contents('php://input', false, null, 0, MAX_BODY_BYTES + 1);
if ($raw === false || $raw === '') {
    respond(400, ['error' => 'Empty request body']);
}
if (strlen($raw) > MAX_BODY_BYTES) {
    respond(413, ['error' => 'Payload too large']);
}

$decoded = json_decode($raw, true);
if (json_last_error() !== JSON_ERROR_NONE || !is_array($decoded) || !isset($decoded['banks']) || !is_array($decoded['banks'])) {
    respond(400, ['error' => 'Body is not valid rate-cache JSON (' . json_last_error_msg() . ')']);
}

// Atomic write: write to a temp file in the same directory, then
// rename() over the real file. rename() is atomic on POSIX
// filesystems, so a reader (api/exchange-rates.php) can never see a
// half-written file, even if it hits this exact moment.
$dir = dirname(CACHE_FILE);
if (!is_dir($dir) && !@mkdir($dir, 0755, true)) {
    respond(500, ['error' => 'data/ folder does not exist and could not be created']);
}
$tmpFile = $dir . '/.exchange-rates-cache.tmp-' . bin2hex(random_bytes(6));
if (file_put_contents($tmpFile, $raw) === false) {
    respond(500, ['error' => 'Could not write temp file — check that data/ is writable by the web server user']);
}
if (!rename($tmpFile, CACHE_FILE)) {
    @unlink($tmpFile);
    respond(500, ['error' => 'Could not replace cache file (rename failed)']);
}

respond(200, [
    'ok'    => true,
    'banks_received' => count($decoded['banks']),
    'saved_to' => CACHE_FILE,
]);
