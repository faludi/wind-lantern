-- Remove the stale -10..10 temperature check and restore the missing flicker check.
ALTER TABLE lanterns
    DROP CHECK lanterns_chk_5,
    ADD CONSTRAINT chk_lanterns_flicker_intensity
        CHECK (flicker_intensity BETWEEN 0 AND 5);
