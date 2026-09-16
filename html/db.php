<?php
declare(strict_types=1);

function db(): PDO {
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $configPath = dirname(__DIR__) . '/wind_lantern_db_config.php';
    if (!is_readable($configPath)) {
        throw new RuntimeException('Database configuration is missing.');
    }

    $config = require $configPath;
    $pdo = new PDO(
        (string)$config['dsn'],
        (string)$config['username'],
        (string)$config['password'],
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]
    );
    return $pdo;
}

function normalize_mac(string $mac): ?string {
    $normalized = strtoupper(preg_replace('/[^a-f0-9]/i', '', trim($mac)) ?? '');
    return preg_match('/^[A-F0-9]{12}$/', $normalized) ? $normalized : null;
}

function redirect_to(string $location): never {
    header('Location: ' . $location);
    exit;
}

function require_login(): array {
    if (empty($_SESSION['user_id'])) {
        redirect_to('index.php');
    }
    return [
        'id' => (int)$_SESSION['user_id'],
        'username' => (string)($_SESSION['username'] ?? ''),
        'is_admin' => !empty($_SESSION['is_admin']),
    ];
}

function csrf_token(): string {
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function verify_csrf(): void {
    if (!hash_equals(csrf_token(), (string)($_POST['csrf_token'] ?? ''))) {
        throw new RuntimeException('Invalid CSRF token.');
    }
}

/**
 * Validates a raw string as an integer within [min, max].
 * Returns the parsed int on success, or null and appends an error message on failure.
 */
function validate_int_range(string $raw, int $min, int $max, string $label, array &$errors): ?int {
    $trimmed = trim($raw);
    if ($trimmed === '' || !preg_match('/^-?\d+$/', $trimmed)) {
        $errors[$label] = "$label must be a whole number between $min and $max.";
        return null;
    }
    $value = (int)$trimmed;
    if ($value < $min || $value > $max) {
        $errors[$label] = "$label must be between $min and $max.";
        return null;
    }
    return $value;
}

/**
 * Validates a raw string as a float within [min, max].
 * Returns the parsed float on success, or null and appends an error message on failure.
 */
function validate_float_range(string $raw, float $min, float $max, string $label, array &$errors): ?float {
    $trimmed = trim($raw);
    if ($trimmed === '' || !is_numeric($trimmed)) {
        $errors[$label] = "$label must be a number between $min and $max.";
        return null;
    }
    $value = (float)$trimmed;
    if ($value < $min || $value > $max) {
        $errors[$label] = "$label must be between $min and $max.";
        return null;
    }
    return $value;
}