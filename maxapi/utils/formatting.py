from __future__ import annotations

from typing import Any

HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}
MD_ESCAPES = {
    "*": "\\*",
    "_": "\\_",
    "`": "\\`",
    "[": "\\[",
    "]": "\\]",
    "~": "\\~",
}


def _escape_html(text: str) -> str:
    """Экранирует символы HTML."""
    for ch, esc in HTML_ESCAPES.items():
        text = text.replace(ch, esc)
    return text


def _escape_md(text: str) -> str:
    """Экранирует спецсимволы Markdown."""
    for ch, esc in MD_ESCAPES.items():
        text = text.replace(ch, esc)
    return text


class _Node:
    """Базовый узел дерева форматирования."""

    def as_html(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def as_markdown(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def __add__(self, other: Any) -> Text:
        return Text(self, other)

    def __radd__(self, other: Any) -> Text:
        return Text(other, self)

    def __str__(self) -> str:
        """По умолчанию возвращает чистый текст без разметки."""
        return ""

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.__dict__ == other.__dict__

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class _Plain(_Node):
    """Простой текст без форматирования."""

    def __init__(self, text: Any) -> None:
        self._text = str(text)

    def as_html(self) -> str:
        return _escape_html(self._text)

    def as_markdown(self) -> str:
        return _escape_md(self._text)

    def __str__(self) -> str:
        return self._text

    def __repr__(self) -> str:
        return f"_Plain({self._text!r})"


class Text(_Node):
    """Контейнер — объединяет несколько элементов без обёрток.

    Пример::

        Text("Hello, ", Bold("world"), "!")
    """

    def __init__(self, *parts: Any) -> None:
        self._parts: list[_Node] = []
        for p in parts:
            if isinstance(p, _Node):
                if isinstance(p, Text):
                    self._parts.extend(p._parts)  # noqa: SLF001
                else:
                    self._parts.append(p)
            else:
                self._parts.append(_Plain(p))

    def as_html(self) -> str:
        return "".join(p.as_html() for p in self._parts)

    def as_markdown(self) -> str:
        return "".join(p.as_markdown() for p in self._parts)

    def __str__(self) -> str:
        return "".join(str(p) for p in self._parts)

    def __repr__(self) -> str:
        items = ", ".join(repr(p) for p in self._parts)
        return f"Text({items})"


class _Styled(_Node):
    """Базовый стилевой элемент с одним содержимым."""

    _html_open: str = ""
    _html_close: str = ""
    _md_open: str = ""
    _md_close: str = ""

    def __init__(self, *parts: Any) -> None:
        self._inner = Text(*parts)

    def as_html(self) -> str:
        return f"{self._html_open}{self._inner.as_html()}{self._html_close}"

    def as_markdown(self) -> str:
        inner = self._inner.as_markdown()
        if not inner.strip(" \t\n\r"):
            return inner

        lspace = len(inner) - len(inner.lstrip(" \t\n\r"))
        rspace = len(inner) - len(inner.rstrip(" \t\n\r"))

        left_sp = inner[:lspace] if lspace else ""
        right_sp = inner[-rspace:] if rspace else ""

        if lspace or rspace:
            content = inner[lspace : len(inner) - rspace]
        else:
            content = inner
        return f"{left_sp}{self._md_open}{content}{self._md_close}{right_sp}"

    def __str__(self) -> str:
        return str(self._inner)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._inner!r})"


class Bold(_Styled):
    """Жирный текст: ``<b>`` / ``**...**``."""

    _html_open = "<b>"
    _html_close = "</b>"
    _md_open = "**"
    _md_close = "**"


class Italic(_Styled):
    """Курсив: ``<i>`` / ``*...*``."""

    _html_open = "<i>"
    _html_close = "</i>"
    _md_open = "*"
    _md_close = "*"


class Underline(_Styled):
    """Подчёркнутый текст: ``<ins>`` / ``++...++``."""

    _html_open = "<ins>"
    _html_close = "</ins>"
    _md_open = "++"
    _md_close = "++"


class Strikethrough(_Styled):
    """Зачёркнутый текст: ``<s>`` / ``~~...~~``."""

    _html_open = "<s>"
    _html_close = "</s>"
    _md_open = "~~"
    _md_close = "~~"


class Code(_Styled):
    """Моноширинный (inline code): ``<code>`` / `` `...` ``."""

    _html_open = "<code>"
    _html_close = "</code>"
    _md_open = "`"
    _md_close = "`"


class Heading(_Styled):
    """Заголовок: ``<b>`` / ``### ...``."""

    _html_open = "<b>"
    _html_close = "</b>"
    _md_open = "### "
    _md_close = ""


class Link(_Node):
    """Гиперссылка: ``<a href="url">text</a>`` / ``[text](url)``.

    Args:
        text: Текст ссылки (строки или узлы форматирования).
        url: URL ссылки.
    """

    def __init__(self, *parts: Any, url: str) -> None:
        self._inner = Text(*parts)
        self._url = url

    def as_html(self) -> str:
        return (
            f'<a href="{_escape_html(self._url)}">{self._inner.as_html()}</a>'
        )

    def as_markdown(self) -> str:
        return f"[{self._inner.as_markdown()}]({self._url})"

    def __str__(self) -> str:
        return str(self._inner)

    def __repr__(self) -> str:
        return f"Link({self._inner!r}, url={self._url!r})"


class UserMention(_Node):
    """Упоминание пользователя по отображаемому тексту и user_id.

    В MAX API: ссылка ``max://user/<user_id>``, текст — полное имя.

    Args:
        display_text: Текст упоминания (полное имя: имя и фамилия,
            или только имя).
        user_id: ID пользователя для URL (max://user/user_id).
    """

    def __init__(self, display_text: Any, user_id: int) -> None:
        self._text = str(display_text)
        self._user_id = user_id

    def as_html(self) -> str:
        return (
            f'<a href="max://user/{self._user_id}">'
            f"{_escape_html(self._text)}</a>"
        )

    def as_markdown(self) -> str:
        return f"[{_escape_md(self._text)}](max://user/{self._user_id})"

    def __str__(self) -> str:
        return self._text

    def __repr__(self) -> str:
        return f"UserMention({self._text!r}, user_id={self._user_id!r})"


def as_html(*parts: Any) -> str:
    """Собирает HTML-строку из набора элементов.

    Пример::

        as_html("Hello, ", Bold("world"), "!")
        # 'Hello, <b>world</b>!'
    """
    return Text(*parts).as_html()


def as_markdown(*parts: Any) -> str:
    """Собирает Markdown-строку из набора элементов.

    Пример::

        as_markdown("Hello, ", Bold("world"), "!")
        # 'Hello, **world**!'
    """
    return Text(*parts).as_markdown()
