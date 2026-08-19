Wind Lantern that flickers based on input via Bluetooth Low Energy from a [Modern Devices wind sensor](https://moderndevice.com/products/wind-sensor).

Part of the [Natural Electronics](https://wabitronics.com) project.

![wind lantern](wind_lantern.png)

## Multi-lantern web setup

The web application in `html/` now stores users, lanterns, and addresses in MySQL.
`Wind_Lantern_NatureAPI.py` identifies each lantern by its Wi-Fi MAC address and
requests its address from:

`https://shinyshape.com/windlantern/lantern_checkin.php?mac=590E72AC9387`

### DreamHost setup

1. Create a MySQL database and database user in the DreamHost panel. Note the database hostname, database name, username, and password.
2. Copy `wind_lantern_db_config.example.php` to `wind_lantern_db_config.php` one directory above the public `html/` directory, then fill in the DreamHost values. Do not upload the completed file to source control.
3. Import `html/schema.sql` into the new database using DreamHost's phpMyAdmin or MySQL client.
4. Visit `/windlantern/admin.php`. The first visit, while the `users` table is empty, creates the first administrator account. After that, the page requires administrator login.
5. Use the administrator page to register each lantern's MAC address, initial address, owner username, and owner password.
6. Update the lantern with `Wind_Lantern_NatureAPI.py`. The older `Wind_Lantern_WiFi.py` is intentionally unchanged.

The existing `wind_lantern_settings.json` file is retained as a migration reference
but is no longer used by the new firmware or dashboard. The public check-in endpoint
returns only the address for a matching active MAC address and does not require login.