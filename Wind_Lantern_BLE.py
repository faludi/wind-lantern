# Rob Faludi 2025
# BLE based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-bluetooth-low-energy-micropython/ 
# Flicker based on code from Grant Whitney
# https://grantwinney.com/raspberry-pi-flickering-candle/

import uasyncio as asyncio
import aioble
import bluetooth
import struct
from machine import Pin, PWM
import time
import random
import _thread

version = "1.0.9"
print("Wind Lantern BLE - Version:", version)

sLock = _thread.allocate_lock()

red_pin = 5
green_pin = 6
blue_pin = 7

red_pin_2 = 8
green_pin_2 = 9
blue_pin_2 = 10

wind_factor = 0

terminateThread = False

# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.temperature
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A72)

# Name of the peripheral you want to connect
peripheral_name="RPi-Pico"

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
 
def red_light():
        global wind_factor
        red_pwm.duty( 100 - min(random.randint(93-wind_factor, 100), 100) )
        red_pwm_2.duty(100 - min(random.randint(93-wind_factor, 100) , 100) ) 
        rand_flicker_sleep()
 
def green_light():
        global wind_factor
        green_pwm.duty( 100 - min(random.randint(33-wind_factor, 34) ,100) )
        green_pwm_2.duty(100 - min(random.randint(33-wind_factor, 34) ,100) )
        rand_flicker_sleep()
 
def rand_flicker_sleep():
    time.sleep(random.randint(3, 10) / 100.0)

def light_candle():
        print("Starting candle thread")
        while terminateThread == False:
                red_light()
                green_light()
                time.sleep_ms(1)

# Helper to decode the wind characteristic encoding (sint16, hundredths of a degree).
def _decode_value(data):
    try:
        if data is not None:
            return struct.unpack("<I", data)[0] / 100
    except Exception as e:
        print("Error decoding wind:", e)
    return None

async def find_wind_sensor():
    # Scan for 5 seconds, in active mode, with a very low interval/window (to
    # maximize detection rate).
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            print(result.name())
            # See if it matches our name and the environmental sensing service.
            if result.name() == peripheral_name and _ENV_SENSE_UUID in result.services():
                return result.device
    return None

_thread.start_new_thread(light_candle, ())

async def main():
    while True:
        device = await find_wind_sensor()
        if not device:
            print("Wind sensor not found. Retrying...")
            await asyncio.sleep_ms(5000)  # Wait for 5 seconds before retrying
            continue

        try:
            print("Connecting to", device)
            connection = await device.connect()
        except asyncio.TimeoutError:
            print("Timeout during connection. Retrying...")
            await asyncio.sleep_ms(5000)  # Wait for 5 seconds before retrying
            continue

        async with connection:
            try:
                wind_service = await connection.service(_ENV_SENSE_UUID)
                wind_characteristic = await wind_service.characteristic(_ENV_SENSE_TEMP_UUID)
                blue_pwm.duty(100) # turn off blue LEDs
                blue_pwm_2.duty(100) # turn off blue LEDs
            except asyncio.TimeoutError:
                print("Timeout discovering services/characteristics. Retrying...")
                await asyncio.sleep_ms(5000)  # Wait for 5 seconds before retrying
                continue
            except AttributeError:
                print("Attribute error. Retrying...")
                await asyncio.sleep_ms(1000)  # Wait for 1 seconds before retrying
                continue

            while True:
                global wind_factor
                try:
                    wind_data = await wind_characteristic.read()
                    if wind_data is not None:
                        wind_speed = _decode_value(wind_data)
                        if wind_speed is not None:
                            print("Wind: {:.2f}".format(wind_speed))
                            wind_factor = max(int(wind_speed), 0) # protect against negative wind factor
                            wind_factor = wind_factor * 2   # increase wind factor effect
                            print("Wind factor:", wind_factor)
                        else:
                            print("Invalid wind data")
                    else:
                        print("Error reading wind: None")
                except Exception as e:
                    print("Error in main loop:", e)
                    break  # Break out of the inner loop and attempt to reconnect
                await asyncio.sleep_ms(1000)  # Read every 1 seconds
                # await light_candle(10)

# Create an Event Loop
loop = asyncio.get_event_loop()
# Create a task to run the main function
loop.create_task(main())

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

