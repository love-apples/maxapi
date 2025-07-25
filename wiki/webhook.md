## Высокоуровневый запуск webhook через Dispatcher.handle\_webhook

```python
async def handle_webhook(self, bot: Bot, host: str = '0.0.0.0', port: int = 8080)
```

Запускает FastAPI-приложение для приёма событий через вебхук.
Рекомендуется для большинства сценариев, когда не требуется ручной контроль над обработкой запроса.

### Параметры

* **bot** (`Bot`): Экземпляр бота, с помощью которого будут обрабатываться события.
* **host** (`str`, по умолчанию `'0.0.0.0'`): Хост, на котором запускается сервер.
* **port** (`int`, по умолчанию `8080`): Порт, на котором будет доступен сервер.

### Поведение

* Создаёт FastAPI-приложение с обработчиком POST-запросов по адресу `'/'`.
* В обработчике автоматически:

  * Десериализует входящий запрос (`await request.json()`).
  * Преобразует событие в объект через `process_update_webhook`.
  * Передаёт событие в диспетчер (`await self.handle(event_object)`).
  * Возвращает `{ "ok": true }` при успехе.
  * Логирует ошибку при неудаче.
* Запускает сервер с помощью метода `init_serve`.

### Пример использования

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot('тут_ваш_токен')
dp = Dispatcher()


@dp.message_created()
async def handle_message(event: MessageCreated):
    await event.message.answer('Бот работает через вебхук!')


async def main():
    await dp.handle_webhook(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

---

## Dispatcher.init\_serve

```python
async def init_serve(self, bot: Bot, host: str = '0.0.0.0', port: int = 8080, **kwargs)
```

Низкоуровневая функция для запуска FastAPI-сервера с уже сконфигурированным приложением.

### Параметры

* **bot** (`Bot`): Экземпляр бота.
* **host** (`str`, по умолчанию `'0.0.0.0'`): На каком адресе принимать входящие запросы.
* **port** (`int`, по умолчанию `8080`): На каком порту будет работать сервер.
* **kwargs**: Дополнительные параметры, передающиеся в конфиг сервера.

### Внутренняя логика

* Формирует объект конфигурации `Config` для сервера (`uvicorn`).
* Создаёт сервер и запускает его методом `server.serve()`.
* Перед запуском вызывает внутреннюю инициализацию диспетчера `await self.__ready(bot)`.

### Пример использования
```python
import asyncio
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from maxapi import Bot, Dispatcher
from maxapi.methods.types.getted_updates import process_update_webhook
from maxapi.types import MessageCreated
from maxapi.dispatcher import webhook_app

logging.basicConfig(level=logging.INFO)

bot = Bot('тут_ваш_токен')
dp = Dispatcher()

 
@dp.message_created()
async def handle_message(event: MessageCreated):
    await event.message.answer('Бот работает через вебхук!')

# Регистрация обработчика
# для вебхука
@webhook_app.post('/')
async def _(request: Request):
    
    # Сериализация полученного запроса
    event_json = await request.json()
    
    # Десериализация полученного запроса
    # в pydantic
    event_object = await process_update_webhook(
        event_json=event_json,
        bot=bot
    )
    
    # ...свой код
    print(f'Информация из вебхука: {event_json}')
    # ...свой код

    # Окончательная обработка запроса
    await dp.handle(event_object)
    
    # Ответ вебхука
    return JSONResponse(content={'ok': True}, status_code=200)


async def main():
    
    # Запуск сервера
    await dp.init_serve(bot, log_level='critical')


if __name__ == '__main__':
    asyncio.run(main())

```
---

## Какой способ выбрать?

* **handle\_webhook** — используйте, если вы хотите «всё из коробки» и не нужны дополнительные роуты или сложная кастомизация.
* **init\_serve** — можно вызывать самостоятельно, если вы хотите вручную управлять жизненным циклом сервера.
