-- Change the default for newly created lanterns; preserve existing settings.
ALTER TABLE lanterns
    ALTER COLUMN night_brightness SET DEFAULT 10;
