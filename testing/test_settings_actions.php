<?php
declare(strict_types=1);

require_once __DIR__ . '/../html/settings_schema.php';
require_once __DIR__ . '/../html/settings_actions.php';

function assert_same($expected, $actual, string $message): void {
    if ($expected !== $actual) {
        throw new RuntimeException($message . "\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true));
    }
}

$fields = lantern_settings_schema();
$lantern = [
    'address' => 'Current Place',
    'settings_endpoint' => 'https://example.test/checkin.php',
];
$post = [
    'address' => "  350 5th Ave\nNew York; NY ",
    'lantern_brightness' => '75',
    'night_start' => '21',
    'night_end' => '7',
    'night_brightness' => '25',
    'color_temperature' => '-3',
    'flicker_intensity' => '1.5',
    'settings_update_interval' => '500',
    'settings_endpoint' => 'https://example.test/new.php',
];

$admin = validate_lantern_settings_submission($post, $fields, $lantern, true);
assert_same('350 5th Ave New York NY', $admin['address'], 'Address sanitization');
assert_same(75, $admin['setting_values']['lantern_brightness'], 'Integer setting coercion');
assert_same(1.5, $admin['setting_values']['flicker_intensity'], 'Float setting coercion');
assert_same(500, $admin['setting_values']['settings_update_interval'], 'Server interval range');
assert_same('https://example.test/new.php', $admin['setting_values']['settings_endpoint'], 'Admin endpoint update');
assert_same([], $admin['field_errors'], 'Valid admin submission');

$pdo = new PDO('sqlite::memory:');
$pdo->exec('CREATE TABLE lanterns (
    id INTEGER PRIMARY KEY,
    mac_address TEXT,
    address TEXT,
    settings_endpoint TEXT,
    settings_update_interval INTEGER,
    lantern_brightness INTEGER,
    night_brightness INTEGER,
    night_start INTEGER,
    night_end INTEGER,
    color_temperature INTEGER,
    flicker_intensity REAL
)');
$pdo->exec("INSERT INTO lanterns VALUES (1, 'AABBCCDDEEFF', 'Old Place', 'https://example.test/checkin.php', 15, 75, 25, 21, 7, -3, 1.5)");
$storedLantern = $pdo->query('SELECT * FROM lanterns WHERE id = 1')->fetch(PDO::FETCH_ASSOC);
$persisted = persist_lantern_settings($pdo, $storedLantern, $admin['address'], $admin['setting_values'], $fields);
assert_same($admin['address'], $persisted['lantern']['address'], 'Persisted address');
assert_same(500, $persisted['lantern']['settings_update_interval'], 'Persisted server interval');
assert_same(3, count($persisted['changes']), 'Changed-field summary');
$unchanged = persist_lantern_settings($pdo, $persisted['lantern'], $admin['address'], $admin['setting_values'], $fields);
assert_same([], $unchanged['changes'], 'Unchanged-field summary');

$nonAdmin = validate_lantern_settings_submission($post, $fields, $lantern, false);
assert_same($lantern['settings_endpoint'], $nonAdmin['setting_values']['settings_endpoint'], 'Non-admin endpoint protection');

$invalid = $post;
$invalid['address'] = '   ';
$invalid['lantern_brightness'] = '101';
$invalid['settings_endpoint'] = 'ftp://example.test/file';
$result = validate_lantern_settings_submission($invalid, $fields, $lantern, true);
assert_same('Address cannot be empty.', $result['field_errors']['Address'], 'Address validation');
assert_same('Lantern Brightness must be between 0 and 100.', $result['field_errors']['Lantern Brightness'], 'Brightness validation');
assert_same('Settings Endpoint must be a valid HTTP or HTTPS URL.', $result['field_errors']['Settings Endpoint'], 'Endpoint validation');

echo "settings_actions tests passed\n";