"""Command-line entrypoint: parse args, build the agent, run the chosen loop.

    python -m g1voice --dry-run            # test on any PC, no robot (free, local LLM)
    python -m g1voice                      # run on the robot (reads G1_* env vars)
    python -m g1voice --provider openai    # use the OpenAI cloud instead of Ollama

Run `python -m g1voice --help` for all options.
"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading

from .agent import VoiceAgent
from .config import ConfigError, Settings
from .logging_setup import setup_logging

log = logging.getLogger("g1voice")


# ------------------------------------------------------------- construction
def _build_brain(kind: str, settings: Settings) -> "BrainProtocol":
    """Construct the brain. 'hybrid' (default) = deterministic motion + LLM chat."""
    from .brain import BrainProtocol  # noqa: F401  (for type only)

    if kind == "keyword":
        from .fake_brain import KeywordBrain
        log.info("Brain: keyword (offline rules, no LLM)")
        return KeywordBrain()
    from .brain import Brain
    llm = Brain(settings.llm, settings.system_prompt)
    if kind == "llm":
        return llm
    from .hybrid_brain import HybridBrain  # default
    log.info("Brain: hybrid (deterministic motion + LLM conversation)")
    return HybridBrain(llm)


def _build_agent(settings: Settings, dry_run: bool, brain_kind: str) -> VoiceAgent:
    """Create a VoiceAgent with mock/real skills and the chosen brain."""
    if dry_run:
        from .skills.mock import MockMotionSkills, MockSpeechSkills
        motion = MockMotionSkills(settings.safety)
        speech = MockSpeechSkills()
        log.info("DRY RUN — mock robot; nothing will physically move")
    else:
        # Imported lazily so dry-run works without the Unitree SDK installed.
        from .skills.motion import RealMotionSkills
        from .skills.speech import RealSpeechSkills
        motion = RealMotionSkills(settings.robot, settings.safety)  # inits DDS
        speech = RealSpeechSkills(settings.robot)

    brain = _build_brain(brain_kind, settings)
    return VoiceAgent(settings, motion, speech, brain)


# --------------------------------------------------------------------- loops
def _run_interactive(agent: VoiceAgent) -> None:
    """Type utterances instead of speaking (used by --dry-run)."""
    print("\nType what you'd say to the robot. 'quit' to exit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"quit", "exit"}:
            break
        if text:
            agent.handle(text)


def _run_voice(agent: VoiceAgent, settings: Settings) -> None:
    """Listen to the robot's ASR and act on each utterance."""
    from . import asr

    utterances: "queue.Queue[str]" = queue.Queue()
    asr.start_asr_listener(settings.robot, utterances.put)
    agent.announce("Voice control ready.")
    log.info("Ready. Speak to the robot. Ctrl-C to stop.")
    try:
        while True:
            agent.handle(utterances.get())
    except KeyboardInterrupt:
        log.info("Shutting down")


# ----------------------------------------------------------------------- CLI
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="g1voice",
        description="Voice-commanded motion for the Unitree G1.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="run without a robot; type commands, see actions logged")
    p.add_argument("--brain", choices=["hybrid", "keyword", "llm"], default="hybrid",
                   help="hybrid (default): deterministic motion + LLM chat; "
                        "keyword: offline rules only (no LLM); "
                        "llm: model decides everything")
    p.add_argument("--fake-llm", action="store_true",
                   help="alias for --brain keyword (offline, no LLM needed)")
    p.add_argument("--provider", choices=["local", "openai"],
                   help="LLM provider (default: local/Ollama, or $G1_PROVIDER)")
    p.add_argument("--iface",
                   help="network interface to the robot, e.g. eth0 (or $G1_IFACE)")
    p.add_argument("--mode", choices=["asr", "realtime"], default="asr",
                   help="voice pipeline (default: asr). realtime is cloud-only")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return p.parse_args(argv)


def _apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """Fold CLI flags onto env-derived settings (CLI wins)."""
    import dataclasses

    llm = settings.llm
    if args.provider:
        llm = dataclasses.replace(llm, provider=args.provider)
    robot = settings.robot
    if args.iface:
        robot = dataclasses.replace(robot, iface=args.iface)
    return dataclasses.replace(settings, llm=llm, robot=robot)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    brain_kind = "keyword" if args.fake_llm else args.brain

    try:
        settings = _apply_overrides(Settings.from_env(), args)
        if brain_kind != "keyword":
            settings.llm.api_key  # validate credentials early (raises ConfigError)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    if args.mode == "realtime" and (brain_kind == "keyword"
                                    or settings.llm.provider != "openai"):
        log.error("realtime mode needs a cloud LLM (use --provider openai "
                  "and --brain llm/hybrid)")
        return 2

    agent = _build_agent(settings, dry_run=args.dry_run, brain_kind=brain_kind)

    if args.dry_run:
        _run_interactive(agent)
    elif args.mode == "realtime":
        from .realtime import run_realtime
        run_realtime(agent, settings)
    else:
        _run_voice(agent, settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
