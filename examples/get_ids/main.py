import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.enums.parse_mode import ParseMode
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


@dp.message_created(F.message.link.type == 'forward')
async def get_ids_from_forward(event: MessageCreated):
    text = (
        'Информация о пересланном сообщении:\n\n'
        
        f'Из чата: <b>{event.message.link.chat_id}</b>\n'
        f'От пользователя: <b>{event.message.link.sender.user_id}</b>'
    )
    await event.message.reply(text)
    

@dp.message_created()
async def get_ids(event: MessageCreated):
    text = (
        f'Ваш ID: <b>{event.from_user.user_id}</b>\n'
        f'ID этого чата: <b>{event.chat.chat_id}</b>'
    )
    await event.message.answer(text, parse_mode=ParseMode.HTML)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())