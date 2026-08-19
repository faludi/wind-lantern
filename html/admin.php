<?php
declare(strict_types=1);
require_once __DIR__ . '/db.php';

session_set_cookie_params([
    'httponly' => true,
    'samesite' => 'Lax',
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
]);
session_start();

$errors = [];
$success = null;
$pdo = null;
$hasUsers = true;

try {
    $pdo = db();
    $hasUsers = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn() > 0;
    if ($hasUsers && (empty($_SESSION['user_id']) || empty($_SESSION['is_admin']))) {
        redirect_to('index.php');
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        if ($hasUsers) {
            verify_csrf();
        }

        $adminUsername = trim((string)($_POST['admin_username'] ?? ''));
        $adminPassword = (string)($_POST['admin_password'] ?? '');
        if (!$hasUsers) {
            if ($adminUsername === '' || strlen($adminPassword) < 12) {
                $errors[] = 'The administrator username is required and the password must be at least 12 characters.';
            } else {
                $statement = $pdo->prepare('INSERT INTO users (username, password_hash, is_admin) VALUES (:username, :password_hash, 1)');
                $statement->execute([
                    'username' => $adminUsername,
                    'password_hash' => password_hash($adminPassword, PASSWORD_DEFAULT),
                ]);
                session_regenerate_id(true);
                $_SESSION['user_id'] = (int)$pdo->lastInsertId();
                $_SESSION['username'] = $adminUsername;
                $_SESSION['is_admin'] = true;
                redirect_to('admin.php');
            }
        } else {
            $mac = normalize_mac((string)($_POST['mac_address'] ?? ''));
            $address = trim((string)($_POST['address'] ?? ''));
            $username = trim((string)($_POST['username'] ?? ''));
            $password = (string)($_POST['password'] ?? '');
            if ($mac === null) $errors[] = 'Enter a valid 12-digit lantern MAC address.';
            if ($address === '' || strlen($address) > 1024) $errors[] = 'Enter an address up to 1024 characters.';
            if ($username === '') $errors[] = 'Enter a username for the lantern owner.';
            if (strlen($password) < 12) $errors[] = 'The lantern owner password must be at least 12 characters.';

            if (!$errors) {
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
                $success = 'Lantern account created.';
            }
        }
    }
} catch (Throwable $error) {
    if ($pdo instanceof PDO && $pdo->inTransaction()) $pdo->rollBack();
    if ($error instanceof PDOException && $error->getCode() === '23000') {
        $errors[] = 'That username or MAC address is already registered.';
    } else {
        $errors[] = 'The database is unavailable or the setup could not be completed.';
    }
}

$csrf = csrf_token();
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wind Lantern Administration</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 720px; margin: 3rem auto; padding: 0 1rem; color: #302a24; background: #eee7db; }
main { background: #fffaf1; padding: 2rem; border: 1px solid #cbbda8; border-radius: 8px; }
label { display: block; margin-top: 1rem; font-weight: 600; }
input { width: 100%; box-sizing: border-box; padding: .7rem; margin-top: .35rem; }
button { margin-top: 1.25rem; padding: .7rem 1rem; cursor: pointer; }
.error { color: #8b2020; }.success { color: #176b3a; }
a { color: #155d70; }
</style>
</head>
<body>
<main>
<h1>Wind Lantern Administration</h1>
<?php foreach ($errors as $error): ?><p class="error"><?= htmlspecialchars($error) ?></p><?php endforeach; ?>
<?php if ($success): ?><p class="success"><?= htmlspecialchars($success) ?></p><?php endif; ?>
<?php if (!$hasUsers): ?>
<p>Create the first administrator account. This form is available only while the users table is empty.</p>
<form method="post">
<label for="admin_username">Administrator username</label>
<input id="admin_username" name="admin_username" required autocomplete="username">
<label for="admin_password">Administrator password</label>
<input id="admin_password" name="admin_password" type="password" required minlength="12" autocomplete="new-password">
<button type="submit">Create administrator</button>
</form>
<?php else: ?>
<p><a href="index.php">Back to dashboard</a> | <a href="index.php?logout=1">Log out</a></p>
<h2>Add a wind lantern</h2>
<form method="post">
<input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf) ?>">
<label for="mac_address">Lantern MAC address</label>
<input id="mac_address" name="mac_address" placeholder="590E72AC9387" required>
<label for="address">Initial location address</label>
<input id="address" name="address" maxlength="1024" required>
<label for="username">Owner username</label>
<input id="username" name="username" required autocomplete="username">
<label for="password">Owner password</label>
<input id="password" name="password" type="password" minlength="12" required autocomplete="new-password">
<button type="submit">Create lantern account</button>
</form>
<?php endif; ?>
</main>
</body>
</html>
