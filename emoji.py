"""
emoji.py — премиум-эмодзи Telegram (пак «Telegram iOS Icons», ID берутся ТОЛЬКО из списка https://emoji.wivvi.net).

Как это работает:
  • Сообщения: везде в коде можно писать обычные эмодзи — PremiumEmojiMiddleware (подключается в main.py)
    перед отправкой сам заменяет известные эмодзи на <tg-emoji emoji-id="…">. Код внутри <code>/<pre> не трогается.
  • Кнопки (reply и inline): текст БЕЗ эмодзи, иконка — в поле icon_custom_emoji_id (см. keyboards.py).
  • Нужен Telegram Premium у владельца бота и Bot API 9.4+. Без Premium вместо иконок в сообщениях
    будут обычные эмодзи, а на кнопках иконки не покажутся.
"""
from __future__ import annotations
import re

try:                                    # aiogram >= 3.7
    from aiogram.client.default import Default
except Exception:                       # pragma: no cover
    Default = None
try:
    from aiogram.client.session.middlewares.base import BaseRequestMiddleware
except Exception:                       # pragma: no cover
    BaseRequestMiddleware = object

# ── ID иконок (имя → emoji-id). Всё из списка emoji.wivvi.net ──────────────
I: dict[str, str] = {
    "store": "5920332557466997677",      # 🏪 Магазин
    "profile": "6035084557378654059",    # 👤 Профиль
    "wallet": "5769126056262898415",     # 👛 Кошелёк
    "chat": "6030784887093464891",       # 💬 Сообщение
    "info": "6028435952299413210",       # ℹ Инфо
    "settings": "6032742198179532882",   # ⚙ Настройки
    "gear": "5850309953293653168",       # ⚙️ Шестерёнка
    "back": "5960671702059848143",       # ⬅️ Назад
    "home": "6042137469204303531",       # 🏠 Дом
    "cancel": "5774077015388852135",     # ❌ Крестик
    "ok": "5774022692642492953",         # ✅ Галочка
    "unlock": "6037496202990194718",     # 🔓 Замок открытый
    "lock": "6037249452824072506",       # 🔒 Замок закрытый
    "repeat": "6030657343744644592",     # 🔁 Повтор
    "doc": "6050643982646513651",        # 📄 Документ строки
    "list": "5766994197705921104",       # 🗂 Список
    "recent": "5775896410780079073",     # 🕓 Недавнее
    "tag": "5890727932011223292",        # 🏷 Ценник
    "tag_fill": "5890883384057533697",   # 🏷 Ценник заливка
    "people": "6032609071373226027",     # 👥 Люди
    "telegram": "6028346797368283073",   # ✈️ Телеграм
    "stars": "6028338546736107668",      # ⭐️ Звёзды TG
    "star": "6034923938486684992",       # ⭐️ Звезда
    "premium": "5836907383292436018",    # 💎 Алмаз с блёстками
    "diamond": "6037083366438737901",    # 💎 Алмаз
    "gold": "6037428784888549034",       # 🥇 Один раз серия (золотая медаль)
    "ton": "5769406891289481208",        # 💎 TON
    "money_out": "5904359114531675993",  # 💰 Вывод денег
    "dollar": "5904462880941545555",     # 🪙 Доллар
    "coin": "5778613750688911681",       # 🪙 Контраст
    "atm": "5879814368572478751",        # 🏧 Банкомат
    "send": "6039391666547201160",       # ⬆️ Отправить
    "fwd": "6037622221625626773",        # ➡️ Переслать
    "edit": "6039779802741739617",       # ✏️ Редактировать
    "stats": "5936143551854285132",      # 📊 Статистика график
    "chart_up": "5938539885907415367",   # 📈 Рост график
    "analytics": "5935913431801532272",  # 📈 Аналитика
    "megaphone": "6021418126061605425",  # 📢 Рупор
    "inbox": "5776182936638329359",      # 📥 Входящие
    "warning": "6030563507299160824",    # ❗️ Внимание
    "question": "6030848053177486888",   # ❓ Вопрос
    "sparkles": "5890925363067886150",   # ✨ Блёстки
    "party": "6041731551845159060",      # 🎉 Ура
    "bulb": "5767288287001580715",       # 💡 Лампочка
    "heart": "5938368005611195877",      # ❤️ Сердце
    "globe": "5776233299424843260",      # 🌐 Глобус
    "hourglass": "5891211339170326418",  # ⌛️ Песочные часы
    "calendar": "5890937706803894250",   # 📅 Календарь
    "clock": "5983150113483134607",      # ⏰️ Часы
    "search": "6032850693348399258",     # 🔎 Поиск
    "gift": "6032644646587338669",       # 🎁 Подарок
    "link": "6028171274939797252",       # 🔗 Ссылка
    "shield": "6030445631921721471",     # 🛡 Щит галочка
    "box": "5884479287171485878",        # 📦 Куб
    "pin": "6043896193887506430",        # 📌 Закрепить
    "trash": "6039522349517115015",      # 🗑 Мусорный бак
    "bell": "6039486778597970865",       # 🔔 Уведомление
    "plus": "6033108709213736873",       # ➕ Добавить человека
    "new": "5895669571058142797",        # 🆕 NEW
    "ban": "5938215362473496448",        # 🚫 Ладонь запрет
    "id": "5886285355279193209",         # 🏷 Тег (для ID)
    "briefcase": "5938492039971737551",  # 💼 Портфель
    "id_card": "6032693626394382504",    # 👤 Аватар
}

# ── Обычное эмодзи в тексте сообщения → премиум-иконка ─────────────────────
TEXT_EMOJI: dict[str, str] = {
    "✅": I["ok"], "❌": I["cancel"], "⚠️": I["warning"], "⚠": I["warning"], "❗": I["warning"], "🚨": I["warning"],
    "❓": I["question"], "ℹ️": I["info"], "ℹ": I["info"],
    "⭐": I["star"], "💎": I["diamond"], "💠": I["ton"],
    "💰": I["money_out"], "💵": I["dollar"], "🪙": I["coin"], "💳": I["atm"], "👛": I["wallet"],
    "🥇": I["gold"], "💼": I["briefcase"],
    "👤": I["profile"], "👥": I["people"], "🆔": I["id"],
    "📅": I["calendar"], "⏰": I["clock"], "🕒": I["recent"], "⏳": I["hourglass"],
    "🔑": I["unlock"], "🔒": I["lock"], "🔎": I["search"], "🔄": I["repeat"],
    "🎁": I["gift"], "🎟": I["tag"], "🏷": I["tag"], "🛡": I["shield"], "🔗": I["link"], "🌐": I["globe"],
    "📢": I["megaphone"], "📊": I["stats"], "📈": I["chart_up"], "📦": I["box"], "💬": I["chat"],
    "✨": I["sparkles"], "🎉": I["party"], "💡": I["bulb"], "❤️": I["heart"], "❤": I["heart"],
    "📌": I["pin"], "🧾": I["doc"], "🏪": I["store"], "🆕": I["new"], "🛠": I["settings"],
    "🔔": I["bell"], "✈️": I["telegram"], "✈": I["telegram"], "🗑": I["trash"], "🏠": I["home"], "🚫": I["ban"],
}
_KEYS = sorted(TEXT_EMOJI, key=len, reverse=True)
_EMO_RE = re.compile("(" + "|".join(re.escape(k) for k in _KEYS) + ")\ufe0f?")
_TOKEN_RE = re.compile(r"(<tg-emoji\b[^>]*>.*?</tg-emoji>|<[^>]*>)", re.S | re.I)
_CODE_OPEN = re.compile(r"<(code|pre)\b", re.I)
_CODE_CLOSE = re.compile(r"</(code|pre)>", re.I)


def tag(name_or_id: str, fallback: str) -> str:
    """<tg-emoji …> по имени из I или по готовому ID."""
    eid = I.get(name_or_id, name_or_id)
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'


def premiumize(text: str) -> str:
    """Заменяет обычные эмодзи в HTML-тексте на премиум. Теги и содержимое <code>/<pre> не трогает."""
    if not text:
        return text
    out: list[str] = []
    depth = 0
    for part in _TOKEN_RE.split(text):
        if not part:
            continue
        if part.startswith("<"):
            if _CODE_OPEN.match(part):
                depth += 1
            elif _CODE_CLOSE.match(part):
                depth = max(0, depth - 1)
            out.append(part)
            continue
        if depth:
            out.append(part)
            continue
        out.append(_EMO_RE.sub(lambda m: tag(TEXT_EMOJI[m.group(1)], m.group(1)), part))
    return "".join(out)


def _is_html(bot, pm) -> bool:
    if Default is not None and isinstance(pm, Default):
        pm = getattr(getattr(bot, "default", None), pm.name, None)
    if pm is None:
        return False
    return str(getattr(pm, "value", pm)).upper() == "HTML"


class PremiumEmojiMiddleware(BaseRequestMiddleware):
    """Исходящий middleware: подменяет эмодзи в text/caption любого HTML-сообщения. Ошибки глотает — отправку не ломает."""

    async def __call__(self, make_request, bot, method):
        try:
            if hasattr(method, "parse_mode") and _is_html(bot, getattr(method, "parse_mode", None)):
                for field, ents in (("text", "entities"), ("caption", "caption_entities")):
                    v = getattr(method, field, None)
                    if isinstance(v, str) and v and not getattr(method, ents, None):
                        new = premiumize(v)
                        if new != v:
                            setattr(method, field, new)
        except Exception as e:           # noqa
            print(f"[premium emoji] {e!r}")
        return await make_request(bot, method)
