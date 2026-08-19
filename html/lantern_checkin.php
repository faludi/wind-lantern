<?php
declare(strict_types=1);
require_once __DIR__ . '/db.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');

$mac = normalize_mac((string)($_GET['mac'] ?? ''));
if ($mac === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid MAC address.']);
    exit;
}

try {
    $statement = db()->prepare('SELECT address FROM lanterns WHERE mac_address = :mac AND is_active = 1');
    $statement->execute(['mac' => $mac]);
    $lantern = $statement->fetch();
    if (!$lantern) {
        http_response_code(404);
        echo json_encode(['error' => 'Lantern not found.']);
        exit;
    }
    echo json_encode(['address' => $lantern['address']], JSON_UNESCAPED_UNICODE);
} catch (Throwable $error) {
    http_response_code(500);
    echo json_encode(['error' => 'Service unavailable.']);
}