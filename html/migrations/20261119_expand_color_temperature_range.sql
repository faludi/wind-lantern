-- Upgrade databases created from the original html/schema.sql.
-- MySQL generated this name for the sixth unnamed CHECK constraint.
-- Confirm it with SHOW CREATE TABLE lanterns if the schema was customized.
ALTER TABLE lanterns
    DROP CHECK lanterns_chk_6,
    ADD CONSTRAINT chk_lanterns_color_temperature
        CHECK (color_temperature BETWEEN -20 AND 20);
