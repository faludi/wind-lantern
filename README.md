# Wind Lantern

A Wi-Fi-connected lantern whose LED flicker responds to local wind conditions. The firmware runs on a Raspberry Pi Pico W using MicroPython. This project is part of [Natural Electronics](https://wabitronics.com).

![wind lantern](wind_lantern.png)

## Architecture

- `main.py` starts the firmware, reads local settings, connects to Wi-Fi, and runs the weather/settings update loop alongside the candle-light thread.
- `nature_api.py` provides Wi-Fi setup, location lookup, time synchronization, and weather requests. Wind speed and gust data come from Open-Meteo.
- `wind_manager.py` contains the wind/gust simulation shared by firmware and the hardware simulator.
- `lantern_hardware.py` owns the LED pin mapping, PWM setup, and Wi-Fi setup-button input.
- `lantern_config.py` defines firmware defaults and normalizes settings from local configuration and the server.
- `settings_store.py` loads and saves normalized settings in `config.json`.
- `settings_state.py` owns the normalized runtime settings and applies partial updates.
- `html/` contains the PHP dashboard and MySQL schema. The dashboard manages lantern accounts and settings.
- `html/settings_schema.php` defines dashboard metadata and the typed settings payload returned to firmware.
- `html/lantern_checkin.php` identifies an active lantern by its Wi-Fi MAC address and returns its current settings and any queued firmware-update request.

The settings flow is:

1. Firmware defaults are defined in `lantern_config.py`.
2. At startup, the device loads and normalizes `config.json`.
3. The device periodically checks in with the configured settings endpoint. Valid remote values update the local settings; invalid or missing values keep their current fallback.
4. The resulting settings are saved to `config.json` when they change.

If the server cannot be reached, the device continues using its local settings. The firmware also refreshes weather data periodically and uses the configured address to resolve its location and timezone.

## Device Setup

1. Install MicroPython on the Pico W and copy the firmware modules from this repository to the device. `main.py` is the startup module.
2. Copy `secrets-example.py` to `secrets.py` and set `WIFI_SSID` and `WIFI_PASSWORD`. Keep the completed `secrets.py` out of source control.
3. To provision Wi-Fi without editing `secrets.py`, hold the setup button low on GP16 while the device starts. Join the `WindLantern-Setup-<last-four-MAC>` access point and submit the network credentials. The setup portal is open and times out after ten minutes.
4. For the multi-lantern dashboard and database setup, follow [testing/setup.md](testing/setup.md).

## Development Checks

The host test suite requires Python 3 and PHP CLI for cross-layer settings checks:

```sh
python3 -m unittest discover -s testing -v
```

The hardware simulator in `testing/lantern_test.py` requires a MicroPython environment and the lantern hardware connected. The host test suite does not require a Pico.
