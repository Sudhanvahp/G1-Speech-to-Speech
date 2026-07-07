"""Configuration: typed, validated, and overridable from environment variables.

All tunables live here. Nothing else in the package reads os.environ, so this
module is the single source of truth for how the agent is configured.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

Provider = Literal["local", "openai"]


# --------------------------------------------------------------------- LLM
@dataclass(frozen=True)
class LLMConfig:
    """Which language model answers, and how to reach it.

    `local` uses Ollama (free, offline, OpenAI-compatible API). `openai` uses
    the OpenAI cloud and requires OPENAI_API_KEY.
    """

    provider: Provider = "local"
    # Local (Ollama). qwen2.5:3b handles the conversation path better than
    # llama3.2 at the same size; motion never depends on the model (see HybridBrain).
    local_model: str = "qwen2.5:3b"
    local_base_url: str = "http://localhost:11434/v1"
    # Cloud (OpenAI)
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    # Shared
    request_timeout_s: float = 30.0
    max_tool_iterations: int = 4  # safety cap on the tool-calling loop
    temperature: float = 0.2      # low = consistent, obedient tool selection

    @property
    def model(self) -> str:
        return self.local_model if self.provider == "local" else self.openai_model

    @property
    def base_url(self) -> str | None:
        return self.local_base_url if self.provider == "local" else None

    @property
    def api_key(self) -> str:
        # Ollama ignores the value but the OpenAI client requires a non-empty one.
        if self.provider == "local":
            return "ollama"
        if not self.openai_api_key:
            raise ConfigError(
                "provider=openai but OPENAI_API_KEY is not set. "
                "Set it, or use the free local provider (--local / G1_PROVIDER=local)."
            )
        return self.openai_api_key


# ------------------------------------------------------------------ safety
@dataclass(frozen=True)
class SafetyConfig:
    """Hard limits applied to every motion command, regardless of the LLM."""

    max_vx: float = 0.4          # m/s forward/back
    max_vy: float = 0.2          # m/s lateral
    max_vyaw: float = 0.5        # rad/s
    max_walk_seconds: float = 3.0
    min_walk_seconds: float = 0.2
    # Heard anywhere in an utterance, these stop the robot WITHOUT calling the LLM.
    stop_words: frozenset[str] = frozenset(
        {"stop", "freeze", "halt", "emergency"}
    )
    # If set, the robot ignores utterances that don't contain this phrase.
    wake_word: str | None = None


# ------------------------------------------------------------------- robot
@dataclass(frozen=True)
class RobotConfig:
    """Robot network + audio topics. Defaults match a stock G1."""

    iface: str = "eth0"          # network interface on the 192.168.123.x net
    dds_domain: int = 0
    client_timeout_s: float = 10.0
    asr_topic: str = "rt/audio_msg"
    tts_speaker_id: int = 1      # 0 = Chinese voice, 1 = English
    # Raw microphone multicast feed (realtime mode only)
    mic_multicast_group: str = "239.168.123.161"
    mic_multicast_port: int = 5555
    self_ip: str = "192.168.123.164"  # this machine's IP on the robot net


# ------------------------------------------------------------------ prompt
SYSTEM_PROMPT = (
    "You are the voice of a Unitree G1 humanoid robot. You control the body ONLY "
    "through the provided motion tools.\n"
    "RULES:\n"
    "1. If the user asks for any movement, CALL the matching tool immediately. Do "
    "NOT ask follow-up questions and do NOT ask for numbers — pick sensible "
    "defaults (walk ~2s, turn 90 degrees) and just do it.\n"
    "2. 'forward'/'steps'/'come here' = walk with positive vx; 'back'/'backward' = "
    "negative vx. 'left' = turn positive degrees; 'right' = negative degrees.\n"
    "3. Only call a tool when the user actually wants to move. For questions like "
    "'what can you do', answer in words and call NO tool.\n"
    "4. Reply in ONE short, friendly sentence (max 15 words). Never mention tool "
    "names, arguments, or that you are an AI.\n"
    "5. Refuse unsafe requests (running, jumping, stairs, hitting, carrying people) "
    "in one sentence and call no tool."
)


# --------------------------------------------------------------- top-level
@dataclass(frozen=True)
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    robot: RobotConfig = field(default_factory=RobotConfig)
    system_prompt: str = SYSTEM_PROMPT

    @staticmethod
    def from_env() -> "Settings":
        """Build settings from environment variables with sane defaults.

        Recognized variables:
          G1_PROVIDER          local | openai            (default: local)
          OPENAI_API_KEY       required if provider=openai
          G1_LOCAL_MODEL       Ollama model             (default: llama3.2)
          G1_OLLAMA_URL        Ollama base URL
          G1_OPENAI_MODEL      OpenAI model             (default: gpt-4o-mini)
          G1_IFACE             network interface        (default: eth0)
          G1_WAKE_WORD         optional wake phrase
        """
        provider = _env_choice("G1_PROVIDER", ("local", "openai"), "local")
        llm = LLMConfig(
            provider=provider,  # type: ignore[arg-type]
            local_model=os.getenv("G1_LOCAL_MODEL", LLMConfig.local_model),
            local_base_url=os.getenv("G1_OLLAMA_URL", LLMConfig.local_base_url),
            openai_model=os.getenv("G1_OPENAI_MODEL", LLMConfig.openai_model),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        safety = SafetyConfig(
            wake_word=(os.getenv("G1_WAKE_WORD") or None),
        )
        robot = RobotConfig(
            iface=os.getenv("G1_IFACE", RobotConfig.iface),
        )
        return Settings(llm=llm, safety=safety, robot=robot)


class ConfigError(RuntimeError):
    """Raised when configuration is invalid or incomplete."""


def _env_choice(name: str, allowed: tuple[str, ...], default: str) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise ConfigError(
            f"{name}={value!r} is invalid; expected one of {allowed}."
        )
    return value
