import re
import base64
from urllib.parse import urlparse


def mid_to_chatid_seq(mid: str) -> tuple[int, int]:
    """
    Декодирует строку mid в chat_id и seq.
    Формат mid: 'mid.' + 16 hex-символов (chat_id) + 16 hex-символов (seq)
    """
    if not isinstance(mid, str):
        raise TypeError('mid должен быть строкой')

    if not re.fullmatch(r'mid\.[0-9a-fA-F]{32}', mid):
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
    """
    if not isinstance(chat_id, int):
        raise TypeError('chat_id должен быть целым числом')
    if not isinstance(seq, int):
        raise TypeError('seq должен быть целым числом')

    if chat_id < -(1 << 63) or chat_id >= (1 << 63):
        raise ValueError('chat_id выходит за пределы знакового 64-битного диапазона')
    if seq < 0 or seq >= (1 << 64):
        raise ValueError('seq выходит за пределы беззнакового 64-битного диапазона')
    
    # Битовая маска гарантирует корректное hex-представление для signed int
    # (отрицательные числа автоматически преобразуются в two's complement)
    chat_id_hex = f"{chat_id & 0xFFFFFFFFFFFFFFFF:016x}"
    seq_hex = f"{seq:016x}"
    
    return f"mid.{chat_id_hex}{seq_hex}"


def build_message_link(mid: str) -> str:
    """
    Генерирует прямую ссылку на сообщение в интерфейсе MAX.
    Формат: https://max.ru/c/{chat_id}/{urlsafe_base64(seq_без_padding)}
    """

    chat_id, seq = mid_to_chatid_seq(mid) # Валидация происходит здесь
    
    # 1. Преобразуем seq в 8 байт (big-endian)
    seq_bytes = seq.to_bytes(8, byteorder="big")
    # 2. Кодируем в URL-safe Base64 и убираем символы дополнения '='
    seq_b64 = base64.urlsafe_b64encode(seq_bytes).decode("ascii").rstrip("=")
    
    return f"https://max.ru/c/{chat_id}/{seq_b64}"


def link_to_chatid_seq(link: str) -> tuple[int, int]:
    """
    Парсит ссылку на сообщение в интерфейсе MAX и извлекает chat_id и seq.
    Формат ссылки: https://max.ru/c/{chat_id}/{urlsafe_base64(seq_без_padding)}

    Не обрабатываются ссылки на публичные каналы вида https://max.ru/{channe_name}/{urlsafe_base64}
    Только приватные чаты и группы

    Returns:
        tuple[int, int]: (chat_id, seq)
    """
    # Валидация типа
    if not isinstance(link, str):
        raise TypeError('link должен быть строкой')
    
    parsed = urlparse(link)
    
    # Валидация схемы и домена
    if parsed.scheme != 'https':
        raise ValueError('Ссылка должна использовать https схему')
    if parsed.netloc != 'max.ru':
        raise ValueError('Ссылка должна указывать на домен max.ru')
    
    # Валидация пути: /c/{chat_id}/{seq_b64}
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) != 3 or path_parts[0] != 'c':
        raise ValueError('Неверный формат пути в ссылке. Ожидается: /c/{chat_id}/{seq_b64}')
    
    # Извлечение и валидация chat_id
    try:
        chat_id = int(path_parts[1])
    except ValueError:
        raise ValueError('chat_id в ссылке должен быть целым числом')
    
    if chat_id < -(1 << 63) or chat_id >= (1 << 63):
        raise ValueError('chat_id выходит за пределы знакового 64-битного диапазона')
    
    # Извлечение seq_b64
    seq_b64 = path_parts[2]
    
    if not seq_b64 or not re.fullmatch(r'[A-Za-z0-9_-]+', seq_b64):
        raise ValueError('seq в ссылке должен быть в url-safe base64 формате')
    
    # Добавляем паддинг для корректного декодирования base64
    # Длина base64 должна быть кратна 4
    padding_needed = (4 - len(seq_b64) % 4) % 4
    seq_b64_padded = seq_b64 + '=' * padding_needed
    
    try:
        # Декодируем из url-safe base64
        seq_bytes = base64.urlsafe_b64decode(seq_b64_padded)
    except Exception as e:
        raise ValueError(f'Ошибка декодирования base64: {e}')
    
    # Валидация длины: seq должен быть 8 байт (64 бита)
    if len(seq_bytes) != 8:
        raise ValueError('seq должен быть представлен 8 байтами (64 бита)')
    
    # Конвертируем байты в int (big-endian, unsigned)
    seq = int.from_bytes(seq_bytes, byteorder='big')
    
    return chat_id, seq
