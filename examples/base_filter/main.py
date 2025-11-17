import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, CommandStart, UpdateUnion
from maxapi.filters import BaseFilter

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


class FilterChat(BaseFilter):
    
    """
    Фильтр, который срабатывает только в чате с названием `Test`
    """
    
    async def __call__(self, event: UpdateUnion):
        
        if not event.chat:
            return False
        
        return event.chat == 'Test'
    

@dp.message_created(CommandStart(), FilterChat())
async def custom_data(event: MessageCreated):
    await event.message.answer('Привет!')
    
    
async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())