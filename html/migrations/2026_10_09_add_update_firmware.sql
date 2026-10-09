ALTER TABLE lanterns
    ADD COLUMN update_firmware TINYINT(1) NOT NULL DEFAULT 0 AFTER firmware_version;
