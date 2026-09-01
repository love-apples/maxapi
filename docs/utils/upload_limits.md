# Upload Limits

::: maxapi.utils.upload_limits

## Пример

```python
from maxapi.enums.upload_type import UploadType
from maxapi.utils.upload_limits import (
    UPLOAD_LIMITS,
    check_upload_size,
)

limits = UPLOAD_LIMITS[UploadType.IMAGE]
print(limits.max_size, limits.max_dimensions)

# Мягкая проверка: пишет предупреждение в логгер `bot`
# и возвращает False, исключение не бросается.
ok = check_upload_size(
    100 * 1024 * 1024,
    UploadType.IMAGE,
    name="photo.png",
)
```

Проверка вызывается автоматически в `BaseConnection.upload_file` и
`BaseConnection.upload_file_buffer`, то есть на любом пути загрузки:
`bot.upload_media`, `InputMedia`/`InputMediaBuffer` в `attachments`,
а также ручной `bot.upload_file`. Предупреждение появится в логах и
без явного вызова `check_upload_size`.
