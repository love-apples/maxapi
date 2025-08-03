from typing import List, Tuple

from ..types.updates import UpdateUnion
from ..filters.filter import BaseFilter

from ..types.updates.message_created import MessageCreated


class Command(BaseFilter):
    
    """
    Фильтр сообщений на соответствие команде.

    Args:
        commands (str | list[str]): Ожидаемая команда или список команд без префикса.
        prefix (str, optional): Префикс команды (по умолчанию '/').
        check_case (bool, optional): Учитывать регистр при сравнении (по умолчанию False).

    Attributes:
        commands (list[str]): Список команд без префикса.
        prefix (str): Префикс команды.
        check_case (bool): Флаг чувствительности к регистру.
    """
    
    def __init__(self, commands: str | List[str], prefix: str = '/', check_case: bool = False):
        
        """
        Инициализация фильтра команд.
        """
        
        if isinstance(commands, str):
            self.commands = [commands]
        else:
            self.commands = commands
            
        self.prefix = prefix
        self.check_case = check_case
        
        if not check_case:
            self.commands = [cmd.lower() for cmd in self.commands]
        
    def parse_command(self, text: str) -> Tuple[str, List[str]]:
        
        """
        Извлекает команду из текста.

        Args:
            text (str): Текст сообщения.

        Returns:
            Optional[str]: Найденная команда с префиксом, либо None.
        """

        args = text.split()
        first = args[0]
        
        if not first.startswith(self.prefix):
            return '', []
        
        return first[len(self.prefix):], args
     
    async def __call__(self, event: UpdateUnion):
         
        """
        Проверяет, соответствует ли сообщение заданной(ым) команде(ам).

        Args:
            event (MessageCreated): Событие сообщения.

        Returns:
            bool: True, если команда совпадает, иначе False.
        """
        
        if not isinstance(event, MessageCreated):
            return False
        
        text = event.message.body.text

        if not text:
            return False
        
        parsed_command, args = self.parse_command(text)
        if not parsed_command:
            return False
        
        if not self.check_case:
            if parsed_command.lower() in [commands.lower() for commands in self.commands]:
                return {'args': args}
            else:
                return False
            
        if parsed_command in self.commands:
            return {'args': args}
        
        return False
    
        
class CommandStart(Command):
    
    """
    Фильтр для команды /start.

    Args:
        prefix (str, optional): Префикс команды (по умолчанию '/').
        check_case (bool, optional): Учитывать регистр (по умолчанию False).
    """
    
    def __init__(self, prefix = '/', check_case = False):
        super().__init__(
            'start', 
            prefix, 
            check_case
        )
        
    async def __call__(self, event):
        return await super().__call__(event)