# Rob Faludi 2026
# Lantern Test Environment to simulate wind effects on LED lanterns

import time
import random
from wind_manager import WindManager
from lantern_hardware import LanternHardware


version = "1.0"
print("Wind Lantern Test - Version:", version)

time.sleep(2) # allow usb connection on startup


hardware = LanternHardware()
hardware.set_candle_duties(3, 70, 3, 70)



# def red_light():
#         global wind_manager
#         factor = wind_manager.get_wind_factor()
#         red_pwm.duty(100 - min(random.uniform(93-factor, 100), 100),)
#         red_pwm_2.duty(100 - min(random.uniform(93-factor, 100) , 100))
#         rand_flicker_sleep()

# def green_light():
#         global wind_manager
#         factor = wind_manager.get_wind_factor()
#         green_pwm.duty(100 - min(random.uniform(29-factor, 30) ,100))
#         green_pwm_2.duty(100 - min(random.uniform(29-factor, 30) ,100))
#         rand_flicker_sleep()
    

def rand_flicker_sleep():
    time.sleep(random.uniform(rand_flick_low, rand_flick_high) / 100.0)

def light_candle():
    global wind_manager
    factor = wind_manager.get_wind_factor()
    intensity = wind_manager.get_intensity()
    hardware.set_red_duties(
        100 - min(random.uniform(95-factor, 100) * intensity, 100),
        100 - min(random.uniform(95-factor, 100) * intensity, 100),
    )
    hardware.set_green_duties(
        100 - min(random.uniform(31-factor, 32) * intensity, 100),
        100 - min(random.uniform(31-factor, 32) * intensity, 100),
    )
    rand_flicker_sleep()
    time.sleep_ms(1)

wind_manager = WindManager()

wind_manager.set_wind(8,22)
print(f'Wind factor: {wind_manager.wind_factor}, Gust factor: {wind_manager.gust_factor}')
rand_flick_low = 3
rand_flick_high = 10


while True:
    try:
        light_candle()
    except KeyboardInterrupt:
        hardware.set_candle_duties(100, 100, 100, 100)
        print('Program Interrupted by the user')
        break

