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
    "InvalidToken",
    "MaxApiError",
    "MaxConnection",
    "MaxIconParamsException",
    "MaxUploadFileFailed",
    "NotAvailableForDownload",
]
