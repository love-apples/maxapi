#!/usr/bin/env python
"""Скрипт для проверки загрузки переменных окружения."""

import os
import sys
from pathlib import Path

# Добавляем путь к conftest
sys.path.insert(0, str(Path(__file__).parent.parent))

# Имитируем загрузку как в conftest.py
try:
    from dotenv import load_dotenv

    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    tests_env = Path(__file__).parent / ".env"

    if env_file.exists():
        load_dotenv(env_file, override=True)
    elif tests_env.exists():
        load_dotenv(tests_env, override=True)
    else:
        load_dotenv(override=True)

    token = os.getenv("MAX_BOT_TOKEN")

    if not token:
        sys.exit(1)

except ImportError:
    sys.exit(1)
