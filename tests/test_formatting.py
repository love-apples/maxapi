from maxapi.enums.text_style import TextStyle
from maxapi.types.message import MessageBody
from maxapi.utils.formatting import (
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

    assert Heading("text").as_html() == "<b>text</b>"
    assert Heading("text").as_markdown() == "### text"


def test_link_and_mention():
    link = Link("google", url="https://google.com")
    assert link.as_html() == '<a href="https://google.com">google</a>'
    assert link.as_markdown() == "[google](https://google.com)"

    mention = UserMention("Alice")
    assert mention.as_html() == '<a href="max://user/Alice">Alice</a>'
    assert mention.as_markdown() == "[Alice](max://user/Alice)"


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
    assert h.as_markdown() == "### Title"
    assert h.as_html() == "<b>Title</b>"


def test_all_styles_in_body():
    styles = [
        (TextStyle.STRONG, "**", "b"),
        (TextStyle.EMPHASIZED, "*", "i"),
        (TextStyle.UNDERLINE, "++", "ins"),
        (TextStyle.STRIKETHROUGH, "~~", "s"),
        (TextStyle.MONOSPACED, "`", "code"),
    ]
    for style, md, html in styles:
        data = {
            "mid": "t",
            "seq": 1,
            "text": "txt",
            "markup": [{"from": 0, "length": 3, "type": style}],
        }
        body = MessageBody(**data)
        assert body.md_text == f"{md}txt{md}"
        assert body.html_text == f"<{html}>txt</{html}>"


def test_heading_in_body():
    data = {
        "mid": "t",
        "seq": 1,
        "text": "Title",
        "markup": [{"from": 0, "length": 5, "type": TextStyle.HEADING}],
    }
    body = MessageBody(**data)
    assert body.md_text == "### Title"
    assert body.html_text == "<b>Title</b>"


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
        "markup": [{"from": 0, "length": 5, "type": TextStyle.USER_MENTION}],
    }
    body = MessageBody(**data)
    assert body.md_text == "[Alice](max://user/Alice)"
    assert body.html_text == '<a href="max://user/Alice">Alice</a>'
