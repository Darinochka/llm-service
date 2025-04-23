import asyncio
import sys
import os
from pathlib import Path

parent_dir = str(Path(__file__).parent.parent)
sys.path.append(parent_dir)

from app.telegram_bot import start_bot

if __name__ == "__main__":
    asyncio.run(start_bot()) 