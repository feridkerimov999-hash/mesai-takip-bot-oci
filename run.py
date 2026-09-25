#!/usr/bin/env python3
import os
import sys
import asyncio

# Scriptin bulunduğu klasörü path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_main import main

if __name__ == "__main__":
    asyncio.run(main())
