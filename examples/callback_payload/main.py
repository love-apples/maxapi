import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import CommandStart
from maxapi.types import (
    CallbackButton,
    MessageCreated,
    MessageCallback,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


class MyPayload(CallbackPayload, prefix='mypayload'):
    foo: str
    action: str


class AnotherPayload(CallbackPayload, prefix='another'):
    bar: str
    value: int


@dp.message_created(CommandStart())
async def show_keyboard(event: MessageCreated):
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton( 
            text='Первая кнопка',
            payload=MyPayload(foo='123', action='edit').pack(), 
        ), 
        CallbackButton(
            text='Вторая кнопка',
            payload=AnotherPayload(bar='abc', value=42).pack(),
        ),
    )
    await event.message.answer('Нажми кнопку!', attachments=[kb.as_markup()])


@dp.message_callback(MyPayload.filter(F.foo == '123'))
async def on_first_callback(event: MessageCallback, payload: MyPayload):
    await event.answer(new_text=f'Первая кнопка: foo={payload.foo}, action={payload.action}')


@dp.message_callback(AnotherPayload.filter())
async def on_second_callback(event: MessageCallback, payload: AnotherPayload):
    await event.answer(new_text=f'Вторая кнопка: bar={payload.bar}, value={payload.value}')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
