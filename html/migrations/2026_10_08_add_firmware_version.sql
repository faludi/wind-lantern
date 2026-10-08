ALTER TABLE lanterns
    ADD COLUMN firmware_version VARCHAR(32) NULL DEFAULT NULL AFTER last_checkin;
