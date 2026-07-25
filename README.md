# Minecraft Server Bot

Telegram-бот для подачи заявок на Minecraft-сервер: регистрация клана и заявка в вайтлист.

## Возможности

- `/start` — приветствие и меню с двумя разделами
- Регистрация клана (название, тег, ник лидера)
- Заявка в вайтлист (ник, возраст, о себе)
- Все заявки сохраняются в SQLite (`applications.db`)
- Заявки уходят в чат админов с кнопками **Принять / Отклонить**
- Заявитель автоматически получает уведомление о решении

## Установка

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка

Задай переменные окружения (или создай `.env` и подключи через `python-dotenv`):

```bash
export BOT_TOKEN=токен_от_BotFather
export ADMIN_CHAT_ID=id_чата_админов
```

`ADMIN_CHAT_ID` можно узнать, добавив бота в группу админов и залогировав `message.chat.id`, либо через @userinfobot.

## Запуск

```bash
python bot.py
```

## Структура проекта

```
bot.py             # логика бота, хендлеры, FSM-анкеты
db.py               # работа с SQLite
requirements.txt    # зависимости
```
