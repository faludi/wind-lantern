<?php
declare(strict_types=1);
// index.php - PHP 8.2
session_start();

// CONFIG: change filename if your JSON file is named differently
$jsonFile = __DIR__ . '/wind_lantern_settings.json';

// Helper: read JSON, return associative array or empty array on failure
function read_json_file(string $path): array {
    if (!file_exists($path)) {
        return [];
    }
    $content = @file_get_contents($path);
    if ($content === false) {
        return [];
    }
    $data = json_decode($content, true);
    return is_array($data) ? $data : [];
}

// Helper: write JSON atomically with lock (create temp + rename)
function write_json_file_atomic(string $path, array $data): bool {
    $dir = dirname($path);
    $tmp = tempnam($dir, 'tmp_json_');
    if ($tmp === false) {
        return false;
    }

    $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    if ($json === false) {
        // encoding failed
        @unlink($tmp);
        return false;
    }

    // write + flush + lock
    $fp = @fopen($tmp, 'c');
    chmod($tmp, 0644);
    if ($fp === false) {
        @unlink($tmp);
        return false;
    }

    // Acquire exclusive lock on the temp file while writing
    if (!flock($fp, LOCK_EX)) {
        fclose($fp);
        @unlink($tmp);
        return false;
    }

    ftruncate($fp, 0);
    rewind($fp);
    $written = fwrite($fp, $json);
    fflush($fp);
    // Release lock and close
    flock($fp, LOCK_UN);
    fclose($fp);

    if ($written === false) {
        @unlink($tmp);
        return false;
    }

    // Rename temp to target (atomic on most OS/filesystems)
    if (!@rename($tmp, $path)) {
        // fallback: try copy + unlink
        if (!@copy($tmp, $path)) {
            @unlink($tmp);
            return false;
        }
        @unlink($tmp);
    }

    return true;
}

// CSRF token generation
if (!isset($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(24));
}
$csrf_token = $_SESSION['csrf_token'];

$errors = [];
$successMessage = null;

// Load existing data
$data = read_json_file($jsonFile);

// If address key missing, ensure it's present (empty string)
if (!array_key_exists('address', $data)) {
    $data['address'] = '';
}

// Handle POST update
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Basic CSRF check
    $postedToken = $_POST['csrf_token'] ?? '';
    if (!is_string($postedToken) || !hash_equals($csrf_token, $postedToken)) {
        $errors[] = 'Invalid CSRF token. Please reload the page and try again.';
    }

    // Get posted address
    $address = $_POST['address'] ?? '';
    $rawAddress = $address; // for debugging if needed
    if (!is_string($address)) {
        $errors[] = 'Invalid address value.';
    } else {
        $address = trim($address);
        $address = preg_replace('/[\r\n\/\"\'\\\\;]+/m', " ", $address); // remove return,newline, slash, quotes, backslash
        $address = preg_replace('/\s+/', ' ',$address); 
        // Validation: adjust rules as needed
        if ($address === '') {
            $errors[] = 'Address cannot be empty.';
        } elseif (mb_strlen($address) > 1024) {
            $errors[] = 'Address is too long (max 1024 characters).';
        }
    }

    if (empty($errors)) {
        // Sanitize: here we store raw text; if you plan to display in HTML, escape when printing.
        $data['address'] = $address;

        if (write_json_file_atomic($jsonFile, $data)) {
            $successMessage = 'Address updated successfully.';
            //sending email with the php mail()
            $message = 'The PHP form has been updated with a new address: ' . $address. "\n\nRaw input was:\n" . $rawAddress;
            mail('rob@faludi.com', 'Wind Lantern Address Update', $message, 'From: rob@faludi.com');
            // Reload to avoid form re-submission when user refreshes
            // But we will redisplay via the same request (do not redirect because user might not want it)
        } else {
            $errors[] = 'Failed to write to the JSON file. Check file permissions.';
        }
    }
}
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wind Lantern - Update Address</title>
<style>
    :root { font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }
    body { padding: 24px; background:#f7f7f9; color:#111; }
    .container { max-width:760px; margin:0 auto; background:#fff; border-radius:10px; box-shadow:0 6px 18px rgba(0,0,0,.06); padding:20px; }
    h1 { margin-top:0; font-size:1.4rem; }
    label { display:block; margin-bottom:.5rem; font-weight:600; }
    textarea { width:100%; min-height:120px; padding:10px; border-radius:6px; border:1px solid #ddd; font-size:1rem; font-family:inherit; }
    .btn { display:inline-block; margin-top:10px; padding:8px 14px; border-radius:8px; border:0; cursor:pointer; background:#0066cc; color:#fff; font-weight:600; }
    .muted { color:#666; font-size:.95rem; margin-bottom:10px; }
    .msg { padding:10px; border-radius:8px; margin-bottom:10px; }
    .err { background:#fff1f0; color:#8b1f1f; border:1px solid #f5c2c2; }
    .ok { background:#f0fff6; color:#0b7a3f; border:1px solid #bfe8c6; }
    pre{ background:#f6f8fa; padding:10px; border-radius:6px; overflow:auto; }
    footer { margin-top:14px; font-size:.85rem; color:#666; }
</style>
<style>
#myDIV {
  width: 100%;
  padding: 50px 0;
  text-align: left;
  background-color: white;
  margin-top: 20px;
  display: none;
}
</style>
</head>
<body>
<div class="container">
    <h1>Wind Lantern - Update Address</h1>

    <?php if (!empty($errors)): ?>
        <div class="msg err">
            <strong>Errors:</strong>
            <ul>
                <?php foreach ($errors as $e): ?>
                    <li><?= htmlspecialchars($e, ENT_QUOTES | ENT_SUBSTITUTE) ?></li>
                <?php endforeach; ?>
            </ul>
        </div>
    <?php endif; ?>

    <?php if ($successMessage): ?>
        <div class="msg ok"><?= htmlspecialchars($successMessage, ENT_QUOTES | ENT_SUBSTITUTE) ?></div>
    <?php endif; ?>

    <form method="post" novalidate>
        <!-- <label for="address">Enter the address to be used for geolocation by the Wind Lantern.</label> -->
        <textarea id="address" name="address" required><?= htmlspecialchars($data['address'] ?? '', ENT_QUOTES | ENT_SUBSTITUTE) ?></textarea>
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf_token, ENT_QUOTES | ENT_SUBSTITUTE) ?>">
        <div>
            <button class="btn" type="submit">Update address</button>
        </div>
    </form>
    <br>
    <blockquote>
    <p class="muted"><strong>Examples:</strong><br>
    <ul><li>350 5th Ave, New York, NY 10018<br>
    <li>Omaha, NB<br>
    <li>02134<br>
    <li>Paris, France</ul><br></p></blockquote>
    <br>

<script>
function myFunction() {
  var x = document.getElementById("myDIV");
  if (x.style.display === "block") {
    x.style.display = "none";
  } else {
    x.style.display = "block";
  }
}
</script>
<button onclick="myFunction()">Debug</button>
<div id="myDIV">
    <hr>
    
    <h4>JSON file preview</h4>
    <pre><?= htmlspecialchars(json_encode(read_json_file($jsonFile), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), ENT_QUOTES | ENT_SUBSTITUTE) ?></pre>
</div>
    <footer>
        <!-- Make sure the webserver user (eg. www-data, wwwrun, apache) has write permission to <?= htmlspecialchars(basename($jsonFile), ENT_QUOTES | ENT_SUBSTITUTE) ?>. -->
    </footer>
</div>
</body>
</html>