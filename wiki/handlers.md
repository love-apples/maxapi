Для регистрации хендлера в maxapi используется объект `Dispatcher` или `Router` и декоратор с указанием типа события и фильтра.

## Общий синтаксис

```python
@dp.<тип_события>(<фильтры>)
async def <имя_функции>(event: <тип_события>):
    ...
```

* `dp` — экземпляр `Dispatcher`

* `<тип_события>` — тип события (например, `message_created`)

* `<фильтр>` — условие `MagicFilter`, по которому срабатывает хендлер (например, наличие текста в сообщении)

* `event` — объект события с данными (например, `MessageCreated`)

## Пример

```python
@dp.message_created(F.message.body.text)
async def echo(event: MessageCreated):
    await event.message.answer(f"Повторяю за вами: {event.message.body.text}")
```

* `@dp.message_created` — хендлер на событие создания сообщения

* `F.message.body.text` — фильтр: сработает только если в сообщении есть текст

* `echo` — асинхронная функция-обработчик, которая принимает событие `MessageCreated`

* В теле функции вызывается метод `answer` для отправки ответа с повтором текста


## Полный код

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.filters import F
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


@dp.message_created(F.message.body.text)
async def echo(event: MessageCreated):
    await event.message.answer(f"Повторяю за вами: {event.message.body.text}")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```