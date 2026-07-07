#!/usr/bin/env python3
"""Phase 0 hardware check — run ON THE ROBOT'S JETSON, robot ON A HARNESS.

Verifies each piece the voice agent depends on, one step at a time (press Enter
between steps). Run this and get all green before running the voice agent.

    python3 check_hardware.py --iface eth0

Steps: DDS connect -> TTS -> volume -> LED -> built-in ASR -> (optional) wave.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from g1voice.config import RobotConfig


def _pause(msg: str) -> None:
    input(f"\n--- {msg}\n    (press Enter to run) ---")


def main() -> int:
    ap = argparse.ArgumentParser(description="G1 hardware smoke test")
    ap.add_argument("--iface", default="eth0", help="interface on 192.168.123.x")
    args = ap.parse_args()
    robot = RobotConfig(iface=args.iface)

    try:
        from unitree_sdk2py.core.channel import (ChannelFactoryInitialize,
                                                 ChannelSubscriber)
        from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
        from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
    except ImportError:
        print("unitree_sdk2py not installed. Install it on the Jetson first "
              "(see README). This script must run on the robot.")
        return 1

    print(f"[1/6] Initializing DDS on {robot.iface!r} ...")
    ChannelFactoryInitialize(robot.dds_domain, robot.iface)
    audio = AudioClient()
    audio.SetTimeout(robot.client_timeout_s)
    audio.Init()
    print("      OK — connected to the robot.")

    _pause("[2/6] TTS: the robot should say a test sentence")
    print("      TtsMaker returned:", audio.TtsMaker("Hardware check. Hello.",
                                                     robot.tts_speaker_id))

    _pause("[3/6] Volume: read, then set to 70")
    print("      current:", audio.GetVolume())
    audio.SetVolume(70)
    print("      now:", audio.GetVolume())

    _pause("[4/6] LED: head should cycle red -> green -> blue")
    for rgb in ((128, 0, 0), (0, 128, 0), (0, 0, 128)):
        audio.LedControl(*rgb)
        time.sleep(1)

    _pause("[5/6] ASR: speak to the robot for 10 seconds")
    heard: list[str] = []

    def on_asr(msg: String_) -> None:
        try:
            text = str(json.loads(msg.data).get("text", msg.data))
        except (ValueError, TypeError, AttributeError):
            text = str(msg.data)
        text = text.strip()
        if text:
            heard.append(text)
            print("      heard:", text)

    sub = ChannelSubscriber(robot.asr_topic, String_)
    sub.Init(on_asr, 10)
    time.sleep(10)
    if not heard:
        print("      WARNING: nothing recognized. Check the VUI service / "
              "firmware, or plan to use the mic-multicast path instead.")

    if input("\n[6/6] Run a WAVE gesture? Robot must be clear. [y/N] ").strip().lower() == "y":
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
        loco = LocoClient()
        loco.SetTimeout(robot.client_timeout_s)
        loco.Init()
        loco.WaveHand()
        print("      waved.")

    print("\nAll checks complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
