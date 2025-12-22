# Документирование обработчиков

Библиотека maxapi позволяет автоматически извлекать информацию о командах из docstring обработчиков и сохранять её для дальнейшего использования.

## Как это работает

При регистрации обработчиков диспетчер автоматически сканирует docstring функций-обработчиков и ищет специальный маркер `commands_info:`. Если обработчик использует фильтр `Command` и содержит в docstring информацию о команде, она будет автоматически извлечена и сохранена в `bot.commands`.

## Синтаксис

В docstring обработчика необходимо указать маркер `commands_info:` с описанием команды:

```python
@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    """
    Обработчик команды /start
    
    commands_info: Запускает бота и показывает приветственное сообщение
    """
    await event.message.answer("Привет! Добро пожаловать!")
```

## Примеры использования

### Простая команда с описанием

```python
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, Command

bot = Bot()
dp = Dispatcher()

@dp.message_created(Command('help'))
async def help_handler(event: MessageCreated):
    """
    Обработчик команды помощи
    
    commands_info: Показывает список доступных команд и их описание
    """
    await event.message.answer("Доступные команды:\n/start - Начать работу\n/help - Помощь")
```

### Несколько команд с одним описанием

```python
@dp.message_created(Command(['start', 'begin', 'go']))
async def start_handler(event: MessageCreated):
    """
    Обработчик команд запуска
    
    commands_info: Инициализирует бота и начинает диалог с пользователем
    """
    await event.message.answer("Бот запущен!")
```

### Многострочное описание

```python
@dp.message_created(Command('settings'))
async def settings_handler(event: MessageCreated):
    """
    Обработчик настроек
    
    commands_info: Открывает меню настроек бота.
    Позволяет изменить язык, уведомления и другие параметры.
    """
    await event.message.answer("Настройки бота")
```

## Получение списка команд

После регистрации всех обработчиков информация о командах доступна через свойство `handlers_commands` объекта бота:

```python
from maxapi.filters.command import CommandsInfo

# Получить список всех команд
commands: list[CommandsInfo] = bot.handlers_commands

# Вывести информацию о командах
for cmd_info in commands:
    print(f"Команды: {cmd_info.commands}")
    print(f"Описание: {cmd_info.info}")
    print("---")
```

## Структура CommandsInfo

`CommandsInfo` — это dataclass, содержащий:

- `commands` (List[str]): Список команд без префикса `/`
- `info` (Optional[str]): Описание команды, извлеченное из docstring (может быть `None`)

```python
from maxapi.filters.command import CommandsInfo

# Пример использования
cmd_info = CommandsInfo(
    commands=['start', 'begin'],
    info='Запускает бота'
)
```

## Логирование команд при старте

Извлеченную информацию о командах можно использовать для логирования всех зарегистрированных команд при запуске бота:

```python
import logging

logger = logging.getLogger(__name__)

@dp.on_started()
async def log_all_commands():
    """Логирует все зарегистрированные команды"""
    logger.info("Зарегистрированные команды:")
    for cmd_info in bot.handlers_commands:
        commands_str = ", ".join([f"/{cmd}" for cmd in cmd_info.commands])
        info_str = f" - {cmd_info.info}" if cmd_info.info else ""
        logger.info(f"  {commands_str}{info_str}")
```

## Важные замечания

1. **Только для Command фильтров**: Информация извлекается только для обработчиков, использующих фильтр `Command`
2. **Автоматическое извлечение**: Происходит автоматически при запуске диспетчера (в методе `start_polling` или `start_webhook`)
3. **Маркер опционален**: Маркер `commands_info:` в docstring необязателен. Если он отсутствует, поле `info` в `CommandsInfo` будет `None`
4. **Регистр не важен**: Маркер `commands_info:` может быть в любом регистре
5. **Многострочность**: Описание может быть многострочным, оно будет извлечено до конца строки или до конца docstring

## Пример полного использования

```python
import asyncio
import logging
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, Command

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    """
    Обработчик команды /start
    
    commands_info: Запускает бота и показывает приветствие
    """
    await event.message.answer("Привет!")

@dp.message_created(Command('help'))
async def help_handler(event: MessageCreated):
    """
    Обработчик команды /help
    
    commands_info: Показывает справку по использованию бота
    """
    await event.message.answer("Справка по командам...")

@dp.message_created(Command('settings'))
async def settings_handler(event: MessageCreated):
    """
    Обработчик команды /settings
    
    commands_info: Открывает меню настроек
    """
    await event.message.answer("Настройки...")

@dp.on_started()
async def log_all_commands():
    """Логирует все зарегистрированные команды"""
    logger = logging.getLogger(__name__)
    
    logger.info("Зарегистрированные команды:")
    for cmd_info in bot.handlers_commands:
        commands_str = ", ".join([f"/{cmd}" for cmd in cmd_info.commands])
        info_str = f" - {cmd_info.info}" if cmd_info.info else ""
        logger.info(f"  {commands_str}{info_str}")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
```
