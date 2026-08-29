<?php
/**
 * AddisERP Solution PLC — contact form handler
 * -------------------------------------------------------------
 * Plain PHP, no external libraries, works on any shared host
 * (Plesk / ethiotelecom hosting) that has PHP + mail() enabled.
 *
 * SETUP:
 * 1. Set $to_email below to the inbox that should receive leads.
 * 2. In Plesk, confirm "mail()" is enabled for the domain
 *    (Plesk > Websites & Domains > PHP Settings > mail() function).
 * 3. If mail() is blocked by your host, switch to SMTP using
 *    PHPMailer (see the note at the bottom of this file).
 * -------------------------------------------------------------
 */

// ---- CONFIG ---------------------------------------------------
$to_email   = "info@addiserp.com";      // <-- change to your real inbox
$site_name  = "AddisERP Solution PLC";
$success_url = "thanks.html";
$error_url   = "contact.html?error=1";
// -----------------------------------------------------------------

function clean($value) {
    $value = trim($value ?? "");
    $value = stripslashes($value);
    $value = htmlspecialchars($value, ENT_QUOTES, "UTF-8");
    return $value;
}

if ($_SERVER["REQUEST_METHOD"] !== "POST") {
    header("Location: contact.html");
    exit;
}

// Honeypot field (optional): if you add <input name="website" style="display:none">
// to the form, uncomment the block below to silently drop bot submissions.
// if (!empty($_POST['website'])) { header("Location: $success_url"); exit; }

$name    = clean($_POST["name"] ?? "");
$company = clean($_POST["company"] ?? "");
$phone   = clean($_POST["phone"] ?? "");
$email   = clean($_POST["email"] ?? "");
$sector  = clean($_POST["sector"] ?? "");
$message = clean($_POST["message"] ?? "");

// Basic required-field validation
if ($name === "" || $company === "" || $phone === "" || $message === "") {
    header("Location: $error_url");
    exit;
}

// Validate email only if the visitor supplied one
if ($email !== "" && !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    header("Location: $error_url");
    exit;
}

$sector_labels = [
    "hrm"    => "HRM + Attendance + Payroll",
    "retail" => "Sales + Purchase + Inventory",
    "both"   => "Both packages",
    "unsure" => "Not sure yet",
];
$sector_label = $sector_labels[$sector] ?? $sector;

$subject = "New website inquiry — $company";

$body  = "New inquiry from the AddisERP website\n";
$body .= "----------------------------------------\n";
$body .= "Name:        $name\n";
$body .= "Company:     $company\n";
$body .= "Phone:       $phone\n";
$body .= "Email:       " . ($email !== "" ? $email : "(not provided)") . "\n";
$body .= "Package:     $sector_label\n";
$body .= "----------------------------------------\n";
$body .= "Message:\n$message\n";

// Use the domain's own address as the envelope sender to avoid
// spam-filter rejection on shared hosting (most hosts require this).
$server_domain = $_SERVER["HTTP_HOST"] ?? "addiserp.com";
$from_address  = "no-reply@" . preg_replace('/^www\./', '', $server_domain);

$headers  = "From: $site_name <$from_address>\r\n";
$headers .= "Reply-To: " . ($email !== "" ? $email : $from_address) . "\r\n";
$headers .= "MIME-Version: 1.0\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";

$sent = @mail($to_email, $subject, $body, $headers);

header("Location: " . ($sent ? $success_url : $error_url));
exit;

/**
 * NOTE — if your host disables PHP's mail():
 * Many shared hosts (including some Plesk setups) prefer SMTP.
 * Drop in PHPMailer (https://github.com/PHPMailer/PHPMailer),
 * upload its /src folder next to this file, and replace the
 * mail() call above with PHPMailer's SMTP send using your
 * hosting provider's SMTP credentials (Plesk > Mail > mailbox settings).
 */
