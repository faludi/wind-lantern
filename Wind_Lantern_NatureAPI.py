# Rob Faludi 2025
# WiFi based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-wi-fi-micropython/
# Flicker based on code from Grant Whitney
# https://grantwinney.com/raspberry-pi-flickering-candle/


from math import log
import uasyncio as asyncio
from machine import Pin, PWM, reset, WDT
import time
import random
import _thread
import requests
import secrets
import gc
import json
import ntptime
from nature_api import Client

version = "1.0.26"
print("Wind Lantern WiFi - Version:", version)

# Wi-Fi credentials
ssid = secrets.WIFI_SSID  # your SSID name
password = secrets.WIFI_PASSWORD  # your WiFi password

wdt = WDT(timeout=8388)  # 8-second watchdog timer

nature_client = Client(ssid, password, default_refresh=300, status_led_pin=None, debug_mode=False, watchdog=wdt)
ipgeolocation_key = getattr(secrets, 'IPGEOLOCATION_API_KEY', None)
if ipgeolocation_key:
    try:
        nature_client.set_api_key('ipgeolocation', ipgeolocation_key)
    except Exception as e:
        print('Warning: failed to set ipgeolocation API key:', e)

address = "350 5th Avenue, New York, NY"
latitude = 40.7484773
longitude = -73.9881643
settings_file_url = "http://shinyshape.com/windlantern/wind_lantern_settings.json"

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
WIND_FACTOR_MULTIPLIER = 1.2
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
blue_pwm.duty(99)
red_pwm_2 = Pulse(Pin(red_pin_2))
red_pwm_2.freq(300)
red_pwm_2.duty(100)
green_pwm_2 = Pulse(Pin(green_pin_2))
green_pwm_2.freq(300)
green_pwm_2.duty(100)
blue_pwm_2 = Pulse(Pin(blue_pin_2))
blue_pwm_2.freq(300)
blue_pwm_2.duty(99)

def connect_to_wifi():
    wdt.feed()
    connection_success = nature_client.connect_wifi()
    errors['wifi_connection'] = not connection_success
    return connection_success

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
        forecast = nature_client.get_forecast("current", "wind_speed_10m,wind_gusts_10m", forecast_days=1, expiry=300)
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
                config = {"address": "350 5th Avenue, New York, NY", "latitude": 40.7484773, "longitude": -73.9881643, "settings_file_url": "http://shinyshape.com/windlantern/wind_lantern_settings.json"}
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
                config.get('settings_file_url') == settings_file_url):
                print("Configuration unchanged, not saving.")
                return
    except Exception as e:
        print("Error reading config for comparison:", e)
    try:
        with open("config.json", "w") as f:
            config = {"address": address, "latitude": latitude, "longitude": longitude, "settings_file_url": settings_file_url}
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

    
async def update_location():
    global address, latitude, longitude, settings_file_url
    location = fetch_address(settings_file_url)
    if location is not None:
        address = location.get('address')
        print("Using Address:", address)
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
                    save_config()
                else:
                    raise ValueError('Location lookup returned no coordinates')
            except Exception as e:
                print('Error setting location:', e)
                errors['location_fetch'] = True
    else:
        print("Using default coordinates")
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
    def __init__(self):
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
        # self.wind_factor = (self.wind_factor * WIND_FACTOR_MULTIPLIER)   # increase wind factor effect
        self.wind_factor = self.adjust(self.wind_factor, k=0.02, center=10)
        self.gust_factor = max((wind_gusts), 0) # protect against negative wind factor
        # self.gust_factor = (self.gust_factor * WIND_FACTOR_MULTIPLIER)   # increase wind factor effect
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
        factor = wind_manager.get_wind_factor()
        red_pwm.duty( 100 - min(random.uniform(93-factor, 100), 100) )
        red_pwm_2.duty(100 - min(random.uniform(93-factor, 100) , 100) ) 
        rand_flicker_sleep()
 
def green_light():
        global wind_manager
        factor = wind_manager.get_wind_factor()
        green_pwm.duty( 100 - min(random.uniform(33-factor, 34) ,100) )
        green_pwm_2.duty(100 - min(random.uniform(33-factor, 34) ,100) )
        rand_flicker_sleep()
 
def rand_flicker_sleep():
    time.sleep(random.randint(3, 10) / 100.0)

def light_candle():
    gc.collect()
    print("Starting candle thread")
    while terminateThread == False:
        red_light()
        green_light()
        time.sleep_ms(1)

wind_manager = WindManager()

async def main():
    wdt.feed()
    global address, latitude, longitude, settings_file_url
    settings = open_config()
    if settings is not None:
        address = settings.get('address', address)
        latitude = settings.get('latitude', latitude)
        longitude = settings.get('longitude', longitude)
        settings_file_url = settings.get('settings_file_url', settings_file_url)

    connection = connect_to_wifi()
    if not connection:
        print('Could not connect to Wi-Fi, exiting')
        reset()

    if address:
        try:
            nature_client.set_location(address)
        except Exception as e:
            print('Warning: initial location setup failed:', e)

    if not nature_client.sync_time():
        print('NTP sync failed, continuing with local time if available.')

    next_sync = time.time()
    while True:
        wdt.feed()
        if not nature_client.wifi_connected:
            break # exit if no connection
        await update_location()
        if (time.time() >= next_sync):
            try:
                print('Syncing time via NTP...')
                wdt.feed()
                ntptime.settime()
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

