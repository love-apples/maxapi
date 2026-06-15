#!/usr/bin/env python
"""Утилита для проверки chat_id для интеграционных тестов.

Использование:
    python tests/get_chat_id.py
"""

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


def main() -> None:
    """Проверяет наличие корректного TEST_CHAT_ID."""
    chat_id = os.environ.get("TEST_CHAT_ID")

    if chat_id is None:
        sys.exit(1)

    try:
        int(chat_id)
    except ValueError:
        sys.exit(1)


if __name__ == "__main__":
    main()
