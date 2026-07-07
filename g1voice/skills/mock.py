"""Mock skills for dry-run testing on any PC — no Unitree SDK, no robot.

They log what the real skills would do and apply the SAME safety clamps, so a
dry run faithfully exercises the LLM, tool-calling, and safety logic.
"""
from __future__ import annotations

import logging

from ..config import SafetyConfig
from . import safety
from .base import AgentState

log = logging.getLogger("g1voice.mock")


class MockMotionSkills:
    def __init__(self, safety_cfg: SafetyConfig) -> None:
        self._cfg = safety_cfg

    def stop(self) -> str:
        log.info("MOTION stop() -> StopMove + Damp")
        return "Stopped."

    def stand_up(self) -> str:
        log.info("MOTION stand_up()")
        return "Standing."

    def sit_down(self) -> str:
        log.info("MOTION sit_down()")
        return "Sitting down."

    def walk(self, vx: float = 0.3, seconds: float = 2.0) -> str:
        cvx, cs = safety.clamp_walk(vx, seconds, self._cfg)
        note = "" if (cvx, cs) == (vx, seconds) else f"  (clamped from vx={vx}, seconds={seconds})"
        log.info("MOTION walk(vx=%.2f, seconds=%.1f)%s", cvx, cs, note)
        return f"Walked {'forward' if cvx >= 0 else 'backward'} for {cs:.1f}s."

    def turn(self, degrees: float = 45.0) -> str:
        _, seconds = safety.turn_plan(degrees, self._cfg)
        log.info("MOTION turn(degrees=%.0f)  (~%.1fs)", degrees, seconds)
        side = "left" if degrees >= 0 else "right"
        return f"Turned {abs(degrees):.0f} degrees {side}."

    def wave(self) -> str:
        log.info("MOTION wave()")
        return "Waved."

    def shake_hand(self) -> str:
        log.info("MOTION shake_hand()")
        return "Offering a handshake."


class MockSpeechSkills:
    def say(self, text: str) -> None:
        log.info('SPEAK "%s"', text)

    def set_state(self, state: AgentState) -> None:
        log.debug("LED %s", state)

    def play_pcm(self, pcm_bytes: bytes) -> None:
        log.debug("SPEAKER %d bytes", len(pcm_bytes))

    def play_stop(self) -> None:
        log.debug("SPEAKER stop")
