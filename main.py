"""
main.py — точка входа бота.
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import CallbackQuery, Message
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from handlers import (
    shop, topup, promo, replacement, admin, admin_extra, fallback, fragment_shop, fragment_admin, gold, ton_shop,
)
from utils import is_banned, is_subscribed, send_subscribe_screen, send_lang_chooser
from database import db
import i18n
from payments import watch_pending
from tondeposit import watch_ton_deposits
from tonrate import watch_ton_rate
from monopay import watch_mono
from emoji import PremiumEmojiMiddleware


class BanMiddleware(BaseMiddleware):
    """Заблокированным пользователям бот не отвечает (кроме слова Banned)."""
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user and is_banned(user.id):
            if hasattr(event, "answer") and not hasattr(event, "data"):
                await event.answer("Banned")
            return
        return await handler(event, data)


class LangMiddleware(BaseMiddleware):
    """
    Язык бота (русский / украинский). Идёт ДО проверки подписки:
      • новый пользователь (нет языка и нет в БД) → показываем выбор языка, остальное не обрабатываем;
      • старый пользователь без выбора → русский (как было);
      • украинские кнопки подменяем на русские канонические — хендлеры язык не знают (см. i18n.py);
      • CUR_UID — чтобы ответы на нажатия (всплывающие уведомления) тоже переводились.
    """
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        uid = user.id
        lang = i18n.lang_of(uid)
        if not lang and db.find_user_by_id(uid):
            lang = "ru"
            i18n.set_lang(uid, "ru")
        is_lang_cb = isinstance(event, CallbackQuery) and (event.data or "").startswith("lang:")
        if not lang and not is_lang_cb:
            text = getattr(event, "text", None) or ""
            state = data.get("state")
            parts = text.split()
            if state and parts[:1] == ["/start"] and len(parts) > 1 and parts[1].isdigit():
                await state.update_data(pending_ref=int(parts[1]))        # реферал не теряем до регистрации
            target = event.message if isinstance(event, CallbackQuery) else event
            if isinstance(event, CallbackQuery):
                await event.answer()
            if target is not None:
                await send_lang_chooser(target)
            return
        token = i18n.CUR_UID.set(uid)
        try:
            if lang == "uk" and isinstance(event, Message) and event.text:
                ru = i18n.button_to_ru(event.text)
                if ru != event.text:
                    try:
                        object.__setattr__(event, "text", ru)
                    except Exception:
                        event = event.model_copy(update={"text": ru})
            data["lang"] = lang
            return await handler(event, data)
        finally:
            i18n.CUR_UID.reset(token)


class SubscriptionMiddleware(BaseMiddleware):
    """
    Обязательная подписка на канал: пока человек не подписан, ЛЮБОЕ его сообщение/кнопка
    приводит только к экрану «Подпишись на канал». Админы и кнопка «Я подписался» — пропускаются.
    """
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user or user.id in ADMIN_IDS:
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and (event.data == "check_sub" or (event.data or "").startswith("lang:")):
            return await handler(event, data)
        if await is_subscribed(data["bot"], user.id):
            return await handler(event, data)

        # Не подписан. Реферальный /start запоминаем, чтобы не потерять после подписки.
        text = getattr(event, "text", None) or ""
        state = data.get("state")
        parts = text.split()
        if state and parts[:1] == ["/start"] and len(parts) > 1 and parts[1].isdigit():
            await state.update_data(pending_ref=int(parts[1]))

        target = event.message if isinstance(event, CallbackQuery) else event
        if isinstance(event, CallbackQuery):
            await event.answer()
        if target is not None:
            await send_subscribe_screen(target, user.first_name or "")
        return


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx пишет строку на КАЖДЫЙ запрос к Supabase (фоновая проверка оплат — раз в ~3.5 с) и забивает лог.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(i18n.TranslateMiddleware())       # русский → украинский для пользователей с языком «uk»
    bot.session.middleware(PremiumEmojiMiddleware())     # обычные эмодзи в тексте → премиум (см. emoji.py)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())
    dp.message.outer_middleware(LangMiddleware())
    dp.callback_query.outer_middleware(LangMiddleware())
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())

    # Порядок важен: глобальные кнопки меню (shop) раньше обработчиков ввода (topup/promo/replacement)
    dp.include_router(admin.router)
    dp.include_router(admin_extra.router)
    dp.include_router(fragment_admin.router)
    dp.include_router(shop.router)
    dp.include_router(fragment_shop.router)
    dp.include_router(gold.router)
    dp.include_router(ton_shop.router)
    dp.include_router(topup.router)
    dp.include_router(promo.router)
    dp.include_router(replacement.router)
    dp.include_router(fallback.router)

    asyncio.create_task(watch_pending(bot))           # Crypto Bot: зачисление оплат (переживает рестарты)
    asyncio.create_task(watch_mono(bot))              # перевод на карту (Monobank API): автопоиск оплат раз в минуту
    asyncio.create_task(watch_ton_rate(bot))          # курс TON с сайта (CoinGecko) для режима «Сайт»
    asyncio.create_task(watch_ton_deposits(bot))      # TON-пополнения: поиск переводов с ID в комментарии
    print("🤖 Бот запущен...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
