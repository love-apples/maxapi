# Real World MAX API Payloads (2026)
# Reverse engineered JSON payloads for MAX Messenger API (Feb 2026). Real-world examples for developers./

> ⭐️ **Original Source & Updates:**
> This document is a snapshot of the collection maintained in **[this GitHub Gist](https://gist.github.com/Danya2904/4280c88912090e7440fb7bfc54abdea3)**.
> Please check the Gist for the most recent updates or to leave comments/stars.
---
# MAX Messenger API & SubCheckerBot Architecture

> **CRITICAL REFERENCE:** This document contains REAL payloads captured from the MAX API on Feb 10, 2026.
> AI coding assistants must use these structures, NOT generic Telegram schemas.

## 1. Bot Identity (`/me`)
*Source: `bot_info_me.json`*
```json

{
  "user_id": 10002,
  "first_name": "SubChecker",
  "username": "example_bot",
  "is_bot": true,
  "last_activity_time": 1770679711537,
  "description": "🚀 Автовыдача бонусов за подписку! Бот проверяет подписку на ваш канал и мгновенно выдает лид-магнит (файл или ссылку). 📈 Расти аудиторию на автомате. ⚙️ Настройка поста за 1 минуту.",
  "avatar_url": "https://i.oneme.ru/i?r=BTFjO43w8Yr1OSJ4tcurq5HiGFXTgmcNFCqWsL5eFLaBsq_WO3gNo_PCmzpboct_jy8",
  "full_avatar_url": "https://i.oneme.ru/i?r=BTFjO43w8Yr1OSJ4tcurq5HiHBeIhpWE6pyKskhnmJMdXK_WO3gNo_PCmzpboct_jy8",
  "commands": [
    {
      "name": "start",
      "description": "Главное меню"
    },
    {
      "name": "menu",
      "description": "Главное меню"
    },
    {
      "name": "help",
      "description": "Помощь"
    }
  ],
  "name": "SubChecker"
}

2. Real API Events (Webhooks)
2.1 Message Event: Text (message_created)
Triggered when a user sends text. Source: event_message_created_xxxx.json (Text variant)
JSON
{
  "timestamp": 1770679787821,
  "message": {
    "recipient": {
      "chat_id": -100000000,
      "chat_type": "dialog",
      "user_id": 10002
    },
    "timestamp": 1770679787821,
    "body": {
      "mid": "mid.0000000008a53b9b019c44bd612d33e0",
      "seq": 116043270574650336,
      "text": "вапва"
    },
    "sender": {
      "user_id": 10001,
      "first_name": "User_Name",
      "last_name": "",
      "is_bot": false,
      "last_activity_time": 1770679783000,
      "name": "User_Name"
    }
  },
  "user_locale": "ru",
  "update_type": "message_created"
}


2.2 Message Event: Image/Media (message_created)
Triggered when a user uploads an image. Source: event_message_created_xxxx.json (Image variant)
JSON
{
  "callback": {
    "timestamp": 1770679806850,
    "callback_id": "f9LHodD0cOIEr0gCxuvowdetqQYLt6YmbfMaYw-zrjhsUTxjwbp1pu6VGgH9pMTYsOXFc5c9A_ZqxUeu6GqH1jb6vU8p9bC00g4jKPOcprtNbfkT3EKf",
    "user": {
      "user_id": 10001,
      "first_name": "User_Name",
      "last_name": "",
      "is_bot": false,
      "last_activity_time": 1770679800000,
      "name": "User_Name"
    },
    "payload": "new_campaign"
  },
  "message": {
    "recipient": {
      "chat_id": -100000000,
      "chat_type": "dialog",
      "user_id": 10001
    },
    "timestamp": 1770659375216,
    "body": {
      "mid": "mid.0000000008a53b9b019c4385e870772f",
      "seq": 116041932814186287,
      "text": "Я бот для проверки подписки на канал и выдачи бонуса",
      "attachments": [
        {
          "callback_id": "f9LHodD0cOLngNLRLPQfSXZgqBDflqFnELT1bmbAqQi_-KxTT5HIDeX8mbroS-_NPPwejDQCmxmqxj_FZOh-_HBHRNUXNQWwswszV-CrIfi236nzywae",
          "payload": {
            "buttons": [
              [
                {
                  "payload": "new_campaign",
                  "text": "➕ Создать новую проверку",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "menu_my_campaigns",
                  "text": "📂 Мои проверки",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "menu_statistics",
                  "text": "📊 Статистика",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "menu_settings",
                  "text": "⚙️ Настройки",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "menu_help",
                  "text": "🆘 Помощь",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "menu_what",
                  "text": "😏 Чё это за бот ваще?",
                  "intent": "default",
                  "type": "callback"
                }
              ]
            ]
          },
          "type": "inline_keyboard"
        },
        {
          "payload": {
            "photo_id": 4484450835,
            "token": "r8MRvzDqRDVaw59SP+XQhHBtiSp/U03et076+m7/hTnBn4EEJXhibpkmWTUPRvUyHUdxlK9RVHN7FbvBC8msKja3jADaBs5vdxxl1GxH1VFJPtxhMrVXfSpZjD+j6NEz",
            "url": "https://i.oneme.ru/i?r=BTGBPUwtwgYUeoFhO7rESmr8FddYu8EkRnc1BbDFbQm1bcgN8COxyU5BTkp85aDzgF4"
          },
          "type": "image"
        }
      ]
    },
    "sender": {
      "user_id": 10002,
      "first_name": "SubChecker",
      "username": "example_bot",
      "is_bot": true,
      "last_activity_time": 1770679807233,
      "name": "SubChecker"
    }
  },
  "timestamp": 1770679806850,
  "user_locale": "ru",
  "update_type": "message_callback"
}

2.3 Callback Event (message_callback)
Triggered when an inline button is pressed. Source: event_message_callback_xxxx.json
JSON
{
  "callback": {
    "timestamp": 1770679803383,
    "callback_id": "f9LHodD0cOJZOniECmtvwY8SptcuW_9QbNqRyNSQ5VH8nUtIQyScJBMaiaOrNLKI256iC4B88gSGGXjh7dNr00chXOtLf3d5ZKJQMRHaU7kNFeK7YASD",
    "user": {
      "user_id": 10001,
      "first_name": "User_Name",
      "last_name": "",
      "is_bot": false,
      "last_activity_time": 1770679800000,
      "name": "User_Name"
    },
    "payload": "utm_view_6"
  },
  "message": {
    "recipient": {
      "chat_id": -100000000,
      "chat_type": "dialog",
      "user_id": 10001
    },
    "timestamp": 1770671779146,
    "body": {
      "mid": "mid.0000000008a53b9b019c44432d4a3a70",
      "seq": 116042745718127216,
      "text": "🔗 UTM-ссылки проверки 6\n\ntest2 — 1 получивших бонус, 2 пытались забрать бонус, 4 просмотров поста, создана 09.02.2026 16:15\ntest1 — 1 получивших бонус, 1 пытались забрать бонус, 0 просмотров поста, создана 09.02.2026 15:03",
      "attachments": [
        {
          "callback_id": "f9LHodD0cOK60l00EgYGGlKfXneQiTsM6PZhvm7lXk8X350aSp-zTa_3fCXD_XN0keytvDsqDkWue_c0DG89UkvHiIWyEcKXtu8HUnk9eKVDkEfJmE83",
          "payload": {
            "buttons": [
              [
                {
                  "payload": "utm_view_6",
                  "text": "🔗 test2",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "utm_view_5",
                  "text": "🔗 test1",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "utm_create_6",
                  "text": "➕ Создать UTM-ссылку",
                  "intent": "default",
                  "type": "callback"
                }
              ],
              [
                {
                  "payload": "view_campaign_6",
                  "text": "🔙 К проверке",
                  "intent": "default",
                  "type": "callback"
                }
              ]
            ]
          },
          "type": "inline_keyboard"
        }
      ],
      "markup": [
        {
          "from": 0,
          "length": 24,
          "type": "strong"
        },
        {
          "from": 26,
          "length": 5,
          "type": "strong"
        },
        {
          "from": 125,
          "length": 5,
          "type": "strong"
        }
      ]
    },
    "sender": {
      "user_id": 10002,
      "first_name": "SubChecker",
      "username": "example_bot",
      "is_bot": true,
      "last_activity_time": 1770679803762,
      "name": "SubChecker"
    }
  },
  "timestamp": 1770679803383,
  "user_locale": "ru",
  "update_type": "message_callback"
}

2.4 User Added (user_added)
Triggered when a user opens the chat or unblocks the bot. Source: event_user_added_xxxx.json
JSON
{
  "chat_id": -100000000,
  "user": {
    "user_id": 10003,
    "first_name": "Test_User",
    "last_name": "",
    "is_bot": false,
    "last_activity_time": 1770679612000,
    "name": "Test_User"
  },
  "is_channel": true,
  "timestamp": 1770679613310,
  "update_type": "user_added"
}


3. The Internal Normalization Layer

IMPORTANT FOR DEVELOPERS: The SubCheckerBot transforms the Raw Data (above) into a Normalized Object in main.py before passing it to Handlers.
- If editing main.py / api.py: Use the **Raw JSON structures** above.
- If editing handlers/.py: Use the **Normalized keys** below.

| Normalized Field (In Handlers) | Mapped From Raw MAX JSON |
|-------------------------------|--------------------------|
| message.text | message.body.text |
| message.from.id / from_user.id | message.sender (MAX has no "from"; we build it from sender) |
| message.chat.id | message.recipient.chat_id; for dialog → recipient.user_id or sender.user_id |
| callback_query.id | callback.callback_id |
| callback_query.data | **callback.payload** (string, e.g. "check_system_sub", "utm_view_6") | 

4. API Quirks & Limits
Images: External URLs are forbidden. Flow: POST /uploads -> Get Token -> POST /messages with token.

Deep Links: Parsed from message.body.text (e.g., /start c42) or specific payload fields if available.
