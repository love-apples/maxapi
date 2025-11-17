import asyncio
import logging

from maxapi import Bot, Dispatcher

# Кнопки
from maxapi.types import (
    ChatButton, 
    LinkButton, 
    CallbackButton, 
    RequestGeoLocationButton, 
    MessageButton, 
    ButtonsPayload, # Для постройки клавиатуры без InlineKeyboardBuilder
    RequestContactButton, 
    OpenAppButton, 
)

from maxapi.types import (
    MessageCreated, 
    MessageCallback, 
    MessageChatCreated,
    CommandStart, 
    Command
)

from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


@dp.message_created(CommandStart())
async def echo(event: MessageCreated):
    await event.message.answer(
        (
            'Привет! Мои команды:\n\n'
            
            '/builder - Клавиатура из InlineKeyboardBuilder\n'
            '/pyaload - Клавиатура из pydantic моделей\n'
        )
    )
    
    
@dp.message_created(Command('builder'))
async def builder(event: MessageCreated):
    builder = InlineKeyboardBuilder()
    
    builder.row(
        ChatButton(
                text="Создать чат", 
                chat_title='Test', 
                chat_description='Test desc'
        ),
        LinkButton(
            text="Документация MAX", 
            url="https://dev.max.ru/docs"
        ),
    )
    
    builder.row(
        RequestGeoLocationButton(text="Геолокация"),
        MessageButton(text="Сообщение"),
    )
    
    builder.row(
        RequestContactButton(text="Контакт"),
        OpenAppButton(
            text="Приложение", 
            web_app=event.bot.me.username, 
            contact_id=event.bot.me.user_id
        ),
    )
    
    builder.row(
        CallbackButton(
            text='Callback',
            payload='test',
        )
    )
    
    await event.message.answer(
        text='Клавиатура из InlineKeyboardBuilder',
        attachments=[
            builder.as_markup()
        ])
    
    
@dp.message_created(Command('payload'))
async def payload(event: MessageCreated):
    buttons = [
        [
            # кнопку типа "chat" убрали из документации,
            # возможны баги
            ChatButton(
                text="Создать чат", 
                chat_title='Test', 
                chat_description='Test desc'
            ),
            LinkButton(
                text="Документация MAX", 
                url="https://dev.max.ru/docs"
            ),
        ],
        [
            RequestGeoLocationButton(text="Геолокация"),
            MessageButton(text="Сообщение"),
        ],
        [
            RequestContactButton(text="Контакт"),
            OpenAppButton(
                text="Приложение", 
                web_app=event.bot.me.username, 
                contact_id=event.bot.me.user_id
            ),
        ],
        [
            CallbackButton(
                text='Callback',
                payload='test',
            )
        ]
    ]
    
    buttons_payload = ButtonsPayload(buttons=buttons).pack()
    
    await event.message.answer(
        text='Клавиатура из pydantic моделей',
        attachments=[
            buttons_payload
        ])
    
    
@dp.message_chat_created()
async def message_chat_created(obj: MessageChatCreated):
    await obj.bot.send_message(
        chat_id=obj.chat.chat_id,
        text=f'Чат создан! Ссылка: {obj.chat.link}'
    )
    

@dp.message_callback()
async def message_callback(callback: MessageCallback):
    await callback.message.answer('Вы нажали на Callback!')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())