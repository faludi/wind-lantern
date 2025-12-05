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

                    // Zoomed-in map using bbox
                    $delta = 0.002; // ~200m radius
                    $minLon = $lonFloat - $delta;
                    $minLat = $latFloat - $delta;
                    $maxLon = $lonFloat + $delta;
                    $maxLat = $latFloat + $delta;

                    $bbox = $minLon . '%2C' . $minLat . '%2C' . $maxLon . '%2C' . $maxLat;
                    $mapSrc  = "https://www.openstreetmap.org/export/embed.html?bbox={$bbox}&layer=mapnik&marker={$latFloat}%2C{$lonFloat}";
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
<html lang="en">
<head>
<meta charset="utf-8">
<title>風灯 – Wind Lantern </title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
/* ---- Overall tea house atmosphere ---- */
body {
    margin: 0;
    padding: 0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background:
        radial-gradient(circle at 0% 0%, rgba(255,255,255,0.5), transparent 55%),
        radial-gradient(circle at 100% 100%, rgba(255,255,255,0.35), transparent 55%),
        linear-gradient(180deg, #f4f0e7 0%, #e7e0d2 35%, #dacfb9 100%);
    color: #3d372f;
}

.page {
    min-height: 100vh;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 32px 16px;
    box-sizing: border-box;
}

/* Main container: wood frame around shōji/paper interior */
.container {
    position: relative;
    max-width: 980px;
    width: 100%;
    background:
        linear-gradient(180deg, #f8f3e9 0%, #f3ecdd 55%, #ede3d0 100%);
    border-radius: 18px;
    border: 8px solid #8a6b45; /* wood frame */
    box-shadow:
        0 14px 40px rgba(0,0,0,0.25),
        inset 0 0 0 1px rgba(255,255,255,0.7);
    padding: 20px 22px 24px;
    box-sizing: border-box;
}

/* Top wood beam */
.container::before {
    content: "";
    position: absolute;
    left: -8px;
    right: -8px;
    top: -16px;
    height: 12px;
    background: linear-gradient(90deg, #7b5e3b, #a37848, #7b5e3b);
    box-shadow: 0 4px 8px rgba(0,0,0,0.25);
}

/* Shoji grid hint */
.shoji-grid {
    position: absolute;
    inset: 14px 14px auto 14px;
    height: 90px;
    pointer-events: none;
    opacity: 0.35;
}
.shoji-grid::before,
.shoji-grid::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 12px;
    border: 1px solid rgba(184,150,105,0.5);
}
.shoji-grid::after {
    background-image:
        linear-gradient(90deg, rgba(185,152,108,0.55) 1px, transparent 1px),
        linear-gradient(180deg, rgba(185,152,108,0.55) 1px, transparent 1px);
    background-size: 72px 52px;
    border-radius: 11px;
}

/* Header */
.header {
    position: relative;
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 6px;
    z-index: 1;
}

.header-title-jp {
    font-size: 1.6rem;
    font-family: "Hiragino Mincho ProN", "Yu Mincho", "MS Mincho", serif;
    font-weight: bold;
    color: #5b432a;
}

.header-title-main {
    font-size: 1.4rem;
    font-weight: bold;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #6c5840;
}

.header-subtitle {
    margin-top: 4px;
    font-size: 0.9rem;
    color: #756750;
}

/* Layout columns */
.columns {
    display: flex;
    flex-wrap: wrap;
    gap: 22px;
    margin-top: 16px;
    position: relative;
    z-index: 1;
}

.col {
    flex: 1 1 280px;
    min-width: 0;
}

/* Sections: paper panels with very subtle texture */
.section {
    background:
        linear-gradient(135deg, rgba(255,255,255,0.8), rgba(246,239,227,0.9)),
        repeating-linear-gradient(180deg, rgba(255,255,255,0.25) 0px, rgba(255,255,255,0.25) 1px, transparent 2px, transparent 4px);
    border-radius: 14px;
    border: 1px solid rgba(188,164,124,0.6);
    box-shadow:
        0 4px 12px rgba(0,0,0,0.08),
        inset 0 0 0 1px rgba(255,255,255,0.5);
    padding: 14px 14px 16px;
}

/* Thin vertical wooden slats between sections */
.section + .section {
    border-left: 3px solid rgba(149,117,78,0.2);
}

/* Section titles */
.section-title {
    font-size: 1.0rem;
    margin: 0 0 6px 0;
    color: #5a4631;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.section-caption {
    font-size: 0.84rem;
    color: #857664;
    margin-bottom: 8px;
}

/* Address textarea */
textarea {
    width: 100%;
    min-height: 120px;
    padding: 9px 10px;
    box-sizing: border-box;
    background:
        radial-gradient(circle at 0% 0%, rgba(255,255,255,0.8), rgba(250,243,232,0.9)),
        repeating-linear-gradient(180deg, rgba(220,205,180,0.25) 0px, rgba(220,205,180,0.25) 1px, transparent 2px, transparent 4px);
    color: #4b3f33;
    border-radius: 10px;
    border: 1px solid rgba(176,150,110,0.7);
    outline: none;
    resize: vertical;
    font-size: 0.95rem;
    line-height: 1.4;
}
textarea:focus {
    border-color: #7aa25f;
    box-shadow:
        0 0 0 1px rgba(112,149,83,0.4),
        0 0 0 4px rgba(170,200,145,0.3);
}

/* Buttons */
.btn-row {
    margin-top: 10px;
}

.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 7px 16px;
    border-radius: 999px;
    border: 1px solid transparent;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.88rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    transition: all 0.16s ease-out;
    text-decoration: none;
    white-space: nowrap;
}

/* Update = matcha green, like tea in a ceramic bowl */
.btn-update {
    color: #233017;
    background: linear-gradient(135deg, #c8de9b, #95b76a);
    border-color: #6e8a47;
    box-shadow:
        0 4px 10px rgba(138,168,98,0.45),
        0 1px 0 rgba(255,255,255,0.7) inset;
}
.btn-update:hover {
    transform: translateY(-1px);
    box-shadow:
        0 6px 14px rgba(138,168,98,0.6),
        0 1px 0 rgba(255,255,255,0.7) inset;
}

/* Refresh = cool stream water */
.btn-refresh {
    color: #294248;
    background: linear-gradient(135deg, #bcdfe2, #88b6c0);
    border-color: #6c9daa;
    box-shadow:
        0 4px 10px rgba(131,170,185,0.45),
        0 1px 0 rgba(255,255,255,0.7) inset;
}
.btn-refresh:hover {
    transform: translateY(-1px);
    box-shadow:
        0 6px 14px rgba(131,170,185,0.6),
        0 1px 0 rgba(255,255,255,0.7) inset;
}

/* Messages */
.msg {
    border-radius: 10px;
    padding: 9px 11px;
    font-size: 0.9rem;
    margin-bottom: 10px;
}
.msg.err {
    background: #fbe5df;
    border: 1px solid #d68a70;
    color: #7b3b2b;
}
.msg.ok {
    background: #e6f4dd;
    border: 1px solid #90b77a;
    color: #355027;
}

/* Wind section details */
.wind-section {
    position: relative;
}

/* A faint vertical division like tatami seams */
.wind-section::before {
    content: "";
    position: absolute;
    inset: 12px 50% 12px auto;
    width: 1px;
    background: linear-gradient(180deg, rgba(150,133,105,0.35), transparent 40%, transparent 60%, rgba(150,133,105,0.35));
    opacity: 0.5;
    pointer-events: none;
}

/* Data rows */
.label {
    display: inline-block;
    width: 130px;
    font-weight: 600;
    color: #5a4631;
    font-size: 0.9rem;
}
.value {
    font-size: 0.9rem;
    color: #4a4337;
}
.row {
    margin: 4px 0;
}

/* Map container = small wooden frame window */
.map-container {
    margin-top: 12px;
    border-radius: 10px;
    overflow: hidden;
    border: 3px solid #a77b4b;
    box-shadow:
        0 2px 8px rgba(0,0,0,0.2),
        0 0 0 1px rgba(255,255,255,0.65) inset;
}
.map-footer {
    font-size: 0.8rem;
    text-align: right;
    margin-top: 6px;
    color: #84735e;
}
.map-footer a {
    color: #567f92;
    text-decoration: none;
}
.map-footer a:hover {
    text-decoration: underline;
}

/* Small note text */
.wind-note {
    font-size: 0.8rem;
    color: #8b7a67;
    margin-top: 4px;
}

/* Responsive tweaks */
@media (max-width: 720px) {
    .container {
        padding: 16px 14px 18px;
        border-width: 6px;
    }
    .columns {
        gap: 16px;
    }
    .wind-section::before {
        display: none;
    }
    /* --- Tatami stripes at bottom of page --- */
	.tatami-stripes {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		height: 110px;
		background:
			/* woven texture */
			repeating-linear-gradient(
				45deg,
				rgba(205, 188, 150, 0.45) 0px,
				rgba(205, 188, 150, 0.45) 3px,
				rgba(222, 206, 173, 0.55) 3px,
				rgba(222, 206, 173, 0.55) 6px
			),
			repeating-linear-gradient(
				-45deg,
				rgba(205, 188, 150, 0.28) 0px,
				rgba(205, 188, 150, 0.28) 3px,
				rgba(222, 206, 173, 0.35) 3px,
				rgba(222, 206, 173, 0.35) 6px
			),
			linear-gradient(
				180deg,
				#d8cba6 0%,
				#d3c29b 40%,
				#cab890 100%
			);
		border-top: 3px solid #a48b59;
		box-shadow:
			0 -2px 6px rgba(0,0,0,0.2),
			inset 0 2px 6px rgba(255,255,255,0.45);
		pointer-events: none;
		z-index: 0;
	}
	
	/* Lift the main content slightly above the tatami */
	.page {
		position: relative;
		z-index: 1;
	}
}
</style>
</head>
<body>
<div class="page">
    <div class="container">
        <div class="shoji-grid" aria-hidden="true"></div>

        <header class="header">
            <div class="header-title-jp">風灯</div>
            <div class="header-title-main">Wind Lantern</div>
        </header>
        <div class="header-subtitle">
            Reacts to the wind from any location.
        </div>

        <?php if ($errors): ?>
            <div class="msg err">
                <strong>There was a problem:</strong>
                <ul>
                    <?php foreach ($errors as $e): ?>
                        <li><?= htmlspecialchars($e) ?></li>
                    <?php endforeach; ?>
                </ul>
            </div>
        <?php endif; ?>

        <?php if ($successMessage): ?>
            <div class="msg ok">
                <?= htmlspecialchars($successMessage) ?>
            </div>
        <?php endif; ?>

        <div class="columns">
            <!-- LEFT: Address / location -->
            <div class="col">
                <section class="section">
                    <h2 class="section-title">Monitored Address</h2>
                    <div class="section-caption">
                        Enter the address for the lantern to watch over. 
                    </div>

                    <form method="post">
                        <textarea name="address"><?= htmlspecialchars($data['address']) ?></textarea>
                        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf_token) ?>">

                        <div class="btn-row">
                            <button class="btn btn-update" type="submit">
                                Update Address
                            </button>
                        </div>
                    </form>
                </section>
            </div>

            <!-- RIGHT: Wind + map -->
            <div class="col">
                <section class="section wind-section">
                    <h2 class="section-title">Current Wind</h2>

                    <?php if ($windError): ?>
                        <div class="msg err">
                            <?= htmlspecialchars($windError) ?>
                        </div>
                        <div class="wind-note">
                            Once you have saved an address, the tea house will listen for the wind again.
                        </div>
                    <?php elseif ($windResult): ?>
                        <div class="row">
                            <span class="label">Address</span>
                            <span class="value"><?= htmlspecialchars($windResult['address']) ?></span>
                        </div>
                        <div class="row">
                            <span class="label">Latitude</span>
                            <span class="value"><?= htmlspecialchars((string)$windResult['lat']) ?></span>
                        </div>
                        <div class="row">
                            <span class="label">Longitude</span>
                            <span class="value"><?= htmlspecialchars((string)$windResult['lon']) ?></span>
                        </div>
                        <div class="row">
                            <span class="label">Wind Speed</span>
                            <span class="value"><?= $windResult['ws_mph'] ?> mph</span>
                        </div>
                        <div class="row">
                            <span class="label">Wind Gusts</span>
                            <span class="value"><?= $windResult['wg_mph'] ?> mph</span>
                        </div>

                        <div class="btn-row" style="margin-top:10px;">
                            <button class="btn btn-refresh" type="button" onclick="window.location.href='index.php'">
                                Refresh Wind
                            </button>
                        </div>

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
                    <?php else: ?>
                        <div class="wind-note">
                            The tea house is waiting for its first address so it knows where to listen.
                        </div>
                    <?php endif; ?>
                </section>
            </div>
        </div>
    </div>
</div>
<div class="tatami-stripes"></div>
</body>
</html>