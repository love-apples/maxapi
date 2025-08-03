from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from .client.default import DefaultConnectionProperties
from .types.errors import Error

from .types.input_media import InputMedia, InputMediaBuffer

from .connection.base import BaseConnection
from .loggers import logger_bot

from .enums.parse_mode import ParseMode
from .enums.sender_action import SenderAction
from .enums.upload_type import UploadType
from .enums.update import UpdateType

from .methods.add_admin_chat import AddAdminChat
from .methods.add_members_chat import AddMembersChat
from .methods.change_info import ChangeInfo
from .methods.delete_bot_from_chat import DeleteMeFromMessage
from .methods.delete_chat import DeleteChat
from .methods.delete_message import DeleteMessage
from .methods.delete_pin_message import DeletePinMessage
# from .methods.download_media import DownloadMedia
from .methods.edit_chat import EditChat
from .methods.edit_message import EditMessage
from .methods.get_chat_by_id import GetChatById
from .methods.get_chat_by_link import GetChatByLink
from .methods.get_chats import GetChats
from .methods.get_list_admin_chat import GetListAdminChat
from .methods.get_me import GetMe
from .methods.get_me_from_chat import GetMeFromChat
from .methods.get_members_chat import GetMembersChat
from .methods.get_messages import GetMessages
from .methods.get_pinned_message import GetPinnedMessage
from .methods.get_updates import GetUpdates
from .methods.get_upload_url import GetUploadURL
from .methods.get_video import GetVideo
from .methods.pin_message import PinMessage
from .methods.remove_admin import RemoveAdmin
from .methods.remove_member_chat import RemoveMemberChat
from .methods.send_action import SendAction
from .methods.send_callback import SendCallback
from .methods.send_message import SendMessage
from .methods.get_subscriptions import GetSubscriptions
from .methods.types.getted_subscriptions import GettedSubscriptions
from .methods.subscribe_webhook import SubscribeWebhook
from .methods.types.subscribed import Subscribed
from .methods.types.unsubscribed import Unsubscribed
from .methods.unsubscribe_webhook import UnsubscribeWebhook
from .methods.get_message import GetMessage

if TYPE_CHECKING:
    from .types.attachments.attachment import Attachment
    from .types.attachments.image import PhotoAttachmentRequestPayload
    from .types.attachments.video import Video
    from .types.chats import Chat, ChatMember, Chats
    from .types.command import BotCommand
    from .types.message import Message, Messages, NewMessageLink
    from .types.users import ChatAdmin, User

    from .methods.types.added_admin_chat import AddedListAdminChat
    from .methods.types.added_members_chat import AddedMembersChat
    from .methods.types.deleted_bot_from_chat import DeletedBotFromChat
    from .methods.types.deleted_chat import DeletedChat
    from .methods.types.deleted_message import DeletedMessage
    from .methods.types.deleted_pin_message import DeletedPinMessage
    from .methods.types.edited_message import EditedMessage
    from .methods.types.getted_list_admin_chat import GettedListAdminChat
    from .methods.types.getted_members_chat import GettedMembersChat
    from .methods.types.getted_pineed_message import GettedPin
    from .methods.types.getted_upload_url import GettedUploadUrl
    from .methods.types.pinned_message import PinnedMessage
    from .methods.types.removed_admin import RemovedAdmin
    from .methods.types.removed_member_chat import RemovedMemberChat
    from .methods.types.sended_action import SendedAction
    from .methods.types.sended_callback import SendedCallback
    from .methods.types.sended_message import SendedMessage


class Bot(BaseConnection):
    
    """Основной класс для работы с API бота.

    Предоставляет методы для взаимодействия с чатами, сообщениями,
    пользователями и другими функциями бота.
    """

    def __init__(
            self, 
            token: str,
            parse_mode: Optional[ParseMode] = None,
            notify: Optional[bool] = None,
            auto_requests: bool = True,
            default_connection: Optional[DefaultConnectionProperties] = None,
            after_input_media_delay: Optional[float] = None,
            auto_check_subscriptions: bool = True
        ):
        
        """
        Инициализирует экземпляр бота с указанным токеном.

        :param token: Токен доступа к API бота
        :param parse_mode: Форматирование по умолчанию
        :param notify: Отключение уведомлений при отправке сообщений (по умолчанию игнорируется) (не работает на стороне MAX)
        :param auto_requests: Автоматическое заполнение полей chat и from_user в Update с помощью API запросов если они не заложены как полноценные объекты в Update (по умолчанию True, при False chat и from_user в некоторых событиях будут выдавать None)
        :param default_connection: Настройки aiohttp
        :param after_input_media_delay: Задержка в секундах после загрузки файла на сервера MAX (без этого чаще всего MAX не успевает обработать вложение и выдает ошибку `errors.process.attachment.file.not.processed`)
        :param auto_check_subscriptions: Проверка на установленные подписки для метода start_polling (бот не работает в поллинге при установленных подписках)
        """
        
        super().__init__()

        self.bot = self
        self.default_connection = default_connection or DefaultConnectionProperties()
        self.after_input_media_delay = after_input_media_delay or 2.0
        self.auto_check_subscriptions = auto_check_subscriptions

        self.__token = token
        self.params: Dict[str, Any] = {'access_token': self.__token}
        self.marker_updates = None
        
        self.parse_mode = parse_mode
        self.notify = notify
        self.auto_requests = auto_requests
        
        self._me: User | None = None
        
    @property
    def me(self):
        return self._me
        
    def _resolve_notify(self, notify: Optional[bool]) -> Optional[bool]:
        return notify if notify is not None else self.notify

    def _resolve_parse_mode(self, mode: Optional[ParseMode]) -> Optional[ParseMode]:
        return mode if mode is not None else self.parse_mode
    
    async def close_session(self) -> None:
        if self.session is not None:
            await self.session.close()
        
    async def send_message(
            self,
            chat_id: Optional[int] = None, 
            user_id: Optional[int] = None,
            text: Optional[str] = None,
            attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None,
            link: Optional[NewMessageLink] = None,
            notify: Optional[bool] = None,
            parse_mode: Optional[ParseMode] = None
        ) -> Optional[SendedMessage | Error]:
        
        """
        Отправляет сообщение в чат или пользователю.

        :param chat_id: ID чата для отправки (обязателен, если не указан user_id)
        :param user_id: ID пользователя для отправки (обязателен, если не указан chat_id)
        :param text: Текст сообщения
        :param attachments: Список вложений к сообщению
        :param link: Данные ссылки сообщения
        :param notify: Отправлять уведомление получателю (по умолчанию берется значение из бота)
        :param parse_mode: Режим форматирования текста

        :return: Объект отправленного сообщения
        """
        
        return await SendMessage(
            bot=self,
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=self._resolve_notify(notify),
            parse_mode=self._resolve_parse_mode(parse_mode)
        ).fetch()
    
    async def send_action(
            self,
            chat_id: Optional[int] = None,
            action: SenderAction = SenderAction.TYPING_ON
        ) -> SendedAction:
        
        """
        Отправляет действие в чат (например, "печатает").

        :param chat_id: ID чата для отправки действия
        :param action: Тип действия (по умолчанию SenderAction.TYPING_ON)

        :return: Результат отправки действия
        """
        
        return await SendAction(
            bot=self,
            chat_id=chat_id,
            action=action
        ).fetch()
    
    async def edit_message(
            self,
            message_id: str,
            text: Optional[str] = None,
            attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None,
            link: Optional[NewMessageLink] = None,
            notify: Optional[bool] = None,
            parse_mode: Optional[ParseMode] = None
        ) -> Optional[EditedMessage | Error]:
        
        """
        Редактирует существующее сообщение.

        :param message_id: ID сообщения для редактирования
        :param text: Новый текст сообщения
        :param attachments: Новые вложения
        :param link: Новая ссылка сообщения
        :param notify: Отправлять уведомление получателю (по умолчанию берется значение из бота)
        :param parse_mode: Режим форматирования текста

        :return: Объект отредактированного сообщения
        """
        
        return await EditMessage(
            bot=self,
            message_id=message_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=self._resolve_notify(notify),
            parse_mode=self._resolve_parse_mode(parse_mode)
        ).fetch()
    
    async def delete_message(
            self,
            message_id: str
        ) -> DeletedMessage:
        
        """
        Удаляет сообщение.

        :param message_id: ID сообщения для удаления

        :return: Результат удаления сообщения
        """
        
        return await DeleteMessage(
            bot=self,
            message_id=message_id,
        ).fetch()
    
    async def delete_chat(
            self,
            chat_id: int
        ) -> DeletedChat:
        
        """
        Удаляет чат.

        :param chat_id: ID чата для удаления

        :return: Результат удаления чата
        """
        
        return await DeleteChat(
            bot=self,
            chat_id=chat_id,
        ).fetch()

    async def get_messages(
            self, 
            chat_id: Optional[int] = None,
            message_ids: Optional[List[str]] = None,
            from_time: Optional[Union[datetime, int]] = None,
            to_time: Optional[Union[datetime, int]] = None,
            count: int = 50,
        ) -> Messages:
        
        """
        Получает сообщения из чата.

        :param chat_id: ID чата (обязателен, если не указаны message_ids)
        :param message_ids: Список ID сообщений для получения
        :param from_time: Время начала периода (datetime или timestamp)
        :param to_time: Время конца периода (datetime или timestamp)
        :param count: Количество сообщений (по умолчанию 50)

        :return: Список сообщений
        """
        
        return await GetMessages(
            bot=self, 
            chat_id=chat_id,
            message_ids=message_ids,
            from_time=from_time,
            to_time=to_time,
            count=count
        ).fetch()
    
    async def get_message(
            self, 
            message_id: str
        ) -> Message:
        
        """
        Получает одно сообщение по ID.

        :param message_id: ID сообщения

        :return: Объект сообщения
        """
        
        return await GetMessage(
            bot=self,
            message_id=message_id
        ).fetch()

    async def get_me(self) -> User:
        
        """
        https://dev.max.ru/docs-api/methods/GET/me\n
        Получает информацию о текущем боте.

        :return: Объект пользователя бота
        """
        
        return await GetMe(self).fetch()
    
    async def get_pin_message(
            self, 
            chat_id: int
        ) -> GettedPin:
        
        """
        Получает закрепленное сообщение в чате.

        :param chat_id: ID чата

        :return: Закрепленное сообщение
        """
        
        return await GetPinnedMessage(
            bot=self, 
            chat_id=chat_id
        ).fetch()
    
    async def change_info(
            self, 
            name: Optional[str] = None, 
            description: Optional[str] = None,
            commands: Optional[List[BotCommand]] = None,
            photo: Optional[PhotoAttachmentRequestPayload] = None
        ) -> User:
        
        """
        Изменяет информацию о боте.

        :param name: Новое имя бота
        :param description: Новое описание бота
        :param commands: Список команд бота
        :param photo: Данные фотографии бота

        :return: Обновленная информация о боте
        """

        return await ChangeInfo(
            bot=self, 
            name=name, 
            description=description, 
            commands=commands, 
            photo=photo
        ).fetch()
    
    async def get_chats(
            self,
            count: int = 50,
            marker: Optional[int] = None
        ) -> Chats:
        
        """
        Получает список чатов бота.

        :param count: Количество чатов (по умолчанию 50)
        :param marker: Маркер для пагинации

        :return: Список чатов
        """
        
        return await GetChats(
            bot=self,
            count=count,
            marker=marker
        ).fetch()
    
    async def get_chat_by_link(
            self, 
            link: str
        ) -> Chat:
        
        """
        Получает чат по ссылке.

        :param link: Ссылка на чат

        :return: Объект чата
        """
        
        return await GetChatByLink(bot=self, link=link).fetch()
    
    async def get_chat_by_id(
            self, 
            id: int
        ) -> Chat:
        
        """
        Получает чат по ID.

        :param id: ID чата

        :return: Объект чата
        """
        
        return await GetChatById(bot=self, id=id).fetch()
    
    async def edit_chat(
            self,
            chat_id: int,
            icon: Optional[PhotoAttachmentRequestPayload] = None,
            title: Optional[str] = None,
            pin: Optional[str] = None,
            notify: Optional[bool] = None,
        ) -> Chat:
        
        """
        Редактирует параметры чата.

        :param chat_id: ID чата
        :param icon: Данные иконки чата
        :param title: Новый заголовок чата
        :param pin: ID сообщения для закрепления
        :param notify: Отправлять уведомление получателю (по умолчанию берется значение из бота)

        :return: Обновленный объект чата
        """
        
        return await EditChat(
            bot=self,
            chat_id=chat_id,
            icon=icon,
            title=title,
            pin=pin,
            notify=self._resolve_notify(notify),
        ).fetch()
    
    async def get_video(
            self, 
            video_token: str
        ) -> Video:
        
        """
        Получает видео по токену.

        :param video_token: Токен видео

        :return: Объект видео
        """
        
        return await GetVideo(
            bot=self, 
            video_token=video_token
        ).fetch()

    async def send_callback(
            self,
            callback_id: str,
            message: Optional[Message] = None,
            notification: Optional[str] = None
        ) -> SendedCallback:
        
        """
        Отправляет callback ответ.

        :param callback_id: ID callback
        :param message: Сообщение для отправки
        :param notification: Текст уведомления

        :return: Результат отправки callback
        """
        
        return await SendCallback(
            bot=self,
            callback_id=callback_id,
            message=message,
            notification=notification
        ).fetch()
    
    async def pin_message(
            self,
            chat_id: int,
            message_id: str,
            notify: Optional[bool] = None
        ) -> PinnedMessage:
        
        """
        Закрепляет сообщение в чате.

        :param chat_id: ID чата
        :param message_id: ID сообщения
        :param notify: Отправлять уведомление получателю (по умолчанию берется значение из бота)

        :return: Закрепленное сообщение
        """
        
        return await PinMessage(
            bot=self,
            chat_id=chat_id,
            message_id=message_id,
            notify=self._resolve_notify(notify),
        ).fetch()
    
    async def delete_pin_message(
            self,
            chat_id: int,
        ) -> DeletedPinMessage:
        
        """
        Удаляет закрепленное сообщение в чате.

        :param chat_id: ID чата

        :return: Результат удаления
        """
        
        return await DeletePinMessage(
            bot=self,
            chat_id=chat_id,
        ).fetch()
    
    async def get_me_from_chat(
            self,
            chat_id: int,
        ) -> ChatMember:
        
        """
        Получает информацию о боте в конкретном чате.

        :param chat_id: ID чата

        :return: Информация о боте в чате
        """
        
        return await GetMeFromChat(
            bot=self,
            chat_id=chat_id,
        ).fetch()
    
    async def delete_me_from_chat(
            self,
            chat_id: int,
        ) -> DeletedBotFromChat:
        
        """
        Удаляет бота из чата.

        :param chat_id: ID чата

        :return: Результат удаления
        """
        
        return await DeleteMeFromMessage(
            bot=self,
            chat_id=chat_id,
        ).fetch()
    
    async def get_list_admin_chat(
            self,
            chat_id: int,
        ) -> GettedListAdminChat:
        
        """
        Получает список администраторов чата.

        :param chat_id: ID чата

        :return: Список администраторов
        """
        
        return await GetListAdminChat(
            bot=self,
            chat_id=chat_id,
        ).fetch()
    
    async def add_list_admin_chat(
            self,
            chat_id: int,
            admins: List[ChatAdmin],
            marker: Optional[int] = None
        ) -> AddedListAdminChat:
        
        """
        Добавляет администраторов в чат.

        :param chat_id: ID чата
        :param admins: Список администраторов
        :param marker: Маркер для пагинации

        :return: Результат добавления
        """
        
        return await AddAdminChat(
            bot=self,
            chat_id=chat_id,
            admins=admins,
            marker=marker,
        ).fetch()
    
    async def remove_admin(
            self,
            chat_id: int,
            user_id: int
        ) -> RemovedAdmin:
        
        """
        Удаляет администратора из чата.

        :param chat_id: ID чата
        :param user_id: ID пользователя

        :return: Результат удаления
        """
        
        return await RemoveAdmin(
            bot=self,
            chat_id=chat_id,
            user_id=user_id,
        ).fetch()
    
    async def get_chat_members(
            self,
            chat_id: int,
            user_ids: Optional[List[int]] = None,
            marker: Optional[int] = None,
            count: Optional[int] = None,
        ) -> GettedMembersChat:
        
        """
        Получает участников чата.

        :param chat_id: ID чата
        :param user_ids: Список ID участников
        :param marker: Маркер для пагинации
        :param count: Количество участников

        :return: Список участников
        """
        
        return await GetMembersChat(
            bot=self,
            chat_id=chat_id,
            user_ids=user_ids,
            marker=marker,
            count=count,
        ).fetch()
        
    async def get_chat_member(
            self,
            chat_id: int,
            user_id: int,
        ) -> Optional[ChatMember]:
        
        """
        Получает участника чата.

        :param chat_id: ID чата
        :param user_id: ID участника

        :return: Участник
        """
        
        members = await self.get_chat_members(
            chat_id=chat_id,
            user_ids=[user_id]
        )
        
        if members.members:
            return members.members[0]

        return None
    
    async def add_chat_members(
            self,
            chat_id: int,
            user_ids: List[int],
        ) -> AddedMembersChat:
        
        """
        Добавляет участников в чат.

        :param chat_id: ID чата
        :param user_ids: Список ID пользователей

        :return: Результат добавления
        """
        
        return await AddMembersChat(
            bot=self,
            chat_id=chat_id,
            user_ids=user_ids,
        ).fetch()
    
    async def kick_chat_member(
            self,
            chat_id: int,
            user_id: int,
            block: bool = False,
        ) -> RemovedMemberChat:
        
        """
        Исключает участника из чата.

        :param chat_id: ID чата
        :param user_id: ID пользователя
        :param block: Блокировать пользователя (по умолчанию False)

        :return: Результат исключения
        """
        
        return await RemoveMemberChat(
            bot=self,
            chat_id=chat_id,
            user_id=user_id,
            block=block,
        ).fetch()
    
    async def get_updates(
            self,
        ) -> Dict:
        
        """
        Получает обновления для бота.

        :return: Список обновлений
        """
        
        return await GetUpdates(
            bot=self,
        ).fetch()
    
    async def get_upload_url(
            self,
            type: UploadType
        ) -> GettedUploadUrl:
        
        """
        Получает URL для загрузки файлов.

        :param type: Тип загружаемого файла

        :return: URL для загрузки
        """
        
        return await GetUploadURL(
            bot=self,
            type=type
        ).fetch()
    
    async def set_my_commands(
            self,
            *commands: BotCommand
        ) -> User:
        
        """
        Устанавливает список команд бота.

        :param commands: Список команд

        :return: Обновленная информация о боте
        """
        
        return await ChangeInfo(
            bot=self,
            commands=list(commands)
        ).fetch()
        
    async def get_subscriptions(self) -> GettedSubscriptions:
        
        """
        Получает список всех подписок.

        :return: Объект со списком подписок
        """
        
        return await GetSubscriptions(bot=self).fetch()
    
    async def subscribe_webhook(
            self,
            url: str,
            update_types: Optional[List[UpdateType]] = None,
            secret: Optional[str] = None
        ) -> Subscribed:
        
        """
        Подписывает бота на получение обновлений через WebHook. 
        После вызова этого метода бот будет получать уведомления о новых событиях в чатах на указанный URL. 
        Ваш сервер должен прослушивать один из следующих портов: `80`, `8080`, `443`, `8443`, `16384`-`32383`.

        :param url: URL HTTP(S)-эндпойнта вашего бота. Должен начинаться с http(s)://
        :param update_types: Список типов обновлений, которые ваш бот хочет получать. 
        Для полного списка типов см. объект
        :param secret: От 5 до 256 символов. Cекрет, который должен быть отправлен в заголовке X-Max-Bot-Api-Secret 
        в каждом запросе Webhook. Разрешены только символы A-Z, a-z, 0-9, и дефис. 
        Заголовок рекомендован, чтобы запрос поступал из установленного веб-узла

        :return: Обновленная информация о боте
        """
        
        return await SubscribeWebhook(
            bot=self,
            url=url,
            update_types=update_types,
            secret=secret
        ).fetch()
        
    async def unsubscribe_webhook(
            self,
            url: str,
        ) -> Unsubscribed:
        
        """
        Отписывает бота от получения обновлений через WebHook. 
        После вызова этого метода бот перестает получать уведомления о новых событиях, 
        и доступна доставка уведомлений через API с длительным опросом.

        :param url: URL HTTP(S)-эндпойнта вашего бота. Должен начинаться с http(s)://

        :return: Обновленная информация о боте
        """
        
        return await UnsubscribeWebhook(
            bot=self,
            url=url,
        ).fetch()
        
    async def delete_webhook(self):
        
        """
        Удаление всех подписок на Webhook
        """
        
        subs = await self.get_subscriptions()
        if subs.subscriptions:
            
            for sub in subs.subscriptions:
                
                await self.unsubscribe_webhook(sub.url)
                logger_bot.info('Удалена подписка на Webhook: %s', sub.url)
        
        
    # async def download_file(
    #         self, 
    #         path: str, 
    #         url: str, 
    #         token: str
    #     ):
        
    #     """
    #     Скачивает медиа с указанной ссылки по токену, сохраняя по определенному пути

    #     :param path: Путь сохранения медиа
    #     :param url: Ссылка на медиа
    #     :param token: Токен медиа

    #     :return: Числовой статус
    #     """
        
    #     return await DownloadMedia(
    #         bot=self,
    #         path=path, 
    #         media_url=url, 
    #         media_token=token
    #     ).fetch()