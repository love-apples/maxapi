

class HandlerException(Exception):
    def __init__(self, handler_title: str, *args, **kwargs):
        
        self.handler_title = handler_title
        self.extra = kwargs
        
        message = f'Обработчик: {handler_title!r}'
        
        if args:
            message += f', детали: {args}'
            
        if kwargs:
            message += f', другое: {kwargs}'
            
        super().__init__(message)