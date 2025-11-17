import asyncio
import logging

from typing import Any, Awaitable, Callable, Dict

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, Command, UpdateUnion
from maxapi.filters.middleware import BaseMiddleware

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


class CustomDataForRouterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        
        data['custom_data'] = f'Это ID того кто вызвал команду: {event_object.from_user.user_id}'
        result = await handler(event_object, data)
        return result
    

@dp.message_created(Command('custom_data'))
async def custom_data(event: MessageCreated, custom_data: str):
    await event.message.answer(custom_data)
    
    
async def main():
    dp.middleware(CustomDataForRouterMiddleware())
    
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())