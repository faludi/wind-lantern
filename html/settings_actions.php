<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';

function validate_lantern_settings_submission(array $post, array $settingsFields, array $lantern, bool $isAdmin): array {
    $fieldErrors = [];
    $data = [];
    $rawAddress = (string)($post['address'] ?? '');
    $address = trim(preg_replace('/[\r\n\/"\'\\\\;]+/m', ' ', $rawAddress) ?? '');
    $address = preg_replace('/\s+/', ' ', $address) ?? '';
    $data['address'] = $address;
    if ($address === '') {
        $fieldErrors['Address'] = 'Address cannot be empty.';
    } elseif (strlen($address) > 1024) {
        $fieldErrors['Address'] = 'Address must be 1024 characters or fewer.';
    }

    $settingValues = [];
    foreach ($settingsFields as $key => $field) {
        if ($key === 'address') {
            continue;
        }
        if ($key === 'settings_endpoint' && !$isAdmin) {
            $settingValues[$key] = $lantern[$key];
            continue;
        }
        $raw = (string)($post[$key] ?? '');
        $data[$key] = $raw;
        if ($field['type'] === 'url') {
            $url = trim($raw);
            $parts = filter_var($url, FILTER_VALIDATE_URL) ? parse_url($url) : false;
            if ($parts === false || !in_array(strtolower((string)($parts['scheme'] ?? '')), ['http', 'https'], true)) {
                $fieldErrors[$field['label']] = 'Settings Endpoint must be a valid HTTP or HTTPS URL.';
                $settingValues[$key] = null;
            } else {
                $settingValues[$key] = $url;
                $data[$key] = $url;
            }
        } else {
            $settingValues[$key] = $field['type'] === 'float'
                ? validate_float_range($raw, $field['min'], $field['max'], $field['label'], $fieldErrors)
                : validate_int_range($raw, (int)$field['min'], (int)$field['max'], $field['label'], $fieldErrors);
        }
    }

    return [
        'address' => $address,
        'setting_values' => $settingValues,
        'data' => $data,
        'field_errors' => $fieldErrors,
    ];
}

function persist_lantern_settings(PDO $pdo, array $lantern, string $address, array $settingValues, array $settingsFields): array {
    $changes = [];
    if ($address !== (string)$lantern['address']) {
        $changes[] = "Address: {$lantern['address']} -> $address";
    }
    foreach ($settingValues as $key => $value) {
        if ($settingsFields[$key]['type'] === 'url') {
            $hasChanged = $value !== (string)$lantern[$key];
        } elseif ($settingsFields[$key]['type'] === 'float') {
            $hasChanged = (float)$value !== (float)$lantern[$key];
        } else {
            $hasChanged = (int)$value !== (int)$lantern[$key];
        }
        if ($hasChanged) {
            $changes[] = "{$settingsFields[$key]['label']}: {$lantern[$key]} -> $value";
        }
    }

    $statement = $pdo->prepare(
        'UPDATE lanterns SET address = :address, settings_endpoint = :settings_endpoint,
         settings_update_interval = :settings_update_interval, lantern_brightness = :lantern_brightness,
         night_brightness = :night_brightness, night_start = :night_start, night_end = :night_end,
         color_temperature = :color_temperature, flicker_intensity = :flicker_intensity
         WHERE id = :id'
    );
    $statement->execute([
        'address' => $address,
        'settings_endpoint' => $settingValues['settings_endpoint'],
        'settings_update_interval' => $settingValues['settings_update_interval'],
        'lantern_brightness' => $settingValues['lantern_brightness'],
        'night_brightness' => $settingValues['night_brightness'],
        'night_start' => $settingValues['night_start'],
        'night_end' => $settingValues['night_end'],
        'color_temperature' => $settingValues['color_temperature'],
        'flicker_intensity' => $settingValues['flicker_intensity'],
        'id' => $lantern['id'],
    ]);

    return [
        'lantern' => array_merge($lantern, ['address' => $address], $settingValues),
        'changes' => $changes,
    ];
}