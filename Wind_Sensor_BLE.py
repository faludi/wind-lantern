# Rob Faludi 2025
# BLE based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-bluetooth-low-energy-micropython/ 
# Uses modern device wind sensor: https://moderndevice.com/products/wind-sensor

from micropython import const
import asyncio
import aioble
import bluetooth
import struct
from machine import ADC, Timer

default_zero_offset = 2000 # wind sensor calibration offset

version = "1.0.8"
print("Wind Sensor BLE - Version:", version)

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
wind_sensor = ADC(26)

# Helper to encode the wind characteristic encoding
# (sint16, hundredths of a lumen).
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

# Get wind and update characteristic
async def sensor_task():
    global zero_offset
    while True:
        wind = wind_sensor.read_u16()
        print("Raw wind:", wind, "Calibration:", zero_offset)
        if wind < zero_offset:
            zero_offset -= (zero_offset - wind) * 0.005 # adjust zero offset downwards very slowly
        zero_offset += 0.01 # also increase the zero offset slightly to avoid runaway
        wind = int( max (wind - (zero_offset * 1.05), 0) ) # add 5% to avoid noise, remove negatives and decimals
        wind_speed_meters_per_second = (wind / 65535) * 26.8224 # convert to m/s based on sensor specs
        wind_speed_meters_per_second = round(wind_speed_meters_per_second, 2) # round to 2 decimal places
        print("Calibrated raw wind:", wind, "Wind speed (m/s):", wind_speed_meters_per_second)
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
