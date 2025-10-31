<?php
// Read the JSON file
$jsonFile = __DIR__ . '/wind_lantern_settings.json';
if (!file_exists($jsonFile)) {
    die("Error: data.json file not found.");
}

$data = json_decode(file_get_contents($jsonFile), true);
if (!isset($data['address'])) {
    die("Error: Address not found in JSON file.");
}

$address = urlencode($data['address']);

// Step 1: Lookup latitude and longitude using Nominatim API
$nominatimUrl = "https://nominatim.openstreetmap.org/search?q={$address}&format=json&limit=1";
$options = [
    "http" => [
        "header" => "User-Agent: PHP/8.2\r\n"
    ]
];
$context = stream_context_create($options);
$nominatimResponse = file_get_contents($nominatimUrl, false, $context);

if ($nominatimResponse === FALSE) {
    die("Error: Failed to fetch coordinates.");
}

$nominatimData = json_decode($nominatimResponse, true);
if (empty($nominatimData)) {
    die("Error: No results found for the given address.");
}

$latitude = $nominatimData[0]['lat'];
$longitude = $nominatimData[0]['lon'];

// Step 2: Lookup wind data using Open-Meteo API
$weatherUrl = "https://api.open-meteo.com/v1/forecast?latitude={$latitude}&longitude={$longitude}&current=wind_speed_10m,wind_gusts_10m";
$weatherResponse = file_get_contents($weatherUrl);

if ($weatherResponse === FALSE) {
    die("Error: Failed to fetch weather data.");
}

$weatherData = json_decode($weatherResponse, true);
$current = $weatherData['current'] ?? [];

$windSpeed = $current['wind_speed_10m'] ?? 'N/A';
$windGusts = $current['wind_gusts_10m'] ?? 'N/A';
// Convert from km/h to mph
$windSpeedMph = round($windSpeed * 0.62137119, 2);
$windGustsMph = round($windGusts * 0.62137119, 2);
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <!-- <meta http-equiv="refresh" content="5" /> -->
    <title>Weather Lookup</title>
    <script type="text/javascript">
        window.onload = function() {
    if(!window.location.hash) {
        window.location = window.location + '#loaded';
        window.location.reload();
    }
}
    </script>
    <style>
        body {
            font-family: system-ui, sans-serif;
            background-color: #f2f2f2;
            color: #333;
            padding: 2rem;
        }
        .container {
            background: white;
            max-width: 500px;
            margin: auto;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }
        .btn { 
            display:inline-block; 
            margin-top:10px; 
            padding:8px 14px; 
            border-radius:8px; 
            border:0; 
            cursor:pointer; 
            background:#0066cc;
            color:#fff;
            font-weight:600; }
        h1 {
            text-align: center;
        }
        .data {
            margin-top: 1rem;
            font-size: 1.1rem;
        }
        .label {
            font-weight: bold;
        }
    </style>
</head>
<body>
<div class="container">
    <h1>Wind Conditions</h1>
    <p align="center"><button onclick="location.reload();">Refresh Page</button></p>
    <div class="data"><span class="label">Address:</span> <?= htmlspecialchars($data['address']) ?></div>
    <div class="data"><span class="label">Latitude:</span> <?= htmlspecialchars($latitude) ?></div>
    <div class="data"><span class="label">Longitude:</span> <?= htmlspecialchars($longitude) ?></div>
    <div class="data"><span class="label">Wind Speed (10m):</span> <?= htmlspecialchars($windSpeedMph) ?> mph</div>
    <div class="data"><span class="label">Wind Gusts (10m):</span> <?= htmlspecialchars($windGustsMph) ?> mph</div>
    <p align="center"><button class="btn" type="button" onclick="window.location.href='index.php';">Back</button></p> 
</div>

</body>
</html>