import unittest

from wind_manager import WindManager


class FakeClock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now


class FixedRandom:
    def randint(self, minimum, maximum):
        return minimum

    def uniform(self, minimum, maximum):
        return minimum


class WindManagerTests(unittest.TestCase):
    def test_wind_factor_ramps_through_gust_transition(self):
        clock = FakeClock()
        manager = WindManager(clock=clock, random_source=FixedRandom())
        manager.set_wind(1, 4)

        self.assertAlmostEqual(manager.get_wind_factor(), manager.wind_factor)

        clock.now = 1
        manager.get_wind_factor()
        self.assertFalse(manager.gusting)

        clock.now = 376
        expected = manager.wind_factor + (manager.gust_factor - manager.wind_factor) * 0.5
        self.assertAlmostEqual(manager.get_wind_factor(), expected)

    def test_flicker_intensity_scales_wind_and_output_range(self):
        clock = FakeClock()
        manager = WindManager(flicker_intensity=2, clock=clock, random_source=FixedRandom())
        manager.set_wind(1, 4)

        self.assertAlmostEqual(manager.wind_factor, 2)
        self.assertAlmostEqual(manager.gust_factor, manager.compress(4) * 2)

        manager.get_wind_factor()
        clock.now = 1
        manager.get_wind_factor()
        clock.now = 376
        self.assertAlmostEqual(manager.get_intensity(), 0.95)


if __name__ == "__main__":
    unittest.main()