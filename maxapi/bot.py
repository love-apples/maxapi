from __future__ import annotations

import os
import warnings
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

from .client.default import DefaultConnectionProperties
from .connection.base import BaseConnection
from .enums.parse_mode import ParseMode
from .enums.sender_action import SenderAction
from .enums.update import UpdateType
from .enums.upload_type import UploadType
from .exceptions.max import InvalidToken
from .loggers import logger_bot
from .methods.add_admin_chat import AddAdminChat
from .methods.add_members_chat import AddMembersChat
from .methods.change_info import ChangeInfo
from .methods.delete_bot_from_chat import DeleteMeFromMessage
from .methods.delete_chat import DeleteChat
from .methods.delete_message import DeleteMessage
from .methods.delete_pin_message import DeletePinMessage
from .methods.edit_chat import EditChat
from .methods.edit_message import EditMessage
from .methods.get_chat_by_id import GetChatById
from .methods.get_chat_by_link import GetChatByLink
from .methods.get_chats import GetChats
from .methods.get_list_admin_chat import GetListAdminChat
from .methods.get_me import GetMe
from .methods.get_me_from_chat import GetMeFromChat
from .methods.get_members_chat import GetMembersChat
from .methods.get_message import GetMessage
from .methods.get_messages import GetMessages
from .methods.get_pinned_message import GetPinnedMessage
from .methods.get_subscriptions import GetSubscriptions
from .methods.get_updates import GetUpdates
from .methods.get_upload_url import GetUploadURL
from .methods.get_video import GetVideo
from .methods.pin_message import PinMessage
from .methods.remove_admin import RemoveAdmin
from .methods.remove_member_chat import RemoveMemberChat
from .methods.send_action import SendAction
from .methods.send_callback import SendCallback
from .methods.send_message import SendMessage
from .methods.subscribe_webhook import SubscribeWebhook
from .methods.types.getted_subscriptions import GettedSubscriptions
from .methods.types.subscribed import Subscribed
from .methods.types.unsubscribed import Unsubscribed
from .methods.unsubscribe_webhook import UnsubscribeWebhook
from .types.attachments import Attachments
from .types.input_media import InputMedia, InputMediaBuffer

if TYPE_CHECKING:
    from .filters.command import CommandsInfo
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
    from .types.attachments.attachment import Attachment
    from .types.attachments.image import PhotoAttachmentRequestPayload
    from .types.attachments.video import Video
    from .types.chats import Chat, ChatMember, Chats
    from .types.command import BotCommand
    from .types.message import Message, Messages, NewMessageLink
    from .types.updates.message_callback import MessageForCallback
    from .types.users import ChatAdmin, User


class Bot(BaseConnection):
    """
    Основной класс для работы с API бота.

    Предоставляет методы для взаимодействия с чатами, сообщениями,
    пользователями и другими функциями бота.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        parse_mode: Optional[ParseMode] = None,
        notify: Optional[bool] = None,
        disable_link_preview: Optional[bool] = None,
        auto_requests: bool = True,
        default_connection: Optional[DefaultConnectionProperties] = None,
        after_input_media_delay: Optional[float] = None,
        auto_check_subscriptions: bool = True,
        marker_updates: Optional[int] = None,
    ):
        """
        Инициализирует экземпляр бота.

        Args:
            token (str): Токен доступа к API бота. При None идет получение из под окружения MAX_BOT_TOKEN.
            parse_mode (Optional[ParseMode]): Форматирование по умолчанию.
            notify (Optional[bool]): Отключение уведомлений при отправке сообщений.
            disable_link_preview (Optional[bool]): Если false, сервер не будет генерировать превью для ссылок в тексте сообщений.
            auto_requests (bool): Автоматическое заполнение chat/from_user через API (по умолчанию True).
            default_connection (Optional[DefaultConnectionProperties]): Настройки соединения.
            after_input_media_delay (Optional[float]): Задержка после загрузки файла.
            auto_check_subscriptions (bool): Проверка подписок для метода start_polling.
            marker_updates (Optional[int]): Маркер для получения обновлений.
        """

        super().__init__()
        self.bot = self
        self.default_connection = (
            default_connection or DefaultConnectionProperties()
        )
        self.after_input_media_delay = after_input_media_delay or 2.0
        self.auto_check_subscriptions = auto_check_subscriptions
        self.commands: List[CommandsInfo] = []

        self.__token = token or os.environ.get("MAX_BOT_TOKEN")
        if self.__token is None:
            raise InvalidToken(
                'Токен не может быть None. Укажите токен в Bot(token="...") или в переменную окружения MAX_BOT_TOKEN'
            )

        self.params: Dict[str, Any] = {}
        self.headers: Dict[str, Any] = {"Authorization": self.__token}
        self.marker_updates = marker_updates

        self.parse_mode = parse_mode
        self.notify = notify
        self.disable_link_preview = disable_link_preview
        self.auto_requests = auto_requests

        self._me: User | None = None

    def set_marker_updates(self, marker_updates: int) -> None:
        """
        Устанавливает маркер для получения обновлений.

        Args:
            marker_updates (int): Маркер для получения обновлений.
        """

        self.marker_updates = marker_updates

    @property
    def handlers_commands(self) -> List[CommandsInfo]:
        """
        Возвращает список команд из зарегистрированных обработчиков текущего инстанса.

        Returns:
            List[CommandsInfo]: Список команд
        """

        return self.commands

    @property
    def me(self) -> Optional[User]:
        """
        Возвращает объект пользователя (бота).

        Returns:
            User | None: Объект пользователя или None.
        """

        return self._me

    def _resolve_disable_link_preview(
        self, disable_link_preview: Optional[bool]
    ) -> Optional[bool]:
        """
        Определяет флаг превью.

        Args:
            disable_link_preview (Optional[bool]): Локальный флаг.

        Returns:
            Optional[bool]: Итоговый флаг.
        """

        return (
            disable_link_preview
            if disable_link_preview is not None
            else self.disable_link_preview
        )

    def _resolve_notify(self, notify: Optional[bool]) -> Optional[bool]:
        """
        Определяет флаг уведомления.

        Args:
            notify (Optional[bool]): Локальный флаг.

        Returns:
            Optional[bool]: Итоговый флаг.
        """

        return notify if notify is not None else self.notify

    def _resolve_parse_mode(
        self, mode: Optional[ParseMode]
    ) -> Optional[ParseMode]:
        """
        Определяет режим форматирования.

        Args:
            mode (Optional[ParseMode]): Локальный режим.

        Returns:
            Optional[ParseMode]: Итоговый режим.
        """

        return mode if mode is not None else self.parse_mode

    async def close_session(self) -> None:
        """
        Закрывает текущую сессию aiohttp.

        Returns:
            None
        """

        if self.session is not None:
            await self.session.close()

    async def send_message(
        self,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        text: Optional[str] = None,
        attachments: Optional[
            List[Attachment | InputMedia | InputMediaBuffer]
            | List[Attachments]
        ] = None,
        link: Optional[NewMessageLink] = None,
        notify: Optional[bool] = None,
        parse_mode: Optional[ParseMode] = None,
        disable_link_preview: Optional[bool] = None,
        sleep_after_input_media: Optional[bool] = True,
    ) -> Optional[SendedMessage]:
        """
        Отправляет сообщение в чат или пользователю.

        https://dev.max.ru/docs-api/methods/POST/messages

        Args:
            chat_id (Optional[int]): ID чата для отправки (если не user_id).
            user_id (Optional[int]): ID пользователя (если не chat_id).
            text (Optional[str]): Текст сообщения.
            attachments (Optional[List[Attachment | InputMedia | InputMediaBuffer]]): Вложения.
            link (Optional[NewMessageLink]): Данные ссылки сообщения.
            notify (Optional[bool]): Флаг уведомления.
            parse_mode (Optional[ParseMode]): Режим форматирования текста.
            disable_link_preview (Optional[bool]): Флаг генерации превью.

        Returns:
            Optional[SendedMessage]: Отправленное сообщение или ошибка.
        """

        return await SendMessage(
            bot=self,
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=self._resolve_notify(notify),
            parse_mode=self._resolve_parse_mode(parse_mode),
            disable_link_preview=self._resolve_disable_link_preview(
                disable_link_preview
            ),
            sleep_after_input_media=sleep_after_input_media,
        ).fetch()

    async def send_action(
        self,
        chat_id: Optional[int] = None,
        action: SenderAction = SenderAction.TYPING_ON,
    ) -> SendedAction:
        """
        Отправляет действие в чат (например, "печатает").

        https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/actions

        Args:
            chat_id (Optional[int]): ID чата.
            action (SenderAction): Тип действия.

        Returns:
            SendedAction: Результат отправки действия.
        """

        return await SendAction(
            bot=self, chat_id=chat_id, action=action
        ).fetch()

    async def edit_message(
        self,
        message_id: str,
        text: Optional[str] = None,
        attachments: Optional[
            List[Attachment | InputMedia | InputMediaBuffer]
            | List[Attachments]
        ] = None,
        link: Optional[NewMessageLink] = None,
        notify: Optional[bool] = None,
        parse_mode: Optional[ParseMode] = None,
        sleep_after_input_media: Optional[bool] = True,
    ) -> Optional[EditedMessage]:
        """
        Редактирует существующее сообщение.

        https://dev.max.ru/docs-api/methods/PUT/messages

        Args:
            message_id (str): ID сообщения.
            text (Optional[str]): Новый текст.
            attachments (Optional[List[Attachment | InputMedia | InputMediaBuffer]]): Новые вложения.
            link (Optional[NewMessageLink]): Новая ссылка.
            notify (Optional[bool]): Флаг уведомления.
            parse_mode (Optional[ParseMode]): Режим форматирования текста.

        Returns:
            Optional[EditedMessage]: Отредактированное сообщение или ошибка.
        """

        return await EditMessage(
            bot=self,
            message_id=message_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=self._resolve_notify(notify),
            parse_mode=self._resolve_parse_mode(parse_mode),
            sleep_after_input_media=sleep_after_input_media,
        ).fetch()

    async def delete_message(self, message_id: str) -> DeletedMessage:
        """
        Удаляет сообщение.

        https://dev.max.ru/docs-api/methods/DELETE/messages

        Args:
            message_id (str): ID сообщения.

        Returns:
            DeletedMessage: Результат удаления.
        """

        return await DeleteMessage(
            bot=self,
            message_id=message_id,
        ).fetch()

    async def delete_chat(self, chat_id: int) -> DeletedChat:
        """
        Удаляет чат.

        https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-

        Args:
            chat_id (int): ID чата.

        Returns:
            DeletedChat: Результат удаления чата.
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

        https://dev.max.ru/docs-api/methods/GET/messages

        Args:
            chat_id (Optional[int]): ID чата.
            message_ids (Optional[List[str]]): ID сообщений.
            from_time (Optional[datetime | int]): Начало периода.
            to_time (Optional[datetime | int]): Конец периода.
            count (int): Количество сообщений.

        Returns:
            Messages: Список сообщений.
        """

        return await GetMessages(
            bot=self,
            chat_id=chat_id,
            message_ids=message_ids,
            from_time=from_time,
            to_time=to_time,
            count=count,
        ).fetch()

    async def get_message(self, message_id: str) -> Message:
        """
        Получает одно сообщение по ID.

        https://dev.max.ru/docs-api/methods/GET/messages/-messageId-

        Args:
            message_id (str): ID сообщения.

        Returns:
            Message: Объект сообщения.
        """

        return await GetMessage(bot=self, message_id=message_id).fetch()

    async def get_me(self) -> User:
        """
        Получает информацию о текущем боте.

        https://dev.max.ru/docs-api/methods/GET/me

        Returns:
            User: Объект пользователя бота.
        """

        return await GetMe(self).fetch()

    async def get_pin_message(self, chat_id: int) -> GettedPin:
        """
        Получает закрепленное сообщение в чате.

        https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/pin

        Args:
            chat_id (int): ID чата.

        Returns:
            GettedPin: Закрепленное сообщение.
        """

        return await GetPinnedMessage(bot=self, chat_id=chat_id).fetch()

    async def change_info(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        description: Optional[str] = None,
        commands: Optional[List[BotCommand]] = None,
        photo: Optional[PhotoAttachmentRequestPayload] = None,
    ) -> User:
        """
        Изменяет данные текущего бота (PATCH /me).

        .. deprecated:: 0.9.8
            Этот метод отсутствует в официальной swagger-спецификации API MAX.
            Использование не рекомендуется.

        https://dev.max.ru/docs-api/methods/PATCH/me

        Args:
            first_name (Optional[str]): Новое имя бота (1–64 символа).
            last_name (str, optional): Второе имя бота (1–64 символа).
            description (Optional[str]): Новое описание бота (1–16000 символов).
            commands (Optional[List[BotCommand]]): Список команд бота (до 32 элементов).
                Передайте пустой список, чтобы удалить все команды.
            photo (Optional[PhotoAttachmentRequestPayload]): Новое фото бота.

        Returns:
            User: Объект с обновлённой информацией о боте.
        """

        warnings.warn(
            "bot.change_info() устарел и отсутствует в официальной swagger-спецификации API MAX. "
            "Использование не рекомендуется.",
            DeprecationWarning,
            stacklevel=2,
        )

        return await ChangeInfo(
            bot=self,
            first_name=first_name,
            last_name=last_name,
            description=description,
            commands=commands,
            photo=photo,
        ).fetch()

    async def get_chats(
        self, count: Optional[int] = None, marker: Optional[int] = None
    ) -> Chats:
        """
        Получает список чатов бота.

        https://dev.max.ru/docs-api/methods/GET/chats

        Args:
            count (Optional[int]): Количество чатов (по умолчанию 50) (1-100).
            marker (Optional[int]): Маркер для пагинации.

        Returns:
            Chats: Список чатов.
        """

        return await GetChats(bot=self, count=count, marker=marker).fetch()

    async def get_chat_by_link(self, link: str) -> Chat:
        """
        Получает чат по ссылке.

        https://dev.max.ru/docs-api/methods/GET/chats/-chatLink-

        Args:
            link (str): Ссылка на чат.

        Returns:
            Chat: Объект чата.
        """

        return await GetChatByLink(bot=self, link=link).fetch()

    async def get_chat_by_id(self, id: int) -> Chat:
        """
        Получает чат по ID.

        https://dev.max.ru/docs-api/methods/GET/chats/-chatId-

        Args:
            id (int): ID чата.

        Returns:
            Chat: Объект чата.
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
        Редактирует информацию о чате.

        https://dev.max.ru/docs-api/methods/PATCH/chats/-chatId-

        Args:
            chat_id (int): ID чата.
            icon (Optional[PhotoAttachmentRequestPayload]): Иконка.
            title (Optional[str]): Новый заголовок (1-200 символов).
            pin (Optional[str]): ID сообщения для закрепления.
            notify (Optional[bool]): Флаг уведомления.

        Returns:
            Chat: Обновленный объект чата.
        """

        return await EditChat(
            bot=self,
            chat_id=chat_id,
            icon=icon,
            title=title,
            pin=pin,
            notify=self._resolve_notify(notify),
        ).fetch()

    async def get_video(self, video_token: str) -> Video:
        """
        Получает видео по токену.

        https://dev.max.ru/docs-api/methods/GET/videos/-videoToken-

        Args:
            video_token (str): Токен видео.

        Returns:
            Video: Объект видео.
        """

        return await GetVideo(bot=self, video_token=video_token).fetch()

    async def send_callback(
        self,
        callback_id: str,
        message: Optional[MessageForCallback] = None,
        notification: Optional[str] = None,
    ) -> SendedCallback:
        """
        Отправляет callback ответ.

        https://dev.max.ru/docs-api/methods/POST/answers

        Args:
            callback_id (str): ID callback.
            message (Optional[MessageForCallback]): Сообщение для отправки.
            notification (Optional[str]): Текст уведомления.

        Returns:
            SendedCallback: Результат отправки callback.
        """

        return await SendCallback(
            bot=self,
            callback_id=callback_id,
            message=message,
            notification=notification,
        ).fetch()

    async def pin_message(
        self, chat_id: int, message_id: str, notify: Optional[bool] = None
    ) -> PinnedMessage:
        """
        Закрепляет сообщение в чате.

        https://dev.max.ru/docs-api/methods/PUT/chats/-chatId-/pin

        Args:
            chat_id (int): ID чата.
            message_id (str): ID сообщения.
            notify (Optional[bool]): Флаг уведомления.

        Returns:
            PinnedMessage: Закрепленное сообщение.
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

        https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/pin

        Args:
            chat_id (int): ID чата.

        Returns:
            DeletedPinMessage: Результат удаления.
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
        Получает информацию о боте в чате.

        https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members/me

        Args:
            chat_id (int): ID чата.

        Returns:
            ChatMember: Информация о боте в чате.
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

        https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/me

        Args:
            chat_id (int): ID чата.

        Returns:
            DeletedBotFromChat: Результат удаления.
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

        https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members/admins

        Args:
            chat_id (int): ID чата.

        Returns:
            GettedListAdminChat: Список администраторов.
        """

        return await GetListAdminChat(
            bot=self,
            chat_id=chat_id,
        ).fetch()

    async def add_list_admin_chat(
        self,
        chat_id: int,
        admins: List[ChatAdmin],
        marker: Optional[int] = None,
    ) -> AddedListAdminChat:
        """
        Добавляет администраторов в чат.

        https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/members/admins

        Args:
            chat_id (int): ID чата.
            admins (List[ChatAdmin]): Список администраторов.
            marker (Optional[int]): Маркер для пагинации.

        Returns:
            AddedListAdminChat: Результат добавления.
        """

        return await AddAdminChat(
            bot=self,
            chat_id=chat_id,
            admins=admins,
            marker=marker,
        ).fetch()

    async def remove_admin(self, chat_id: int, user_id: int) -> RemovedAdmin:
        """
        Удаляет администратора из чата.

        https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId-

        Args:
            chat_id (int): ID чата.
            user_id (int): ID пользователя.

        Returns:
            RemovedAdmin: Результат удаления.
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

        https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members

        Args:
            chat_id (int): ID чата.
            user_ids (Optional[List[int]]): Список ID участников.
            marker (Optional[int]): Маркер для пагинации.
            count (Optional[int]): Количество участников (по умолчанию 20) (1-100).

        Returns:
            GettedMembersChat: Список участников.
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

        https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members

        Args:
            chat_id (int): ID чата.
            user_id (int): ID участника.

        Returns:
            Optional[ChatMember]: Участник.
        """

        members = await self.get_chat_members(
            chat_id=chat_id, user_ids=[user_id]
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

        https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/members

        Args:
            chat_id (int): ID чата.
            user_ids (List[int]): Список ID пользователей.

        Returns:
            AddedMembersChat: Результат добавления.
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

        https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members

        Args:
            chat_id (int): ID чата.
            user_id (int): ID пользователя.
            block (bool): Блокировать пользователя (по умолчанию False).

        Returns:
            RemovedMemberChat: Результат исключения.
        """

        return await RemoveMemberChat(
            bot=self,
            chat_id=chat_id,
            user_id=user_id,
            block=block,
        ).fetch()

    async def get_updates(
        self,
        limit: Optional[int] = None,
        timeout: Optional[int] = None,
        marker: Optional[int] = None,
        types: Optional[Sequence[UpdateType]] = None,
    ) -> Dict:
        """
        Получает обновления для бота.

        https://dev.max.ru/docs-api/methods/GET/updates

        Returns:
            Dict: Список обновлений.
        """

        return await GetUpdates(
            bot=self, limit=limit, marker=marker, types=types, timeout=timeout
        ).fetch()

    async def get_upload_url(self, type: UploadType) -> GettedUploadUrl:
        """
        Получает URL для загрузки файлов.

        https://dev.max.ru/docs-api/methods/POST/uploads

        Args:
            type (UploadType): Тип загружаемого файла.

        Returns:
            GettedUploadUrl: URL для загрузки.
        """

        return await GetUploadURL(bot=self, type=type).fetch()

    async def set_my_commands(self, *commands: BotCommand) -> User:
        """
        Устанавливает список команд бота.

        Args:
            *commands (BotCommand): Список команд.

        Returns:
            User: Обновленная информация о боте.
        """

        warnings.warn(
            "bot.change_info() устарел и отсутствует в официальной swagger-спецификации API MAX. "
            "Использование не рекомендуется.",
            DeprecationWarning,
            stacklevel=2,
        )

        return await ChangeInfo(bot=self, commands=list(commands)).fetch()

    async def get_subscriptions(self) -> GettedSubscriptions:
        """
        Получает список всех подписок.

        https://dev.max.ru/docs-api/methods/GET/subscriptions

        Returns:
            GettedSubscriptions: Объект со списком подписок.
        """

        return await GetSubscriptions(bot=self).fetch()

    async def subscribe_webhook(
        self,
        url: str,
        update_types: Optional[List[UpdateType]] = None,
        secret: Optional[str] = None,
    ) -> Subscribed:
        """
        Подписывает бота на получение обновлений через WebHook.

        https://dev.max.ru/docs-api/methods/POST/subscriptions

        Args:
            url (str): URL HTTP(S)-эндпойнта вашего бота.
            update_types (Optional[List[UpdateType]]): Список типов обновлений.
            secret (Optional[str]): Секрет для Webhook (5-256 симолов).

        Returns:
            Subscribed: Результат подписки.
        """

        return await SubscribeWebhook(
            bot=self, url=url, update_types=update_types, secret=secret
        ).fetch()

    async def unsubscribe_webhook(
        self,
        url: str,
    ) -> Unsubscribed:
        """
        Отписывает бота от получения обновлений через WebHook.

        https://dev.max.ru/docs-api/methods/DELETE/subscriptions

        Args:
            url (str): URL HTTP(S)-эндпойнта вашего бота.

        Returns:
            Unsubscribed: Результат отписки.
        """

        return await UnsubscribeWebhook(
            bot=self,
            url=url,
        ).fetch()

    async def delete_webhook(self) -> None:
        """
        Удаляет все подписки на Webhook.

        https://dev.max.ru/docs-api/methods/DELETE/subscriptions

        Returns:
            None
        """

        subs = await self.get_subscriptions()
        if subs.subscriptions:
            for sub in subs.subscriptions:
                await self.unsubscribe_webhook(sub.url)
                logger_bot.info("Удалена подписка на Webhook: %s", sub.url)
