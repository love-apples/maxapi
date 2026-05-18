"""Тесты для фильтров и команд."""

from unittest.mock import Mock

import pytest

# Core Stuff
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import Command
from maxapi.filters.filter import BaseFilter
from maxapi.filters.state import StateFilter
from maxapi.types.updates.message_created import MessageCreated


class TestBaseFilter:
    """Тесты BaseFilter."""

    @pytest.mark.asyncio
    async def test_base_filter_default(self, sample_message_created_event):
        """Тест базового фильтра по умолчанию."""
        filter_obj = BaseFilter()
        result = await filter_obj(sample_message_created_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_custom_filter_return_true(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего True."""

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                return True

        filter_obj = TestFilter()
        result = await filter_obj(sample_message_created_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_custom_filter_return_false(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего False."""

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                return False

        filter_obj = TestFilter()
        result = await filter_obj(sample_message_created_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_filter_return_dict(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего словарь."""

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                return {"test_key": "test_value"}

        filter_obj = TestFilter()
        result = await filter_obj(sample_message_created_event)
        assert isinstance(result, dict)
        assert result["test_key"] == "test_value"


class TestStateFilter:
    """Тесты фильтра FSM-состояний."""

    @pytest.fixture
    def form(self):
        from maxapi.context.state_machine import State, StatesGroup

        class Form(StatesGroup):
            name = State()
            age = State()

        return Form

    def test_state_filter_requires_state(self):
        """StateFilter без состояний не имеет смысла."""
        with pytest.raises(
            ValueError, match="Нужно передать хотя бы одно состояние"
        ):
            StateFilter()

        with pytest.raises(
            ValueError, match=r'StateFilter\("\*"\).*StateFilter\(None\)'
        ):
            StateFilter([])

    @pytest.mark.asyncio
    async def test_state_filter_matches_state_object(
        self, sample_message_created_event, form
    ):
        """StateFilter совпадает по State-объекту и строке из storage."""
        assert (
            await StateFilter(form.name)(
                sample_message_created_event,
                raw_state=form.name,
            )
            is True
        )
        assert (
            await StateFilter(form.name)(
                sample_message_created_event,
                raw_state="Form:name",
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_string_and_none(
        self, sample_message_created_event, form
    ):
        """Поддерживаются строковые состояния и отсутствие состояния."""
        assert (
            await StateFilter("Form:name")(
                sample_message_created_event,
                raw_state=form.name,
            )
            is True
        )
        assert (
            await StateFilter(None)(
                sample_message_created_event,
                raw_state=None,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_default_state_object(
        self, sample_message_created_event
    ):
        """Как в aiogram: пустой State() совпадает с raw_state=None."""
        from maxapi.context.state_machine import State

        assert (
            await StateFilter(State())(
                sample_message_created_event,
                raw_state=None,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_wildcard(
        self, sample_message_created_event, form
    ):
        """'*' работает как aiogram wildcard для любого raw_state."""
        assert (
            await StateFilter("*")(
                sample_message_created_event,
                raw_state=form.age,
            )
            is True
        )
        assert (
            await StateFilter("*")(
                sample_message_created_event,
                raw_state=None,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_state_object_wildcard(
        self, sample_message_created_event, form
    ):
        """State со значением '*' тоже работает как wildcard aiogram."""
        from maxapi.context.state_machine import State

        any_state = State()
        any_state.name = "*"

        assert (
            await StateFilter(any_state)(
                sample_message_created_event,
                raw_state=form.age,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_states_group(
        self, sample_message_created_event, form
    ):
        """StatesGroup раскрывается в список состояний группы."""
        assert (
            await StateFilter(form)(
                sample_message_created_event,
                raw_state=form.age,
            )
            is True
        )
        assert (
            await StateFilter(form())(
                sample_message_created_event,
                raw_state=form.name,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_nested_states_group(
        self, sample_message_created_event
    ):
        """Вложенные StatesGroup матчятся как в aiogram."""
        from maxapi.context.state_machine import State, StatesGroup

        class Form(StatesGroup):
            class Nested(StatesGroup):
                step = State()

        assert (
            await StateFilter(Form)(
                sample_message_created_event,
                raw_state=Form.Nested.step,
            )
            is True
        )
        assert (
            await StateFilter(Form)(
                sample_message_created_event,
                raw_state="Form.Nested:step",
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_inherited_states_group(
        self, sample_message_created_event
    ):
        """StatesGroup включает состояния базовых групп."""
        from maxapi.context.state_machine import State, StatesGroup

        class BaseForm(StatesGroup):
            name = State()

        class Form(BaseForm):
            age = State()

        assert (
            await StateFilter(Form)(
                sample_message_created_event,
                raw_state=BaseForm.name,
            )
            is True
        )
        assert (
            await StateFilter(Form)(
                sample_message_created_event,
                raw_state=Form.age,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_matches_inherited_nested_states_group_alias(
        self, sample_message_created_event
    ):
        """Наследник сохраняет строковые aliases вложенных базовых групп."""
        from maxapi.context.state_machine import State, StatesGroup

        class BaseForm(StatesGroup):
            class Nested(StatesGroup):
                step = State()

        class Form(BaseForm):
            age = State()

        assert (
            await StateFilter(Form)(
                sample_message_created_event,
                raw_state="BaseForm.Nested:step",
            )
            is True
        )
        assert (
            await StateFilter(Form)(
                sample_message_created_event,
                raw_state="Form.Nested:step",
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_accepts_single_iterable(
        self, sample_message_created_event, form
    ):
        """Один iterable со state-значениями разворачивается."""
        assert (
            await StateFilter([form.name, form.age])(
                sample_message_created_event,
                raw_state=form.age,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_keeps_mixed_iterable_and_positional_states(
        self, sample_message_created_event, form
    ):
        """Iterable не должен съедать следующие позиционные состояния."""
        assert (
            await StateFilter([form.name], form.age)(
                sample_message_created_event,
                raw_state=form.name,
            )
            is True
        )
        assert (
            await StateFilter([form.name], form.age)(
                sample_message_created_event,
                raw_state=form.age,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_accepts_multiple_positional_states(
        self, sample_message_created_event, form
    ):
        """Несколько позиционных состояний работают как в aiogram."""
        assert (
            await StateFilter(form.name, form.age)(
                sample_message_created_event,
                raw_state=form.age,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_returns_false_on_mismatch(
        self, sample_message_created_event, form
    ):
        """Несовпадающее состояние блокирует фильтр."""
        assert (
            await StateFilter(form.name)(
                sample_message_created_event,
                raw_state=form.age,
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_state_filter_exclude_blocks_matching_state(
        self, sample_message_created_event, form
    ):
        """exclude имеет приоритет над основными состояниями."""
        assert (
            await StateFilter("*", exclude=form.age)(
                sample_message_created_event,
                raw_state=form.age,
            )
            is False
        )
        assert (
            await StateFilter("*", exclude=form.age)(
                sample_message_created_event,
                raw_state=form.name,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_exclude_with_group(
        self, sample_message_created_event, form
    ):
        """Из группы можно исключить отдельные состояния."""
        assert (
            await StateFilter(form, exclude=[form.age])(
                sample_message_created_event,
                raw_state=form.name,
            )
            is True
        )
        assert (
            await StateFilter(form, exclude=[form.age])(
                sample_message_created_event,
                raw_state=form.age,
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_state_filter_exclude_none_means_no_exclusions(
        self, sample_message_created_event
    ):
        """exclude=None оставляет поведение StateFilter('*') прежним."""
        assert (
            await StateFilter("*", exclude=None)(
                sample_message_created_event,
                raw_state=None,
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_exclude_default_state_with_iterable(
        self, sample_message_created_event
    ):
        """Для исключения default-state используется exclude=[None]."""
        assert (
            await StateFilter("*", exclude=[None])(
                sample_message_created_event,
                raw_state=None,
            )
            is False
        )
        assert (
            await StateFilter("*", exclude=[None])(
                sample_message_created_event,
                raw_state="Form:name",
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_exclude_states_group(
        self, sample_message_created_event, form
    ):
        """exclude=StatesGroup исключает любое состояние группы."""
        assert (
            await StateFilter("*", exclude=form)(
                sample_message_created_event,
                raw_state=form.name,
            )
            is False
        )
        assert (
            await StateFilter("*", exclude=form)(
                sample_message_created_event,
                raw_state="Other:state",
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_state_filter_exclude_keeps_mixed_iterable_and_state(
        self, sample_message_created_event, form
    ):
        """exclude тоже разворачивает mixed iterable-аргументы."""
        assert (
            await StateFilter("*", exclude=([form.name], form.age))(
                sample_message_created_event,
                raw_state=form.name,
            )
            is False
        )
        assert (
            await StateFilter("*", exclude=([form.name], form.age))(
                sample_message_created_event,
                raw_state=form.age,
            )
            is False
        )
        assert (
            await StateFilter("*", exclude=([form.name], form.age))(
                sample_message_created_event,
                raw_state="Other:state",
            )
            is True
        )

    def test_state_filter_str_includes_exclude(self, form):
        """В строковом виде видно исключённые состояния."""
        assert "exclude=Form:age" in str(StateFilter("*", exclude=form.age))


class TestCommandFilter:
    """Тесты фильтра команд."""

    def test_command_filter_init(self):
        """Тест инициализации Command фильтра."""
        cmd = Command("start")
        assert "start" in cmd.commands

    def test_command_filter_multiple(self):
        """Тест Command с несколькими командами."""
        cmd = Command(["start", "begin", "go"])
        assert "start" in cmd.commands
        assert "begin" in cmd.commands
        assert "go" in cmd.commands

    @pytest.mark.asyncio
    async def test_command_filter_match(self):
        """Тест Command фильтра при совпадении."""
        # Core Stuff
        from maxapi.types.message import Message, MessageBody

        cmd = Command("start")

        # Создаем событие с командой /start
        event = Mock(spec=MessageCreated)
        message_body = Mock(spec=MessageBody)
        message_body.text = "/start"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        # Мокаем bot.me для корректной работы фильтра
        mock_bot = Mock()
        mock_me = Mock()
        mock_me.username = None
        mock_bot.me = mock_me
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        # Command возвращает словарь с 'args' при совпадении
        assert result is not False
        assert isinstance(result, dict)
        assert "args" in result

    @pytest.mark.asyncio
    async def test_command_filter_no_match(self):
        """Тест Command фильтра при несовпадении."""
        # Core Stuff
        from maxapi.types.message import Message, MessageBody

        cmd = Command("start")

        # Создаем событие без команды
        event = Mock(spec=MessageCreated)
        message_body = Mock(spec=MessageBody)
        message_body.text = "just text"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        # Мокаем bot.me для корректной работы фильтра
        mock_bot = Mock()
        mock_me = Mock()
        mock_me.username = None
        mock_bot.me = mock_me
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        assert result is False

    async def test_command_filter_body_none(self):
        """Если у сообщения body == None — фильтр должен вернуть False."""
        from maxapi.types.message import Message

        cmd = Command("start")

        event = Mock(spec=MessageCreated)
        message = Mock(spec=Message)
        message.body = None
        event.message = message

        mock_bot = Mock()
        mock_me = Mock()
        mock_me.username = None
        mock_bot.me = mock_me
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        assert result is False


class TestCallbackPayloadFilter:
    """Тесты фильтра CallbackPayload."""

    def test_callback_payload_init(self):
        """Тест инициализации PayloadFilter."""
        # Core Stuff
        from maxapi.filters.callback_payload import PayloadFilter

        # CallbackPayload - это BaseModel, используется через PayloadFilter
        # Создаем простой класс payload для теста
        class TestPayload(CallbackPayload):
            value: str

        payload_filter = PayloadFilter(model=TestPayload, rule=None)
        assert payload_filter.model == TestPayload
        assert payload_filter.rule is None

    @pytest.mark.asyncio
    async def test_callback_payload_match(self):
        """Тест PayloadFilter при совпадении."""
        # Core Stuff
        from maxapi.filters.callback_payload import PayloadFilter
        from maxapi.types.callback import Callback
        from maxapi.types.updates.message_callback import MessageCallback

        # Создаем простой класс payload для теста
        class TestPayload(CallbackPayload):
            value: str

        payload_filter = PayloadFilter(model=TestPayload, rule=None)

        # Создаем payload строку (prefix|value)
        payload_str = "TestPayload|test_value"

        callback = Mock(spec=Callback)
        callback.payload = payload_str

        event = Mock(spec=MessageCallback)
        event.callback = callback

        result = await payload_filter(event)

        assert result is not False
        assert isinstance(result, dict)
        assert "payload" in result
        assert isinstance(result["payload"], TestPayload)
        assert result["payload"].value == "test_value"

    @pytest.mark.asyncio
    async def test_callback_payload_no_match(self):
        """Тест PayloadFilter при несовпадении."""
        # Core Stuff
        from maxapi.filters.callback_payload import PayloadFilter
        from maxapi.types.callback import Callback
        from maxapi.types.updates.message_callback import MessageCallback

        # Создаем простой класс payload для теста
        class TestPayload(CallbackPayload):
            value: str

        payload_filter = PayloadFilter(model=TestPayload, rule=None)

        # Неправильный payload (неправильный prefix)
        callback = Mock(spec=Callback)
        callback.payload = "WrongPrefix|test_value"

        event = Mock(spec=MessageCallback)
        event.callback = callback

        result = await payload_filter(event)

        assert result is False

    def test_callback_payload_unpack_optional_empty_as_none(self):
        """Пустые сегменты payload должны становиться None для Optional."""

        class IqPayload(CallbackPayload, prefix="iq"):
            action: str
            timestamp: int | None = None
            callback_storage_id: int | None = None

        payload = IqPayload.unpack("iq|meter_readings_enter||")

        assert payload.action == "meter_readings_enter"
        assert payload.timestamp is None
        assert payload.callback_storage_id is None

    def test_callback_payload_unpack_required_string_keeps_empty(self):
        """Для обязательного str пустое значение остаётся пустой строкой."""

        class RequiredPayload(CallbackPayload, prefix="rq"):
            action: str
            required_text: str

        payload = RequiredPayload.unpack("rq|do_something|")

        assert payload.action == "do_something"
        assert payload.required_text == ""
