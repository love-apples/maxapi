"""Тесты для свойства Message.url с объединённой логикой.

Проверяются два формата URL:

1. URL, полученный от API для постов в канале:
    https://max.ru/{channel_name}/{seq_b64}
2. URL, сгенерированный для диалогов и групповых чатов:
    https://max.ru/c/{chat_id}/{seq_b64}

"""

from maxapi.types.message import Message


class TestMessageUrlProperty:
    """Тесты для свойства url в модели Message."""

    def test_url_from_api_channel_post(self):
        """URL из API для поста в канале — возвращается как есть."""
        api_url = "https://max.ru/news_channel/AZ2H-TzaAOc"
        data = {
            "url": api_url,
            "recipient": {
                "chat_id": None,
                "user_id": None,
                "chat_type": "channel",
            },
            "timestamp": 1234567890,
            "body": {
                "mid": "mid.ffffbd3137103a3d019d87f93cda00e7",
                "seq": 116398669919027431,
                "text": "Channel post",
            },
        }
        msg = Message.model_validate(data)

        assert msg.url == api_url
        assert msg.url_api == api_url
        dumped = msg.model_dump()
        assert dumped["url"] == api_url
        assert "url_api" not in dumped

    def test_url_generated_for_dialog(self):
        """Для диалога без url из API — ссылка генерируется из body.mid."""
        data = {
            "recipient": {
                "chat_id": -73455901853123,
                "user_id": None,
                "chat_type": "dialog",
            },
            "timestamp": 1234567890,
            "body": {
                "mid": "mid.ffffbd3137103a3d019d87f93cda00e7",
                "seq": 116398669919027431,
                "text": "Hello",
            },
        }
        msg = Message.model_validate(data)

        assert msg.url == "https://max.ru/c/-73455901853123/AZ2H-TzaAOc"
        assert msg.url_api is None
        assert msg.model_dump()["url"] is None

    def test_url_generated_for_group_chat(self):
        """Для группового чата без url из API — ссылка генерируется."""
        data = {
            "recipient": {
                "chat_id": -71955698945289,
                "user_id": None,
                "chat_type": "chat",
            },
            "timestamp": 1234567890,
            "body": {
                "mid": "mid.ffffbe8e821ff2f7019d75dd00d34b7a",
                "seq": 116378757443570554,
                "text": "Chat group message",
            },
        }
        msg = Message.model_validate(data)

        assert msg.url == "https://max.ru/c/-71955698945289/AZ113QDTS3o"
        assert msg.url_api is None
        assert msg.model_dump()["url"] is None

    def test_url_none_when_no_body(self):
        """Если нет body — url возвращает None."""
        data = {
            "recipient": {
                "chat_id": 241387420,
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
        api_url = "https://max.ru/special_channel/AZ113QDTS3o"
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
        api_url = "https://max.ru/channel/AZ2H-TzaAOc"

        # Случай 1: с url из API
        msg_with_url = Message.model_validate(
            {
                "url": api_url,
                "recipient": {
                    "chat_id": None,
                    "user_id": None,
                    "chat_type": "channel",
                },
                "timestamp": 123,
                "body": {
                    "mid": "mid.ffffbd3137103a3d019d87f93cda00e7",
                    "seq": 116398669919027431,
                },
            }
        )
        dumped = msg_with_url.model_dump()
        assert dumped["url"] == api_url

        # Случай 2: без url из API
        msg_no_url = Message.model_validate(
            {
                "recipient": {
                    "chat_id": 241387420,
                    "user_id": None,
                    "chat_type": "dialog",
                },
                "timestamp": 123,
                "body": {
                    "mid": "mid.ffffbd3137103a3d019d87f93cda00e7",
                    "seq": 116398669919027431,
                },
            }
        )
        dumped = msg_no_url.model_dump()
        assert dumped["url"] is None

    def test_url_property_priority(self):
        """url_api имеет приоритет над генерацией из body."""
        api_url = "https://max.ru/priority_test/AZ2H-TzaAOc"
        data = {
            "url": api_url,
            "recipient": {
                "chat_id": 241387420,
                "user_id": None,
                "chat_type": "dialog",
            },
            "timestamp": 123,
            "body": {
                "mid": "mid.ffffbd3137103a3d019d87f93cda00e7",
                "seq": 116398669919027431,
            },
        }
        msg = Message.model_validate(data)

        assert msg.url == api_url
        assert msg.url_api == api_url

    def test_url_with_negative_chat_id(self):
        """Генерация ссылки работает с отрицательными chat_id (каналы)."""
        expected_url = "https://max.ru/c/-71955698945289/AZ113QDTS3o"

        data = {
            "recipient": {
                "chat_id": -71955698945289,
                "user_id": None,
                "chat_type": "channel",
            },
            "timestamp": 123,
            "body": {
                "mid": "mid.ffffbe8e821ff2f7019d75dd00d34b7a",
                "seq": 116378757443570554,
            },
        }
        msg = Message.model_validate(data)

        assert msg.url == expected_url

    def test_model_dump_json_includes_url(self):
        """model_dump(mode='json') включает url с правильным значением."""
        msg = Message.model_validate(
            {
                "url": "https://max.ru/test/AZ113QDTS3o",
                "recipient": {
                    "chat_id": None,
                    "user_id": None,
                    "chat_type": "channel",
                },
                "timestamp": 123,
                "body": {
                    "mid": "mid.ffffbe8e821ff2f7019d75dd00d34b7a",
                    "seq": 116378757443570554,
                },
            }
        )

        dumped_json = msg.model_dump(mode="json")
        assert dumped_json["url"] == "https://max.ru/test/AZ113QDTS3o"
