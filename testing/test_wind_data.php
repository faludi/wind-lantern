<?php
declare(strict_types=1);

require_once __DIR__ . '/../html/wind_data.php';

function assert_same($expected, $actual, string $message): void {
    if ($expected !== $actual) {
        throw new RuntimeException($message . "\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true));
    }
}

function fake_fetch(array $responses, array &$urls): callable {
    return static function ($url, $context = null) use ($responses, &$urls) {
        $urls[] = $url;
        foreach ($responses as $needle => $response) {
            if (strpos($url, $needle) !== false) {
                return $response;
            }
        }
        return false;
    };
}

$urls = [];
$fetch = fake_fetch([
    'nominatim.openstreetmap.org' => json_encode([['lat' => '40.1', 'lon' => '-73.2']]),
    'api.open-meteo.com' => json_encode(['current' => ['wind_speed_10m' => 10, 'wind_gusts_10m' => 20]]),
], $urls);
$wind = fetch_wind_data('Test City', $fetch);
assert_same(null, $wind['error'], 'Successful fetch error');
assert_same(40.1, $wind['result']['lat'], 'Latitude');
assert_same(-73.2, $wind['result']['lon'], 'Longitude');
assert_same(6.21, $wind['result']['ws_mph'], 'Wind unit conversion');
assert_same(2, count($urls), 'Expected two external requests');

assert_same('Please enter and save an address first.', fetch_wind_data('')['error'], 'Empty address');
assert_same(
    'Failed to fetch coordinates.',
    fetch_wind_data('Test City', fake_fetch(['nominatim.openstreetmap.org' => false], $urls))['error'],
    'Geocoding request failure'
);
assert_same(
    'No results found for the address.',
    fetch_wind_data('Unknown Place', fake_fetch(['nominatim.openstreetmap.org' => '[]'], $urls))['error'],
    'No geocoding result'
);
assert_same(
    'Failed to fetch weather.',
    fetch_wind_data('Test City', fake_fetch([
        'nominatim.openstreetmap.org' => json_encode([['lat' => '40.1', 'lon' => '-73.2']]),
        'api.open-meteo.com' => false,
    ], $urls))['error'],
    'Weather request failure'
);
assert_same(
    'Weather data incomplete.',
    fetch_wind_data('Test City', fake_fetch([
        'nominatim.openstreetmap.org' => json_encode([['lat' => '40.1', 'lon' => '-73.2']]),
        'api.open-meteo.com' => json_encode(['current' => []]),
    ], $urls))['error'],
    'Incomplete weather payload'
);

echo "wind_data tests passed\n";