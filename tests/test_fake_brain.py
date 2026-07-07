"""Tests for the offline KeywordBrain — no LLM, no robot."""
import unittest

from g1voice.fake_brain import KeywordBrain


class TestKeywordBrain(unittest.TestCase):
    def setUp(self):
        self.brain = KeywordBrain()
        self.calls: list[tuple[str, dict]] = []

    def _execute(self, name, args):
        self.calls.append((name, args))
        return f"ran {name}"

    def _tool(self, text):
        self.calls.clear()
        self.brain.handle(text, self._execute)
        return self.calls[0][0] if self.calls else None

    def test_basic_intents(self):
        self.assertEqual(self._tool("please wave"), "wave")
        self.assertEqual(self._tool("shake my hand"), "shake_hand")
        self.assertEqual(self._tool("stand up now"), "stand_up")
        self.assertEqual(self._tool("sit down"), "sit_down")
        self.assertEqual(self._tool("walk forward"), "walk")
        self.assertEqual(self._tool("turn left"), "turn")

    def test_direction_args(self):
        self.brain.handle("go backward", self._execute)
        self.assertLess(self.calls[0][1]["vx"], 0)
        self.calls.clear()
        self.brain.handle("turn right", self._execute)
        self.assertLess(self.calls[0][1]["degrees"], 0)

    def test_unknown_request_calls_no_tool(self):
        # 'backflip' must NOT be mistaken for 'back'/walk.
        self.assertIsNone(self._tool("do a backflip"))
        self.assertIsNone(self._tool("what is the weather"))


if __name__ == "__main__":
    unittest.main()
