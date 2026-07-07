"""Unit tests for the safety layer — the part that must never be wrong.

Run:  python -m pytest    (or: python -m unittest discover)
These need no robot, no SDK, and no network.
"""
import math
import unittest

from g1voice.config import SafetyConfig
from g1voice.skills import safety


class TestClamps(unittest.TestCase):
    def setUp(self):
        self.cfg = SafetyConfig()

    def test_walk_speed_clamped(self):
        vx, _ = safety.clamp_walk(10.0, 2.0, self.cfg)
        self.assertEqual(vx, self.cfg.max_vx)
        vx, _ = safety.clamp_walk(-10.0, 2.0, self.cfg)
        self.assertEqual(vx, -self.cfg.max_vx)

    def test_walk_duration_clamped(self):
        _, s = safety.clamp_walk(0.2, 999.0, self.cfg)
        self.assertEqual(s, self.cfg.max_walk_seconds)
        _, s = safety.clamp_walk(0.2, 0.0, self.cfg)
        self.assertEqual(s, self.cfg.min_walk_seconds)

    def test_turn_direction_and_bounds(self):
        yaw, secs = safety.turn_plan(90, self.cfg)
        self.assertGreater(yaw, 0)                 # left = positive
        self.assertLessEqual(secs, self.cfg.max_walk_seconds)
        yaw, _ = safety.turn_plan(-90, self.cfg)
        self.assertLess(yaw, 0)                     # right = negative

    def test_turn_capped_at_180(self):
        _, secs = safety.turn_plan(9999, self.cfg)
        expected = min(math.radians(180) / self.cfg.max_vyaw,
                       self.cfg.max_walk_seconds)
        self.assertAlmostEqual(secs, expected)


class TestStopDetection(unittest.TestCase):
    def setUp(self):
        self.cfg = SafetyConfig()

    def test_detects_stop_words(self):
        for phrase in ("stop", "STOP!", "please freeze", "emergency now", "halt."):
            self.assertTrue(safety.is_stop_command(phrase, self.cfg), phrase)

    def test_ignores_non_stop(self):
        for phrase in ("walk forward", "wave hello", "turn around", "stopwatch"):
            self.assertFalse(safety.is_stop_command(phrase, self.cfg), phrase)


if __name__ == "__main__":
    unittest.main()
