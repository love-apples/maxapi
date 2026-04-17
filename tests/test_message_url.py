"""Тесты для свойства Message.url с объединённой логикой.

Того что приходит присылает API:
Только для постов в канале вида https://max.ru/c/{channel_name}/{seq_b64}

И генерированной ссылки для диалогов и групповых чатов:
https://max.ru/c/{chat_id}/{seq_b64}

"""

from maxapi.enums.chat_type import ChatType
from maxapi.types.message import Message, MessageBody, Recipient


class TestMessageUrlProperty:
    """Тесты для свойства url в модели Message."""

    def _make_recipient(self, chat_id: int | None = None,
                        user_id: int | None = None,
                        chat_type: ChatType = ChatType.DIALOG) -> Recipient:
        return Recipient(
            chat_id=chat_id,
            user_id=user_id,
            chat_type=chat_type,
        )

    def _make_body(self, mid: str, seq: int = 123,
                   text: str | None = "test") -> MessageBody:
        return MessageBody(
            mid=mid,
            seq=seq,
            text=text,
        )


    def test_url_from_api_channel_post(self):
        """URL из API для поста в канале — возвращается как есть."""
        api_url = "https://max.ru/c/news_channel/abc123"
        data = {
            "url": api_url,
            "recipient": {
                "chat_id": None,
                "user_id": None,
                "chat_type": "channel",
            },
            "timestamp": 1234567890,
            "body": {
                "mid": "mid.1234567890abcdef1234567890abcdef",
                "seq": 42,
                "text": "Channel post",
            },
        }
        msg = Message.model_validate(data)

        assert msg.url == api_url
        assert msg.url_api == api_url  # 🔹 было _url_storage
        dumped = msg.model_dump()
        assert dumped["url"] == api_url
        assert "url_api" not in dumped


    def test_url_generated_for_dialog(self):
        """Для диалога без url из API — ссылка генерируется из body.mid."""
        mid = "mid.000000000000006400000000000001c8"  # chat_id=100, seq=456

        data = {
            "recipient": {
                "chat_id": 100,
                "user_id": None,
                "chat_type": "dialog",
            },
            "timestamp": 1234567890,
            "body": {
                "mid": mid,
                "seq": 456,
                "text": "Hello",
            },
        }
        msg = Message.model_validate(data)

        assert msg.url is not None
        assert msg.url.startswith("https://max.ru/c/100/")
        assert msg.url_api is None
        assert msg.model_dump()["url"] is None


    def test_url_generated_for_group_chat(self):
        """Для группового чата без url из API — ссылка генерируется."""
        mid = "mid.00000000000000c800000000000003e8"  # chat_id=200, seq=1000

        data = {
            "recipient": {
                "chat_id": 200,
                "user_id": None,
                "chat_type": "chat",
            },
            "timestamp": 1234567890,
            "body": {
                "mid": mid,
                "seq": 1000,
                "text": "Chat group message",
            },
        }
        msg = Message.model_validate(data)

        assert msg.url is not None
        assert msg.url.startswith("https://max.ru/c/200/")
        assert msg.url_api is None
        assert msg.model_dump()["url"] is None

    def test_url_none_when_no_body(self):
        """Если нет body — url возвращает None."""
        data = {
            "recipient": {
                "chat_id": 300,
                "user_id": None,
                "chat_type": "dialog",
            },
            "timestamp": 1234567890,
        }
        msg = Message.model_validate(data)

        assert msg.url is None
        assert msg.url_api is None
        assert msg.model_dump()["url"] is None


    def test_url_none_when_no_body_but_url_from_api(self):
        """Если API прислал url, но нет body — возвращается url из API."""
        api_url = "https://max.ru/c/special_channel/xyz"
        data = {
            "url": api_url,
            "recipient": {
                "chat_id": None,
                "user_id": None,
                "chat_type": "channel",
            },
            "timestamp": 1234567890,
        }
        msg = Message.model_validate(data)

        assert msg.url == api_url
        assert msg.url_api == api_url
        assert msg.model_dump()["url"] == api_url

    def test_serialization_preserves_original_url(self):
        """Сериализация сохраняет оригинальный url, а не сгенерированный."""
        # Кейс 1: с url из API
        msg_with_url = Message.model_validate({
            "url": "https://max.ru/c/channel/original",
            "recipient": {"chat_id": None, "user_id": None, "chat_type": "channel"},
            "timestamp": 123,
            "body": {"mid": "mid.000000000000006400000000000001c8", "seq": 1},
        })
        dumped = msg_with_url.model_dump()
        assert dumped["url"] == "https://max.ru/c/channel/original"

        # Кейс 2: без url из API
        msg_no_url = Message.model_validate({
            "recipient": {"chat_id": 100, "user_id": None, "chat_type": "dialog"},
            "timestamp": 123,
            "body": {"mid": "mid.000000000000006400000000000001c8", "seq": 1},
        })
        dumped = msg_no_url.model_dump()
        assert dumped["url"] is None

    def test_url_property_priority(self):
        """url_api имеет приоритет над генерацией из body."""
        api_url = "https://max.ru/c/priority_test/abc"
        mid = "mid.000000000000006400000000000001c8"

        data = {
            "url": api_url,
            "recipient": {"chat_id": 100, "user_id": None, "chat_type": "dialog"},
            "timestamp": 123,
            "body": {"mid": mid, "seq": 1},
        }
        msg = Message.model_validate(data)

        assert msg.url == api_url  # Вернулся оригинал, а не сгенерированная ссылка
        assert msg.url_api == api_url

    def test_url_with_negative_chat_id(self):
        """Генерация ссылки работает с отрицательными chat_id (каналы)."""
        mid = "mid.fffffffffffffc18000000000000000a"  # chat_id=-1000, seq=10

        data = {
            "recipient": {"chat_id": -1000, "user_id": None, "chat_type": "channel"},
            "timestamp": 123,
            "body": {"mid": mid, "seq": 10},
        }
        msg = Message.model_validate(data)

        assert msg.url is not None
        assert "/-1000/" in msg.url

    def test_model_dump_json_includes_url(self):
        """model_dump(mode='json') также включает url с правильным значением."""
        msg = Message.model_validate({
            "url": "https://max.ru/c/test/json_test",
            "recipient": {"chat_id": None, "user_id": None, "chat_type": "channel"},
            "timestamp": 123,
            "body": {"mid": "mid.000000000000006400000000000001c8", "seq": 1},
        })

        dumped_json = msg.model_dump(mode="json")
        assert dumped_json["url"] == "https://max.ru/c/test/json_test"
