import re
import base64
from urllib.parse import urlparse
import binascii

def _validate_chat_id(chat_id: int) -> None:
    """Проверяет, что chat_id в диапазоне signed int64."""
    if chat_id < -(1 << 63) or chat_id >= (1 << 63):
        raise ValueError("chat_id выходит за пределы знакового 64-битного диапазона")

def mid_to_chatid_seq(mid: str) -> tuple[int, int]:
    """
    Декодирует строку mid в пару (chat_id, seq).

    Формат mid: "mid." + 32 hex-символа, где:
        - первые 16 символов: chat_id (signed int64, stored as unsigned hex)
        - последние 16 символов: seq (unsigned int64)

    Args:
        mid (str): Строка формата "mid.{32 hex символа}"

    Returns:
        tuple[int, int]: Кортеж (chat_id, seq), где chat_id — signed, seq — unsigned

    Raises:
        TypeError: Если mid не является строкой
        ValueError: Если mid не соответствует ожидаемому формату
    """
    if not isinstance(mid, str):
        raise TypeError("mid должен быть строкой")

    if not re.fullmatch(r"mid\.[0-9a-fA-F]{32}", mid):
        raise ValueError('mid должен быть в формате "mid." + 32 hex-символа')

    hex_part = mid[4:]

    # Первые 16 символов — chat_id. MAX хранит его как signed 64-bit,
    # но в hex он представлен как unsigned. Конвертируем обратно в signed.
    chat_id_unsigned = int(hex_part[:16], 16)
    chat_id = chat_id_unsigned - (1 << 64) if chat_id_unsigned >= (1 << 63) else chat_id_unsigned

    # Последние 16 символов — seq. Всегда положительное 64-bit число.
    seq = int(hex_part[16:], 16)

    return chat_id, seq


def chatid_seq_to_mid(chat_id: int, seq: int) -> str:
    """
    Создаёт валидную строку mid из chat_id и seq.

    Формат результата: "mid." + 32 hex-символа (16 для chat_id + 16 для seq)

    Args:
        chat_id (int): ID чата (signed int64, диапазон: -(2**63) .. 2**63-1)
        seq (int): Порядковый номер сообщения (unsigned int64, диапазон: 0 .. 2**64-1)

    Returns:
        str: Строка mid формата "mid.{32 hex символа}"

    Raises:
        TypeError: Если chat_id или seq не являются int
        ValueError: Если chat_id или seq выходят за допустимые диапазоны
    """
    if not isinstance(chat_id, int):
        raise TypeError("chat_id должен быть целым числом")
    if not isinstance(seq, int):
        raise TypeError("seq должен быть целым числом")

    _validate_chat_id(chat_id)
    if seq < 0 or seq >= (1 << 64):
        raise ValueError("seq выходит за пределы беззнакового 64-битного диапазона")

    # Битовая маска гарантирует корректное hex-представление для signed int
    # (отрицательные числа автоматически преобразуются в two"s complement)
    chat_id_hex = f"{chat_id & 0xFFFFFFFFFFFFFFFF:016x}"
    seq_hex = f"{seq:016x}"

    return f"mid.{chat_id_hex}{seq_hex}"


def build_message_link(mid: str) -> str:
    """
    Генерирует прямую ссылку на сообщение в интерфейсе MAX.

    Args:
        mid (str): Значение из message.body.mid

    Returns:
        str: URL ссылка на сообщение в интерфейсе пользовательского приложения MAX.
        Формат: https://max.ru/c/{chat_id}/{urlsafe_base64(seq_без_padding)}

    Raises:
        TypeError: Если mid не строка
        ValueError: Если mid не соответствует формату "mid." + 32 hex-символа
    """

    chat_id, seq = mid_to_chatid_seq(mid) # Валидация происходит здесь

    # 1. Преобразуем seq в 8 байт (big-endian)
    seq_bytes = seq.to_bytes(8, byteorder="big")
    # 2. Кодируем в URL-safe Base64 и убираем символы дополнения "="
    seq_b64 = base64.urlsafe_b64encode(seq_bytes).decode("ascii").rstrip("=")

    return f"https://max.ru/c/{chat_id}/{seq_b64}"


def link_to_chatid_seq(link: str) -> tuple[int, int]:
    """
    Парсит ссылку на сообщение в интерфейсе MAX и извлекает chat_id и seq.

    Не обрабатываются ссылки на публичные каналы вида https://max.ru/{channel_name}/{urlsafe_base64}
    Только приватные чаты и группы.

    Args:
        link (str): Ссылка формата https://max.ru/c/{chat_id}/{seq_b64}

    Returns:
        tuple[int, int]: (chat_id, seq)

    Raises:
        TypeError: Если link не строка
        ValueError: Если ссылка невалидна или ссылка на канал (chat_id не число)
    """
    # Валидация типа
    if not isinstance(link, str):
        raise TypeError("link должен быть строкой")

    parsed = urlparse(link)

    # Валидация схемы и домена
    if parsed.scheme != "https":
        raise ValueError("Ссылка должна использовать https схему")
    if parsed.netloc != "max.ru":
        raise ValueError("Ссылка должна указывать на домен max.ru")

    # Валидация пути: /c/{chat_id}/{seq_b64}
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) != 3 or path_parts[0] != "c":
        raise ValueError("Неверный формат пути в ссылке. Ожидается: /c/{chat_id}/{seq_b64}")

    # Извлечение и валидация chat_id
    try:
        chat_id = int(path_parts[1])
    except ValueError as e:
        raise ValueError("chat_id в ссылке должен быть целым числом") from e

    _validate_chat_id(chat_id)

    # Извлечение seq_b64
    seq_b64 = path_parts[2]

    if not seq_b64 or not re.fullmatch(r"[A-Za-z0-9_-]+", seq_b64):
        raise ValueError("seq в ссылке должен быть в url-safe base64 формате")

    # Добавляем паддинг для корректного декодирования base64
    # Длина base64 должна быть кратна 4
    padding_needed = (4 - len(seq_b64) % 4) % 4
    seq_b64_padded = seq_b64 + "=" * padding_needed

    try:
        # Декодируем из url-safe base64
        seq_bytes = base64.urlsafe_b64decode(seq_b64_padded)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Ошибка декодирования base64: {e}") from e

    # Валидация длины: seq должен быть 8 байт (64 бита)
    if len(seq_bytes) != 8:
        raise ValueError("seq должен быть представлен 8 байтами (64 бита)")

    # Конвертируем байты в int (big-endian, unsigned)
    seq = int.from_bytes(seq_bytes, byteorder="big")

    return chat_id, seq
