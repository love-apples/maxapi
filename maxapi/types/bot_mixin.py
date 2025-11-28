from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..bot import Bot


class BotMixin:
    """Миксин для проверки инициализации bot."""

    bot: Any

    def _ensure_bot(self) -> "Bot":
        """
        Проверяет, что bot инициализирован, и возвращает его.

        Returns:
            Bot: Объект бота.

        Raises:
            RuntimeError: Если bot не инициализирован.
        """

        if self.bot is None:
            raise RuntimeError("Bot не инициализирован")

        return self.bot  # type: ignore
