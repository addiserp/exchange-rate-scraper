<?php
/**
 * Copy this file to upload-token.php (same folder) and replace the
 * value below with a long random secret — e.g. generate one with:
 *   openssl rand -hex 32
 *
 * Put that exact same string into your GitHub repo's Actions secret
 * named RATES_UPLOAD_TOKEN (Settings → Secrets and variables →
 * Actions → New repository secret).
 *
 * upload-token.php itself is listed in .gitignore — it should only
 * ever exist on the live server, uploaded manually via FTP/SFTP/File
 * Manager, never committed to git or shared anywhere.
 */

define('UPLOAD_TOKEN', 'change-me');
