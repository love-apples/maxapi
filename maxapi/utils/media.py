"""Утилиты для определения типа медиафайлов."""

from __future__ import annotations

from typing import Optional

import puremagic

from ..enums.upload_type import UploadType


def detect_upload_type_from_bytes(data: bytes) -> UploadType:
    """Определяет тип файла по содержимому (magic bytes).

    Args:
        data: Байты файла (достаточно первых 4096).

    Returns:
        UploadType: Тип файла (VIDEO, IMAGE, AUDIO или FILE).
    """

    mime_type = _detect_mime(data)

    if mime_type is None:
        return UploadType.FILE

    if mime_type.startswith("video/"):
        return UploadType.VIDEO
    elif mime_type.startswith("image/"):
        return UploadType.IMAGE
    elif mime_type.startswith("audio/"):
        return UploadType.AUDIO
    else:
        return UploadType.FILE


def _detect_mime(data: bytes) -> Optional[str]:
    """Определяет MIME-тип по байтам.

    Args:
        data: Байты для анализа.

    Returns:
        Optional[str]: MIME-тип или None.
    """

    try:
        matches = puremagic.magic_string(data)
        if matches:
            return matches[0].mime_type
    except Exception:
        pass
    return None
