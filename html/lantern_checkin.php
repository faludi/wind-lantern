<?php
declare(strict_types=1);
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/settings_schema.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

$mac = normalize_mac((string)($_GET['mac'] ?? ''));
if ($mac === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid MAC address.']);
    exit;
}

try {
    $pdo = db();
    $settingsFields = lantern_settings_schema();
    $settingsColumns = implode(', ', array_keys($settingsFields));
    $statement = $pdo->prepare(
        'SELECT ' . $settingsColumns .
        ' FROM lanterns WHERE mac_address = :mac AND is_active = 1'
    );
    $statement->execute(['mac' => $mac]);
    $lantern = $statement->fetch();
    if (!$lantern) {
        http_response_code(404);
        echo json_encode(['error' => 'Lantern not found.']);
        exit;
    }

    $version = substr(trim((string)($_GET['version'] ?? '')), 0, 32);
    $statement = $pdo->prepare('UPDATE lanterns SET last_checkin = NOW(), firmware_version = COALESCE(:version, firmware_version) WHERE mac_address = :mac');
    $statement->execute(['mac' => $mac, 'version' => $version !== '' ? $version : null]);

    // Atomic claim so the one-time trigger is delivered once and then cleared.
    $statement = $pdo->prepare('UPDATE lanterns SET update_firmware = 0 WHERE mac_address = :mac AND update_firmware = 1');
    $statement->execute(['mac' => $mac]);
    $updateFirmware = $statement->rowCount() === 1;

    $response = ['update_firmware' => $updateFirmware] + lantern_settings_payload($lantern);
    echo json_encode($response, JSON_UNESCAPED_UNICODE);
} catch (Throwable $error) {
    http_response_code(500);
    echo json_encode(['error' => 'Service unavailable.']);
}