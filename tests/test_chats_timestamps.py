from datetime import datetime

import pydantic_core
import pytest
from maxapi.enums.chat_status import ChatStatus
from maxapi.enums.chat_type import ChatType
from maxapi.types.chats import Chat


def test_convert_timestamps_none():
    # participants is None — должно остаться None
    chat = Chat(
        chat_id=1,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=0,
        participants_count=1,
        is_public=False,
        participants=None,
    )

    assert chat.participants is None


def test_convert_timestamps_millis_to_datetime():
    # подготовим временные метки в миллисекундах
    now = datetime.now()
    ms = int(now.timestamp() * 1000)
    data = {"u1": ms, "u2": ms + 1000}

    chat = Chat(
        chat_id=2,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=0,
        participants_count=2,
        is_public=False,
        participants=data,
    )

    assert isinstance(chat.participants, dict)
    assert isinstance(chat.participants["u1"], datetime)
    # преобразованная datetime должна приблизительно соответствовать исходному времени
    assert abs((chat.participants["u1"] - now).total_seconds()) < 1
    assert (
        chat.participants["u2"] - chat.participants["u1"]
    ).total_seconds() == 1


def test_convert_timestamps_with_none_values_raises_validation_error():
    # Если некоторые метки времени равны None, валидация должна упасть,
    # поскольку значения participants типизированы как datetime (а не Optional[datetime]).
    data = {"u1": None, "u2": 1609459200000}
    with pytest.raises(pydantic_core.ValidationError):
        Chat(
            chat_id=3,
            type=ChatType.CHAT,
            status=ChatStatus.ACTIVE,
            last_event_time=0,
            participants_count=2,
            is_public=False,
            participants=data,
        )


def test_serialize_participants_datetime_to_millis():
    """Проверяем, что словарь participants с datetime значениями сериализуется в миллисекунды."""
    from datetime import timedelta

    now = datetime.now()
    later = now + timedelta(seconds=1)

    participants = {"u1": now, "u2": later}

    # Используем model_construct, чтобы избежать выполнения before-валидатора
    # и подставить datetime напрямую в participants для проверки сериализации.
    chat = Chat.model_construct(
        chat_id=4,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=0,
        participants_count=2,
        is_public=False,
        participants=participants,
    )

    dumped = chat.model_dump()
    assert isinstance(dumped["participants"], dict)
    a_ms = dumped["participants"]["u1"]
    b_ms = dumped["participants"]["u2"]
    assert isinstance(a_ms, int)
    assert isinstance(b_ms, int)
    # проверяем, что разница в миллисекундах равна 1000
    assert b_ms - a_ms == 1000


def test_serialize_participants_none_is_none():
    """Проверяем, что participants=None сериализуется как None."""
    chat = Chat(
        chat_id=5,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=0,
        participants_count=0,
        is_public=False,
        participants=None,
    )

    dumped = chat.model_dump()
    assert dumped["participants"] is None
