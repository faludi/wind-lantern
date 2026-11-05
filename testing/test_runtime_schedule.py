import unittest

from runtime_schedule import RuntimeSchedule


class FakeTicks:
    period = 1 << 16

    def __init__(self, now):
        self.now = now

    def ticks_ms(self):
        return self.now

    def ticks_add(self, ticks, delta):
        return (ticks + delta) % self.period

    def ticks_diff(self, first, second):
        return ((first - second + self.period // 2) % self.period) - self.period // 2


class RuntimeScheduleTests(unittest.TestCase):
    def test_initial_deadlines_depend_on_startup_sync_result(self):
        ticks = FakeTicks(100)
        synced = RuntimeSchedule(ticks, 900, 12000, True)
        unsynced = RuntimeSchedule(ticks, 900, 12000, False)

        self.assertTrue(synced.settings_due(100))
        self.assertTrue(synced.periodic_due(100))
        self.assertFalse(synced.time_sync_due(100))
        self.assertEqual(synced.next_time_sync, 12100)
        self.assertEqual(unsynced.next_time_sync, 1000)

    def test_deadlines_reschedule_from_completion_time(self):
        ticks = FakeTicks(100)
        schedule = RuntimeSchedule(ticks, 900, 12000, True)

        schedule.schedule_settings_update(250, 3000)
        schedule.schedule_periodic_update(400)
        schedule.schedule_time_sync(500)

        self.assertFalse(schedule.settings_due(250))
        self.assertTrue(schedule.settings_due(3250))
        self.assertFalse(schedule.periodic_due(400))
        self.assertTrue(schedule.periodic_due(1300))
        self.assertFalse(schedule.time_sync_due(500))
        self.assertTrue(schedule.time_sync_due(12500))

    def test_wait_uses_nearest_deadline_and_zero_for_overdue_work(self):
        ticks = FakeTicks(100)
        schedule = RuntimeSchedule(ticks, 900, 12000, True)
        schedule.schedule_settings_update(100, 500)
        schedule.schedule_periodic_update(100)

        self.assertEqual(schedule.wait_ms(200), 400)
        self.assertEqual(schedule.wait_ms(600), 0)
        self.assertEqual(schedule.wait_ms(1000), 0)

    def test_tick_deadlines_wrap_correctly(self):
        ticks = FakeTicks(FakeTicks.period - 50)
        schedule = RuntimeSchedule(ticks, 100, 200, True)

        schedule.schedule_settings_update(ticks.ticks_ms(), 100)

        self.assertFalse(schedule.settings_due(FakeTicks.period - 1))
        self.assertTrue(schedule.settings_due(50))


if __name__ == "__main__":
    unittest.main()