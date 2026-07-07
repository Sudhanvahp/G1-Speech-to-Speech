"""Tests for HybridBrain: deterministic motion, LLM only for conversation,
and graceful degradation when the LLM is unavailable."""
import unittest

from g1voice.brain import LLMUnavailable, Reply
from g1voice.hybrid_brain import HybridBrain


class _RecordingLLM:
    """Stand-in LLM that records whether it was consulted."""

    def __init__(self, fail=False):
        self.called = False
        self.fail = fail

    def handle(self, user_text, execute):
        self.called = True
        if self.fail:
            raise LLMUnavailable("down")
        return Reply(text="chat reply", tools_called=[])


class TestHybridBrain(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def _execute(self, name, args):
        self.calls.append(name)
        return f"ran {name}"

    def test_motion_is_deterministic_and_skips_llm(self):
        llm = _RecordingLLM()
        brain = HybridBrain(llm)
        reply = brain.handle("walk forward", self._execute)
        self.assertEqual(self.calls, ["walk"])
        self.assertFalse(llm.called)          # motion never hits the LLM
        self.assertEqual(reply.tools_called, ["walk"])

    def test_conversation_goes_to_llm(self):
        llm = _RecordingLLM()
        brain = HybridBrain(llm)
        reply = brain.handle("who made you", self._execute)
        self.assertTrue(llm.called)
        self.assertEqual(self.calls, [])       # no motion
        self.assertEqual(reply.text, "chat reply")

    def test_graceful_degradation_when_llm_down(self):
        llm = _RecordingLLM(fail=True)
        brain = HybridBrain(llm)
        # Motion still works ...
        brain.handle("wave", self._execute)
        self.assertEqual(self.calls, ["wave"])
        # ... and a chat question degrades cleanly instead of raising.
        reply = brain.handle("tell me a joke", self._execute)
        self.assertIsNotNone(reply.text)


if __name__ == "__main__":
    unittest.main()
