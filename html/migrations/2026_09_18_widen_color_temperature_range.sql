-- Widens the color_temperature CHECK constraint from -5..5 to -6..6.
-- Run SHOW CREATE TABLE lanterns; first to confirm the auto-generated
-- constraint name if it differs from the one below (MySQL 8.0.16+ default
-- naming pattern is <table>_chk_<n>).

ALTER TABLE lanterns
    DROP CHECK lanterns_chk_5,
    ADD CONSTRAINT lanterns_chk_5 CHECK (color_temperature BETWEEN -6 AND 6);
