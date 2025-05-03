#!/usr/bin/env python3
"""
Rawe Ceek Thrice - F1 Live Timing to Philips Hue Bridge

This application connects to the F1 live timing data stream and
controls Philips Hue lights based on the current race leader.
"""

from rawe_ceek_thrice.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
