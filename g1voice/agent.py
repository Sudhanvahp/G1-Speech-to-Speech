"""VoiceAgent — wires speech input, the LLM brain, safety, and robot skills.

Flow for each utterance:
  1. Emergency stop words are handled locally, BEFORE the LLM (works offline).
  2. An optional wake word gates everything else.
  3. The brain chooses tools + a reply; tools run through the safety-clamped
     skills; the reply is spoken.
"""
from __future__ import annotations

import logging

from .brain import BrainProtocol, LLMUnavailable, Reply
from .config import Settings
from .skills import safety
from .skills.base import MotionSkills, SpeechSkills, validate_tools

log = logging.getLogger(__name__)


class VoiceAgent:
    def __init__(
        self,
        settings: Settings,
        motion: MotionSkills,
        speech: SpeechSkills,
        brain: BrainProtocol,
    ) -> None:
        validate_tools(motion)  # fail fast if a tool has no method
        self._settings = settings
        self._motion = motion
        self._speech = speech
        self._brain = brain
        self._speech.set_state("idle")

    def announce(self, text: str) -> None:
        """Speak a message directly (e.g. a startup greeting), no LLM."""
        self._speech.say(text)

    def handle(self, text: str) -> None:
        """Process one recognized utterance end to end. Never raises."""
        text = text.strip()
        if not text:
            return
        try:
            self._handle(text)
        except LLMUnavailable as exc:
            # Clean, single-line message — no stack trace. The most common cause
            # is Ollama not running (start it, or use --fake-llm).
            log.error("Brain unavailable: %s", exc)
            self._speech.set_state("error")
            self._speech.say("My language model is not reachable right now.")
            self._speech.set_state("idle")
        except Exception:
            log.exception("Error while handling %r", text)
            self._speech.set_state("error")
            self._speech.say("Sorry, something went wrong.")
            self._speech.set_state("idle")

    # -- internal ------------------------------------------------------------
    def _handle(self, text: str) -> None:
        cfg = self._settings.safety

        # 1. Emergency stop — bypasses the LLM entirely.
        if safety.is_stop_command(text, cfg):
            log.warning("STOP word heard -> emergency stop")
            self._motion.stop()
            self._speech.say("Stopped.")
            return

        # 2. Wake word gate.
        if cfg.wake_word and cfg.wake_word.lower() not in text.lower():
            log.debug("Ignoring (no wake word): %r", text)
            return

        # 3. Think, act, speak.
        log.info("USER: %s", text)
        self._speech.set_state("thinking")
        reply: Reply = self._brain.handle(text, self._execute_tool)
        if reply.text:
            log.info("ROBOT: %s", reply.text)
            self._speech.say(reply.text)
        else:
            self._speech.set_state("idle")

    def _execute_tool(self, name: str, args: dict) -> str:
        """Run one motion tool with clamped args; return a result string."""
        method = getattr(self._motion, name)
        try:
            return method(**args)
        except TypeError as exc:  # bad args from the model
            log.warning("Tool %s rejected args %s: %s", name, args, exc)
            return f"error: invalid arguments for {name}"
        except Exception as exc:
            log.exception("Tool %s failed", name)
            self._speech.set_state("error")
            return f"error: {name} failed ({exc})"
