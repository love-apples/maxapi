## 💬 Работа с сообщениями

### `send_message(...)`

**Описание:** Отправить сообщение в чат или пользователю.

**Аргументы:**

* `chat_id` *(int)* — ID чата. Обязателен, если не указан `user_id`.
* `user_id` *(int)* — ID пользователя. Обязателен, если не указан `chat_id`.
* `text` *(str)* — текст сообщения.
* `attachments` *(List\[Attachment])* — вложения (фото, видео и т.д.).
* `link` *(NewMessageLink)* — объект для создания ссылочного сообщения.
* `notify` *(bool)* — отправлять ли уведомление (по умолчанию берётся из настроек бота).
* `parse_mode` *(ParseMode)* — форматирование текста (например, `ParseMode.HTML`).

**Возвращает:** `SendedMessage` — объект отправленного сообщения.

---

### `edit_message(...)`

**Описание:** Редактировать существующее сообщение.

**Аргументы:**

* `message_id` *(str)* — ID сообщения, полученное ранее в `SendedMessage.id`.
* `text`, `attachments`, `link`, `notify`, `parse_mode` — см. `send_message`.

**Возвращает:** `EditedMessage` — объект изменённого сообщения.

---

### `delete_message(message_id)`

**Описание:** Удалить сообщение по его ID.

**Аргументы:**

* `message_id` *(str)* — ID сообщения.

**Возвращает:** `DeletedMessage` — результат удаления.

---

### `get_messages(...)`

**Описание:** Получить список сообщений.

**Аргументы:**

* `chat_id` *(int)* — ID чата.
* `message_ids` *(List\[str])* — список ID сообщений.
* `from_time` / `to_time` *(datetime | int)* — диапазон по времени.
* `count` *(int)* — сколько сообщений вернуть (по умолчанию 50).

**Возвращает:** `Messages` — список объектов сообщений.

---

### `get_message(message_id)`

**Описание:** Получить одно сообщение по ID.

**Аргументы:**

* `message_id` *(str)* — ID сообщения.

**Возвращает:** `Messages` — содержит одно сообщение в списке.

---

### `pin_message(...)`

**Описание:** Закрепить сообщение в чате.

**Аргументы:**

* `chat_id` *(int)* — ID чата.
* `message_id` *(str)* — ID сообщения.
* `notify` *(bool)* — уведомление.

**Возвращает:** `PinnedMessage`

---

### `delete_pin_message(chat_id)`

**Описание:** Удалить закреплённое сообщение.

**Аргументы:**

* `chat_id` *(int)* — ID чата.

**Возвращает:** `DeletedPinMessage`

---

## 🤖 Информация о боте

### `get_me()`

**Описание:** Получить объект бота.

**Возвращает:** `User` — текущий бот.

---

### `change_info(...)`

**Описание:** Изменить профиль бота.

**Аргументы:**

* `name` *(str)* — новое имя.
* `description` *(str)* — описание.
* `commands` *(List\[BotCommand])* — команды (name + description).
* `photo` *(Dict)* — `{ "url": ..., "token": ... }` — загруженное изображение. URL можно получить через `get_upload_url(...)`.

**Возвращает:** `User`

---

### `set_my_commands(*commands)`

**Описание:** Установить команды бота.

**Аргументы:**

* `commands` *(BotCommand)* — команды, например `BotCommand(name="help", description="Справка")`

**Возвращает:** `User`

---

## 👥 Работа с чатами

### `get_chats(...)`

**Описание:** Получить список чатов.

**Аргументы:**

* `count` *(int)* — количество (по умолчанию 50).
* `marker` *(int)* — маркер страницы.

**Возвращает:** `Chats`

---

### `get_chat_by_id(id)` / `get_chat_by_link(link)`

**Описание:** Получить объект чата по ID или публичной ссылке.

**Возвращает:** `Chat`

---

### `edit_chat(...)`

**Описание:** Изменить чат.

**Аргументы:**

* `chat_id`, `title`, `pin`, `notify` — как выше.
* `icon` *(PhotoAttachmentRequestPayload)* — вложение фото, загруженное через `get_upload_url(...)` и `download_file(...)`.

**Возвращает:** `Chat`

---

### `delete_chat(chat_id)`

Удаляет чат.

**Возвращает:** `DeletedChat`

---

## 👤 Работа с участниками чатов

### `get_chat_members(...)` / `get_chat_member(...)`

**Описание:** Получить одного или нескольких участников.

**Возвращает:** `GettedMembersChat` (у него есть `.members`)

---

### `add_chat_members(...)`

**Описание:** Добавить участников.

**Аргументы:**

* `chat_id`, `user_ids` *(List\[str])* — список строковых ID.

**Возвращает:** `AddedMembersChat`

---

### `kick_chat_member(...)`

**Описание:** Исключить и опционально заблокировать.

**Возвращает:** `RemovedMemberChat`

---

### `get_list_admin_chat(...)` / `add_list_admin_chat(...)` / `remove_admin(...)`

**Описание:** Управление администраторами.

**Возвращают:** `GettedListAdminChat`, `AddedListAdminChat`, `RemovedAdmin`

---

### `get_me_from_chat(...)`

**Описание:** Получить, кем является бот в чате.

**Возвращает:** `ChatMember`

### `delete_me_from_chat(...)`

**Удаляет бота из чата.**

**Возвращает:** `DeletedBotFromChat`

---

## 🔄 Обновления и действия

### `get_updates()`

**Описание:** Получить события (новости, сообщения и т.д.).

**Возвращает:** `UpdateUnion`

---

### `send_action(...)`

**Описание:** Отправить "печатает..." и т.д.

**Аргументы:**

* `chat_id`, `action` *(SenderAction)* — например, `SenderAction.TYPING_ON`

**Возвращает:** `SendedAction`

---

### `send_callback(...)`

**Описание:** Ответ на callback-кнопку.

**Аргументы:**

* `callback_id`, `message`, `notification`

**Возвращает:** `SendedCallback`

---

## 📎 Медиа и файлы

### `get_video(video_token)`

**Возвращает:** `Video`

### `get_upload_url(type)`

**Аргументы:** `type` *(UploadType)* — например, `UploadType.IMAGE`

**Возвращает:** `GettedUploadUrl` (у него есть `.url`)

### `download_file(path, url, token)` (НЕАКТУАЛЬНО)

**Описание:** Скачивает файл, используя URL и токен.

**Возвращает:** статус загрузки
