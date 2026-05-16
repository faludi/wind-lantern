# A library that connects to realtime weather and natural events data, using open-meteo and other sources.

import time
import network
import requests
from Url_encode import url_encode
import machine
import ntptime

__version__ = "0.1.5"

class Client:
    def __init__(self, ssid, password, default_refresh=300, status_led_pin=None, debug_mode=False, watchdog=None):
        self.ssid = ssid
        self.password = password
        self.default_refresh = default_refresh
        self.status_led_pin = status_led_pin
        self.ipgeolocation_api_key = None
        self.watchdog = watchdog
        self.wifi_connected = False
        self.address = None
        self.location = None
        self.utc_offset = 0
        self.headers = {"User-Agent": "rp2"}  # Add a custom user agent
        self.debug_mode = debug_mode
        # In-memory TTL cache for fetched data: key -> { 'value': ..., 'expires_at': ... }
        self._cache = {}

        if self.status_led_pin is not None:
            self.led = machine.Pin(self.status_led_pin, machine.Pin.OUT)
            self.led.off()
                
    def connect_wifi(self, attempts_per_cycle=10, max_attempts=10):
        while max_attempts > 0:
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            # Connect to network
            wlan.connect(self.ssid, self.password)
            tries = attempts_per_cycle
            while tries > 0:
                if wlan.status() >= 3:
                    self.wifi_connected = True
                    break
                tries -= 1
                if self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
                print('Waiting for Wi-Fi connection...')
                time.sleep(1)
            # Check if connection is successful
            if wlan.status() != 3:
                print('Failed to establish a network connection')
                max_attempts -= 1
            else:
                print('Connection successful!')
                network_info = wlan.ifconfig()
                print('IP address:', network_info[0])
                return True
        print('Exceeded maximum connection attempts, resetting device...')
        machine.reset()

    def sync_time(self, max_retries=5):
        for _ in range(max_retries):
            try:
                
                print('Syncing time via NTP...')
                if  self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
                ntptime.settime()
                return True
            except Exception as e:
                print("Error syncing time:", e)
        print(f"Failed to sync time after {max_retries} attempts.")
        return False
    
    def get_local_timezone_offset(self):
        try:
            if self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
            response = requests.get(f"https://api.ipgeolocation.io/v3/timezone?apiKey={self.ipgeolocation_api_key}&ip=", headers=self.headers, timeout=8)
            if self.debug_mode:
                print(f"Response: {response.content}")
            timezone_data = response.json()
            if self.debug_mode:
                print(f"Timezone data: {timezone_data}")  # Debugging line to check the timezone data  
            if 'time_zone' in timezone_data and 'offset_with_dst' in timezone_data['time_zone']:
                offset_str = timezone_data['time_zone']['offset_with_dst']
                return int(offset_str) * 60 * 60
        except Exception as e:
            print('Error fetching local timezone offset:', e)
        return 0 # if not available, assume UTC

    def set_timezone_from_location(self):
        if not self.location:
            raise ValueError("Location is not set.")
        
        try:
            if self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
            if self.ipgeolocation_api_key: 
                response = requests.get(f"https://api.ipgeolocation.io/v3/timezone?apiKey={self.ipgeolocation_api_key}&lat={self.location['latitude']}&long={self.location['longitude']}", headers=self.headers, timeout=8)
            else:        
                response = requests.get(f"https://timeapi.io/api/v1/time/current/coordinate?latitude={self.location['latitude']}&longitude={self.location['longitude']}", headers=self.headers, timeout=8)
            if self.debug_mode:
                print(response.content)
                print('Response code: ', response.status_code)
            timezone_data = response.json()
                
            if 'utc_offset_seconds' in timezone_data:
                self.utc_offset = timezone_data['utc_offset_seconds']
            elif 'time_zone' in timezone_data and 'offset_with_dst' in timezone_data['time_zone']:
                offset_str = timezone_data['time_zone']['offset_with_dst']
                self.utc_offset = int(offset_str) * 60 * 60
            else:
                raise ValueError("UTC offset not found in timezone data.")
        except Exception as e:
            print('Error fetching timezone data:', e)
            return False
        
    def set_location(self, address):
        self.address = address
        url=url_encode()
        encoded_address = url.encode(address)
        if self.debug_mode:
            print(f"Encoded address: {encoded_address}")  # Debugging line to check the encoded address
        try:
            headers = {
                "User-Agent": "rp2"  # Add a custom user agent
            }
            if  self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
            response = requests.get(f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1", headers=self.headers, timeout=8)
            if self.debug_mode:
                print(response.content)
            response_code = response.status_code
            location_data = response.json()
            if self.debug_mode:
                print('Response code: ', response_code)
            
            if location_data:
                self.location = {
                    "latitude": location_data[0]["lat"],
                    "longitude": location_data[0]["lon"]
                }

            else:
                raise ValueError("Location not found")
        except Exception as e:
            print('Error fetching location data:', e)

    def _cache_key(self, category, parameter):
        """Create a cache key that includes category, parameter and current location.
        Falls back to a generic key if location is not set."""
        if self.location and 'latitude' in self.location and 'longitude' in self.location:
            return f"{category}:{parameter}:{self.location['latitude']},{self.location['longitude']}"
        return f"{category}:{parameter}:none"

    def check_cache(self, category, parameter, expiry):
        """Return cached value if present and unexpired, return 'expired' if it existed but expired, else None."""
        key = self._cache_key(category, parameter)
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() < entry.get('expires_at', 0):
            return entry.get('value')
        # expired
        try:
            del self._cache[key]
        except KeyError:
            pass
        return "expired"

    def set_cache(self, category, parameter, value, expiry):
        """Store a value in the cache with an expiry (seconds)."""
        key = self._cache_key(category, parameter)
        self._cache[key] = {
            'value': value,
            'expires_at': time.time() + int(expiry)
        }

    def get_location(self):
        if not self.location:
            return None
        return self.location

    def get_address(self):
        if not self.address:
            return None
        return self.address
    
    def get_remote_offset(self):
        return self.utc_offset

    
    def get_forecast(self, category, parameters, forecast_days=1, expiry=900):
        if not self.wifi_connected:
            raise ConnectionError("Wi-Fi is not connected.")
        
        if not self.location:
            raise ValueError("Location is not set.")
        
        if type(parameters) is str:
            parameters = parameters.split(",")  # Convert comma-separated string to list

        params_string = ",".join(parameters)
        if self.debug_mode:
            print(f"Requesting forecast for parameters: {params_string}")  # Debugging line to check the requested parameters

        # Check cache for each parameter and return cached value if available and not expired
        for param in parameters:
            cache_return = self.check_cache(category, param, expiry)
            if cache_return is not None and cache_return != "expired":
                if self.debug_mode:
                    print(f"Cache hit for {param}: {cache_return}")  # Debugging line to check cache hits
                return {param: cache_return}
            elif cache_return == "expired":
                if self.debug_mode:
                    print(f"Cache expired for {param}")  # Debugging line to check cache expiration

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={self.location['latitude']}&longitude={self.location['longitude']}&{category}={params_string}&forecast_days={forecast_days}"
        
        if  self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
        response = requests.get(weather_url, headers=self.headers, timeout=8)
        data = response.json()
        if self.debug_mode:
            print(f"Weather data: {data}")  # Debugging line to check the weather data
        response_code = response.status_code
        if self.debug_mode:
            print('Response code: ', response_code)

        results = {}
        for parameter in parameters:
            if category in data and parameter in data[category]:
                results[parameter] = data[category][parameter]
            else:
                results[parameter] = None  # or you could choose to raise an error or skip it
        # Store fetched values in cache for future requests
        try:
            for parameter, val in results.items():
                # cache even None values so repeated misses do not repeatedly hit the API
                self.set_cache(category, parameter, val, expiry)
        except Exception:
            # If caching fails for any reason, continue and return results
            pass
        return results
    
    def set_api_key(self, type, key):
        if type == "ipgeolocation":
            self.ipgeolocation_api_key = key
        else:
            raise ValueError("Unsupported API type. Currently only 'ipgeolocation' is supported.")
        
    def get_astronomy(self, category, parameter):
        if not self.wifi_connected:
            raise ConnectionError("Wi-Fi is not connected.")
        
        if not self.location:
            raise ValueError("Location is not set.")

        astro_url = f"https://api.ipgeolocation.io/v3/astronomy?apiKey={self.ipgeolocation_api_key}&lat={self.location['latitude']}&long={self.location['longitude']}"
        
        if  self.watchdog: self.watchdog.feed()  # Feed the watchdog if configured
        response = requests.get(astro_url, headers=self.headers, timeout=8)
        data = response.json()
        if self.debug_mode:
            print(f"Astronomy data: {data}")  # Debugging line to check the astronomy data
        response_code = response.status_code
        if self.debug_mode:
            print('Response code: ', response_code)

        if category in data and parameter in data[category]:
            return data[category][parameter]
        else:
            raise ValueError(f"{parameter} is not available in the {category} data.")
        