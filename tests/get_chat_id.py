#!/usr/bin/env python
"""Утилита для получения chat_id для тестов.

Использование:
    python tests/get_chat_id.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Загружаем .env
try:
    from dotenv import load_dotenv

    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    sys.exit(1)

# Core Stuff
from maxapi import Bot


async def main():
    """Получает список чатов."""
    token = os.environ.get("MAX_BOT_TOKEN")

    if not token:
        sys.exit(1)

    bot = Bot(token=token)

    try:
        chats = await bot.get_chats(count=10)

        if not chats.chats or len(chats.chats) == 0:
            return

    except Exception:
        sys.exit(1)
    finally:
        await bot.close_session()


if __name__ == "__main__":
    asyncio.run(main())
