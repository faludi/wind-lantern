-- Adds user-configurable lantern settings columns.
-- Safe to run against the existing production database; existing rows keep
-- their current address and receive the documented defaults for new columns.

ALTER TABLE lanterns
    ADD COLUMN lantern_brightness TINYINT UNSIGNED NOT NULL DEFAULT 100
        CHECK (lantern_brightness BETWEEN 0 AND 100) AFTER address,
    ADD COLUMN night_brightness TINYINT UNSIGNED NOT NULL DEFAULT 20
        CHECK (night_brightness BETWEEN 0 AND 100) AFTER lantern_brightness,
    ADD COLUMN night_start TINYINT UNSIGNED NOT NULL DEFAULT 22
        CHECK (night_start BETWEEN 0 AND 23) AFTER night_brightness,
    ADD COLUMN night_end TINYINT UNSIGNED NOT NULL DEFAULT 8
        CHECK (night_end BETWEEN 0 AND 23) AFTER night_start,
    ADD COLUMN color_temperature TINYINT NOT NULL DEFAULT 0
        CHECK (color_temperature BETWEEN -5 AND 5) AFTER night_end,
    ADD COLUMN flicker_intensity DECIMAL(4,2) NOT NULL DEFAULT 1.00
        CHECK (flicker_intensity BETWEEN 0.1 AND 10) AFTER color_temperature;
