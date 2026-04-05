"""Регрессионный тест: Literal-дискриминация MarkupLink / MarkupUserMention.

До исправления (Python 3.10 + old Enum) все элементы markup с type="link"
десериализовались как MarkupElement вместо MarkupLink, из-за чего
терялось поле url. Аналогично для type="user_mention" / MarkupUserMention.

Ссылка на отчёт: TextStyle был plain Enum, из-за этого Pydantic v2
не мог корректно выбрать подкласс в union по Literal-дискриминатору.
После перехода на StrEnum (с _compat-бэкпортом для Python 3.10)
дискриминация работает корректно на всех поддерживаемых версиях Python.
"""

import pytest
from maxapi.enums.text_style import TextStyle
from maxapi.types.message import (
    MarkupElement,
    MarkupLink,
    MarkupUserMention,
    MessageBody,
)


@pytest.fixture
def message_body_with_links() -> MessageBody:
    """MessageBody с элементами link и user_mention в markup."""
    return MessageBody.model_validate(
        {
            "mid": "msg_regression_001",
            "seq": 1,
            "text": (
                "Привет! Вот ссылка https://example.com и ещё одна "
                "https://other.com, а также упоминание пользователя."
            ),
            "markup": [
                # ссылки — должны стать MarkupLink
                {
                    "type": "link",
                    "from": 119,
                    "length": 26,
                },
                {
                    "type": "link",
                    "from": 409,
                    "length": 10,
                    "url": "https://example.com",
                },
                {
                    "type": "link",
                    "from": 422,
                    "length": 19,
                    "url": "https://other.com",
                },
                # упоминание — должно стать MarkupUserMention
                {
                    "type": "user_mention",
                    "from": 0,
                    "length": 5,
                    "user_id": 12345,
                },
                # жирный — должен остаться MarkupElement
                {"type": "strong", "from": 3, "length": 32},
            ],
        }
    )


def test_link_markup_deserialized_as_markup_link(
    message_body_with_links,
):
    """type='link' должен давать MarkupLink, не MarkupElement.

    Регрессия: клиент сообщил, что элементы с type='link'
    возвращались как MarkupElement и не имели поля url.
    """
    assert message_body_with_links.markup is not None

    link_elements = [
        m for m in message_body_with_links.markup if m.type == TextStyle.LINK
    ]

    assert len(link_elements) == 3, (
        f"Ожидалось 3 элемента с type=link, получено {len(link_elements)}"
    )

    for m in link_elements:
        assert isinstance(m, MarkupLink), (
            f"Элемент с type='link' должен быть "
            f"MarkupLink, получен {type(m).__name__}. "
            f"Регрессия: Literal[TextStyle.LINK] в "
            f"MarkupLink не работает как "
            f"дискриминатор union."
        )
        assert hasattr(m, "url"), (
            f"MarkupLink должен иметь поле 'url', "
            f"но оно отсутствует. Тип: "
            f"{type(m).__name__}"
        )


def test_user_mention_markup_deserialized(
    message_body_with_links,
):
    """type='user_mention' → MarkupUserMention.

    Регрессия: аналогичная проблема для
    Literal[TextStyle.USER_MENTION].
    """
    assert message_body_with_links.markup is not None

    mention_elements = [
        m
        for m in message_body_with_links.markup
        if m.type == TextStyle.USER_MENTION
    ]

    assert len(mention_elements) == 1

    m = mention_elements[0]
    assert isinstance(m, MarkupUserMention), (
        f"Элемент с type='user_mention' должен быть "
        f"MarkupUserMention, "
        f"получен {type(m).__name__}."
    )
    assert hasattr(m, "user_id"), (
        "MarkupUserMention должен иметь поле 'user_id'"
    )


def test_strong_markup_remains_markup_element(
    message_body_with_links,
):
    """type='strong' — нет подкласса, MarkupElement."""
    assert message_body_with_links.markup is not None

    strong_elements = [
        m for m in message_body_with_links.markup if m.type == TextStyle.STRONG
    ]

    assert len(strong_elements) == 1
    assert type(strong_elements[0]) is MarkupElement


def test_markup_link_url_preserved_from_api(
    message_body_with_links,
):
    """url из API-ответа сохраняется в MarkupLink.url."""
    assert message_body_with_links.markup is not None

    links_with_url = [
        m
        for m in message_body_with_links.markup
        if isinstance(m, MarkupLink) and m.url is not None
    ]

    assert len(links_with_url) == 2
    urls = {m.url for m in links_with_url}
    assert "https://example.com" in urls
    assert "https://other.com" in urls


def test_markup_link_without_url_is_still_markup_link(
    message_body_with_links,
):
    """MarkupLink без url → MarkupLink(url=None)."""
    assert message_body_with_links.markup is not None

    links_without_url = [
        m
        for m in message_body_with_links.markup
        if isinstance(m, MarkupLink) and m.url is None
    ]

    assert len(links_without_url) == 1, (
        "Элемент link без url должен десериализоваться"
        " как MarkupLink с url=None, "
        "а не как MarkupElement."
    )
