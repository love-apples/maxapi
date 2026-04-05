from enum import unique

from ._compat import StrEnum


@unique
class HTTPMethod(StrEnum):
    """
    HTTP-методы, поддерживаемые клиентом API.

    Используются при выполнении запросов к серверу.
    """

    POST = "POST"
    GET = "GET"
    PATCH = "PATCH"
    PUT = "PUT"
    DELETE = "DELETE"
