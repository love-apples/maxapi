from .dispatcher import HandlerException, MiddlewareException
from .download_file import DownloadFileError, NotAvailableForDownload
from .max import (
    InvalidToken,
    MaxApiError,
    MaxConnection,
    MaxIconParamsException,
    MaxUploadFileFailed,
)

__all__ = [
    "DownloadFileError",
    "HandlerException",
    "InvalidToken",
    "MaxApiError",
    "MaxConnection",
    "MaxIconParamsException",
    "MaxUploadFileFailed",
    "MiddlewareException",
    "NotAvailableForDownload",
]
