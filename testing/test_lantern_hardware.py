import unittest

from lantern_hardware import LanternHardware


class FakePin:
    OUT = 1
    IN = 0
    PULL_UP = 2
    instances = []
    button_readings = []

    def __init__(self, pin, mode=None, pull=None):
        self.pin = pin
        self.mode = mode
        self.pull = pull
        self.level = 1
        self.readings = list(self.button_readings) if pin == 16 else []
        self.instances.append(self)

    def value(self, level=None):
        if level is not None:
            self.level = level
            return
        if self.readings:
            self.level = self.readings.pop(0)
        return self.level


class FakePWM:
    instances = []

    def __init__(self, pin):
        self.pin = pin
        self.frequency = None
        self.duty = None
        self.instances.append(self)

    def freq(self, frequency):
        self.frequency = frequency

    def duty_u16(self, duty):
        self.duty = duty


class LanternHardwareTests(unittest.TestCase):
    def setUp(self):
        FakePin.instances = []
        FakePin.button_readings = []
        FakePWM.instances = []

    def create_hardware(self, sleep_ms=None):
        return LanternHardware(FakePin, FakePWM, sleep_ms)

    def test_initializes_board_pwm_and_digital_outputs(self):
        hardware = self.create_hardware()

        self.assertEqual([pwm.pin.pin for pwm in FakePWM.instances], [5, 6, 8, 9])
        self.assertTrue(all(pwm.frequency == 300 for pwm in FakePWM.instances))
        self.assertTrue(all(pwm.duty == 65535 for pwm in FakePWM.instances))
        self.assertEqual(hardware.blue.pin, 7)
        self.assertEqual(hardware.blue_2.pin, 10)
        self.assertEqual(hardware.blue.value(), 1)
        self.assertEqual(hardware.blue_2.value(), 1)

        hardware.red_pwm.duty(50)
        self.assertEqual(FakePWM.instances[0].duty, 32767)

        hardware.set_candle_duties(10, 20, 30, 40)
        self.assertEqual([pwm.duty for pwm in FakePWM.instances], [6553, 13107, 19660, 26214])
        hardware.set_status_color(0, 100)
        self.assertEqual([pwm.duty for pwm in FakePWM.instances], [65535, 0, 65535, 0])

    def test_setup_button_uses_active_low_debounce(self):
        FakePin.button_readings = [0, 0]
        delays = []
        hardware = self.create_hardware(delays.append)

        self.assertTrue(hardware.setup_button_pressed())
        button = FakePin.instances[-1]
        self.assertEqual(button.pin, 16)
        self.assertEqual(button.mode, FakePin.IN)
        self.assertEqual(button.pull, FakePin.PULL_UP)
        self.assertEqual(delays, [50])


if __name__ == "__main__":
    unittest.main()