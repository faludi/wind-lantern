ALTER TABLE lanterns
    ADD COLUMN settings_endpoint VARCHAR(1024) NOT NULL DEFAULT 'https://shinyshape.com/windlantern/lantern_checkin.php' AFTER address,
    ADD COLUMN settings_update_interval SMALLINT UNSIGNED NOT NULL DEFAULT 15 CHECK (settings_update_interval BETWEEN 1 AND 10080) AFTER settings_endpoint;