from unittest.mock import Mock, patch

from maxapi.connection.base import BaseConnection
from maxapi.enums.chat_type import ChatType
from maxapi.enums.format import Format
from maxapi.enums.parse_mode import TextFormat
from maxapi.methods.edit_message import EditMessage
from maxapi.methods.send_message import SendMessage
from maxapi.types.message import Message


def test_format_alias_import():
    assert Format is TextFormat


def test_bot_send_message_passes_format(bot):
    from maxapi import bot as bot_module

    send_message_instance = Mock()
    send_message_instance.fetch = Mock(return_value=Mock())

    with patch.object(
        bot_module, "SendMessage", return_value=send_message_instance
    ) as mocked_send_message:
        bot.send_message(chat_id=1, text="hello", format=TextFormat.HTML)

    called_kwargs = mocked_send_message.call_args.kwargs
    assert called_kwargs["format"] == TextFormat.HTML


def test_bot_edit_message_passes_format(bot):
    from maxapi import bot as bot_module

    edit_message_instance = Mock()
    edit_message_instance.fetch = Mock(return_value=Mock())

    with patch.object(
        bot_module, "EditMessage", return_value=edit_message_instance
    ) as mocked_edit_message:
        bot.edit_message(
            message_id="msg_1", text="hello", format=TextFormat.MARKDOWN
        )

    called_kwargs = mocked_edit_message.call_args.kwargs
    assert called_kwargs["format"] == TextFormat.MARKDOWN


def test_send_message_fetch_uses_format_in_json(bot):
    method = SendMessage(
        bot=bot,
        chat_id=1,
        text="hello",
        format=TextFormat.HTML,
    )

    with patch.object(
        BaseConnection, "request", return_value=Mock()
    ) as mocked_request:
        method.fetch()

    request_kwargs = mocked_request.call_args.kwargs
    assert request_kwargs["json"]["format"] == TextFormat.HTML.value


def test_edit_message_fetch_uses_format_in_json(bot):
    method = EditMessage(
        bot=bot,
        message_id="msg_1",
        text="hello",
        format=TextFormat.MARKDOWN,
    )

    with patch.object(
        BaseConnection, "request", return_value=Mock()
    ) as mocked_request:
        method.fetch()

    request_kwargs = mocked_request.call_args.kwargs
    assert request_kwargs["json"]["format"] == TextFormat.MARKDOWN.value


def test_send_message_format_as_string(bot):
    method = SendMessage(
        bot=bot,
        chat_id=1,
        text="hello",
        format="html",
    )

    with patch.object(
        BaseConnection, "request", return_value=Mock()
    ) as mocked_request:
        method.fetch()

    request_kwargs = mocked_request.call_args.kwargs
    assert request_kwargs["json"]["format"] == "html"


def test_edit_message_format_as_string(bot):
    method = EditMessage(
        bot=bot,
        message_id="msg_1",
        text="hello",
        format="markdown",
    )

    with patch.object(
        BaseConnection, "request", return_value=Mock()
    ) as mocked_request:
        method.fetch()

    request_kwargs = mocked_request.call_args.kwargs
    assert request_kwargs["json"]["format"] == "markdown"


def test_send_message_init_converts_string_to_enum(bot):
    """Проверка обратной совместимости: format может быть строкой."""
    msg = SendMessage(bot=bot, chat_id=1, text="привет", format="html")
    assert msg.format == TextFormat.HTML
    assert msg.format is not None
    assert msg.format.value == "html"


def test_edit_message_init_converts_string_to_enum(bot):
    """Проверка обратной совместимости: format может быть строкой."""
    msg = EditMessage(
        bot=bot, message_id="m1", text="привет", format="markdown"
    )
    assert msg.format == TextFormat.MARKDOWN
    assert msg.format is not None
    assert msg.format.value == "markdown"


def test_send_message_text_none_absent_from_json(bot):
    method = SendMessage(
        bot=bot,
        chat_id=1,
        text=None,
    )

    with patch.object(
        BaseConnection, "request", return_value=Mock()
    ) as mocked_request:
        method.fetch()

    request_kwargs = mocked_request.call_args.kwargs
    assert "text" not in request_kwargs["json"]


def test_message_helpers_pass_format_to_bot():
    bot = Mock()
    bot.send_message = Mock(return_value=Mock())
    bot.edit_message = Mock(return_value=Mock())

    message = Message.model_validate(
        {
            "recipient": {
                "user_id": 1,
                "chat_id": 2,
                "chat_type": ChatType.CHAT.value,
            },
            "timestamp": 1,
            "body": {"mid": "msg_1", "seq": 1, "text": "hello"},
        }
    )
    message.bot = bot

    message.answer(text="a", format=TextFormat.MARKDOWN)
    message.reply(text="b", format=TextFormat.HTML)
    message.forward(chat_id=3, format=TextFormat.MARKDOWN)
    message.edit(text="c", format=TextFormat.HTML)

    assert bot.send_message.call_count == 3
    assert bot.edit_message.call_count == 1

    answer_call = bot.send_message.call_args_list[0].kwargs
    reply_call = bot.send_message.call_args_list[1].kwargs
    forward_call = bot.send_message.call_args_list[2].kwargs
    edit_call = bot.edit_message.call_args_list[0].kwargs

    assert answer_call["format"] == TextFormat.MARKDOWN
    assert reply_call["format"] == TextFormat.HTML
    assert forward_call["format"] == TextFormat.MARKDOWN
    assert edit_call["format"] == TextFormat.HTML
