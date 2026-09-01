"""Хелперы для сборки query-параметров запросов к API."""


def bool_to_query(value: bool) -> str:  # noqa: FBT001
    """Сериализует bool в строку query-параметра ("true"/"false")."""
    return "true" if value else "false"
