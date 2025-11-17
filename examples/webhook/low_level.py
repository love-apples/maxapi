import asyncio
import logging

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    raise ImportError(
        '\n\t Не установлен fastapi!'
        '\n\t Выполните команду для установки fastapi: '
        '\n\t pip install fastapi>=0.68.0'
        '\n\t Или сразу все зависимости для работы вебхука:'
        '\n\t pip install maxapi[webhook]'
    )

from maxapi import Bot, Dispatcher
from maxapi.methods.types.getted_updates import process_update_webhook
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()

 
@dp.message_created()
async def handle_message(event: MessageCreated):
    await event.message.answer('Бот работает через вебхук!')

# Регистрация обработчика
# для вебхука
@dp.webhook_post('/')
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
