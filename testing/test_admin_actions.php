<?php
declare(strict_types=1);

require_once __DIR__ . '/../html/admin_actions.php';

function assert_same($expected, $actual, string $message): void {
    if ($expected !== $actual) {
        throw new RuntimeException($message . "\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true));
    }
}

function create_test_database(): PDO {
    $pdo = new PDO('sqlite::memory:');
    $pdo->exec('CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0
    )');
    $pdo->exec('CREATE TABLE lanterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mac_address TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        address TEXT NOT NULL,
        update_firmware INTEGER NOT NULL DEFAULT 0
    )');
    return $pdo;
}

$pdo = create_test_database();
$invalidFirstAdmin = handle_admin_post($pdo, false, ['admin_username' => '', 'admin_password' => 'short']);
assert_same(1, count($invalidFirstAdmin['errors']), 'Invalid first-admin errors');
assert_same(0, (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn(), 'Invalid first admin is not inserted');

$firstAdmin = handle_admin_post($pdo, false, ['admin_username' => 'root', 'admin_password' => 'long-secure-password']);
assert_same(['id' => 1, 'username' => 'root'], $firstAdmin['created_admin'], 'First-admin session data');
$adminRow = $pdo->query('SELECT * FROM users WHERE id = 1')->fetch(PDO::FETCH_ASSOC);
assert_same(1, (int)$adminRow['is_admin'], 'First account has admin role');
if (!password_verify('long-secure-password', $adminRow['password_hash'])) {
    throw new RuntimeException('First-admin password was not hashed correctly');
}

$createdLantern = handle_admin_post($pdo, true, [
    'action' => 'create_lantern',
    'mac_address' => 'aa:bb:cc:dd:ee:ff',
    'address' => 'Test Address',
    'username' => 'owner',
    'password' => 'owner-secure-password',
]);
assert_same('Lantern account created.', $createdLantern['success'], 'Create-lantern success');
$owner = $pdo->query("SELECT * FROM users WHERE username = 'owner'")->fetch(PDO::FETCH_ASSOC);
$lantern = $pdo->query('SELECT * FROM lanterns WHERE user_id = ' . (int)$owner['id'])->fetch(PDO::FETCH_ASSOC);
assert_same('AABBCCDDEEFF', $lantern['mac_address'], 'Normalized lantern MAC');
assert_same('Test Address', $lantern['address'], 'Created lantern address');

$updateUser = handle_admin_post($pdo, true, [
    'action' => 'update_user',
    'user_id' => (string)$owner['id'],
    'username' => 'owner-renamed',
    'password' => '',
]);
assert_same(['id' => (int)$owner['id'], 'username' => 'owner-renamed'], $updateUser['updated_user'], 'Updated user session data');
$updatedOwner = $pdo->query('SELECT * FROM users WHERE id = ' . (int)$owner['id'])->fetch(PDO::FETCH_ASSOC);
if (!password_verify('owner-secure-password', $updatedOwner['password_hash'])) {
    throw new RuntimeException('Username-only update should preserve the password hash');
}

$queueUpdate = handle_admin_post($pdo, true, [
    'action' => 'set_firmware_update',
    'lantern_id' => (string)$lantern['id'],
    'update_firmware' => '1',
]);
assert_same('Firmware update queued for next check-in.', $queueUpdate['success'], 'Firmware queue message');
assert_same(1, (int)$pdo->query('SELECT update_firmware FROM lanterns WHERE id = ' . (int)$lantern['id'])->fetchColumn(), 'Firmware flag');

$unknownAction = handle_admin_post($pdo, true, ['action' => 'unknown']);
assert_same(['Unknown administration action.'], $unknownAction['errors'], 'Unknown action error');

echo "admin_actions tests passed\n";