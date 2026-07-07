"""Pure, testable clamping helpers shared by the real and mock motion skills.

Keeping these free of any SDK import means the safety limits are identical in
dry-run and on the robot, and can be unit-tested without hardware.
"""
from __future__ import annotations

import math

from ..config import SafetyConfig


def clamp(value: float, limit: float) -> float:
    """Clamp `value` to the symmetric range [-limit, limit]."""
    return max(-limit, min(limit, value))


def clamp_walk(vx: float, seconds: float, cfg: SafetyConfig) -> tuple[float, float]:
    """Return (vx, seconds) forced within safe bounds."""
    vx = clamp(vx, cfg.max_vx)
    seconds = min(max(seconds, cfg.min_walk_seconds), cfg.max_walk_seconds)
    return vx, seconds


def turn_plan(degrees: float, cfg: SafetyConfig) -> tuple[float, float]:
    """Return (yaw_rate rad/s, seconds) to rotate `degrees` in place, clamped.

    Direction follows the sign of `degrees` (positive = left/CCW).
    """
    degrees = max(-180.0, min(180.0, degrees))
    yaw_rate = math.copysign(cfg.max_vyaw, degrees or 1.0)
    seconds = min(abs(math.radians(degrees)) / cfg.max_vyaw, cfg.max_walk_seconds)
    return yaw_rate, seconds


def is_stop_command(text: str, cfg: SafetyConfig) -> bool:
    """True if the utterance contains a stop word (whole-word match)."""
    words = {w.strip(".,!?;:") for w in text.lower().split()}
    return bool(words & cfg.stop_words)
