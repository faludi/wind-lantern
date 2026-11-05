import unittest

from clock_service import LanternClock


class FakeClient:
    def __init__(self, offsets=(), sync_result=True):
        self.offsets = list(offsets)
        self.sync_result = sync_result
        self.sync_calls = 0

    def sync_time(self):
        self.sync_calls += 1
        return self.sync_result

    def get_local_timezone_offset(self):
        return self.offsets.pop(0)


class LanternClockTests(unittest.TestCase):
    def test_refresh_converts_offset_and_local_hour_wraps(self):
        client = FakeClient(offsets=[-5 * 3600])
        clock = LanternClock(client, output=lambda *args: None)

        self.assertEqual(clock.refresh_local_offset(), -5)
        self.assertEqual(clock.local_hour(2), 21)
        self.assertEqual(clock.local_hour(8), 3)

    def test_failed_refresh_keeps_last_known_offset(self):
        client = FakeClient(offsets=[3 * 3600, None])
        clock = LanternClock(client, output=lambda *args: None)

        self.assertEqual(clock.refresh_local_offset(), 3)
        self.assertEqual(clock.refresh_local_offset(), 3)

    def test_sync_time_delegates_to_client(self):
        client = FakeClient(sync_result=False)
        clock = LanternClock(client)

        self.assertFalse(clock.sync_time())
        self.assertEqual(client.sync_calls, 1)


if __name__ == "__main__":
    unittest.main()