<?php
declare(strict_types=1);

function fetch_wind_data(string $address, ?callable $fetch = null): array {
    if (trim($address) === '') {
        return ['error' => 'Please enter and save an address first.', 'result' => null];
    }

    if ($fetch === null) {
        $fetch = static function ($url, $context = null) {
            return @file_get_contents($url, false, $context);
        };
    }

    $encodedAddress = urlencode($address);
    $nominatimUrl = "https://nominatim.openstreetmap.org/search?q={$encodedAddress}&format=json&limit=1";
    $context = stream_context_create([
        'http' => ['header' => "User-Agent: WindLantern/1.0\r\n"]
    ]);
    $nomResponse = $fetch($nominatimUrl, $context);

    if ($nomResponse === false) {
        return ['error' => 'Failed to fetch coordinates.', 'result' => null];
    }

    $nom = json_decode($nomResponse, true);
    if (!$nom || !isset($nom[0]['lat'], $nom[0]['lon'])) {
        return ['error' => 'No results found for the address.', 'result' => null];
    }

    $lat = $nom[0]['lat'];
    $lon = $nom[0]['lon'];
    $weatherUrl = "https://api.open-meteo.com/v1/forecast?latitude={$lat}&longitude={$lon}&current=wind_speed_10m,wind_gusts_10m";
    $weatherResponse = $fetch($weatherUrl);

    if ($weatherResponse === false) {
        return ['error' => 'Failed to fetch weather.', 'result' => null];
    }

    $weather = json_decode($weatherResponse, true);
    $current = $weather['current'] ?? [];
    if (!isset($current['wind_speed_10m'], $current['wind_gusts_10m'])) {
        return ['error' => 'Weather data incomplete.', 'result' => null];
    }

    $latitude = (float)$lat;
    $longitude = (float)$lon;
    $delta = 0.002;
    $minLongitude = $longitude - $delta;
    $minLatitude = $latitude - $delta;
    $maxLongitude = $longitude + $delta;
    $maxLatitude = $latitude + $delta;
    $bbox = $minLongitude . '%2C' . $minLatitude . '%2C' . $maxLongitude . '%2C' . $maxLatitude;
    $zoom = 16;

    return [
        'error' => null,
        'result' => [
            'address' => $address,
            'lat' => $latitude,
            'lon' => $longitude,
            'ws_kmh' => $current['wind_speed_10m'],
            'wg_kmh' => $current['wind_gusts_10m'],
            'ws_mph' => round($current['wind_speed_10m'] * 0.62137119, 2),
            'wg_mph' => round($current['wind_gusts_10m'] * 0.62137119, 2),
            'map_src' => "https://www.openstreetmap.org/export/embed.html?bbox={$bbox}&layer=mapnik&marker={$latitude}%2C{$longitude}",
            'map_link' => "https://www.openstreetmap.org/?mlat={$latitude}&mlon={$longitude}#map={$zoom}/{$latitude}/{$longitude}",
        ],
    ];
}