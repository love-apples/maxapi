from enum import Enum


class HTTPMethod(str, Enum):
    """
    HTTP-методы, поддерживаемые клиентом API.

    Используются при выполнении запросов к серверу.
    """

    POST = "POST"
    GET = "GET"
    PATCH = "PATCH"
    PUT = "PUT"
    DELETE = "DELETE"
