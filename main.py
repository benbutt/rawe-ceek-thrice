#!/usr/bin/env python3
"""
Rawe Ceek Thrice - F1 Live Timing to Philips Hue Bridge

This application connects to the F1 live timing data stream and
controls Philips Hue lights based on the current race leader.
"""

import asyncio

from rawe_ceek_thrice.main import main

if __name__ == "__main__":
    asyncio.run(main())
