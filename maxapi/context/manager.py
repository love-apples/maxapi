from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from ..dispatcher import Dispatcher
    from .base import BaseContext
    from .state_machine import State


class ContextManager:
    """
    Высокоуровневый доступ к контекстам диспетчера.
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        context_getter: Callable[[int | None, int | None], BaseContext],
    ) -> None:
        self.dispatcher = dispatcher
        self._context_getter = context_getter

    def _get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        """Возвращает контекст по идентификаторам."""
        return self._context_getter(chat_id, user_id)

    def get_context(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
    ) -> BaseContext:
        """
        Возвращает контекст пользователя по идентификаторам.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.

        Returns:
            Контекст.
        """
        return self._get_context(chat_id, user_id)

    async def set_state(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        state: State | str | None = None,
    ) -> None:
        """
        Устанавливает состояние пользователя.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.
            state: Новое состояние или None для сброса.
        """
        context = self._get_context(chat_id, user_id)
        await context.set_state(state)

    async def get_state(
        self, *, chat_id: int | None, user_id: int | None
    ) -> State | str | None:
        """
        Возвращает состояние пользователя.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.

        Returns:
            Текущее состояние или None.
        """
        context = self._get_context(chat_id, user_id)
        return await context.get_state()

    async def set_data(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        data: dict[str, Any],
    ) -> None:
        """
        Полностью заменяет данные пользователя.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.
            data: Новый словарь контекста.
        """
        context = self._get_context(chat_id, user_id)
        await context.set_data(data)

    async def get_data(
        self, *, chat_id: int | None, user_id: int | None
    ) -> dict[str, Any]:
        """
        Возвращает данные пользователя.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.

        Returns:
            Словарь с данными контекста.
        """
        context = self._get_context(chat_id, user_id)
        return await context.get_data()

    async def update_data(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Обновляет данные пользователя.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.
            data: Словарь значений для обновления.
            **kwargs: Пары ключ-значение для обновления.

        Returns:
            Актуальный словарь данных.
        """
        context = self._get_context(chat_id, user_id)
        update = dict(data or {})
        update.update(kwargs)
        return await context.update_data(**update)

    async def clear(self, *, chat_id: int | None, user_id: int | None) -> None:
        """
        Очищает данные и состояние пользователя.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.
        """
        context = self._get_context(chat_id, user_id)
        await context.clear()
