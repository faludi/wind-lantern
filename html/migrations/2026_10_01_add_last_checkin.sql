ALTER TABLE lanterns
    ADD COLUMN last_checkin TIMESTAMP NULL DEFAULT NULL AFTER flicker_intensity;
