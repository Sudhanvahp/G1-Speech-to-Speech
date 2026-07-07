"""KeywordBrain — a rule-based stand-in for the LLM.

No model, no network, no API key. It maps common phrases to motion tools so you
can exercise the entire agent (safety, tool execution, speech) with zero setup.
Use via `--fake-llm`. Handy for CI, demos, and testing on the robot offline.

It is intentionally simple: keyword matching, not language understanding. The
real Brain (brain.py) is what you use for natural conversation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .brain import Reply, ToolExecutor

log = logging.getLogger(__name__)

_HELP = ("I can walk, turn, stand, sit, wave, or shake hands. "
         "Try 'wave' or 'walk forward'.")


@dataclass(frozen=True)
class Command:
    """A recognized motion command: which tool, its args, and what to say."""

    tool: str
    args: dict
    reply: str


def match_command(user_text: str) -> Command | None:
    """Map an utterance to a motion Command, or None if it isn't a command.

    Whole-word matching (so 'backflip' is not read as 'back'). This is the
    deterministic, safety-critical path used by KeywordBrain and HybridBrain.
    """
    w = {token.strip(".,!?;:'\"") for token in user_text.lower().split()}
    if w & {"shake", "handshake"}:
        return Command("shake_hand", {}, "Here's my hand.")
    if "wave" in w:
        return Command("wave", {}, "Hello!")
    if w & {"stand", "standup"} or {"get", "up"} <= w:
        return Command("stand_up", {}, "Standing up.")
    if w & {"sit", "crouch", "squat", "kneel"}:
        return Command("sit_down", {}, "Sitting down.")
    if w & {"turn", "spin", "rotate"} or w & {"left", "right"}:
        degrees = -90.0 if "right" in w else 90.0
        side = "right" if degrees < 0 else "left"
        return Command("turn", {"degrees": degrees}, f"Turning {side}.")
    if w & {"walk", "forward", "backward", "back", "come", "go", "move", "steps"}:
        backward = bool(w & {"backward", "back"})
        return Command("walk", {"vx": -0.3 if backward else 0.3, "seconds": 2.0},
                       f"Walking {'backward' if backward else 'forward'}.")
    if w & {"hello", "hi", "hey"}:
        return Command("wave", {}, "Hi there!")
    return None


class KeywordBrain:
    """Offline rule-based brain. Implements the Brain interface, no LLM."""

    def handle(self, user_text: str, execute: ToolExecutor) -> Reply:
        cmd = match_command(user_text)
        if cmd is None:
            return Reply(text=_HELP, tools_called=[])
        execute(cmd.tool, cmd.args)
        return Reply(text=cmd.reply, tools_called=[cmd.tool])
