"""
utils.py — общие хелперы.
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
from aiogram import Bot
from aiogram.types import (
    Message, CallbackQuery, FSInputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.enums import ParseMode
import html
from config import (
    ADMIN_IDS, CUR, SHOP_PHOTO_PATH, PROFILE_PHOTO_PATH, TOPUP_PHOTO_PATH, SUB_PHOTO_PATH,
    INFO_PHOTO_PATH, SUPPORT_PHOTO_PATH, TELEGRAM_PHOTO_PATH, CATALOG_PHOTO_PATH,
    STARS_PHOTO_PATH, PREMIUM_PHOTO_PATH,
    REQUIRED_CHANNEL, REQUIRED_CHANNEL_URL,
)
from database import db


def is_banned(uid: int) -> bool:
    u = db.find_user_by_id(uid)
    return u.get("status") == "Заблокирован" if u else False


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def _photo(path):
    return FSInputFile(path) if os.path.exists(path) else None


def SHOP_PHOTO():    return _photo(SHOP_PHOTO_PATH)
def PROFILE_PHOTO(): return _photo(PROFILE_PHOTO_PATH)
def TOPUP_PHOTO():   return _photo(TOPUP_PHOTO_PATH)
def SUB_PHOTO():     return _photo(SUB_PHOTO_PATH)
def INFO_PHOTO():    return _photo(INFO_PHOTO_PATH)
def SUPPORT_PHOTO(): return _photo(SUPPORT_PHOTO_PATH)
def TELEGRAM_PHOTO(): return _photo(TELEGRAM_PHOTO_PATH)
def CATALOG_PHOTO(): return _photo(CATALOG_PHOTO_PATH)
def STARS_PHOTO():   return _photo(STARS_PHOTO_PATH)
def PREMIUM_PHOTO(): return _photo(PREMIUM_PHOTO_PATH)


# ── Обязательная подписка на канал ─────────────────────────
_sub_ok: dict[int, float] = {}     # uid → когда последний раз подтвердили подписку
_SUB_TTL = 60.0
_sub_warned = False


async def is_subscribed(bot: Bot, uid: int, use_cache: bool = True) -> bool:
    """
    Подписан ли пользователь на REQUIRED_CHANNEL. Положительный ответ кэшируется на минуту,
    отрицательный — нет (после подписки пускаем сразу).
    Если бот не видит канал (не админ / неверное имя) — НЕ блокируем всех, но громко пишем в лог.
    """
    global _sub_warned
    if use_cache and time.monotonic() - _sub_ok.get(uid, -1e9) < _SUB_TTL:
        return True
    try:
        m = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=uid)
    except Exception as e:
        if not _sub_warned:
            _sub_warned = True
            logging.getLogger("sub").error(
                "Не могу проверить подписку на %s: %r. Сделайте бота АДМИНИСТРАТОРОМ канала — "
                "пока этого нет, обязательная подписка не работает.", REQUIRED_CHANNEL, e)
        return True
    ok = m.status not in ("left", "kicked", "banned")
    if m.status == "restricted":
        ok = bool(getattr(m, "is_member", True))
    if ok:
        _sub_ok[uid] = time.monotonic()
    return ok


def kb_subscribe_inline() -> InlineKeyboardMarkup:
    from keyboards import ib
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("Подписаться", "bell", url=REQUIRED_CHANNEL_URL)],
        [ib("Я подписался", "ok", callback_data="check_sub")],
    ])


async def send_subscribe_screen(msg: Message, first_name: str):
    import texts as T          # локально: texts тянет lolz/countries
    await answer_screen(msg, T.txt_subscribe(first_name or "пользователь"),
                        kb_subscribe_inline(), SUB_PHOTO())


async def answer_screen(msg: Message, text: str, kb, photo=None):
    """Отправляет экран (фото+подпись или просто текст) вместе с меню-клавиатурой."""
    try:
        if photo:
            return await msg.answer_photo(photo, caption=text, parse_mode=ParseMode.HTML,
                                          reply_markup=kb)
    except Exception as e:
        print(f"[answer_screen photo] {e}")
    return await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb,
                            disable_web_page_preview=True)


async def run_with_dots(msg: Message, label: str, coro):
    """
    Показывает «label.» → «label..» → «label...» пока выполняется coro.
    Возвращает (результат, исключение). Статус-сообщение удаляется.
    """
    status = await msg.answer(f"{label}.")
    task = asyncio.ensure_future(coro)
    i = 1
    while not task.done():
        await asyncio.wait({task}, timeout=1.0)
        if task.done():
            break
        i = i % 3 + 1
        try:
            await status.edit_text(f"{label}{'.' * i}")
        except Exception:
            pass
    try:
        await status.delete()
    except Exception:
        pass
    try:
        return task.result(), None
    except Exception as e:  # noqa
        return None, e


# ── Редактирование inline-сообщений ──
async def safe_edit(callback: CallbackQuery, photo, text: str, kb):
    """Редактирует сообщение; если есть фото — меняет медиа."""
    try:
        msg = callback.message
        if photo and (msg.photo or msg.document):
            await msg.edit_media(
                InputMediaPhoto(media=photo, caption=text, parse_mode=ParseMode.HTML),
                reply_markup=kb)
        elif photo:
            await msg.answer_photo(photo, caption=text,
                                   parse_mode=ParseMode.HTML, reply_markup=kb)
            try:
                await msg.delete()
            except Exception:
                pass
        else:
            try:
                await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        print(f"[safe_edit] {e}")
        try:
            if photo:
                await callback.message.answer_photo(photo, caption=text,
                                                    parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            pass


async def safe_edit_or_answer(callback: CallbackQuery, text: str, reply_markup=None):
    """
    Универсальная замена callback.message.edit_text().
    Работает как с обычными сообщениями, так и с фото-сообщениями
    (где edit_text падает с 'there is no text in the message to edit').
    """
    msg = callback.message
    try:
        if msg.photo or msg.document or msg.video or msg.animation:
            # Фото-сообщение: редактируем caption или отправляем новое
            try:
                await msg.edit_caption(caption=text, parse_mode=ParseMode.HTML,
                                       reply_markup=reply_markup)
            except Exception:
                await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception as e:
        print(f"[safe_edit_or_answer] {e}")
        try:
            await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except Exception:
            pass




# ── Общие хелперы ──────────────────────────────────────────
def money(v: float) -> str:
    """12.5 → «12.5 ₴», 100.0 → «100 ₴»."""
    return f"{float(v):,.2f}".rstrip("0").rstrip(".").replace(",", " ") + f" {CUR}"


def user_label(uid: int, username: str | None = None, name: str | None = None) -> str:
    """HTML: @username (id) либо кликабельное имя."""
    if username:
        return f"@{html.escape(username)} (<code>{uid}</code>)"
    return f'<a href="tg://user?id={uid}">{html.escape(name or "клиент")}</a> (<code>{uid}</code>)'


async def notify_admins(bot: Bot, text: str, reply_markup=None, photo: str | None = None,
                        document: str | None = None) -> int:
    """Рассылает сообщение всем админам. photo/document — file_id. Возвращает, скольким дошло.
    Если Telegram не принял reply_markup (например, URL-кнопка на закрытый профиль) — шлём без неё."""
    sent = 0
    for aid in ADMIN_IDS:
        for kb in ((reply_markup, None) if reply_markup else (None,)):
            try:
                if photo:
                    await bot.send_photo(aid, photo, caption=text, reply_markup=kb)
                elif document:
                    await bot.send_document(aid, document, caption=text, reply_markup=kb)
                else:
                    await bot.send_message(aid, text, reply_markup=kb, disable_web_page_preview=True)
                sent += 1
                break
            except Exception as e:
                print(f"[notify_admins] {aid}: {e!r}")
    return sent
