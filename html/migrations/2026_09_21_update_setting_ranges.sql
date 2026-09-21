-- Updates color_temperature to -10..10 and flicker_intensity to 0..20.

ALTER TABLE lanterns
    DROP CHECK lanterns_chk_5,
    ADD CONSTRAINT lanterns_chk_5 CHECK (color_temperature BETWEEN -10 AND 10),
    DROP CHECK lanterns_chk_6,
    ADD CONSTRAINT lanterns_chk_6 CHECK (flicker_intensity BETWEEN 0 AND 20);
