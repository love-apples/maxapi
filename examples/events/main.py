import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import (
    BotStarted, 
    Command, 
    MessageCreated, 
    CallbackButton, 
    MessageCallback, 
    BotAdded, 
    ChatTitleChanged, 
    MessageEdited, 
    MessageRemoved, 
    UserAdded, 
    UserRemoved,
    BotStopped,
    DialogCleared,
    DialogMuted,
    DialogUnmuted,
    ChatButton,
    MessageChatCreated
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()


@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(
            text='Кнопка 1',
            payload='btn_1'
        ),
        CallbackButton(
            text='Кнопка 2',
            payload='btn_2',
        )
    )
    builder.add(
        ChatButton(
            text='Создать чат',
            chat_title='Тест чат'
        )
    )

    await event.message.answer(
        text='Привет!', 
        attachments=[
            builder.as_markup(),
        ]                               # Для MAX клавиатура это вложение, 
    )                                       # поэтому она в attachments


@dp.bot_added()
async def bot_added(event: BotAdded):
    
    if not event.chat:
        logging.info('Не удалось получить chat, возможно отключен auto_requests!')
        return
    
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'Привет чат {event.chat.title}!'
    )
    
    
@dp.message_removed()
async def message_removed(event: MessageRemoved):
    await bot.send_message(
        chat_id=event.chat_id,
        text='Я всё видел!'
    )
    
    
@dp.bot_started()
async def bot_started(event: BotStarted):
    await bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )
    
    
@dp.chat_title_changed()
async def chat_title_changed(event: ChatTitleChanged):
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'Крутое новое название "{event.title}"!'
    )
    
    
@dp.message_callback()
async def message_callback(event: MessageCallback):
    await event.answer(
        new_text=f'Вы нажали на кнопку {event.callback.payload}!'
    )
    

@dp.message_edited()
async def message_edited(event: MessageEdited):
    await event.message.answer(
        text='Вы отредактировали сообщение!'
    )
    
    
@dp.user_removed()
async def user_removed(event: UserRemoved):
    
    if not event.from_user:
        return await bot.send_message(
            chat_id=event.chat_id,
            text=f'Неизвестный кикнул {event.user.first_name} 😢'
        )
        
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'{event.from_user.first_name} кикнул {event.user.first_name} 😢'
    )
    
    
@dp.user_added()
async def user_added(event: UserAdded):
    
    if not event.chat:
        return await bot.send_message(
            chat_id=event.chat_id,
            text=f'Чат приветствует вас, {event.user.first_name}!'
        )
        
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'Чат "{event.chat.title}" приветствует вас, {event.user.first_name}!'
    )
    

@dp.bot_stopped()
async def bot_stopped(event: BotStopped):
    logging.info(event.from_user.full_name, 'остановил бота') # type: ignore
    
    
@dp.dialog_cleared()
async def dialog_cleared(event: DialogCleared):
    logging.info(event.from_user.full_name, 'очистил историю чата с ботом') # type: ignore
    
    
@dp.dialog_muted()
async def dialog_muted(event: DialogMuted):
    logging.info(event.from_user.full_name, 'отключил оповещения от чата бота до ', event.muted_until_datetime) # type: ignore
    
    
@dp.dialog_unmuted()
async def dialog_unmuted(event: DialogUnmuted):
    logging.info(event.from_user.full_name, 'включил оповещения от чата бота') # type: ignore
    

@dp.dialog_unmuted()
async def dialog_removed(event: DialogUnmuted):
    logging.info(event.from_user.full_name, 'удалил диалог с ботом') # type: ignore
    

@dp.message_chat_created()
async def message_chat_created(event: MessageChatCreated):
    await bot.send_message(
        chat_id=event.chat.chat_id,
        text=f'Чат создан! Ссылка: {event.chat.link}'
    )


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())