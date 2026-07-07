"""HybridBrain — deterministic motion + LLM conversation. The production default.

Rationale: small local models are unreliable at tool-calling (they narrate
instead of acting, or call the wrong tool). Motion is safety-critical, so we do
NOT delegate it to the model. Instead:

  * If the utterance is a recognized motion command -> execute it deterministically
    via the keyword matcher (instant, correct, works even if the LLM is down).
  * Otherwise (questions, chit-chat) -> ask the LLM for a spoken reply.

This gives rock-solid actuation with natural-language conversation, and degrades
gracefully: if the LLM is unreachable, motion commands still work.
"""
from __future__ import annotations

import logging

from .brain import BrainProtocol, LLMUnavailable, Reply, ToolExecutor
from .fake_brain import match_command

log = logging.getLogger(__name__)


class HybridBrain:
    def __init__(self, llm: BrainProtocol) -> None:
        self._llm = llm

    def handle(self, user_text: str, execute: ToolExecutor) -> Reply:
        cmd = match_command(user_text)
        if cmd is not None:
            log.debug("Deterministic match: %s", cmd.tool)
            execute(cmd.tool, cmd.args)
            return Reply(text=cmd.reply, tools_called=[cmd.tool])

        # Not a motion command -> conversation. Fall back gracefully if the LLM
        # is unavailable so a chat question never blocks the robot.
        try:
            return self._llm.handle(user_text, execute)
        except LLMUnavailable as exc:
            log.warning("LLM unavailable for conversation: %s", exc)
            return Reply(
                text="I can move on command, but chat isn't available right now.",
                tools_called=[],
            )
