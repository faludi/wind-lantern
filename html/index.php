<?php
declare(strict_types=1);
session_start();

// CONFIG: JSON settings file
$jsonFile = __DIR__ . '/wind_lantern_settings.json';

// Helper: read
function read_json_file(string $path): array {
    if (!file_exists($path)) return [];
    $content = @file_get_contents($path);
    if ($content === false) return [];
    $decoded = json_decode($content, true);
    return is_array($decoded) ? $decoded : [];
}

// Helper: write atomic
function write_json_file_atomic(string $path, array $data): bool {
    $dir = dirname($path);
    $tmp = tempnam($dir, 'tmp_json_');
    if ($tmp === false) return false;

    $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    if ($json === false) { @unlink($tmp); return false; }

    $fp = @fopen($tmp, 'c');
    @chmod($tmp, 0644);
    if ($fp === false) { @unlink($tmp); return false; }

    if (!flock($fp, LOCK_EX)) { fclose($fp); @unlink($tmp); return false; }

    ftruncate($fp, 0);
    fwrite($fp, $json);
    fflush($fp);
    flock($fp, LOCK_UN);
    fclose($fp);

    if (!@rename($tmp, $path)) {
        if (!@copy($tmp, $path)) { @unlink($tmp); return false; }
        @unlink($tmp);
    }

    return true;
}

// CSRF token
if (!isset($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(24));
}
$csrf_token = $_SESSION['csrf_token'];

$errors = [];
$successMessage = null;

// Load JSON
$data = read_json_file($jsonFile);
if (!isset($data['address'])) $data['address'] = '';

// Handle POST (address update)
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $postedToken = $_POST['csrf_token'] ?? '';
    if (!hash_equals($csrf_token, $postedToken)) {
        $errors[] = 'Invalid CSRF token.';
    }

    $rawAddress = $_POST['address'] ?? '';
    if (!is_string($rawAddress)) {
        $errors[] = 'Invalid address.';
    } else {
        $address = trim($rawAddress);
        $address = preg_replace('/[\r\n\/"\'\\\\;]+/m', ' ', $address);
        $address = preg_replace('/\s+/', ' ', $address);

        if ($address === '') {
            $errors[] = 'Address cannot be empty.';
        } elseif (strlen($address) > 1024) {
            $errors[] = 'Address too long.';
        }
    }

    if (!$errors) {
        $data['address'] = $address;
        if (write_json_file_atomic($jsonFile, $data)) {
            $successMessage = 'Address updated successfully.';

            @mail(
                'rob@faludi.com',
                'Wind Lantern Address Update',
                "New address: $address\n\nRaw:\n$rawAddress",
                'From: rob@faludi.com'
            );
        } else {
            $errors[] = 'Could not write JSON (permissions issue?).';
        }
    }
}

// -----------------------------------------------------------
// ALWAYS SHOW CURRENT WIND CONDITIONS
// -----------------------------------------------------------
$windError = null;
$windResult = null;
$addr = trim($data['address']);

if ($addr === '') {
    $windError = 'Please enter and save an address first.';
} else {
    $encodedAddress = urlencode($addr);

    // 1) Nominatim lookup
    $nominatimUrl = "https://nominatim.openstreetmap.org/search?q={$encodedAddress}&format=json&limit=1";
    $context = stream_context_create([
        'http' => ['header' => "User-Agent: WindLantern/1.0\r\n"]
    ]);
    $nomResponse = @file_get_contents($nominatimUrl, false, $context);

    if ($nomResponse === false) {
        $windError = 'Failed to fetch coordinates.';
    } else {
        $nom = json_decode($nomResponse, true);
        if (!$nom || !isset($nom[0]['lat'], $nom[0]['lon'])) {
            $windError = 'No results found for the address.';
        } else {
            $lat = $nom[0]['lat'];
            $lon = $nom[0]['lon'];

            // 2) Open-Meteo weather lookup
            $weatherUrl = "https://api.open-meteo.com/v1/forecast?latitude={$lat}&longitude={$lon}&current=wind_speed_10m,wind_gusts_10m";
            $weatherResponse = @file_get_contents($weatherUrl);

            if ($weatherResponse === false) {
                $windError = 'Failed to fetch weather.';
            } else {
                $weather = json_decode($weatherResponse, true);
                $current = $weather['current'] ?? [];

                if (!isset($current['wind_speed_10m'], $current['wind_gusts_10m'])) {
                    $windError = 'Weather data incomplete.';
                } else {
                    $ws = $current['wind_speed_10m'];
                    $wg = $current['wind_gusts_10m'];

                    $latFloat = (float)$lat;
                    $lonFloat = (float)$lon;

                    // ----- ZOOMED-IN MAP USING BBOX -----
                    // Smaller delta = more zoomed-in
                    $delta = 0.005; // ~400m-ish around the point
                    $minLon = $lonFloat - $delta;
                    $minLat = $latFloat - $delta;
                    $maxLon = $lonFloat + $delta;
                    $maxLat = $latFloat + $delta;

                    $bbox = $minLon . '%2C' . $minLat . '%2C' . $maxLon . '%2C' . $maxLat;
                    $mapSrc  = "https://www.openstreetmap.org/export/embed.html?bbox={$bbox}&layer=mapnik&marker={$latFloat}%2C{$lonFloat}";
                    // Larger view link can still use a standard zoom level
                    $zoom    = 16;
                    $mapLink = "https://www.openstreetmap.org/?mlat={$latFloat}&mlon={$lonFloat}#map={$zoom}/{$latFloat}/{$lonFloat}";

                    $windResult = [
                        'address'   => $addr,
                        'lat'       => $latFloat,
                        'lon'       => $lonFloat,
                        'ws_kmh'    => $ws,
                        'wg_kmh'    => $wg,
                        'ws_mph'    => round($ws * 0.62137119, 2),
                        'wg_mph'    => round($wg * 0.62137119, 2),
                        'map_src'   => $mapSrc,
                        'map_link'  => $mapLink,
                    ];
                }
            }
        }
    }
}
?>
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Wind Lantern</title>
<style>
body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background:#f7f7f9;
    padding:24px;
}
.container {
    max-width:760px;
    margin:0 auto;
    background:#fff;
    padding:20px;
    border-radius:10px;
    box-shadow:0 6px 18px rgba(0,0,0,.06);
}
textarea {
    width:97%;
    min-height:120px;
}
.btn {
    color:#fff;
    border:none;
    padding:8px 14px;
    border-radius:20px;
    cursor:pointer;
    font-weight:600;
    margin-right:8px;
}
.btn-update {
    background:#28a745; /* green */
}
.btn-refresh {
    background:#00aaee; /* blue */
}
.msg.err {
    background:#ffe9e9;
    color:#992222;
    padding:10px;
    border-radius:8px;
}
.msg.ok {
    background:#e4ffe9;
    color:#226622;
    padding:10px;
    border-radius:8px;
}
.label {
    display:inline-block;
    width:150px;
    font-weight:bold;
}
.map-container {
    margin-top:12px;
    border:1px solid #ccc;
    border-radius:6px;
    overflow:hidden;
}
.map-footer {
    font-size:0.85rem;
    text-align:right;
    margin-top:4px;
}
.map-footer a {
    color:#0077cc;
    text-decoration:none;
}
.map-footer a:hover {
    text-decoration:underline;
}
</style>
</head>
<body>
<div class="container">

<h1>Wind Lantern – Update Address</h1>

<?php if ($errors): ?>
<div class="msg err">
    <strong>Errors:</strong>
    <ul>
        <?php foreach ($errors as $e): ?>
            <li><?= htmlspecialchars($e) ?></li>
        <?php endforeach; ?>
    </ul>
</div>
<?php endif; ?>

<?php if ($successMessage): ?>
<div class="msg ok"><?= htmlspecialchars($successMessage) ?></div>
<?php endif; ?>

<form method="post">
    <textarea name="address"><?= htmlspecialchars($data['address']) ?></textarea>
    <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf_token) ?>">
    <br><br>
    <button class="btn btn-update" type="submit">Update Address</button>
    <br><br><br>
</form>

<hr>
<h2>Current Wind Conditions</h2>
<p><button class="btn btn-refresh" type="button" onclick="window.location.href='index.php'">
            Refresh Wind
        </button></p>

<?php if ($windError): ?>
    <div class="msg err"><?= htmlspecialchars($windError) ?></div>
<?php elseif ($windResult): ?>
    <div><span class="label">Address:</span> <?= htmlspecialchars($windResult['address']) ?></div>
    <div><span class="label">Latitude:</span> <?= htmlspecialchars((string)$windResult['lat']) ?></div>
    <div><span class="label">Longitude:</span> <?= htmlspecialchars((string)$windResult['lon']) ?></div>
    <div><span class="label">Wind Speed:</span> <?= $windResult['ws_mph'] ?> mph</div>
    <div><span class="label">Wind Gusts:</span> <?= $windResult['wg_mph'] ?> mph</div>


    <div class="map-container">
        <iframe
            width="100%"
            height="250"
            frameborder="0"
            scrolling="no"
            marginheight="0"
            marginwidth="0"
            src="<?= htmlspecialchars($windResult['map_src'], ENT_QUOTES | ENT_SUBSTITUTE) ?>">
        </iframe>
    </div>
    <div class="map-footer">
        <a href="<?= htmlspecialchars($windResult['map_link'], ENT_QUOTES | ENT_SUBSTITUTE) ?>" target="_blank" rel="noopener">
            View larger map
        </a>
    </div>
<?php endif; ?>

</div>
</body>
</html>