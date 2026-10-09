"""
i18n.py — язык бота: русский / украинский.

Идея: ВЕСЬ код бота пишет и понимает русский («канонический» язык). Для пользователя с языком «uk» два прозрачных слоя:
  • ИСХОДЯЩИЙ (TranslateMiddleware, на сессии бота): перед отправкой переводит text/caption и тексты кнопок
    русский → украинский по таблице фрагментов i18n_uk.py (самые длинные фрагменты первыми, одним проходом);
  • ВХОДЯЩИЙ (LangMiddleware, в main.py): если пользователь нажал украинскую кнопку, текст сообщения подменяется
    на русский канонический, поэтому ни один хендлер не знает про язык. Обычный набранный текст не трогается.
Язык хранится в users.lang ('ru' | 'uk') и кэшируется. Выбор — при первом /start (до проверки подписки на канал),
сменить можно в «Профиль → Язык / Мова».
Фрагмент без перевода в i18n_uk.py просто останется русским — ничего не ломается.
"""
from __future__ import annotations
import contextvars
import re

from i18n_uk import PAIRS, COUNTRY_NAMES

try:
    from aiogram.client.session.middlewares.base import BaseRequestMiddleware
except Exception:                       # pragma: no cover
    BaseRequestMiddleware = object

LANGS = ("ru", "uk")
CUR_UID: contextvars.ContextVar[int] = contextvars.ContextVar("cur_uid", default=0)
_cache: dict[int, str] = {}


# ── язык пользователя ──────────────────────────────────────
def lang_of(uid: int) -> str:
    """'ru' | 'uk' | '' (ещё не выбирал)."""
    if not uid:
        return ""
    v = _cache.get(uid)
    if v:
        return v
    from database import db
    try:
        v = db.get_lang(uid)
    except Exception as e:
        print(f"[i18n] get_lang: {e!r}")
        v = ""
    if v in LANGS:
        _cache[uid] = v
        return v
    return ""


def set_lang(uid: int, lang: str) -> None:
    """Запоминает язык в кэше и (если пользователь уже в БД) в users.lang. Новому пользователю язык запишет _register()."""
    if lang not in LANGS:
        return
    _cache[uid] = lang
    from database import db
    try:
        db.set_lang(uid, lang)
    except Exception as e:
        print(f"[i18n] set_lang: {e!r}")


# ── перевод ────────────────────────────────────────────────
_LET = "A-Za-zА-Яа-яЁёІіЇїЄєҐґ"
_MAP: dict[str, str] = {**PAIRS, **COUNTRY_NAMES}


def _compile(mapping: dict[str, str]) -> re.Pattern:
    parts = []
    for k in sorted(mapping, key=len, reverse=True):
        pre = rf"(?<![{_LET}])" if k[:1].isalpha() else ""
        post = rf"(?![{_LET}])" if k[-1:].isalpha() else ""
        parts.append(pre + re.escape(k) + post)
    return re.compile("|".join(parts))


_RE = _compile(_MAP)


def tr(text: str) -> str:
    """Русский (канонический) текст → украинский. Не найденные фрагменты остаются как есть."""
    if not text:
        return text
    return _RE.sub(lambda m: _MAP[m.group(0)], text)


# ── обратное преобразование нажатой кнопки: украинская → русская (для хендлеров) ──
_rev_exact: dict[str, str] | None = None
_REV_COUNTRY = {uk: ru for ru, uk in COUNTRY_NAMES.items() if uk != ru}
_REV_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(\d+) зірок · (.*)$", re.S), r"\1 звёзд · \2"),
    (re.compile(r"^(\d+) міс · (.*)$", re.S), r"\1 мес · \2"),
    (re.compile(r"^Підтвердити · (.*)$", re.S), r"Подтвердить · \1"),
    (re.compile(r"^Сплатити TON · (.*)$", re.S), r"Оплатить TON · \1"),
    (re.compile(r"^Сплатити · (.*)$", re.S), r"Оплатить · \1"),
]
_COUNTRY_BTN = re.compile(r"^(\S+) (.+?) · (.+)$", re.S)


def _build_rev() -> dict[str, str]:
    import keyboards as K
    rev: dict[str, str] = {}
    for name, val in vars(K).items():
        if isinstance(val, str) and (name.startswith("B_") or name == "TO_ADMIN"):
            t = tr(val)
            if t != val:
                if t in rev and rev[t] != val:
                    print(f"[i18n] коллизия кнопок: {t!r} ← {rev[t]!r} / {val!r}")
                rev[t] = val
    return rev


def button_to_ru(text: str) -> str:
    """Если text — украинская кнопка (статическая или с ценой/страной), вернёт её русский вариант; иначе text без изменений."""
    global _rev_exact
    if _rev_exact is None:
        _rev_exact = _build_rev()
    if text in _rev_exact:
        return _rev_exact[text]
    for rx, rep in _REV_RULES:
        if rx.match(text):
            return rx.sub(rep, text)
    m = _COUNTRY_BTN.match(text)
    if m and m.group(2) in _REV_COUNTRY:
        return f"{m.group(1)} {_REV_COUNTRY[m.group(2)]} · {m.group(3)}"
    return text


# ── разметка (кнопки) ──────────────────────────────────────
def tr_markup(rm):
    """ReplyKeyboardMarkup / InlineKeyboardMarkup → копия с переведёнными подписями кнопок."""
    if rm is None:
        return rm
    if hasattr(rm, "inline_keyboard"):
        rows = [[b.model_copy(update={"text": tr(b.text)}) for b in row] for row in rm.inline_keyboard]
        return rm.model_copy(update={"inline_keyboard": rows})
    if hasattr(rm, "keyboard"):
        rows = [[b.model_copy(update={"text": tr(b.text)}) if hasattr(b, "model_copy") else b for b in row]
                for row in rm.keyboard]
        upd = {"keyboard": rows}
        if getattr(rm, "input_field_placeholder", None):
            upd["input_field_placeholder"] = tr(rm.input_field_placeholder)
        return rm.model_copy(update=upd)
    return rm


class TranslateMiddleware(BaseRequestMiddleware):
    """Исходящий middleware сессии бота: переводит сообщения для пользователей с языком 'uk'."""

    async def __call__(self, make_request, bot, method):
        try:
            chat_id = getattr(method, "chat_id", None)
            uid = chat_id if isinstance(chat_id, int) and chat_id > 0 else CUR_UID.get()
            if uid and lang_of(uid) == "uk":
                for field in ("text", "caption"):
                    v = getattr(method, field, None)
                    if isinstance(v, str) and v:
                        setattr(method, field, tr(v))
                rm = getattr(method, "reply_markup", None)
                if rm is not None:
                    setattr(method, "reply_markup", tr_markup(rm))
        except Exception as e:           # noqa — перевод не должен ронять отправку
            print(f"[i18n translate] {e!r}")
        return await make_request(bot, method)
