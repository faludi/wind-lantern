<?php
declare(strict_types=1);

function lantern_settings_schema(): array {
    return [
        'address' => [
            'label' => 'Address',
            'hint' => 'Examples: "350 5th Ave, New York, NY" or "40.749284, -73.985607")',
            'type' => 'string',
            'default' => '',
        ],
        'lantern_brightness' => [
            'label' => 'Lantern Brightness',
            'hint' => 'Percent of full brightness, 0 to 100, default 100',
            'type' => 'int',
            'min' => 0,
            'max' => 100,
            'default' => 100,
        ],
        'night_brightness' => [
            'label' => 'Night Brightness',
            'hint' => 'Percent of full brightness at night, 0 to 100, default 20',
            'type' => 'int',
            'min' => 0,
            'max' => 100,
            'default' => 20,
        ],
        'night_start' => [
            'label' => 'Night Start',
            'hint' => 'Hour when night mode begins.',
            'type' => 'int',
            'min' => 0,
            'max' => 23,
            'default' => 22,
        ],
        'night_end' => [
            'label' => 'Night End',
            'hint' => 'Hour when night mode ends.',
            'type' => 'int',
            'min' => 0,
            'max' => 23,
            'default' => 8,
        ],
        'color_temperature' => [
            'label' => 'Color Temperature',
            'hint' => '',
            'type' => 'int',
            'min' => -10,
            'max' => 10,
            'default' => 0,
        ],
        'flicker_intensity' => [
            'label' => 'Flicker Intensity',
            'hint' => 'Sensitivity to wind, 0 to 5 multiplier, default 1',
            'type' => 'float',
            'min' => 0,
            'max' => 5,
            'step' => 0.1,
            'default' => 1.0,
        ],
        'settings_update_interval' => [
            'label' => 'Settings Update Interval',
            'hint' => 'Frequency of settings updates, 5 to 180 minutes, default 15',
            'type' => 'int',
            'min' => 1,
            'max' => 10080,
            'ui_min' => 5,
            'ui_max' => 180,
            'default' => 15,
        ],
        'settings_endpoint' => [
            'label' => 'Settings Endpoint',
            'hint' => 'HTTP or HTTPS URL used to retrieve online settings.',
            'type' => 'url',
            'default' => 'https://shinyshape.com/windlantern/lantern_checkin.php',
        ],
    ];
}

function lantern_settings_payload(array $row): array {
    $settings = [];
    foreach (lantern_settings_schema() as $key => $field) {
        if (!array_key_exists($key, $row)) {
            throw new InvalidArgumentException('Missing setting: ' . $key);
        }
        if ($field['type'] === 'int') {
            $settings[$key] = (int)$row[$key];
        } elseif ($field['type'] === 'float') {
            $settings[$key] = (float)$row[$key];
        } else {
            $settings[$key] = (string)$row[$key];
        }
    }
    return $settings;
}
