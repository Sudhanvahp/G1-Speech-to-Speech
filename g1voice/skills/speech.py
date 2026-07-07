"""Real speech skills — TTS, speaker playback, and LED feedback via AudioClient.

Requires that the DDS channel factory is already initialized (RealMotionSkills
does this in its constructor). Requires `unitree_sdk2py`.
"""
from __future__ import annotations

import logging

from ..config import RobotConfig
from .base import LED_COLORS, AgentState

log = logging.getLogger(__name__)

_PLAY_APP = "g1voice"  # PlayStream application id


class RealSpeechSkills:
    """Implements the SpeechSkills protocol against the physical robot."""

    def __init__(self, robot: RobotConfig) -> None:
        from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

        self._speaker_id = robot.tts_speaker_id
        self._client = AudioClient()
        self._client.SetTimeout(robot.client_timeout_s)
        self._client.Init()
        log.info("AudioClient ready")

    def say(self, text: str) -> None:
        if not text:
            return
        self.set_state("speaking")
        try:
            self._client.TtsMaker(text, self._speaker_id)
        except Exception:  # speech must never crash the agent
            log.exception("TTS failed for %r", text)
        finally:
            self.set_state("idle")

    def set_volume(self, percent: int) -> None:
        self._client.SetVolume(max(0, min(100, percent)))

    def set_state(self, state: AgentState) -> None:
        r, g, b = LED_COLORS.get(state, LED_COLORS["idle"])
        try:
            self._client.LedControl(r, g, b)
        except Exception:  # LED feedback is best-effort
            log.debug("LED control failed", exc_info=True)

    def play_pcm(self, pcm_bytes: bytes) -> None:
        """Play raw 16 kHz mono s16le PCM (realtime mode)."""
        self._client.PlayStream(_PLAY_APP, "agent", pcm_bytes)

    def play_stop(self) -> None:
        self._client.PlayStop(_PLAY_APP)
