# Rob Faludi 2025
# BLE based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-bluetooth-low-energy-micropython/ 
# Uses modern device wind sensor: https://moderndevice.com/products/wind-sensor

from micropython import const
import asyncio
import aioble
import bluetooth
import struct
from machine import ADC, Timer, Pin
import _thread

version = "1.0.9"
print("Wind Sensor BLE - Version:", version)

default_zero_offset = 2000 # wind sensor calibration offset
mode = 'anemometer' # 'anemometer' or 'modern_device_rev_C

sLock = _thread.allocate_lock()
terminateThread = False

#org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.irradiance
_ENV_SENSE_WIND_UUID = bluetooth.UUID(0x2A72)
# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_WIND = const(1360) #0x0550  

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000

# Register GATT server.
wind_service = aioble.Service(_ENV_SENSE_UUID)
wind_characteristic = aioble.Characteristic(
wind_service, _ENV_SENSE_WIND_UUID, read=True, notify=True)
aioble.register_services(wind_service)

# set up sensor
print("Mode:", mode)
if mode == 'modern_device_rev_C':
    wind_sensor = ADC(26)
elif mode == 'anemometer':
    pass
else:
    raise ValueError("Invalid mode. Choose 'modern_device_rev_C' or 'anemometer'.")

# Helper to encode the wind characteristic
def _encode_value(wind_speed):
    return struct.pack("<I", int(wind_speed * 100))

def _write_zero_offset(t):  
    global zero_offset
    open("calibration.txt", "w").write(str(zero_offset))
    print("**Calibration saved:", zero_offset)

# initialize timer for periodic zero_offset storage
timer = Timer(-1)
timer.init(period=(60*60*1000), mode=Timer.PERIODIC, callback=_write_zero_offset)

def _read_zero_offset():
    try:
        offset = float(open("calibration.txt", "r").read())
        print("**Calibration loaded:", offset)
        return offset
    except Exception as e:
        print("Error reading calibration file:", e)
        return default_zero_offset # default value if file read fails
    
zero_offset = _read_zero_offset()
wind_speed_meters_per_second = 0.0

def read_anemometer():
    global wind_speed_meters_per_second
    global terminateThread
    global zero_offset
    import time
    pulse_count = 0
    last_time = time.ticks_ms()
    
    def pulse_handler(pin):
        nonlocal pulse_count
        pulse_count += 1

    anemometer_pin = Pin(15, Pin.IN, Pin.PULL_UP)
    anemometer_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)
    
    while not terminateThread:
        time.sleep(5)  # Measure every 5 seconds
        current_time = time.ticks_ms()
        elapsed_time = time.ticks_diff(current_time, last_time) / 1000  # in seconds
        last_time = current_time
        
        # Calculate wind speed in m/s (assuming 1 pulse per rotation and 2.4m circumference)
        # rotations = pulse_count / 2.0  # assuming 2 pulses per rotation
        # wind_speed_meters_per_second = (rotations * 2.4) / elapsed_time
        # wind_speed_meters_per_second = round(wind_speed_meters_per_second, 2)
        wind_speed_meters_per_second = pulse_count / elapsed_time * 5
        wind_speed_meters_per_second = round(wind_speed_meters_per_second, 2)
        
        print("Anemometer - Pulses:", pulse_count, "Elapsed Time (s):", elapsed_time, "Wind Speed (m/s):", wind_speed_meters_per_second)
        
        pulse_count = 0  # Reset count for next interval   

if mode == 'anemometer':
    _thread.start_new_thread(read_anemometer, ())


# Get wind and update characteristic
async def sensor_task():
    global zero_offset, wind_speed_meters_per_second
    while True:
        if mode == 'modern_device_rev_C':
            wind = wind_sensor.read_u16()
            print("Raw wind:", wind, "Calibration:", zero_offset)
            if wind < zero_offset:
                zero_offset -= (zero_offset - wind) * 0.005 # adjust zero offset downwards very slowly
            zero_offset += 0.01 # also increase the zero offset slightly to avoid runaway
            wind = int( max (wind - (zero_offset * 1.05), 0) ) # add 5% to avoid noise, remove negatives and decimals
            wind_speed_meters_per_second = (wind / 65535) * 26.8224 # convert to m/s based on sensor specs
            wind_speed_meters_per_second = round(wind_speed_meters_per_second, 2) # round to 2 decimal places
            print("Calibrated raw wind:", wind, "Wind speed (m/s):", wind_speed_meters_per_second)
        elif mode == 'anemometer':
            pass
        wind_characteristic.write(_encode_value(wind_speed_meters_per_second), send_update=True)
        print("Sent:", wind_speed_meters_per_second)
        await asyncio.sleep_ms(1000)
        
# Serially wait for connections. Don't advertise while a central is connected.
async def peripheral_task():
    while True:
        try:
            async with await aioble.advertise(
                _ADV_INTERVAL_MS,
                name="RPi-Pico",
                services=[_ENV_SENSE_UUID],
                appearance=_ADV_APPEARANCE_WIND,
                ) as connection:
                    print("Connection from", connection.device)
                    await connection.disconnected()
        except asyncio.CancelledError:
            # Catch the CancelledError
            print("Peripheral task cancelled")
        except Exception as e:
            print("Error in peripheral_task:", e)
        finally:
            # Ensure the loop continues to the next iteration
            await asyncio.sleep_ms(100)

# Run both tasks
async def main():
    t1 = asyncio.create_task(sensor_task())
    t2 = asyncio.create_task(peripheral_task())
    await asyncio.gather(t1, t2)
    
asyncio.run(main())
