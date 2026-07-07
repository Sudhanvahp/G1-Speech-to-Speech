#!/usr/bin/env python3
"""Convenience entrypoint. Equivalent to `python -m g1voice`.

    python main.py --dry-run     # test on any PC (free, no robot)
    python main.py --iface eth0  # run on the robot
"""
import sys

from g1voice.cli import main

if __name__ == "__main__":
    sys.exit(main())
