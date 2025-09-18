import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot('тут_ваш_токен')
dp = Dispatcher()


@dp.message_created(F.message.body.text)
async def echo(event: MessageCreated):
    await event.message.answer(f"Повторяю за вами: {event.message.body.text}")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())