-- Clamp existing values before tightening the flicker_intensity constraint.

UPDATE lanterns
SET flicker_intensity = 5
WHERE flicker_intensity > 5;

ALTER TABLE lanterns
    DROP CHECK lanterns_chk_6,
    ADD CONSTRAINT lanterns_chk_6 CHECK (flicker_intensity BETWEEN 0 AND 5);