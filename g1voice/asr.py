"""Speech input from the G1's built-in ASR (Automatic Speech Recognition).

The robot's VUI service publishes recognized text on a DDS topic; we subscribe
and hand each utterance to a callback. Requires `unitree_sdk2py`.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from .config import RobotConfig

log = logging.getLogger(__name__)

Utterance = Callable[[str], None]


def _extract_text(raw: object) -> str:
    """Pull the recognized text out of an ASR message payload.

    The payload is usually JSON like {"text": "...", "index": N} but firmware
    versions vary, so fall back to the raw string.
    """
    try:
        return str(json.loads(raw).get("text", "")).strip()  # type: ignore[arg-type]
    except (ValueError, TypeError, AttributeError):
        return str(raw).strip()


def start_asr_listener(robot: RobotConfig, on_utterance: Utterance) -> None:
    """Subscribe to the ASR topic. Non-blocking; callbacks fire on a DDS thread.

    The DDS channel factory must already be initialized (RealMotionSkills does
    this). Call this once; the subscription lives for the process lifetime.
    """
    from unitree_sdk2py.core.channel import ChannelSubscriber
    from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_

    def _handler(msg: String_) -> None:
        text = _extract_text(msg.data)
        if text:
            on_utterance(text)

    subscriber = ChannelSubscriber(robot.asr_topic, String_)
    subscriber.Init(_handler, 10)
    log.info("Listening for speech on DDS topic %r", robot.asr_topic)
