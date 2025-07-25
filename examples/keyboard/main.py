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

bot = Bot('тут_ваш_токен')
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
async def echo(event: MessageCreated):
    builder = InlineKeyboardBuilder()
    
    builder.row(
        ChatButton(
                text="Создать чат", 
                chat_title='Test', 
                chat_description='Test desc'
        ),
        LinkButton(
            text="Канал разработчика", 
            url="https://t.me/loveapples_dev"
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
async def echo(event: MessageCreated):
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
                text="Канал разработчика", 
                url="https://t.me/loveapples_dev"
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
async def callback(obj: MessageChatCreated):
    await obj.bot.send_message(
        chat_id=obj.chat.chat_id,
        text=f'Чат создан! Ссылка: {obj.chat.link}'
    )
    

@dp.message_callback()
async def callback(callback: MessageCallback):
    await callback.message.answer('Вы нажали на Callback!')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())