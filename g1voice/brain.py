"""The language-model brain: turn user text into tool calls + a spoken reply.

Provider-agnostic — talks to any OpenAI-compatible endpoint, so the same code
drives a free local Ollama model or the OpenAI cloud. The brain decides WHICH
tool to call; it never executes anything itself (the agent does that), which
keeps the AI cleanly separated from robot actuation.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable, Protocol

from openai import APIConnectionError, APIError, OpenAI

from .config import LLMConfig
from .skills.base import TOOL_NAMES, openai_tools

log = logging.getLogger(__name__)

# Executes a tool call by name+args and returns a short result string.
ToolExecutor = Callable[[str, dict], str]


class LLMUnavailable(RuntimeError):
    """The language model could not be reached or returned an API error."""


@dataclass
class Reply:
    """Outcome of handling one utterance."""

    text: str | None                 # what to speak, if anything
    tools_called: list[str]          # tool names executed, in order


class BrainProtocol(Protocol):
    """Anything that can turn user text + a tool executor into a Reply.

    Implemented by `Brain` (real LLM) and `KeywordBrain` (offline rules).
    """

    def handle(self, user_text: str, execute: ToolExecutor) -> Reply: ...


class Brain:
    def __init__(self, cfg: LLMConfig, system_prompt: str) -> None:
        self._cfg = cfg
        self._client = OpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            timeout=cfg.request_timeout_s,
        )
        self._tools = openai_tools()
        self._history: list[dict] = [{"role": "system", "content": system_prompt}]
        log.info("Brain ready: provider=%s model=%s", cfg.provider, cfg.model)

    def handle(self, user_text: str, execute: ToolExecutor) -> Reply:
        """Run one user turn through the model, executing any tool calls.

        `execute(name, args)` performs the tool and returns a result string that
        is fed back so the model can confirm what happened.
        """
        self._history.append({"role": "user", "content": user_text})
        called: list[str] = []

        for _ in range(self._cfg.max_tool_iterations):
            message = self._complete()
            self._history.append(message)

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                text = message.get("content")
                self._trim_history()
                return Reply(text=text, tools_called=called)

            for call in tool_calls:
                name, args = _parse_call(call)
                if name not in TOOL_NAMES:
                    result = f"error: unknown tool {name!r}"
                    log.warning(result)
                else:
                    log.info("tool %s(%s)", name, args)
                    called.append(name)
                    result = execute(name, args)
                self._history.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        log.warning("Hit max_tool_iterations without a final reply")
        self._trim_history()
        return Reply(text=None, tools_called=called)

    # -- internal ------------------------------------------------------------
    def _complete(self) -> dict:
        try:
            resp = self._client.chat.completions.create(
                model=self._cfg.model,
                messages=self._history,
                tools=self._tools,
                temperature=self._cfg.temperature,
            )
        except APIConnectionError as exc:
            hint = ("cannot reach Ollama at "
                    f"{self._cfg.base_url} — is `ollama serve` running?") \
                if self._cfg.provider == "local" else "cannot reach the OpenAI API"
            raise LLMUnavailable(hint) from exc
        except APIError as exc:
            raise LLMUnavailable(f"{self._cfg.provider} API error: {exc}") from exc
        # Normalize to a plain dict we fully control (avoids SDK object quirks).
        msg = resp.choices[0].message
        out: dict = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            out["tool_calls"] = [{
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name,
                             "arguments": tc.function.arguments or "{}"},
            } for tc in msg.tool_calls]
        return out

    def _trim_history(self, keep: int = 20) -> None:
        """Bound context growth: keep the system prompt + the last `keep` turns."""
        if len(self._history) > keep * 2:
            self._history = [self._history[0]] + self._history[-keep:]


def _parse_call(call: dict) -> tuple[str, dict]:
    name = call["function"]["name"]
    raw = call["function"].get("arguments") or "{}"
    try:
        args = json.loads(raw)
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        log.warning("Bad tool arguments %r; using empty args", raw)
        args = {}
    return name, args
