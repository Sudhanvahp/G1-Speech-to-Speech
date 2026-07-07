"""Contracts for robot capabilities and the LLM tool schemas.

The tool schemas are the single source of truth for what the LLM may do. Every
tool name MUST correspond to a method on a MotionSkills implementation; this is
enforced at startup by `validate_tools()`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

# Head-LED colors (R, G, B) used as visual state feedback.
LED_COLORS: dict[str, tuple[int, int, int]] = {
    "idle": (0, 0, 64),
    "listening": (0, 128, 0),
    "thinking": (128, 64, 0),
    "speaking": (0, 64, 128),
    "error": (128, 0, 0),
}

AgentState = str  # one of LED_COLORS keys


@runtime_checkable
class MotionSkills(Protocol):
    """Safe, high-level motion primitives. Every method returns a short human
    string describing what happened (fed back to the LLM as the tool result)."""

    def stop(self) -> str: ...
    def stand_up(self) -> str: ...
    def sit_down(self) -> str: ...
    def walk(self, vx: float = 0.3, seconds: float = 2.0) -> str: ...
    def turn(self, degrees: float = 45.0) -> str: ...
    def wave(self) -> str: ...
    def shake_hand(self) -> str: ...


@runtime_checkable
class SpeechSkills(Protocol):
    """Speech output and LED state feedback."""

    def say(self, text: str) -> None: ...
    def set_state(self, state: AgentState) -> None: ...
    def play_pcm(self, pcm_bytes: bytes) -> None: ...
    def play_stop(self) -> None: ...


# --- LLM tool schemas (OpenAI/Ollama function-calling format) ---------------
TOOL_SCHEMAS: list[dict] = [
    {"name": "stop", "description": "Immediately stop all motion and hold still.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "stand_up", "description": "Stand up into a balanced standing pose.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "sit_down", "description": "Squat down and relax. Robot ends low and still.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "walk",
     "description": "Walk in a straight line. Positive vx = forward, negative = backward.",
     "parameters": {"type": "object", "properties": {
         "vx": {"type": "number",
                "description": "speed in m/s, magnitude clamped to <= 0.4"},
         "seconds": {"type": "number",
                     "description": "duration, clamped to 0.2-3.0 s"}},
         "required": []}},
    {"name": "turn",
     "description": "Turn in place. Positive degrees = left, negative = right.",
     "parameters": {"type": "object", "properties": {
         "degrees": {"type": "number", "description": "-180 to 180"}},
         "required": []}},
    {"name": "wave", "description": "Wave a hand to greet a person.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "shake_hand", "description": "Extend a hand to offer a handshake.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
]

# Names the LLM is allowed to call.
TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOL_SCHEMAS)


def openai_tools() -> list[dict]:
    """Wrap the schemas in the OpenAI `tools` envelope."""
    return [{"type": "function", "function": s} for s in TOOL_SCHEMAS]


def validate_tools(motion: object) -> None:
    """Fail fast if a tool schema has no matching motion method."""
    missing = [name for name in TOOL_NAMES if not callable(getattr(motion, name, None))]
    if missing:
        raise TypeError(
            f"{type(motion).__name__} is missing tool methods: {sorted(missing)}"
        )
