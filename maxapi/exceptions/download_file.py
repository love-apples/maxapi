from .base import MaxError


class NotAvailableForDownload(MaxError): ...


class DownloadFileError(MaxError):
    """Ошибка при скачивании файла."""
