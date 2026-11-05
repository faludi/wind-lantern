<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';

function handle_admin_post(PDO $pdo, bool $hasUsers, array $post): array {
    $result = [
        'errors' => [],
        'success' => null,
        'created_admin' => null,
        'updated_user' => null,
    ];

    if (!$hasUsers) {
        $adminUsername = trim((string)($post['admin_username'] ?? ''));
        $adminPassword = (string)($post['admin_password'] ?? '');
        if ($adminUsername === '' || strlen($adminPassword) < 12) {
            $result['errors'][] = 'The administrator username is required and the password must be at least 12 characters.';
        } else {
            $statement = $pdo->prepare('INSERT INTO users (username, password_hash, is_admin) VALUES (:username, :password_hash, 1)');
            $statement->execute([
                'username' => $adminUsername,
                'password_hash' => password_hash($adminPassword, PASSWORD_DEFAULT),
            ]);
            $result['created_admin'] = [
                'id' => (int)$pdo->lastInsertId(),
                'username' => $adminUsername,
            ];
        }
        return $result;
    }

    $action = (string)($post['action'] ?? 'create_lantern');
    if ($action === 'create_lantern') {
        $mac = normalize_mac((string)($post['mac_address'] ?? ''));
        $address = trim((string)($post['address'] ?? ''));
        $username = trim((string)($post['username'] ?? ''));
        $password = (string)($post['password'] ?? '');
        if ($mac === null) $result['errors'][] = 'Enter a valid 12-digit lantern MAC address.';
        if ($address === '' || strlen($address) > 1024) $result['errors'][] = 'Enter an address up to 1024 characters.';
        if ($username === '' || strlen($username) > 100) $result['errors'][] = 'Enter an owner username up to 100 characters.';
        if (strlen($password) < 12) $result['errors'][] = 'The lantern owner password must be at least 12 characters.';

        if (!$result['errors']) {
            $pdo->beginTransaction();
            $statement = $pdo->prepare('INSERT INTO users (username, password_hash, is_admin) VALUES (:username, :password_hash, 0)');
            $statement->execute([
                'username' => $username,
                'password_hash' => password_hash($password, PASSWORD_DEFAULT),
            ]);
            $ownerId = (int)$pdo->lastInsertId();
            $statement = $pdo->prepare('INSERT INTO lanterns (mac_address, user_id, address) VALUES (:mac, :user_id, :address)');
            $statement->execute(['mac' => $mac, 'user_id' => $ownerId, 'address' => $address]);
            $pdo->commit();
            $result['success'] = 'Lantern account created.';
        }
    } elseif ($action === 'update_user') {
        $userId = filter_var($post['user_id'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
        $username = trim((string)($post['username'] ?? ''));
        $password = (string)($post['password'] ?? '');
        if ($userId === false) $result['errors'][] = 'User not found.';
        if ($username === '' || strlen($username) > 100) $result['errors'][] = 'Enter a username up to 100 characters.';
        if ($password !== '' && strlen($password) < 12) $result['errors'][] = 'A replacement password must be at least 12 characters.';
        if (!$result['errors']) {
            $sql = $password === ''
                ? 'UPDATE users SET username = :username WHERE id = :id'
                : 'UPDATE users SET username = :username, password_hash = :password_hash WHERE id = :id';
            $statement = $pdo->prepare($sql);
            $params = ['username' => $username, 'id' => $userId];
            if ($password !== '') $params['password_hash'] = password_hash($password, PASSWORD_DEFAULT);
            $statement->execute($params);
            $result['updated_user'] = ['id' => (int)$userId, 'username' => $username];
            $result['success'] = 'User updated.';
        }
    } elseif ($action === 'set_firmware_update') {
        $lanternId = filter_var($post['lantern_id'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
        if ($lanternId === false) {
            $result['errors'][] = 'Lantern not found.';
        } else {
            $enabled = ($post['update_firmware'] ?? '') === '1' ? 1 : 0;
            $statement = $pdo->prepare('UPDATE lanterns SET update_firmware = :enabled WHERE id = :id');
            $statement->execute(['enabled' => $enabled, 'id' => $lanternId]);
            $result['success'] = $enabled ? 'Firmware update queued for next check-in.' : 'Firmware update cancelled.';
        }
    } else {
        $result['errors'][] = 'Unknown administration action.';
    }

    return $result;
}