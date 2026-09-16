# Rob Faludi 2025
# WiFi based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-wi-fi-micropython/
# Flicker based on code from Grant Whitney
# https://grantwinney.com/raspberry-pi-flickering-candle/


import uasyncio as asyncio
from machine import Pin, PWM, reset, WDT
import time
import random
import _thread
import requests
import secrets
import gc
import json
import network
from nature_api import Client

version = "1.0.35"
print("Wind Lantern NatureAPI - Version:", version)

time.sleep(2) # allow usb connection on startup

# Wi-Fi credentials
ssid = secrets.WIFI_SSID  # your SSID name
password = secrets.WIFI_PASSWORD  # your WiFi password

wdt = WDT(timeout=8388)  # 8-second watchdog timer

nature_client = Client(ssid, password, debug_mode=False, watchdog=wdt)
ipgeolocation_key = getattr(secrets, 'IPGEOLOCATION_API_KEY', None)
if ipgeolocation_key:
    try:
        nature_client.set_api_key('ipgeolocation', ipgeolocation_key)
    except Exception as e:
        print('Warning: failed to set ipgeolocation API key:', e)

address = "350 5th Avenue, New York, NY"
latitude = 40.7484773
longitude = -73.9881643
settings_endpoint = "https://shinyshape.com/windlantern/lantern_checkin.php"
settings_file_url = settings_endpoint
lantern_mac = None
day_brightness = 100
night_brightness = 10
night_start_localtime = 22
night_end_localtime = 8
color_temperature = 0
flicker_intensity = 1.0
night_mode_current = 100
night_mode_target = 100
night_mode_fade_from = 100
night_mode_fade_to = 100
night_mode_fade_start = None
initial_time_sync_complete = False
cached_timezone_offset_hours = 0
timezone_offset_next_refresh = 0
night_mode_next_update = 0
TIMEZONE_OFFSET_REFRESH_MS = 3600000  # re-check timezone offset hourly
NIGHT_MODE_UPDATE_INTERVAL_MS = 1000  # recompute night mode at most once per second

red_pin = 5
green_pin = 6
blue_pin = 7

red_pin_2 = 8
green_pin_2 = 9
blue_pin_2 = 10
LED = Pin("LED", Pin.OUT)      # digital output for status LED

GUST_INTERVAL_LOW = 15000  # 15 seconds
GUST_INTERVAL_HIGH = 40000  # 40 seconds
GUST_LENGTH_LOW = 3000  # 3 seconds
GUST_LENGTH_HIGH = 15000  # 15 seconds
WIND_FACTOR_K = 0.03 # how strongly the wind factor is pulled towards the center value
# A gentle breeze should have the most effect, and higher winds should have less effect to prevent the lantern from flickering too wildly in strong winds. 
WIND_FACTOR_CENTER = 6 # increase wind effect below this speed, decrease effect above this speed.

errors = {
    'wifi_connection': True,
    'weather_fetch': False,
    'config_fetch': False,
    'location_fetch': False
}

terminateThread = False

class Pulse(PWM):
    def duty(self, percent_duty):
        return self.duty_u16(int(percent_duty/100 *65535))
    
red_pwm = Pulse(Pin(red_pin))
red_pwm.freq(300)
red_pwm.duty(100)
green_pwm = Pulse(Pin(green_pin))
green_pwm.freq(300)
green_pwm.duty(100)
blue_pwm = Pulse(Pin(blue_pin))
blue_pwm.freq(300)
blue_pwm.duty(100)
red_pwm_2 = Pulse(Pin(red_pin_2))
red_pwm_2.freq(300)
red_pwm_2.duty(100)
green_pwm_2 = Pulse(Pin(green_pin_2))
green_pwm_2.freq(300)
green_pwm_2.duty(100)
blue_pwm_2 = Pulse(Pin(blue_pin_2))
blue_pwm_2.freq(300)
blue_pwm_2.duty(100)

def connect_to_wifi():
    wdt.feed()
    connection_success = nature_client.connect_wifi()
    errors['wifi_connection'] = not connection_success
    return connection_success

def get_lantern_mac():
    wlan = network.WLAN(network.STA_IF)
    mac_bytes = wlan.config('mac')
    return ''.join('{:02X}'.format(value) for value in mac_bytes)

def get_settings_url():
    return settings_endpoint + '?mac=' + get_lantern_mac()

def parse_datetime(timestamp):
    # Split the timestamp into date and time
    date_str, time_str = timestamp.split('T')
    # Extract year, month, day
    year, month, day = date_str.split('-')
    # Extract hours and minutes
    hour, minute = time_str.split(':')
    # Combine into final time format
    formatted_time = f"{month}/{day}/{year} {hour:2}:{minute:2} UTC"
    return(formatted_time)

def fetch_weather_data():
    try:
        wdt.feed()
        forecast = nature_client.get_weather("current", "wind_speed_10m,wind_gusts_10m", forecast_days=1, expiry=300)
        if not forecast or forecast.get('wind_speed_10m') is None:
            errors['weather_fetch'] = True
            return None
        errors['weather_fetch'] = False
        timestamp = f"{time.gmtime()[0]:04}-{time.gmtime()[1]:02}-{time.gmtime()[2]:02}T{time.gmtime()[3]:02}:{time.gmtime()[4]:02}"
        return {
            'current': {
                'wind_speed_10m': forecast.get('wind_speed_10m'),
                'wind_gusts_10m': forecast.get('wind_gusts_10m'),
                'time': timestamp
            }
        }
    except Exception as e:
        print('Error fetching weather data:', e)
        errors['weather_fetch'] = True
        return None
    
def open_config():
    try:
        with open('config.json', 'r') as f:
            config_str = f.read()
            config = json.loads(config_str)
            # print(config)
            return config
    except OSError:
        print("Creating configuration file.")
        try:
            with open("config.json", "w") as f:
                config = {"address": "350 5th Avenue, New York, NY", "latitude": 40.7484773, "longitude": -73.9881643, "settings_file_url": "http://shinyshape.com/windlantern/wind_lantern_settings.json", "lantern_brightness": 100, "night_brightness": 10, "night_start": 22, "night_end": 8, "color_temperature": 0, "flicker_intensity": 1.0}
                json_string = json.dumps(config)
                # print(config)
                f.write(json_string)
                return config
        except Exception as e:
            print("Error storing light levels:", e)

def save_config():
    try:
        with open("config.json", "r") as f:
            config_str = f.read()
            config = json.loads(config_str)
            if (config.get('address') == address and
                config.get('latitude') == latitude and
                config.get('longitude') == longitude and
                config.get('settings_file_url') == settings_file_url and
                config.get('lantern_brightness') == day_brightness and
                config.get('night_brightness') == night_brightness and
                config.get('night_start') == night_start_localtime and
                config.get('night_end') == night_end_localtime and
                config.get('color_temperature') == color_temperature and
                config.get('flicker_intensity') == flicker_intensity):
                print("Configuration unchanged, not saving.")
                return
    except Exception as e:
        print("Error reading config for comparison:", e)
    try:
        with open("config.json", "w") as f:
            config = {"address": address, "latitude": latitude, "longitude": longitude, "settings_file_url": settings_file_url, "lantern_brightness": day_brightness, "night_brightness": night_brightness, "night_start": night_start_localtime, "night_end": night_end_localtime, "color_temperature": color_temperature, "flicker_intensity": flicker_intensity}
            json_string = json.dumps(config)
            # print(config)
            f.write(json_string)
            print("Configuration saved.")
    except Exception as e:
        print("Error saving config:", e)

def fetch_address(url):
    try:
        # Make GET request
        wdt.feed()
        response = requests.get(url, timeout=8)
        # Get response code
        response_code = response.status_code
        print('Response code: ', response_code)
        # response_content = response.content
        # print('Response content:', response_content)
        config_raw = response.json()
        # Print results
        print('Configuration: ', config_raw)
        errors['config_fetch'] = False
        return config_raw
    except Exception as e:
        print('Error fetching settings:', e)
        errors['config_fetch'] = True
        return None

    
async def update_settings():
    global address, latitude, longitude, settings_file_url
    global day_brightness, night_brightness, night_start_localtime, night_end_localtime, color_temperature, flicker_intensity
    settings = fetch_address(settings_file_url)
    if settings is not None:
        address = settings.get('address', address)
        print("Using Address:", address)
        day_brightness = normalize_brightness(settings.get('lantern_brightness', day_brightness))
        night_brightness = normalize_night_brightness(settings.get('night_brightness', night_brightness))
        night_start_localtime = normalize_night_hour(settings.get('night_start', night_start_localtime))
        night_end_localtime = normalize_night_hour(settings.get('night_end', night_end_localtime))
        color_temperature = normalize_color_temperature(settings.get('color_temperature', color_temperature))
        flicker_intensity = normalize_flicker_intensity(settings.get('flicker_intensity', flicker_intensity))
        wind_manager.flicker_intensity = flicker_intensity
        if address:
            try:
                nature_client.set_location(address)
                client_location = nature_client.get_location()
                if client_location:
                    latitude = float(client_location['latitude'])
                    longitude = float(client_location['longitude'])
                    errors['location_fetch'] = False
                    try:
                        nature_client.set_timezone_from_location()
                    except Exception as e:
                        print('Warning: failed to set timezone from location:', e)
                else:
                    raise ValueError('Location lookup returned no coordinates')
            except Exception as e:
                print('Error setting location:', e)
                errors['location_fetch'] = True
        save_config()
    else:
        print("Using default settings")
        errors['location_fetch'] = True

async def error_led(milliseconds):
    # bit one is wifi, bit two is weather fetch, bit three is config fetch, bit four is location fetch
    # for example if config fetch and location fetch failed, blinks = 0b1100 = 12
    global errors
    start_time = time.ticks_ms()
    while time.ticks_ms() - start_time < milliseconds:
        count = 0
        blinks = 0
        for error in errors.values():
            if error:
                blinks = blinks | 1 << count
            count += 1
        if blinks != 0:
            for i in range(blinks):
                wdt.feed()
                LED.on()
                await asyncio.sleep(0.3)
                LED.off()
                await asyncio.sleep(0.3)
            LED.off()
        wdt.feed()
        await asyncio.sleep_ms(1000)


class WindManager:
    def __init__(self, flicker_intensity=1.0):
        self.flicker_intensity = flicker_intensity
        self.wind_factor = 0
        self.gust_factor = 0
        self.gust_ramp = random.randint(GUST_LENGTH_LOW, GUST_LENGTH_HIGH) * 0.25
        self.speed = 0
        self.gusts = 0
        self.gusting = True
        self.start_time = time.ticks_ms()
        self.delay = 0

    def set_wind(self, wind_speed, wind_gusts):
        self.speed = wind_speed
        self.gusts = wind_gusts
        self._calc_wind_factor(self.speed, self.gusts)

    def adjust(self, x, k=0.02, center=10):
        return x - k * (x - center) * abs(x - center)

    def _calc_wind_factor(self, wind_speed, wind_gusts):
        self.wind_factor = max((wind_speed), 0) # protect against negative wind factor
        self.wind_factor *= self.flicker_intensity
        self.wind_factor = self.adjust(self.wind_factor, k=0.02, center=10)
        self.gust_factor = max((wind_gusts), 0) # protect against negative wind factor
        self.gust_factor *= self.flicker_intensity
        self.gust_factor = self.adjust(self.gust_factor, k=0.02, center=10)

    def _calc_gusting(self):
        if time.ticks_ms() - self.start_time > self.delay:
            self.start_time = time.ticks_ms()
            self.gust_ramp = random.randint(GUST_LENGTH_LOW, GUST_LENGTH_HIGH) * 0.25
            if not self.gusting:
                self.gusting = True
                self.gust_factor = self.gust_factor * random.uniform(0.8, 1.2) # add some randomness to gust factor
                self.delay = random.randint(GUST_LENGTH_LOW, GUST_LENGTH_HIGH)
                print("Gusting for", self.delay / 1000, "secs")
            elif self.gusting:
                self.gusting = False
                self.delay = random.randint(GUST_INTERVAL_LOW, GUST_INTERVAL_HIGH)
                print("Next gust in", self.delay / 1000, "secs") 
        return self.wind_factor
    
    def get_wind_factor(self):
        self._calc_gusting()
        if self.gusting:
            # gust, reduced by the full difference with wind at first, then down to no reduction at 1/4 time
            difference = ( self.gust_factor - self.wind_factor )
            percent = max(( 1- (time.ticks_ms() - self.start_time) / self.gust_ramp ), 0) 
            factor = self.gust_factor - ( difference * percent )
        else:
            # wind, increased by the full difference with gusts at first, then down to no increase at 1/4 time
            difference = ( self.gust_factor - self.wind_factor )
            percent = max(( 1 - (time.ticks_ms() - self.start_time) / self.gust_ramp ), 0) 
            factor = self.wind_factor + ( difference * percent )
        # factor = factor * random.uniform(0.85, 1.0) # add some randomness
        return factor
    
def red_light():
        global wind_manager
        brightness_level = update_night_mode_state()
        factor = wind_manager.get_wind_factor()
        red_pwm.duty(scale_brightness(100 - min(random.uniform(93-factor, 100), 100), brightness_level))
        red_pwm_2.duty(scale_brightness(100 - min(random.uniform(93-factor, 100) , 100), brightness_level))
        rand_flicker_sleep()

def green_light():
        global wind_manager
        brightness_level = update_night_mode_state()
        factor = wind_manager.get_wind_factor()
        green_pwm.duty(scale_brightness(100 - min(random.uniform(29-factor-color_temperature, 30-color_temperature) ,100), brightness_level))
        green_pwm_2.duty(scale_brightness(100 - min(random.uniform(29-factor-color_temperature, 30-color_temperature) ,100), brightness_level))
        rand_flicker_sleep()

def normalize_brightness(value):
    try:
        return min(max(float(value), 0), 100)
    except (TypeError, ValueError):
        return 100

def scale_brightness(duty, brightness_override=None):
    if brightness_override is None:
        brightness_override = day_brightness
    brightness_level = normalize_brightness(brightness_override)
    return 100 - ((100 - duty) * brightness_level / 100)

def normalize_color_temperature(value):
    try:
        return min(max(float(value), -5), 5)
    except (TypeError, ValueError):
        return 0

def normalize_flicker_intensity(value):
    try:
        return max(float(value), 0)
    except (TypeError, ValueError):
        return 1

def normalize_night_brightness(value):
    try:
        return min(max(float(value), 0), 100)
    except (TypeError, ValueError):
        return 10

def normalize_night_hour(value):
    try:
        hour = int(value)
    except (TypeError, ValueError):
        return 0
    if hour < 0:
        return 0
    if hour > 23:
        return 23
    return hour

def get_local_timezone_offset_hours():
    global cached_timezone_offset_hours, timezone_offset_next_refresh
    if not nature_client.wifi_connected:
        return cached_timezone_offset_hours
    now = time.ticks_ms()
    if time.ticks_diff(now, timezone_offset_next_refresh) < 0:
        return cached_timezone_offset_hours
    timezone_offset_next_refresh = time.ticks_add(now, TIMEZONE_OFFSET_REFRESH_MS)
    try:
        offset_seconds = nature_client.get_local_timezone_offset()
        cached_timezone_offset_hours = int(offset_seconds / 3600)
        print('Local timezone offset (hours):', cached_timezone_offset_hours)
    except Exception as e:
        print('Warning: failed to determine local timezone offset:', e)
    return cached_timezone_offset_hours

def is_night_window(local_hour, start_hour, end_hour):
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return local_hour >= start_hour and local_hour < end_hour
    return local_hour >= start_hour or local_hour < end_hour

def update_night_mode_state():
    global night_mode_current, night_mode_target, night_mode_fade_from, night_mode_fade_to, night_mode_fade_start, night_mode_next_update
    if not initial_time_sync_complete:
        return day_brightness
    now = time.ticks_ms()
    # Skip recompute on most frames; the flicker loop calls this far more often than the state can change.
    if night_mode_fade_start is None and time.ticks_diff(now, night_mode_next_update) < 0:
        return night_mode_current
    night_mode_next_update = time.ticks_add(now, NIGHT_MODE_UPDATE_INTERVAL_MS)

    offset_hours = get_local_timezone_offset_hours()
    local_hour = (time.gmtime()[3] + offset_hours) % 24
    # print(f"Local hour: {local_hour}, Night start: {night_start_localtime}, Night end: {night_end_localtime}")
    target = night_brightness if is_night_window(local_hour, night_start_localtime, night_end_localtime) else day_brightness

    if night_mode_target != target:
        night_mode_fade_from = night_mode_current
        night_mode_fade_to = target
        night_mode_fade_start = now
        night_mode_target = target

    if night_mode_fade_start is not None:
        elapsed = time.ticks_diff(now, night_mode_fade_start)
        if elapsed >= 10000:
            night_mode_current = night_mode_fade_to
            night_mode_fade_start = None
        else:
            progress = elapsed / 10000
            night_mode_current = night_mode_fade_from + (night_mode_fade_to - night_mode_fade_from) * progress
    else:
        night_mode_current = night_mode_target

    return night_mode_current

def rand_flicker_sleep():
    time.sleep(random.randint(3, 10) / 100.0)

def light_candle():
    gc.collect()
    print("Starting candle thread")
    while terminateThread == False:
        red_light()
        green_light()
        time.sleep_ms(1)

wind_manager = WindManager(flicker_intensity)

async def main():
    wdt.feed()
    global address, latitude, longitude, settings_file_url, lantern_mac, day_brightness, night_brightness, night_start_localtime, night_end_localtime, color_temperature, flicker_intensity, night_mode_current, night_mode_target, night_mode_fade_from, night_mode_fade_to, night_mode_fade_start, initial_time_sync_complete
    settings = open_config()
    if settings is not None:
        address = settings.get('address', address)
        latitude = settings.get('latitude', latitude)
        longitude = settings.get('longitude', longitude)
        settings_file_url = settings.get('settings_file_url', settings_file_url)
        day_brightness = normalize_brightness(
            settings.get('lantern_brightness', day_brightness)
        )
        night_brightness = normalize_night_brightness(
            settings.get('night_brightness', night_brightness)
        )
        night_start_localtime = normalize_night_hour(
            settings.get('night_start', night_start_localtime)
        )
        night_end_localtime = normalize_night_hour(
            settings.get('night_end', night_end_localtime)
        )
        color_temperature = normalize_color_temperature(
            settings.get('color_temperature', color_temperature)
        )
        flicker_intensity = normalize_flicker_intensity(
            settings.get('flicker_intensity', flicker_intensity)
        )
        wind_manager.flicker_intensity = flicker_intensity

    night_mode_current = day_brightness
    night_mode_target = day_brightness
    night_mode_fade_from = day_brightness
    night_mode_fade_to = day_brightness
    night_mode_fade_start = None

    connection = connect_to_wifi()
    if not connection:
        print('Could not connect to Wi-Fi, exiting')
        reset()

    lantern_mac = get_lantern_mac()
    settings_file_url = get_settings_url()
    print('Lantern MAC:', lantern_mac)

    if address:
        try:
            nature_client.set_location(address)
        except Exception as e:
            print('Warning: initial location setup failed:', e)

    if not nature_client.sync_time():
        print('NTP sync failed, continuing with local time if available.')
    initial_time_sync_complete = True

    next_sync = time.time()
    while True:
        wdt.feed()
        if not nature_client.wifi_connected:
            break # exit if no connection
        await update_settings()
        if (time.time() >= next_sync):
            try:
                print('Syncing time via NTP...')
                wdt.feed()
                nature_client.sync_time()
                print(f"DateTime: {time.gmtime()[0]}-{time.gmtime()[1]:02}-{time.gmtime()[2]:02} {time.gmtime()[3]:02}:{time.gmtime()[4]:02}:{time.gmtime()[5]:02} UTC  ")
                next_sync = time.time() + 43200 # update every 12 hours
            except Exception as e:
                next_sync = time.time() + 600 # try again in 10 minutes
                print("Failed to update NTP or solar data, retrying in 10 minutes.", e)
        try:
            # Fetch and display weather data using nature_api
            weather = fetch_weather_data()
            if weather is not None:
                # print('Weather Data:', weather)
                wind_speed = weather['current']['wind_speed_10m']*0.27778
                wind_gusts = weather['current']['wind_gusts_10m']*0.27778
                timestamp = weather['current']['time']
                wind_manager.set_wind(wind_speed, wind_gusts)
                print('Timestamp:', parse_datetime(timestamp))
                print(f"Speed: {weather['current']['wind_speed_10m']} kph, Gusts: {weather['current']['wind_gusts_10m']} kph")
                print(f"Speed: {wind_speed * 2.23693629:.2f} mph, Gusts: {wind_gusts * 2.23693629:.2f} mph") 
                print(f"Speed {wind_speed:.2f} m/s, Gusts {wind_gusts:.2f} m/s")
                print("Wind factor:", wind_manager.wind_factor, "Gust factor:", wind_manager.gust_factor)
            else:
                print('No weather data available')
        except Exception as e:
            print('Error fetching weather data:', e)
        await error_led(15*60*1000)
        # await asyncio.sleep_ms(15*60*1000)  # Read every 15 minutes

# Create an Event Loop
wdt = WDT(timeout=8388)  # 8-second watchdog timer
loop = asyncio.get_event_loop()
# Create a task to run the main function
loop.create_task(main())
_thread.start_new_thread(light_candle, ())

try:
    # Run the event loop indefinitely
    loop.run_forever()
except Exception as e:
    print('Error occurred: ', e)
except KeyboardInterrupt:
    red_pwm.duty(100)
    red_pwm_2.duty(100)
    green_pwm.duty(100)
    green_pwm_2.duty(100)
    print('Program Interrupted by the user')
    terminateThread = True
