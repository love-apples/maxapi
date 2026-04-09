from maxapi.enums.text_style import TextStyle
from maxapi.types.message import MessageBody
from maxapi.utils.formatting import (
    Blockquote,
    Bold,
    Code,
    Heading,
    Italic,
    Link,
    Strikethrough,
    Text,
    Underline,
    UserMention,
    as_html,
    as_markdown,
)


def test_basic_formatting():
    assert Bold("text").as_html() == "<b>text</b>"
    assert Bold("text").as_markdown() == "**text**"

    assert Italic("text").as_html() == "<i>text</i>"
    assert Italic("text").as_markdown() == "*text*"

    assert Underline("text").as_html() == "<ins>text</ins>"
    assert Underline("text").as_markdown() == "++text++"

    assert Strikethrough("text").as_html() == "<s>text</s>"
    assert Strikethrough("text").as_markdown() == "~~text~~"

    assert Code("text").as_html() == "<code>text</code>"
    assert Code("text").as_markdown() == "`text`"

    assert Heading("text").as_html() == "<h1>text</h1>"
    assert Heading("text").as_markdown() == "# text"

    assert Blockquote("text").as_html() == "<blockquote>text</blockquote>"
    assert Blockquote("text").as_markdown() == "> text"


def test_link_and_mention():
    link = Link("google", url="https://google.com")
    assert link.as_html() == '<a href="https://google.com">google</a>'
    assert link.as_markdown() == "[google](https://google.com)"

    mention = UserMention("Alice", user_id=1)
    assert mention.as_html() == '<a href="max://user/1">Alice</a>'
    assert mention.as_markdown() == "[Alice](max://user/1)"


def test_text_container():
    t = Text("Hello, ", Bold("world"), "!")
    assert t.as_html() == "Hello, <b>world</b>!"
    assert t.as_markdown() == "Hello, **world**!"
    assert str(t) == "Hello, world!"


def test_nested_formatting():
    t = Bold(Italic("bold italic"))
    assert t.as_html() == "<b><i>bold italic</i></b>"
    assert t.as_markdown() == "***bold italic***"


def test_markdown_space_handling():
    assert Bold(" text ").as_markdown() == " **text** "
    assert Italic("  italic\n").as_markdown() == "  *italic*\n"
    assert Bold("   ").as_markdown() == "   "
    assert Bold("").as_markdown() == ""


def test_html_escaping():
    assert Bold("<script>").as_html() == "<b>&lt;script&gt;</b>"
    expected = '<a href="http://x?a=1&amp;b=2">a &amp; b</a>'
    assert Link("a & b", url="http://x?a=1&b=2").as_html() == expected


def test_markdown_escaping():
    assert Bold("*star*").as_markdown() == "**\\*star\\***"


def test_as_helpers():
    assert as_html("a", Bold("b")) == "a<b>b</b>"
    assert as_markdown("a", Bold("b")) == "a**b**"


def test_message_body_integration():
    data = {
        "mid": "test",
        "seq": 1,
        "text": "Hello world",
        "markup": [
            {"from": 0, "length": 5, "type": TextStyle.STRONG},
            {"from": 6, "length": 5, "type": TextStyle.EMPHASIZED},
        ],
    }
    body = MessageBody(**data)
    assert body.html_text == "<b>Hello</b> <i>world</i>"
    assert body.md_text == "**Hello** *world*"

    data_complex = {
        "mid": "test2",
        "seq": 2,
        "text": "abcde",
        "markup": [
            {"from": 0, "length": 3, "type": TextStyle.STRONG},  # abc
            {"from": 2, "length": 3, "type": TextStyle.EMPHASIZED},  # cde
        ],
    }
    body_complex = MessageBody(**data_complex)
    assert body_complex.html_text == "<b>ab</b><b><i>c</i></b><i>de</i>"
    assert body_complex.md_text == "**ab*****c****de*"


def test_message_body_empty():
    body = MessageBody(mid="1", seq=1, text="plain")
    assert body.html_text == "plain"
    assert body.md_text == "plain"
    assert body.text_decorated.as_html() == "plain"


def test_message_body_none_text():
    body = MessageBody(mid="1", seq=1, text=None)
    assert body.html_text is None
    assert body.md_text is None
    assert body.text_decorated is None


def test_magic_methods():
    b = Bold("b")
    i = Italic("i")
    text = b + i
    assert text.as_html() == "<b>b</b><i>i</i>"

    text2 = "plain " + b
    assert text2.as_html() == "plain <b>b</b>"

    assert b == Bold("b")
    assert b != Bold("c")
    assert b != i

    assert repr(b) == "Bold(Text(_Plain('b')))"
    assert repr(Code("c")) == "Code(Text(_Plain('c')))"
    assert repr(Text("a", "b")) == "Text(_Plain('a'), _Plain('b'))"


def test_heading_markdown():
    h = Heading("Title")
    assert h.as_markdown() == "# Title"
    assert h.as_html() == "<h1>Title</h1>"


def test_blockquote_markdown_multiline():
    q = Blockquote("first\nsecond\n\nthird")
    assert q.as_markdown() == "> first\n> second\n>\n> third"
    assert q.as_html() == "<blockquote>first\nsecond\n\nthird</blockquote>"


def test_blockquote_markdown_empty():
    q = Blockquote("")
    assert q.as_markdown() == ""
    assert q.as_html() == "<blockquote></blockquote>"


def test_all_styles_in_body():
    styles = [
        (TextStyle.STRONG, "**", "b"),
        (TextStyle.EMPHASIZED, "*", "i"),
        (TextStyle.UNDERLINE, "++", "ins"),
        (TextStyle.STRIKETHROUGH, "~~", "s"),
        (TextStyle.MONOSPACED, "`", "code"),
        (TextStyle.BLOCKQUOTE, "> ", "blockquote"),
    ]
    for style, md, html in styles:
        data = {
            "mid": "t",
            "seq": 1,
            "text": "txt",
            "markup": [{"from": 0, "length": 3, "type": style}],
        }
        body = MessageBody(**data)
        expected_md = (
            f"{md}txt{md}" if style != TextStyle.BLOCKQUOTE else "> txt"
        )
        assert body.html_text == f"<{html}>txt</{html}>"
        assert body.md_text == expected_md


def test_heading_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Title",
        "markup": [{"from": 0, "length": 5, "type": TextStyle.HEADING}],
    }
    body = MessageBody(**data)
    assert body.md_text == "# Title"
    assert body.html_text == "<h1>Title</h1>"


def test_blockquote_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Quote",
        "markup": [{"from": 0, "length": 5, "type": TextStyle.BLOCKQUOTE}],
    }
    body = MessageBody(**data)
    assert body.md_text == "> Quote"
    assert body.html_text == "<blockquote>Quote</blockquote>"


def test_blockquote_wraps_heading_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Title",
        "markup": [
            {"from": 0, "length": 5, "type": TextStyle.BLOCKQUOTE},
            {"from": 0, "length": 5, "type": TextStyle.HEADING},
        ],
    }
    body = MessageBody(**data)
    assert body.md_text == "> # Title"
    assert body.html_text == "<blockquote><h1>Title</h1></blockquote>"


def test_blockquote_wraps_strong_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Quote",
        "markup": [
            {"from": 0, "length": 5, "type": TextStyle.BLOCKQUOTE},
            {"from": 0, "length": 5, "type": TextStyle.STRONG},
        ],
    }
    body = MessageBody(**data)
    assert body.md_text == "> **Quote**"
    assert body.html_text == "<blockquote><b>Quote</b></blockquote>"


def test_link_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "google",
        "markup": [
            {
                "from": 0,
                "length": 6,
                "type": TextStyle.LINK,
                "url": "https://g.co",
            }
        ],
    }
    body = MessageBody(**data)
    assert body.md_text == "[google](https://g.co)"
    assert body.html_text == '<a href="https://g.co">google</a>'


def test_mention_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Alice",
        "markup": [
            {
                "from": 0,
                "length": 5,
                "type": TextStyle.USER_MENTION,
                "user_id": 42,
            }
        ],
    }
    body = MessageBody(**data)
    assert body.md_text == "[Alice](max://user/42)"
    assert body.html_text == '<a href="max://user/42">Alice</a>'


def test_mention_in_body_with_user_link():
    """MarkupUserMention может содержать user_link; парсинг и вывод ок."""
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Bob",
        "markup": [
            {
                "from": 0,
                "length": 3,
                "type": TextStyle.USER_MENTION,
                "user_id": 100,
                "user_link": "max://user/100",
            }
        ],
    }
    body = MessageBody(**data)
    assert body.md_text == "[Bob](max://user/100)"
    assert body.html_text == '<a href="max://user/100">Bob</a>'
    # Проверяем, что разметка распарсилась в MarkupUserMention с user_link
    assert len(body.markup) == 1
    mention = body.markup[0]
    assert mention.type == TextStyle.USER_MENTION
    assert getattr(mention, "user_id", None) == 100
    assert getattr(mention, "user_link", None) == "max://user/100"


def test_message_body_markup_uses_utf16_offsets_with_emoji():
    data = {
        "mid": "utf16-emoji",
        "seq": 1,
        "text": "🛒 Привет мир",
        "markup": [
            {"from": 3, "length": 6, "type": TextStyle.STRONG},  # Привет
            {"from": 10, "length": 3, "type": TextStyle.EMPHASIZED},  # мир
        ],
    }
    body = MessageBody(**data)
    assert body.html_text == "🛒 <b>Привет</b> <i>мир</i>"
    assert body.md_text == "🛒 **Привет** *мир*"


def test_message_body_user_mention_uses_utf16_offsets():
    data = {
        "mid": "utf16-mention",
        "seq": 1,
        "text": "🛒 Alice",
        "markup": [
            {
                "from": 3,
                "length": 5,
                "type": TextStyle.USER_MENTION,
                "user_id": 42,
            }
        ],
    }
    body = MessageBody(**data)
    assert body.md_text == "🛒 [Alice](max://user/42)"
    assert body.html_text == '🛒 <a href="max://user/42">Alice</a>'
