<?php
declare(strict_types=1);
require_once __DIR__ . '/db.php';

session_set_cookie_params([
    'httponly' => true,
    'samesite' => 'Lax',
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
]);
session_start();
enforce_session_timeout();

$errors = [];
$success = null;
$pdo = null;
$hasUsers = true;
$users = [];
$lanterns = [];
$selectedUser = null;
$showLanternCreation = false;

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

        if (!$hasUsers) {
            $adminUsername = trim((string)($_POST['admin_username'] ?? ''));
            $adminPassword = (string)($_POST['admin_password'] ?? '');
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
                $_SESSION['last_activity'] = time();
                redirect_to('admin.php');
            }
        } else {
            $action = (string)($_POST['action'] ?? 'create_lantern');
            if ($action === 'create_lantern') {
                $mac = normalize_mac((string)($_POST['mac_address'] ?? ''));
                $address = trim((string)($_POST['address'] ?? ''));
                $username = trim((string)($_POST['username'] ?? ''));
                $password = (string)($_POST['password'] ?? '');
                if ($mac === null) $errors[] = 'Enter a valid 12-digit lantern MAC address.';
                if ($address === '' || strlen($address) > 1024) $errors[] = 'Enter an address up to 1024 characters.';
                if ($username === '' || strlen($username) > 100) $errors[] = 'Enter an owner username up to 100 characters.';
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
            } elseif ($action === 'update_user') {
                $userId = filter_var($_POST['user_id'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
                $username = trim((string)($_POST['username'] ?? ''));
                $password = (string)($_POST['password'] ?? '');
                if ($userId === false) $errors[] = 'User not found.';
                if ($username === '' || strlen($username) > 100) $errors[] = 'Enter a username up to 100 characters.';
                if ($password !== '' && strlen($password) < 12) $errors[] = 'A replacement password must be at least 12 characters.';
                if (!$errors) {
                    $sql = $password === ''
                        ? 'UPDATE users SET username = :username WHERE id = :id'
                        : 'UPDATE users SET username = :username, password_hash = :password_hash WHERE id = :id';
                    $statement = $pdo->prepare($sql);
                    $params = ['username' => $username, 'id' => $userId];
                    if ($password !== '') $params['password_hash'] = password_hash($password, PASSWORD_DEFAULT);
                    $statement->execute($params);
                    if ((int)($_SESSION['user_id'] ?? 0) === (int)$userId) {
                        $_SESSION['username'] = $username;
                    }
                    $success = 'User updated.';
                }
            } else {
                $errors[] = 'Unknown administration action.';
            }
        }
    }

    if ($hasUsers) {
        $users = $pdo->query('SELECT id, username, is_admin, created_at FROM users ORDER BY is_admin DESC, id')->fetchAll();
        $lanterns = $pdo->query(
            'SELECT lanterns.id, lanterns.mac_address, lanterns.user_id, lanterns.address, lanterns.created_at, users.username AS owner_username
             FROM lanterns JOIN users ON users.id = lanterns.user_id ORDER BY lanterns.id'
        )->fetchAll();
        $selectedUserId = filter_var($_GET['user'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
        if ($selectedUserId !== false) {
            foreach ($users as $user) {
                if ((int)$user['id'] === $selectedUserId) {
                    $selectedUser = $user;
                    break;
                }
            }
            if ($selectedUser === null) $errors[] = 'User not found.';
        }
        $showLanternCreation = ($_GET['create_lantern'] ?? '') === '1';
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
select { width: 100%; box-sizing: border-box; padding: .7rem; margin-top: .35rem; }
button { margin-top: 1.25rem; padding: .7rem 1rem; cursor: pointer; }
.error { color: #8b2020; }.success { color: #176b3a; }
a { color: #155d70; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th, td { padding: .75rem 0; border-bottom: 1px solid #cbbda8; text-align: left; vertical-align: top; }
small { color: #645a50; }
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
<?php if ($selectedUser): ?>
<p><a href="admin.php">Back to users and lanterns</a></p>
<h2>Edit user</h2>
<form method="post" action="admin.php?user=<?= (int)$selectedUser['id'] ?>">
<input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf) ?>">
<input type="hidden" name="action" value="update_user">
<input type="hidden" name="user_id" value="<?= (int)$selectedUser['id'] ?>">
<label for="username">Username</label>
<input id="username" name="username" value="<?= htmlspecialchars($selectedUser['username']) ?>" maxlength="100" required autocomplete="username">
<label for="password">Replacement password <small>(leave blank to keep current password)</small></label>
<input id="password" name="password" type="password" minlength="12" autocomplete="new-password">
<button type="submit">Update user</button>
</form>
<?php elseif ($showLanternCreation): ?>
<p><a href="admin.php">Back to users and lanterns</a></p>
<h2>Add a wind lantern</h2>
<form method="post">
<input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf) ?>">
<input type="hidden" name="action" value="create_lantern">
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
<?php else: ?>
<p><a href="admin.php?create_lantern=1">Add a wind lantern</a></p>
<h2>Users</h2>
<?php if (!$users): ?>
<p>No users found.</p>
<?php else: ?>
<table>
<thead><tr><th>User</th><th>Role</th><th>Created</th></tr></thead>
<tbody>
<?php foreach ($users as $user): ?>
<tr>
<td><a href="admin.php?user=<?= (int)$user['id'] ?>"><?= htmlspecialchars($user['username']) ?></a></td>
<td><?= $user['is_admin'] ? 'Superuser' : 'Lantern owner' ?></td>
<td><?= htmlspecialchars($user['created_at']) ?></td>
</tr>
<?php endforeach; ?>
</tbody>
</table>
<?php endif; ?>

<h2>Lanterns</h2>
<?php if (!$lanterns): ?>
<p>No lanterns found.</p>
<?php else: ?>
<table>
<thead><tr><th>MAC address</th><th>Owner</th><th>Created</th></tr></thead>
<tbody>
<?php foreach ($lanterns as $lantern): ?>
<tr>
<td><a href="index.php?lantern=<?= (int)$lantern['id'] ?>"><?= htmlspecialchars($lantern['mac_address']) ?></a></td>
<td><?= htmlspecialchars($lantern['owner_username']) ?></td>
<td><?= htmlspecialchars($lantern['created_at']) ?></td>
</tr>
<?php endforeach; ?>
</tbody>
</table>
<?php endif; ?>
<?php endif; ?>
<?php endif; ?>
</main>
</body>
</html>
