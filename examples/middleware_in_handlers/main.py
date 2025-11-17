import asyncio
import logging

from typing import Any, Awaitable, Callable, Dict

from maxapi import Bot, Dispatcher
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import MessageCreated, Command, UpdateUnion

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


class CheckChatTitleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        
        if event_object.chat.title == 'MAXApi':
            return await handler(event_object, data)


class CustomDataMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        
        data['custom_data'] = f'Это ID того кто вызвал команду: {event_object.from_user.user_id}'
        
        await handler(event_object, data)


@dp.message_created(Command('start'), CheckChatTitleMiddleware())
async def start(event: MessageCreated):
    await event.message.answer('Это сообщение было отправлено, так как ваш чат называется "MAXApi"!')

    
@dp.message_created(Command('custom_data'), CustomDataMiddleware())
async def custom_data(event: MessageCreated, custom_data: str):
    await event.message.answer(custom_data)
    
    
@dp.message_created(Command('many_middlewares'), CheckChatTitleMiddleware(), CustomDataMiddleware())
async def many_middlewares(event: MessageCreated, custom_data: str):
    await event.message.answer('Это сообщение было отправлено, так как ваш чат называется "MAXApi"!')
    await event.message.answer(custom_data)
    

async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())