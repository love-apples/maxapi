"""
Скачивает образцы файлов и сохраняет их фрагменты + ожидаемые метаданные
в fixtures.json для последующего тестирования.

Два режима работы:

1. Ручной (USE_AUTOMATIC_EXPECTED = False):
   - В SAMPLE_URLS нужно указать expected-поля вручную (format, width, ...)
   - Скрипт скачивает head/tail, дописывает mime_type, file_size из HTTP-ответа
   - Подходит для фиксации эталонных значений
   - Если expected не указаны — фикстура пропускается

2. Автоматический (USE_AUTOMATIC_EXPECTED = True):
   - В SAMPLE_URLS достаточно указать только url
   - Скрипт сам запускает FileInspector и получает все expected-поля
   - Подходит для быстрого добавления новых фикстур
   - Полученные значения нужно проверить вручную перед коммитом!

Файл содержит примеры SAMPLE_URLS. Отрредактировать для добавления новых.

Фикстуры не затираются полностью:
- Существующие в fixtures.json остаются нетронутыми
- Если имя совпадает — обновляется (перезаписывается)
- Новые добавляются
- Перед именованием проверить fixtures.json

Запуск:
    python prepare_fixtures.py                  # все из SAMPLE_URLS
    python prepare_fixtures.py mp4_vp9 mkv_h264 # только указанные
"""

import asyncio
import base64
import contextlib
import json
import logging
import sys
from pathlib import Path
from typing import cast

import aiohttp
from maxapi.utils.file_inspector import FileInspector

logger = logging.getLogger(__name__)
FIXTURES_FILE = Path(__file__).parent / "fixtures.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Если True — expected берутся из FileInspector автоматически.
# Внимание: полученные значения нужно проверять вручную!
USE_AUTOMATIC_EXPECTED = True


SAMPLE_URLS = {
    # Провеирть ключи. Совпадающие заменят данные, новые добавят.

    # Без expected — работает только в автоматическом режиме.
    # Формат, размеры и т.д. будут получены из FileInspector.
    "mp4_vp9": {
        "url": "https://samplelib.com/mp4/sample-10s-vp9.mp4",
    },

    # С expected — работает в обоих режимах.
    # В ручном режиме значения берутся отсюда.
    # В автоматическом — перезаписываются тем, что вернул FileInspector.
    "mkv_h264": {
        "url": "https://example.com/h264.mkv",
        "expected": {
            "width": 3840,
            "height": 2160,
            "duration": 19.0,
            "fps": 50.0,
            "sample_rate": 48000,
            "format": "MKV",
        },
        "head_size": 8192,
    },

    # Минимальный объём
    "png_transparency": {
        "url": (
            "https://upload.wikimedia.org/wikipedia/commons/4/47/"
            "PNG_transparency_demonstration_1.png"
        ),
        "expected": {"format": "PNG", "width": 800, "height": 600},
        "head_size": 2048,
    },

    # Локальный файл
    "mp3_id3_tag": {
        "file": "/path/to/local/mp3.mp3",
        "expected": {"format": "MP3", "duration": 160, "sample_rate": 44100, bit},
    },
}


async def download_head(
    session: aiohttp.ClientSession, url: str, size: int
) -> tuple[bytes, str, int | None]:
    """Скачивает начало файла. Возвращает (данные, content_type, file_size)."""
    async with session.get(url, headers=DEFAULT_HEADERS) as resp:
        content_type = resp.headers.get("Content-Type", "")
        file_size = None
        with contextlib.suppress(ValueError):
            file_size = int(resp.headers.get("Content-Length", "0")) or None

        data = b""
        while len(data) < size:
            chunk = await resp.content.read(size - len(data))
            if not chunk:
                break
            data += chunk
        return data, content_type, file_size


def read_local_head(filepath: str, size: int) -> tuple[bytes, str, int | None]:
    """Читает начало локального файла."""
    import mimetypes

    path = Path(filepath)
    content_type, _ = mimetypes.guess_type(filepath)
    file_size = path.stat().st_size
    with open(filepath, "rb") as f:  # noqa: PTH123
        head = f.read(size)
    return head, content_type or "application/octet-stream", file_size


def read_local_tail(filepath: str, size: int) -> bytes:
    """Читает конец локального файла."""
    with open(filepath, "rb") as f:  # noqa: PTH123
        f.seek(max(0, Path(filepath).stat().st_size - size))
        return f.read()


async def download_tail(
    session: aiohttp.ClientSession,
    url: str,
    size: int,
    head: bytes,
) -> bytes:
    """Скачивает конец файла через Range-запрос.
    Если сервер не поддерживает Range, возвращает b"".
    """
    headers = {**DEFAULT_HEADERS, "Range": f"bytes=-{size}"}
    async with session.get(url, headers=headers) as resp:
        if resp.status not in (200, 206):
            return b""
        data = b""
        while len(data) < size:
            chunk = await resp.content.read(size - len(data))
            if not chunk:
                break
            data += chunk

        # Проверяем, что сервер вернул хвост, а не весь файл
        if data[: len(head)] == head[: len(data)]:
            return b""
        return data


def _load_existing() -> dict:
    """Загружает существующие фикстуры из JSON."""
    if not FIXTURES_FILE.exists():
        return {}
    return json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))


async def get_expected(name, cfg, session) -> tuple[bytes, bytes]:
    if USE_AUTOMATIC_EXPECTED:
        logger.info(
            "Получаю expected для %s: %s",
            name,
            cfg.get("url") or cfg.get("file"),
        )

        inspector = FileInspector()
        if "file" in cfg:
            finfo = await inspector.inspect_file(cfg["file"])
        elif "url" in cfg:
            finfo = await inspector.inspect_url(cfg["url"], session=session)
        else:
            raise ValueError(
                "В параметрах не найдена ссылка на источник url или file"
            )
        head = inspector.last_head
        tail = inspector.last_tail
        expected = finfo.model_dump()
        cfg["expected"] = expected
        cfg["head_size"] = len(head)
        cfg["tail_size"] = len(tail)
        # Очистка данных
        for k in tuple(expected):
            if not expected[k]:
                del expected[k]
        del expected["file_name"]
        if (
            set(expected.keys()) == {"url", "mime_type", "file_size"}
            or len(expected) <= 3
        ):
            logger.warning(
                "Не достаточно данных в expected для %s: %s",
                name,
                expected,
            )
            cfg["expected"] = {}
            return b"", b""
        return head, tail
    return b"", b""


async def generate_fixture(name, cfg, session, head, tail) -> dict | None:
    logger.info("Скачиваю %s: %s", name, cfg.get("url") or cfg.get("file"))
    try:
        fixture = {}
        content_type = file_size = None
        if not cfg.get("expected"):
            # Если не указаны ожидания, пропускаем
            return None
        if not USE_AUTOMATIC_EXPECTED:
            if "url" in cfg:
                # Была создана вначале функции,
                # если есть хоть один url в списке
                session = cast(aiohttp.ClientSession, session)

                head, content_type, file_size = await download_head(
                    session, cfg["url"], cfg["head_size"]
                )
                tail = b""
                if cfg.get("tail_size"):
                    tail = await download_tail(
                        session, cfg["url"], cfg["tail_size"], head
                    )
            elif "file" in cfg:
                head, content_type, file_size = read_local_head(
                    cfg["file"], cfg.get("head_size", 65536)
                )
                if cfg.get("tail_size"):
                    tail = read_local_tail(cfg["file"], cfg["tail_size"])

            fixture.update(
                {
                    "mine_type": content_type,
                    "file_size": file_size,
                }
            )
        fixture.update(
            {
                "head_b64": base64.b64encode(head).decode(),
                "tail_b64": base64.b64encode(tail).decode(),
                **cfg["expected"],
                # Сохраним url в фикстуре для проверки параметров
                "url": cfg.get("url")
                or f"file://{Path(cfg.get('file')).name}",
            }
        )
        # Очистим от пустых значений
        for k in tuple(fixture):
            if not fixture[k]:
                del fixture[k]
        logger.info("  OK: head=%s, tail=%s", len(head), len(tail))
        return fixture

    except Exception as exc:
        logger.error("  FAIL: %s", exc)


async def main():
    names = sys.argv[1:] if len(sys.argv) > 1 else list(SAMPLE_URLS)
    fixtures = _load_existing()
    updated = False
    need_session = any(
        "url" in SAMPLE_URLS[name] for name in names if name in SAMPLE_URLS
    )
    session = aiohttp.ClientSession() if need_session else None
    try:
        for name in names:
            if name not in SAMPLE_URLS:
                logger.warning("Пропущено: %s", name)
                continue

            cfg = SAMPLE_URLS[name]

            head, tail = await get_expected(name, cfg, session)
            fixture = await generate_fixture(name, cfg, session, head, tail)
            if fixture:
                fixtures[name] = fixture
                updated = True
    finally:
        if session:
            await session.close()

    if updated:
        FIXTURES_FILE.write_text(
            json.dumps(fixtures, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Сохранено: %s", FIXTURES_FILE)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)-7s| %(message)s"
    )
    asyncio.run(main())
