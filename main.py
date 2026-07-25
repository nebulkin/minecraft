import logging
import os

import asyncpg
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# ---------- Настройки (задаются в Environment Variables на Render) ----------

BOT_TOKEN = os.getenv("BOT_TOKEN", "СЮДА_ТВОЙ_ТОКЕН")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render сам даёт адрес сервиса в переменной RENDER_EXTERNAL_URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Render передаёт номер порта в переменной PORT
PORT = int(os.getenv("PORT", "10000"))

router = Router()
db_pool: asyncpg.Pool | None = None


# ---------- База данных (Supabase / Postgres) ----------

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, ssl="require")

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clan_applications (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                name TEXT,
                tag TEXT,
                leader_nick TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whitelist_applications (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                nickname TEXT,
                age TEXT,
                about TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )


async def add_clan_application(user_id: int, username: str, name: str, tag: str, leader_nick: str) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO clan_applications (user_id, username, name, tag, leader_nick) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, username, name, tag, leader_nick,
        )
        return row["id"]


async def add_whitelist_application(user_id: int, username: str, nickname: str, age: str, about: str) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO whitelist_applications (user_id, username, nickname, age, about) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, username, nickname, age, about,
        )
        return row["id"]


async def get_clan_application(app_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM clan_applications WHERE id = $1", app_id)


async def get_whitelist_application(app_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM whitelist_applications WHERE id = $1", app_id)


async def set_clan_status(app_id: int, status: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE clan_applications SET status = $1 WHERE id = $2", status, app_id)


async def set_whitelist_status(app_id: int, status: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE whitelist_applications SET status = $1 WHERE id = $2", status, app_id)


# ---------- Клавиатуры ----------

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Зарегать клан", callback_data="clan_register")],
            [InlineKeyboardButton(text="📋 Подать заявку в вайтлист", callback_data="whitelist_apply")],
        ]
    )


def admin_decision_kb(prefix: str, app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"{prefix}_accept:{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"{prefix}_decline:{app_id}"),
            ]
        ]
    )


# ---------- Состояния (FSM) для анкет ----------

class ClanRegisterForm(StatesGroup):
    name = State()
    tag = State()
    leader_nick = State()


class WhitelistForm(StatesGroup):
    nickname = State()
    age = State()
    about = State()


# ---------- /start ----------

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Добро пожаловать в бот подачи заявки на наш Minecraft-сервер.\n"
        "Ниже навигация — ознакомься с тем, что тебе нужно.",
        reply_markup=main_menu_kb(),
    )


# ---------- Регистрация клана ----------

@router.callback_query(F.data == "clan_register")
async def clan_register_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanRegisterForm.name)
    await callback.message.answer("Введи название клана:")
    await callback.answer()


@router.message(ClanRegisterForm.name)
async def clan_register_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ClanRegisterForm.tag)
    await message.answer("Теперь введи тег клана (короткая аббревиатура):")


@router.message(ClanRegisterForm.tag)
async def clan_register_tag(message: Message, state: FSMContext):
    await state.update_data(tag=message.text)
    await state.set_state(ClanRegisterForm.leader_nick)
    await message.answer("Ник лидера клана в Minecraft:")


@router.message(ClanRegisterForm.leader_nick)
async def clan_register_leader(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(leader_nick=message.text)
    data = await state.get_data()
    await state.clear()

    app_id = await add_clan_application(
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.full_name,
        name=data["name"],
        tag=data["tag"],
        leader_nick=data["leader_nick"],
    )

    await message.answer(
        "Заявка на регистрацию клана принята и отправлена на рассмотрение!\n\n"
        f"Название: {data['name']}\n"
        f"Тег: {data['tag']}\n"
        f"Лидер: {data['leader_nick']}"
    )

    if ADMIN_CHAT_ID:
        await bot.send_message(
            ADMIN_CHAT_ID,
            "🆕 Новая заявка на регистрацию клана\n\n"
            f"От: @{message.from_user.username or message.from_user.id}\n"
            f"Название: {data['name']}\n"
            f"Тег: {data['tag']}\n"
            f"Лидер: {data['leader_nick']}",
            reply_markup=admin_decision_kb("clan", app_id),
        )


# ---------- Заявка в вайтлист ----------

@router.callback_query(F.data == "whitelist_apply")
async def whitelist_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(WhitelistForm.nickname)
    await callback.message.answer("Твой ник в Minecraft:")
    await callback.answer()


@router.message(WhitelistForm.nickname)
async def whitelist_nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await state.set_state(WhitelistForm.age)
    await message.answer("Сколько тебе лет?")


@router.message(WhitelistForm.age)
async def whitelist_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await state.set_state(WhitelistForm.about)
    await message.answer("Расскажи немного о себе (опыт игры, откуда узнал о сервере и т.д.):")


@router.message(WhitelistForm.about)
async def whitelist_about(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(about=message.text)
    data = await state.get_data()
    await state.clear()

    app_id = await add_whitelist_application(
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.full_name,
        nickname=data["nickname"],
        age=data["age"],
        about=data["about"],
    )

    await message.answer(
        "Заявка в вайтлист принята и отправлена на рассмотрение!\n\n"
        f"Ник: {data['nickname']}\n"
        f"Возраст: {data['age']}\n"
        f"О себе: {data['about']}"
    )

    if ADMIN_CHAT_ID:
        await bot.send_message(
            ADMIN_CHAT_ID,
            "🆕 Новая заявка в вайтлист\n\n"
            f"От: @{message.from_user.username or message.from_user.id}\n"
            f"Ник: {data['nickname']}\n"
            f"Возраст: {data['age']}\n"
            f"О себе: {data['about']}",
            reply_markup=admin_decision_kb("wl", app_id),
        )


# ---------- Решения админов ----------

async def _notify_applicant(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text)
    except TelegramBadRequest:
        # пользователь мог заблокировать бота — просто пропускаем
        pass


@router.callback_query(F.data.startswith("clan_accept:") | F.data.startswith("clan_decline:"))
async def clan_decision(callback: CallbackQuery, bot: Bot):
    action, app_id_str = callback.data.split(":")
    app_id = int(app_id_str)
    app = await get_clan_application(app_id)
    if not app:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    if action == "clan_accept":
        await set_clan_status(app_id, "accepted")
        await callback.message.edit_text(callback.message.text + "\n\n✅ Принято")
        await _notify_applicant(bot, app["user_id"], f"Твоя заявка на клан «{app['name']}» одобрена! 🎉")
    else:
        await set_clan_status(app_id, "declined")
        await callback.message.edit_text(callback.message.text + "\n\n❌ Отклонено")
        await _notify_applicant(bot, app["user_id"], f"Твоя заявка на клан «{app['name']}» отклонена.")

    await callback.answer()


@router.callback_query(F.data.startswith("wl_accept:") | F.data.startswith("wl_decline:"))
async def whitelist_decision(callback: CallbackQuery, bot: Bot):
    action, app_id_str = callback.data.split(":")
    app_id = int(app_id_str)
    app = await get_whitelist_application(app_id)
    if not app:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    if action == "wl_accept":
        await set_whitelist_status(app_id, "accepted")
        await callback.message.edit_text(callback.message.text + "\n\n✅ Принято")
        await _notify_applicant(bot, app["user_id"], "Твоя заявка в вайтлист одобрена! Добро пожаловать на сервер 🎉")
    else:
        await set_whitelist_status(app_id, "declined")
        await callback.message.edit_text(callback.message.text + "\n\n❌ Отклонено")
        await _notify_applicant(bot, app["user_id"], "Твоя заявка в вайтлист отклонена.")

    await callback.answer()


# ---------- Точка входа ----------

async def on_startup(bot: Bot):
    await init_db()
    if WEBHOOK_HOST:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook установлен: {WEBHOOK_URL}")


async def health_check(request: web.Request) -> web.Response:
    # Этот адрес будет пинговать cron-job.org, чтобы Render не усыплял сервис
    return web.Response(text="Bot is alive")


def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/", health_check)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
