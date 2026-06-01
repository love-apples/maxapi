"""
Ручная подача событий в Dispatcher без polling и webhook.

Подходит, когда события приходят из вашего транспорта: очереди, сокета,
теста, другого сервиса или уже существующего HTTP-приложения, но вы не хотите
запускать `dp.start_polling()` и не хотите регистрировать webhook в MAX.

Запуск:
    MAX_BOT_TOKEN=your_token python 13_manual_events_bot.py
"""

import asyncio
import contextlib
import json
from typing import Any, cast

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()

from maxapi import Bot, Dispatcher, F
from maxapi.enums.chat_type import ChatType
from maxapi.enums.update import UpdateType
from maxapi.methods.types.getted_updates import process_update_webhook
from maxapi.types.message import Message, MessageBody, Recipient
from maxapi.types.updates.message_created import MessageCreated
from maxapi.types.users import User
from maxapi.utils.updates import enrich_event


class ConsoleBot(Bot):
    """Бот для локальной демонстрации без запросов к API."""

    async def get_me(self) -> User:
        """Вернуть данные бота без сетевого запроса."""

        return User(
            user_id=123456789,
            first_name="Manual Bot",
            username="manual_bot",
            is_bot=True,
            last_activity_time=1700000000000,
        )

    async def send_message(self, *args: Any, **kwargs: Any) -> None:
        """Показать ответ handler в консоли вместо отправки в MAX."""

        text = kwargs.get("text") or (args[0] if args else "")
        print(f"Ответ handler: {text}")


bot = ConsoleBot(token="demo-token", auto_requests=False)
dp = Dispatcher()

MESSAGE_CREATED_JSON = """
{
  "update_type": "message_created",
  "timestamp": 1700000000000,
  "message": {
    "sender": {
      "user_id": 987654321,
      "first_name": "Manual",
      "last_name": "",
      "username": null,
      "is_bot": false,
      "last_activity_time": 1700000000000
    },
    "recipient": {
      "user_id": 123456789,
      "chat_id": 123456789,
      "chat_type": "dialog"
    },
    "timestamp": 1700000000000,
    "body": {
      "mid": "mid.example",
      "seq": 1,
      "text": "Привет без polling и webhook",
      "attachments": [],
      "markup": []
    }
  },
  "user_locale": "ru"
}
"""


@dp.message_created(F.message.body.text)
async def on_text(event: MessageCreated) -> None:
    text = event.message.body.text if event.message.body else ""

    # Это обычный handler maxapi. Источник события не важен:
    # polling, webhook или ручной вызов dp.handle(event).
    await event.message.answer(f"Получил событие вручную: {text}")


async def build_manual_message_event(
    *,
    chat_id: int,
    user_id: int,
    text: str,
) -> MessageCreated:
    event = MessageCreated(
        update_type=UpdateType.MESSAGE_CREATED,
        timestamp=1700000000000,
        bot=None,
        from_user=None,
        chat=None,
        message=Message(
            sender=User(
                user_id=user_id,
                first_name="Manual",
                last_name="",
                username=None,
                is_bot=False,
                last_activity_time=1700000000000,
            ),
            recipient=Recipient(
                user_id=user_id,
                chat_id=chat_id,
                chat_type=ChatType.DIALOG,
            ),
            timestamp=1700000000000,
            body=MessageBody(
                mid="mid.example",
                seq=1,
                text=text,
            ),
            bot=None,
        ),
        user_locale="ru",
    )

    return cast(MessageCreated, await enrich_event(event, bot))


async def build_manual_message_event_from_json_string() -> MessageCreated:
    """Собрать событие из обычной JSON-строки."""

    raw_event = json.loads(MESSAGE_CREATED_JSON)
    event = await process_update_webhook(raw_event, bot)
    if not isinstance(event, MessageCreated):
        msg = "В примере ожидается событие message_created"
        raise TypeError(msg)

    return cast(MessageCreated, event)


async def feed_event_from_your_code() -> None:
    # Вариант 1: собрать pydantic-модель вручную.
    # event = await build_manual_message_event(
    #     chat_id=123456789,
    #     user_id=987654321,
    #     text="Привет без polling и webhook",
    # )

    # Вариант 2: распарсить сырое событие MAX API из JSON-строки.
    event = await build_manual_message_event_from_json_string()

    await dp.handle(event)


async def main() -> None:
    # Подготавливает handlers, middleware, фильтры и привязывает bot
    # к dispatcher. ConsoleBot не делает реальных запросов к MAX.
    await dp.startup(bot)

    # Здесь вместо примера может быть чтение из очереди, websocket,
    # собственного API, тестового сценария и т.п.
    await feed_event_from_your_code()


if __name__ == "__main__":
    asyncio.run(main())
