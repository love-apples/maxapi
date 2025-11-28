from .dispatcher import HandlerException, MiddlewareException
from .download_file import NotAvailableForDownload
from .max import (
    InvalidToken,
    MaxApiError,
    MaxConnection,
    MaxIconParamsException,
    MaxUploadFileFailed,
)

__all__ = [
    "HandlerException",
    "MiddlewareException",
    "InvalidToken",
    "MaxConnection",
    "MaxUploadFileFailed",
    "MaxIconParamsException",
    "MaxApiError",
    "NotAvailableForDownload",
]
