## Web and Device Setup

The PHP application in `html/` stores users, lanterns, and their settings in MySQL. The firmware in `main.py` identifies each device by its Wi-Fi MAC address and checks in with `html/lantern_checkin.php`. The endpoint returns settings for an active registered lantern, records its firmware version and check-in time, and delivers a queued firmware update once.

### Web deployment

1. Create a MySQL database and database user with your hosting provider. Note the database hostname, database name, username, and password.
2. Copy `wind_lantern_db_config.example.php` to `wind_lantern_db_config.php` one directory above the public `html/` directory, then enter the database values. Keep the completed file out of source control and outside the public web directory.
3. Import `html/schema.sql` into the new database using the provider's database tools or a MySQL client.
4. Visit `/windlantern/admin.php` and create the first administrator account while the `users` table is empty. After setup, the page requires an administrator login.
5. In the administration page, register each lantern's MAC address, initial address, owner username, and owner password. Use the device's station/Wi-Fi MAC address.
6. Sign in to `/windlantern/index.php` to edit the lantern settings. The dashboard settings endpoint should be `https://shinyshape.com/windlantern/lantern_checkin.php` unless your deployment uses a different host.

### Device setup

1. Install MicroPython on the Pico W and copy the current firmware files from the repository to its filesystem. `main.py` is the startup module.
2. Create `secrets.py` from `secrets-example.py` and set the Wi-Fi network name and password. Do not commit the completed secrets file.
3. On startup, the firmware loads `config.json`, connects to Wi-Fi, and checks in with the configured settings endpoint. If the device has not been configured for Wi-Fi, hold the setup button low on GP16 during startup to launch the `WindLantern-Setup-<last-four-MAC>` access point. The portal is open and remains available for up to ten minutes.
	Select a nearby network from the list, or select Other network and enter its name for a hidden or unlisted network. The list contains up to 20 networks found when setup started, ordered by signal strength.
	After selecting Connect, the page shows connection progress. Once the network settings are saved, the lantern lights turn green and the page offers Done; the lantern restarts after Done or after 30 seconds. If the phone loses the setup connection, the green lights indicate success.
4. Register the device's MAC address in the admin page. The first successful check-in receives its address and settings; the firmware periodically checks again based on `settings_update_interval`.
5. To request a firmware update, queue it for the lantern in the admin page. The next check-in claims the one-time request, and the device pulls the firmware repository and restarts.

The check-in endpoint is public to the device and does not require a dashboard login; it only returns settings for a matching active MAC address. The older `wind_lantern_settings.json` settings path is not used by the current firmware.