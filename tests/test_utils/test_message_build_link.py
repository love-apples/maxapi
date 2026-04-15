import pytest
import base64
from maxapi.utils.message import (
    mid_to_chatid_seq,
    chatid_seq_to_mid,
    build_message_link,
    link_to_chatid_seq,
)

# =============================================================================
# Реальные тестовые данные из продакшена
# =============================================================================
REAL_TEST_CASES = [
    # Положительный chat_id
    {
        "chat_id": 191387420,
        "mid": "mid.000000000b68571c019d5eac630d58ce",
        "seq": 116353259870705870,
        "link": None,  # ссылка не предоставлена, сгенерируем в тесте
    },
    {
        "chat_id": 191387420,
        "mid": "mid.000000000b68571c019d5eaa646c000f",
        "seq": 116353251303751695,
        "link": None,
    },
    # Отрицательный chat_id с готовой ссылкой
    {
        "chat_id": -73455901853123,
        "mid": "mid.ffffbd3137103a3d019d87f93cda00e7",
        "seq": 116398669919027431,
        "link": "https://max.ru/c/-73455901853123/AZ2H-TzaAOc",
    },
    {
        "chat_id": -71955698945289,
        "mid": "mid.ffffbe8e821ff2f7019d75dd00d34b7a",
        "seq": 116378757443570554,
        "link": "https://max.ru/c/-71955698945289/AZ113QDTS3o",
    },
]


# =============================================================================
# Тесты на реальных данных
# =============================================================================
class TestRealData:
    """Тесты на реальных примерах из продакшена"""

    @pytest.mark.parametrize("case", REAL_TEST_CASES)
    def test_mid_to_chatid_seq_real(self, case):
        """Декодирование mid -> (chat_id, seq)"""
        chat_id, seq = mid_to_chatid_seq(case["mid"])
        assert chat_id == case["chat_id"]
        assert seq == case["seq"]

    @pytest.mark.parametrize("case", REAL_TEST_CASES)
    def test_chatid_seq_to_mid_real(self, case):
        """Кодирование (chat_id, seq) -> mid"""
        mid = chatid_seq_to_mid(case["chat_id"], case["seq"])
        assert mid == case["mid"]

    @pytest.mark.parametrize("case", REAL_TEST_CASES)
    def test_roundtrip_mid(self, case):
        """Круговое преобразование: mid -> (chat_id, seq) -> mid"""
        chat_id, seq = mid_to_chatid_seq(case["mid"])
        mid_restored = chatid_seq_to_mid(chat_id, seq)
        assert mid_restored == case["mid"]

    @pytest.mark.parametrize("case", REAL_TEST_CASES)
    def test_roundtrip_chatid_seq(self, case):
        """Круговое преобразование: (chat_id, seq) -> mid -> (chat_id, seq)"""
        mid = chatid_seq_to_mid(case["chat_id"], case["seq"])
        chat_id_restored, seq_restored = mid_to_chatid_seq(mid)
        assert chat_id_restored == case["chat_id"]
        assert seq_restored == case["seq"]

    @pytest.mark.parametrize("case", [c for c in REAL_TEST_CASES if c["link"]])
    def test_build_message_link_real(self, case):
        """Генерация ссылки из mid"""
        link = build_message_link(case["mid"])
        assert link == case["link"]

    @pytest.mark.parametrize("case", [c for c in REAL_TEST_CASES if c["link"]])
    def test_link_to_chatid_seq_real(self, case):
        """Парсинг ссылки -> (chat_id, seq)"""
        chat_id, seq = link_to_chatid_seq(case["link"])
        assert chat_id == case["chat_id"]
        assert seq == case["seq"]

    @pytest.mark.parametrize("case", [c for c in REAL_TEST_CASES if c["link"]])
    def test_roundtrip_link(self, case):
        """Круговое преобразование: link -> (chat_id, seq) -> link"""
        chat_id, seq = link_to_chatid_seq(case["link"])
        mid = chatid_seq_to_mid(chat_id, seq)
        link_restored = build_message_link(mid)
        assert link_restored == case["link"]

    @pytest.mark.parametrize("case", REAL_TEST_CASES)
    def test_full_pipeline(self, case):
        """Полный пайплайн: (chat_id, seq) -> mid -> link -> (chat_id, seq)"""
        mid = chatid_seq_to_mid(case["chat_id"], case["seq"])
        link = build_message_link(mid)
        chat_id_parsed, seq_parsed = link_to_chatid_seq(link)
        
        assert chat_id_parsed == case["chat_id"]
        assert seq_parsed == case["seq"]
        
        # Дополнительно: если была исходная ссылка, проверяем совпадение
        if case["link"]:
            assert link == case["link"]


# =============================================================================
# Тесты на граничные значения
# =============================================================================
class TestEdgeCases:
    """Тесты на граничные значения 64-битных чисел"""

    def test_chat_id_min_signed(self):
        """Минимальное значение signed int64: -2^63"""
        chat_id = -(1 << 63)
        seq = 0
        mid = chatid_seq_to_mid(chat_id, seq)
        chat_id_restored, seq_restored = mid_to_chatid_seq(mid)
        assert chat_id_restored == chat_id
        assert seq_restored == seq

    def test_chat_id_max_signed(self):
        """Максимальное значение signed int64: 2^63 - 1"""
        chat_id = (1 << 63) - 1
        seq = (1 << 64) - 1  # max unsigned seq
        mid = chatid_seq_to_mid(chat_id, seq)
        chat_id_restored, seq_restored = mid_to_chatid_seq(mid)
        assert chat_id_restored == chat_id
        assert seq_restored == seq

    def test_seq_zero(self):
        """seq = 0"""
        chat_id = 0
        seq = 0
        mid = chatid_seq_to_mid(chat_id, seq)
        assert mid == "mid.00000000000000000000000000000000"
        chat_id_restored, seq_restored = mid_to_chatid_seq(mid)
        assert chat_id_restored == 0
        assert seq_restored == 0

    def test_seq_max_unsigned(self):
        """seq = 2^64 - 1 (максимальное unsigned 64-bit)"""
        chat_id = 0
        seq = (1 << 64) - 1
        mid = chatid_seq_to_mid(chat_id, seq)
        assert mid == "mid.0000000000000000ffffffffffffffff"
        chat_id_restored, seq_restored = mid_to_chatid_seq(mid)
        assert seq_restored == seq

    def test_negative_chat_id_hex_representation(self):
        """Проверка two's complement для отрицательных chat_id"""
        # -1 в two's complement 64-bit = 0xFFFFFFFFFFFFFFFF
        chat_id = -1
        seq = 0
        mid = chatid_seq_to_mid(chat_id, seq)
        assert mid == "mid.ffffffffffffffff0000000000000000"
        chat_id_restored, _ = mid_to_chatid_seq(mid)
        assert chat_id_restored == -1


# =============================================================================
# Тесты на ошибки валидации
# =============================================================================
class TestValidationErrors:
    """Тесты на корректную обработку невалидных входных данных"""

    # ------------------ mid_to_chatid_seq ------------------
    def test_mid_wrong_type(self):
        with pytest.raises(TypeError, match="mid должен быть строкой"):
            mid_to_chatid_seq(12345)

    def test_mid_missing_prefix(self):
        with pytest.raises(ValueError, match='mid должен начинаться с "mid."'):
            mid_to_chatid_seq("000000000b68571c019d5eac630d58ce")

    def test_mid_wrong_length_short(self):
        with pytest.raises(ValueError, match="длина hex значения mid должна быть 32 символа"):
            mid_to_chatid_seq("mid.000000000b68571c")

    def test_mid_wrong_length_long(self):
        with pytest.raises(ValueError, match="длина hex значения mid должна быть 32 символа"):
            mid_to_chatid_seq("mid.000000000b68571c019d5eac630d58ce00")

    def test_mid_invalid_hex_chars(self):
        with pytest.raises(ValueError, match="должно быть в hex-формате"):
            mid_to_chatid_seq("mid.000000000b68571g019d5eac630d58ce")  # 'g' не hex

    # ------------------ chatid_seq_to_mid ------------------
    def test_chatid_wrong_type(self):
        with pytest.raises(TypeError, match="chat_id должен быть целым числом"):
            chatid_seq_to_mid("123", 100)

    def test_seq_wrong_type(self):
        with pytest.raises(TypeError, match="seq должен быть целым числом"):
            chatid_seq_to_mid(123, "100")

    def test_chat_id_out_of_range_low(self):
        with pytest.raises(ValueError, match="chat_id выходит за пределы"):
            chatid_seq_to_mid(-(1 << 63) - 1, 0)

    def test_chat_id_out_of_range_high(self):
        with pytest.raises(ValueError, match="chat_id выходит за пределы"):
            chatid_seq_to_mid(1 << 63, 0)

    def test_seq_negative(self):
        with pytest.raises(ValueError, match="seq выходит за пределы"):
            chatid_seq_to_mid(0, -1)

    def test_seq_out_of_range(self):
        with pytest.raises(ValueError, match="seq выходит за пределы"):
            chatid_seq_to_mid(0, 1 << 64)

    # ------------------ build_message_link ------------------
    def test_link_wrong_mid_prefix(self):
        with pytest.raises(ValueError, match='mid должен начинаться с "mid."'):
            build_message_link("invalid.000000000b68571c019d5eac630d58ce")

    def test_link_wrong_mid_format(self):
        with pytest.raises(ValueError, match="должно быть в hex-формате"):
            build_message_link("mid.000000000b68571g019d5eac630d58ce")

    def test_link_wrong_mid_length(self):
        with pytest.raises(ValueError, match="длина hex значения mid должна быть 32 символа"):
            build_message_link("mid.0000")

    # ------------------ link_to_chatid_seq ------------------
    def test_link_wrong_type(self):
        with pytest.raises(TypeError, match="link должен быть строкой"):
            link_to_chatid_seq(12345)

    def test_link_wrong_scheme(self):
        with pytest.raises(ValueError, match="Ссылка должна использовать http или https схему"):
            link_to_chatid_seq("ftp://max.ru/c/123/ABC")

    def test_link_wrong_domain(self):
        with pytest.raises(ValueError, match="Ссылка должна указывать на домен max.ru"):
            link_to_chatid_seq("https://example.com/c/123/ABC")

    def test_link_wrong_path_format(self):
        with pytest.raises(ValueError, match="Неверный формат пути"):
            link_to_chatid_seq("https://max.ru/chat/123/ABC")

    def test_link_wrong_path_parts_count(self):
        with pytest.raises(ValueError, match="Неверный формат пути"):
            link_to_chatid_seq("https://max.ru/c/123")  # нет seq

    def test_link_chat_id_not_int(self):
        with pytest.raises(ValueError, match="chat_id в ссылке должен быть целым числом"):
            link_to_chatid_seq("https://max.ru/c/abc/ABC")

    def test_link_invalid_base64_chars(self):
        with pytest.raises(ValueError, match="должен быть в url-safe base64 формате"):
            link_to_chatid_seq("https://max.ru/c/123/ABC@#$")

    def test_link_base64_decode_error(self):
        # Некорректный base64 (невозможно декодировать)
        with pytest.raises(ValueError, match="Ошибка декодирования base64"):
            link_to_chatid_seq("https://max.ru/c/123/!!!")

    def test_link_seq_wrong_byte_length(self):
        # Base64, который декодируется не в 8 байт
        # "AQ" -> 1 байт после декодирования
        with pytest.raises(ValueError, match="seq должен быть представлен 8 байтами"):
            link_to_chatid_seq("https://max.ru/c/123/AQ")


# =============================================================================
# Тесты на генерацию ссылок (build_message_link)
# =============================================================================
class TestBuildMessageLink:
    """Тесты функции build_message_link"""

    def test_link_format_positive_chat(self):
        """Проверка формата ссылки для положительного chat_id"""
        mid = "mid.000000000b68571c019d5eac630d58ce"
        link = build_message_link(mid)
        assert link.startswith("https://max.ru/c/")
        assert "191387420" in link  # chat_id в ссылке

    def test_link_format_negative_chat(self):
        """Проверка формата ссылки для отрицательного chat_id"""
        mid = "mid.ffffbd3137103a3d019d87f93cda00e7"
        link = build_message_link(mid)
        assert link.startswith("https://max.ru/c/-")
        assert "-73455901853123" in link

    def test_link_seq_base64_urlsafe_no_padding(self):
        """seq в ссылке должен быть url-safe base64 без паддинга"""
        mid = "mid.00000000000000000000000000000001"  # seq = 1
        link = build_message_link(mid)
        seq_part = link.split("/")[-1]
        assert "=" not in seq_part  # нет паддинга
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in seq_part)

    def test_link_seq_decoding_consistency(self):
        """Декодирование seq из ссылки должно давать исходное значение"""
        test_cases = [
            (0, "AAAAAAAAAAA"),      # 0 -> 8 нулевых байт
            (1, "AAAAAAAAAAE"),      # 1 -> 7 нулей + 0x01
            (255, "AAAAAAAAAAP"),    # 255 -> 7 нулей + 0xFF
            (116353259870705870, "AZ1erGMNWM4"),  # из реальных данных
        ]
        for seq, expected_b64_prefix in test_cases:
            mid = chatid_seq_to_mid(12345, seq)
            link = build_message_link(mid)
            seq_from_link = link.split("/")[-1]
            # Проверяем, что декодирование даёт исходный seq
            padding = (4 - len(seq_from_link) % 4) % 4
            decoded = base64.urlsafe_b64decode(seq_from_link + "=" * padding)
            assert int.from_bytes(decoded, "big") == seq


# =============================================================================
# Параметризованные тесты для покрытия различных сценариев
# =============================================================================
@pytest.mark.parametrize("chat_id,seq", [
    (0, 0),
    (1, 1),
    (-1, 1),
    (999999999, 999999999),
    (-999999999, 999999999),
    (2**62, 2**63),  # большие значения в пределах диапазона
    (-(2**62), 2**63 - 1),
])
def test_parametrized_roundtrip(chat_id: int, seq: int):
    """Параметризованный тест кругового преобразования"""
    mid = chatid_seq_to_mid(chat_id, seq)
    chat_id_restored, seq_restored = mid_to_chatid_seq(mid)
    assert chat_id_restored == chat_id
    assert seq_restored == seq
    
    link = build_message_link(mid)
    chat_id_from_link, seq_from_link = link_to_chatid_seq(link)
    assert chat_id_from_link == chat_id
    assert seq_from_link == seq
