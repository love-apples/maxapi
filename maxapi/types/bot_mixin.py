from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import Bot


class BotMixin:
    """Миксин для проверки инициализации bot."""

    def _ensure_bot(self) -> "Bot":
        """
        Проверяет, что bot инициализирован, и возвращает его.

        Returns:
            Bot: Объект бота.

        Raises:
            RuntimeError: Если bot не инициализирован.
        """

        bot = getattr(self, "bot", None)
        if bot is None:
            raise RuntimeError("Bot не инициализирован")

        return bot  # type: ignore
