"""Real motion skills — clamped wrappers over the Unitree G1 LocoClient.

Only high-level, factory-tested primitives are used (Move / StandUp / WaveHand
/ ShakeHand). The LLM never gets raw joint control, and every velocity and
duration is clamped by g1voice.skills.safety before reaching the robot.

Importing this module requires `unitree_sdk2py` (installed on the robot's
Jetson). For PC testing without the SDK, use skills.mock instead.
"""
from __future__ import annotations

import logging
import time

from ..config import RobotConfig, SafetyConfig
from . import safety

log = logging.getLogger(__name__)

_CONTROL_DT = 0.1  # seconds between velocity commands during a motion


class RealMotionSkills:
    """Implements the MotionSkills protocol against the physical robot.

    Note: constructing this initializes the shared DDS channel factory, so it
    must be created before any other Unitree client (SpeechSkills reuses it).
    """

    def __init__(self, robot: RobotConfig, safety_cfg: SafetyConfig) -> None:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

        self._cfg = safety_cfg
        log.info("Initializing DDS on interface %r ...", robot.iface)
        ChannelFactoryInitialize(robot.dds_domain, robot.iface)
        self._client = LocoClient()
        self._client.SetTimeout(robot.client_timeout_s)
        self._client.Init()
        log.info("LocoClient ready")

    # -- emergency -----------------------------------------------------------
    def stop(self) -> str:
        """Stop moving and go compliant (damp). Safe to call at any time."""
        try:
            self._client.StopMove()
        finally:
            self._client.Damp()
        return "Stopped."

    # -- postures ------------------------------------------------------------
    def stand_up(self) -> str:
        self._client.StandUp()
        time.sleep(1.0)
        self._client.BalanceStand()
        return "Standing."

    def sit_down(self) -> str:
        self._client.StopMove()
        self._client.Squat()
        return "Sitting down."

    # -- locomotion ----------------------------------------------------------
    def walk(self, vx: float = 0.3, seconds: float = 2.0) -> str:
        vx, seconds = safety.clamp_walk(vx, seconds, self._cfg)
        self._drive(vx, 0.0, 0.0, seconds)
        return f"Walked {'forward' if vx >= 0 else 'backward'} for {seconds:.1f}s."

    def turn(self, degrees: float = 45.0) -> str:
        yaw_rate, seconds = safety.turn_plan(degrees, self._cfg)
        self._drive(0.0, 0.0, yaw_rate, seconds)
        side = "left" if degrees >= 0 else "right"
        return f"Turned {abs(degrees):.0f} degrees {side}."

    # -- gestures ------------------------------------------------------------
    def wave(self) -> str:
        self._client.WaveHand()
        return "Waved."

    def shake_hand(self) -> str:
        self._client.ShakeHand()
        return "Offering a handshake."

    # -- internal ------------------------------------------------------------
    def _drive(self, vx: float, vy: float, vyaw: float, seconds: float) -> None:
        """Stream velocity commands for `seconds`, then stop. Any error stops."""
        end = time.monotonic() + seconds
        try:
            while time.monotonic() < end:
                self._client.Move(vx, vy, vyaw)
                time.sleep(_CONTROL_DT)
        finally:
            self._client.StopMove()
