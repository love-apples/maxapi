import logging

from maxapi.context.state_machine import State
from maxapi.enums.update import UpdateType
from maxapi.filters.handler import Handler


def test_handler_init_states_variations():
    async def h(event):
        pass

    s = State()
    handler = Handler(
        func_event=h, update_type=UpdateType.MESSAGE_CREATED, states=s
    )
    assert handler.states == [s]

    handler2 = Handler(
        func_event=h, update_type=UpdateType.MESSAGE_CREATED, states=[s]
    )
    assert handler2.states == [s]

    handler3 = Handler(s, func_event=h, update_type=UpdateType.MESSAGE_CREATED)
    assert handler3.states == [s]


def test_handler_unknown_filter(caplog):
    async def h(event):
        pass

    with caplog.at_level(logging.INFO):
        Handler(
            "unknown", func_event=h, update_type=UpdateType.MESSAGE_CREATED
        )
        assert "Неизвестный фильтр `unknown`" in caplog.text
