import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


@dp.message_created(F.message.body.text == 'привет')
async def on_hello(event: MessageCreated):
    await event.message.answer('Привет!')


@dp.message_created(F.message.body.text.lower().contains('помощь'))
async def on_help(event: MessageCreated):
    await event.message.answer('Чем могу помочь?')


@dp.message_created(F.message.body.text.regexp(r'^\d{4}$'))
async def on_code(event: MessageCreated):
    await event.message.answer('Принят 4-значный код')


@dp.message_created(F.message.body.attachments)
async def on_attachment(event: MessageCreated):
    await event.message.answer('Получено вложение')


@dp.message_created(F.message.body.text.len() > 20)
async def on_long_text(event: MessageCreated):
    await event.message.answer('Слишком длинное сообщение')


@dp.message_created(F.message.body.text.len() > 0)
async def on_non_empty(event: MessageCreated):
    await event.message.answer('Вы что-то написали.')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
