# Rob Faludi 2025
# WiFi based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-wi-fi-micropython/
# Flicker based on code from Grant Whitney
# https://grantwinney.com/raspberry-pi-flickering-candle/

import uasyncio as asyncio
from machine import Pin, PWM, reset
import time
import random
import _thread
import network
import requests
import secrets
import config
import gc

version = "1.0.14"
print("Wind Lantern WiFi - Version:", version)

# Wi-Fi credentials
ssid = secrets.WIFI_SSID  # your SSID name
password = secrets.WIFI_PASSWORD  # your WiFi password

address = config.ADDRESS

# if no address is provided, use these default coordinates:
latitude = config.LATITUDE
longitude = config.LONGITUDE

red_pin = 5
green_pin = 6
blue_pin = 7

red_pin_2 = 8
green_pin_2 = 9
blue_pin_2 = 10

GUST_INTERVAL_LOW = 15000  # 15 seconds
GUST_INTERVAL_HIGH = 180000  # 3 minutes
GUST_LENGTH_LOW = 3000  # 3 seconds
GUST_LENGTH_HIGH = 15000  # 15 seconds

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
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Connect to network
    wlan.connect(ssid, password)
    connection_timeout = 10
    while connection_timeout > 0:
        if wlan.status() >= 3:
            break
        connection_timeout -= 1
        print('Waiting for Wi-Fi connection...')
        time.sleep(1)
    # Check if connection is successful
    if wlan.status() != 3:
        print('Failed to establish a network connection')
        return False
    else:
        print('Connection successful!')
        network_info = wlan.ifconfig()
        print('IP address:', network_info[0])
        return True

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
        # Make GET request
        response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=wind_speed_10m,wind_gusts_10m", timeout=10)
        # Get response code
        response_code = response.status_code
        # Get response content
        response_content = response.content
        weather = response.json()
        # Print results
        print('Response code: ', response_code)
        # print('Response content:', response_content)
        return weather
    except Exception as e:
        print('Error fetching weather data:', e)
        return None
    
def fetch_config():
    try:
        # Make GET request
        response = requests.get(config.SETTINGS_FILE_URL, timeout=10)
        # Get response code
        response_code = response.status_code
        # Get response content
        response_content = response.content
        print('Response code: ', response_code)
        config_raw = response.json()
        # Print results
        print('Configuration: ', config_raw)
        return config_raw
    except Exception as e:
        print('Error fetching settings:', e)
        return None

def fetch_location_from_address(address):
    try:
        headers = {
            "User-Agent": "rp2"  # Adding the custom user agent
        }
        response = requests.get(f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1", headers=headers, timeout=10)
        # print(response.content)
        response_code = response.status_code
        response_content = response.content
        location_data = response.json()
        print('Response code: ', response_code)
        
        if location_data:
            lat = location_data[0]['lat']
            lon = location_data[0]['lon']
            print(f"Fetched coordinates for address '{address}': Latitude {lat}, Longitude {lon}")
            return float(lat), float(lon)
        else:
            raise ValueError("Location not found")
    except Exception as e:
        print('Error fetching location data:', e)
        return None, None  

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

    def _calc_wind_factor(self, wind_speed, wind_gusts):
        self.wind_factor = max((wind_speed), 0) # protect against negative wind factor
        self.wind_factor = (self.wind_factor * 1.5)   # increase wind factor effect
        self.gust_factor = max((wind_gusts), 0) # protect against negative wind factor
        self.gust_factor = (self.gust_factor * 1.5)   # increase wind factor effect

    def _calc_gusting(self):
        if time.ticks_ms() - self.start_time > self.delay:
            self.start_time = time.ticks_ms()
            self.gust_ramp = random.randint(GUST_LENGTH_LOW, GUST_LENGTH_HIGH) * 0.25
            if not self.gusting:
                self.gusting = True
                self.delay = random.randint(GUST_LENGTH_LOW, GUST_LENGTH_HIGH)
                print("GUST STARTED for", self.delay / 1000, "secs")
            elif self.gusting:
                self.gusting = False
                self.delay = random.randint(GUST_INTERVAL_LOW, GUST_INTERVAL_HIGH)
                print("GUST ENDED, next in", self.delay / 1000, "secs") 
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
    global latitude, longitude
    connection = False
    connection_timeout = 10
    while not connection:
            connection = connect_to_wifi()
            connection_timeout -= 1
            if connection_timeout == 0:
                print('Could not connect to Wi-Fi, exiting')
                reset()

    config = fetch_config()
    if config is not None:
        address = config.get('address')
        # latitude = config.get('latitude')
        # longitude = config.get('longitude')

    # print("Using Latitude:", latitude, "Longitude:", longitude, "Address:", address)
    print("Using Address:", address)

    if address:
        latitude, longitude = fetch_location_from_address(address.replace(" ", "+"))
    while True:
        if not connection:
            break # exit if no connection
        try:
            # Fetch and display weather data
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
        await asyncio.sleep_ms(15*60*1000)  # Read every 15 minutes

# Create an Event Loop
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

