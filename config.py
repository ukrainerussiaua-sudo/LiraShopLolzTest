"""
config.py — настройки бота. Секреты берутся ТОЛЬКО из переменных окружения / .env
(см. .env.example). В коде никаких токенов не хранится.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Не задана переменная окружения {name} (см. .env.example)")
    return v


# ══════════════════════════════════════
# TELEGRAM / БРЕНД
# ══════════════════════════════════════
BOT_TOKEN    = _req("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MangoShopBot").lstrip("@")     # username бота — задайте в .env
ADMIN_IDS    = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

SHOP_NAME            = "Mango Shop"
SHOP_CHANNEL         = "@mangostarss"                       # канал (обязательная подписка)
SHOP_CHANNEL_URL     = "https://t.me/mangostarss"
SHOP_CHAT            = "@mango_markett"                     # чат
SHOP_CHAT_URL        = "https://t.me/mango_markett"
SUPPORT_ACCOUNT      = "@mango_user"                        # поддержка
SUPPORT_URL          = "https://t.me/mango_user"
REQUIRED_CHANNEL     = "@mangostarss"                       # бот должен быть АДМИНОМ этого канала
REQUIRED_CHANNEL_URL = SHOP_CHANNEL_URL

# Валюта магазина — гривна. Все цены, балансы и курсы — в ₴.
CUR = "₴"

# ══════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════
SUPABASE_URL = _req("SUPABASE_URL")
SUPABASE_KEY = _req("SUPABASE_KEY")   # service_role

# ══════════════════════════════════════
# LOLZ MARKET (источник аккаунтов)
# Токен: lolz.live → Настройки → API, права: read + market
# ══════════════════════════════════════
LOLZ_TOKEN     = _req("LOLZ_TOKEN")
LOLZ_BASE_URL  = os.getenv("LOLZ_BASE_URL", "https://api.lzt.market")
# Наценка больше не используется: цена каждой страны задаётся в админке («💲 Цены»)
MARKUP_PERCENT = float(os.getenv("MARKUP_PERCENT", "30"))
# Фильтр спамблока на стороне Lolz: no = только без спамблока
LOLZ_SPAM      = os.getenv("LOLZ_SPAM", "no")
# Происхождение: autoreg (авторег) и self_registration (саморег) — именно так их зовёт Lolz.
# В Supabase (bot_settings.lolz_origins) можно переопределить. Старое "self_registered" лечится автоматически (lolz.normalize_origins).
LOLZ_ORIGINS   = [x.strip() for x in os.getenv("LOLZ_ORIGINS", "autoreg,self_registration").split(",") if x.strip()]
# Сколько аккаунтов (от самого дешёвого) пробуем купить на Lolz, если первые уже разобрали
MAX_BUY_TRIES = 5
GUARANTEE_HOURS = int(os.getenv("GUARANTEE_HOURS", "5"))
# Lolz считает в рублях (запросы к API остаются в RUB — так цены и fast-buy совпадают с кабинетом Lolz).
# Сколько ₴ стоит 1 ₽ — нужно, чтобы сравнивать цену Lolz с гривневой ценой клиента и считать себестоимость.
# Можно менять в админке («💸 Себестоимость → Курс Lolz»), это значение — стартовое.
LOLZ_RUB_TO_UAH = float(os.getenv("LOLZ_RUB_TO_UAH", "0.46") or 0.46)
# Реферальный бонус пригласившему за покупку приглашённого, ₴
REF_BONUS = float(os.getenv("REF_BONUS", "2") or 0)

# ══════════════════════════════════════
# ПУТИ К ИЗОБРАЖЕНИЯМ
# ══════════════════════════════════════
IMAGES_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
SHOP_PHOTO_PATH     = os.path.join(IMAGES_DIR, "shop.jpg")
PROFILE_PHOTO_PATH  = os.path.join(IMAGES_DIR, "profile.jpg")
TOPUP_PHOTO_PATH    = os.path.join(IMAGES_DIR, "topup.jpg")
SUB_PHOTO_PATH      = os.path.join(IMAGES_DIR, "sub.jpg")
INFO_PHOTO_PATH     = os.path.join(IMAGES_DIR, "info.jpg")
SUPPORT_PHOTO_PATH  = os.path.join(IMAGES_DIR, "support.jpg")
TELEGRAM_PHOTO_PATH = os.path.join(IMAGES_DIR, "telegram.jpg")
CATALOG_PHOTO_PATH  = os.path.join(IMAGES_DIR, "catalog.jpg")
STARS_PHOTO_PATH    = os.path.join(IMAGES_DIR, "stars.jpg")      # баннер добавите позже — без файла бот шлёт просто текст
PREMIUM_PHOTO_PATH  = os.path.join(IMAGES_DIR, "premium.jpg")

# ══════════════════════════════════════
# ПОПОЛНЕНИЕ БАЛАНСА
# ══════════════════════════════════════
# Перевод на карту: реквизиты можно задать здесь (.env) или в админке («💳 Реквизиты карты») — админка важнее.
# Платёж подтверждает админ по чеку (скрин/PDF) — автопроверки банка нет.
CARD_NUMBER = os.getenv("CARD_NUMBER", "").strip()
CARD_HOLDER = os.getenv("CARD_HOLDER", "").strip()
CARD_BANK   = os.getenv("CARD_BANK", "").strip()
MIN_TOPUP_DEFAULT = float(os.getenv("MIN_TOPUP", "50") or 50)          # ₴, меняется в админке
CARD_PAYMENT_TTL_H = int(os.getenv("CARD_PAYMENT_TTL_H", "24") or 24)  # сколько живёт заявка без чека (ручной режим)

# Автопроверка перевода на карту через Monobank Open API (monopay.py). Токен задан → работает «Проверить оплату» без админа.
# Токен: застосунок Monobank → «Ще» → «Інше» → «Monobank Open API». Карта в CARD_NUMBER/«Реквизиты карты» должна быть с этого токена.
MONOBANK_API_TOKEN  = os.getenv("MONOBANK_API_TOKEN", "").strip()
MONOBANK_ACCOUNT_ID = os.getenv("MONOBANK_ACCOUNT_ID", "0").strip() or "0"   # 0 = основной счёт; список: GET /personal/client-info
MONOBANK_PAYMENT_TTL_MIN = int(os.getenv("MONOBANK_PAYMENT_TTL_MIN", "30") or 30)   # сколько минут даётся на оплату

# Crypto Bot: счёт выставляется в UAH (fiat). Если Crypto Bot не принял UAH — запасной пересчёт в USDT по этому курсу.
CRYPTO_PAY_TOKEN    = os.getenv("CRYPTO_PAY_TOKEN", "")
CRYPTO_PAY_ASSET    = os.getenv("CRYPTO_PAY_ASSET", "USDT").upper()
CRYPTO_PAY_TESTNET  = os.getenv("CRYPTO_PAY_TESTNET", "0") == "1"
CRYPTO_PAY_BASE_URL = ("https://testnet-pay.crypt.bot/api" if CRYPTO_PAY_TESTNET
                       else "https://pay.crypt.bot/api")
CRYPTO_PAY_RETURN_URL = f"https://t.me/{BOT_USERNAME}"
CRYPTO_UAH_TO_USDT_FALLBACK = float(os.getenv("CRYPTO_UAH_TO_USDT_FALLBACK", "41.5") or 41.5)

# TON-пополнение: адрес приёма и курс задаются в админке («💠 Настройки TON»).
# Если адрес в админке не задан, а TON_MNEMONIC есть — принимаем на адрес горячего кошелька бота.
TON_DEPOSIT_POLL_S = int(os.getenv("TON_DEPOSIT_POLL_S", "30") or 30)   # как часто бот сам ищет новые переводы
# Курс TON с сайта (CoinGecko, TON→UAH). Ключ необязателен (бесплатный Demo-ключ даёт больше лимит).
COINGECKO_API_KEY    = os.getenv("COINGECKO_API_KEY", "").strip()
TON_RATE_REFRESH_S   = int(os.getenv("TON_RATE_REFRESH_S", "60") or 60)       # как часто обновлять курс
TON_RATE_MAX_AGE_S   = int(os.getenv("TON_RATE_MAX_AGE_S", "900") or 900)     # курс старше — не используем (TON-операции встают на паузу)

# ══════════════════════════════════════
# FRAGMENT: Telegram Stars + Premium (порт n0/fragment-tg)
# Cookies — из браузера, где вы вошли на fragment.com через Telegram и подключили ТОТ ЖЕ TON-кошелёк,
# что и в TON_MNEMONIC (DevTools → Application → Cookies → fragment.com).
# ══════════════════════════════════════
FRAGMENT_STEL_SSID      = os.getenv("FRAGMENT_STEL_SSID", "").strip()
FRAGMENT_STEL_TOKEN     = os.getenv("FRAGMENT_STEL_TOKEN", "").strip()
FRAGMENT_STEL_TON_TOKEN = os.getenv("FRAGMENT_STEL_TON_TOKEN", "").strip()
FRAGMENT_USER_AGENT   = os.getenv("FRAGMENT_USER_AGENT", "").strip()      # лучше вставить User-Agent вашего браузера
FRAGMENT_STEL_DT        = os.getenv("FRAGMENT_STEL_DT", "-180").strip()    # смещение часового пояса, мин (МСК = -180)
TON_MNEMONIC            = os.getenv("TON_MNEMONIC", "").strip()            # 24 слова горячего кошелька
TON_WALLET_VERSION      = os.getenv("TON_WALLET_VERSION", "v4r2").strip().lower()
TONCENTER_URL           = os.getenv("TONCENTER_URL", "https://toncenter.com/api/v2").rstrip("/")
TONCENTER_API_KEY       = os.getenv("TONCENTER_API_KEY", "").strip()      # необязательно, но с ключом меньше лимитов
FRAGMENT_CONFIGURED = bool(FRAGMENT_STEL_SSID and FRAGMENT_STEL_TOKEN
                           and FRAGMENT_STEL_TON_TOKEN and TON_MNEMONIC)

# ══════════════════════════════════════
# ССЫЛКИ
# ══════════════════════════════════════
# Документы (telegra.ph и т.п.). Пусто = строка в боте не показывается. Задаются в .env
DOC_RULES_URL   = os.getenv("DOC_RULES_URL", "").strip()
DOC_PRIVACY_URL = os.getenv("DOC_PRIVACY_URL", "").strip()
DOC_TERMS_URL   = os.getenv("DOC_TERMS_URL", "").strip()

# ══════════════════════════════════════
# СТРАНЫ: ключ → флаг, название, ISO-код для Lolz, телефонный код.
# Цены больше НЕ задаются здесь — берутся живьём с Lolz + наценка.
# Это ЗАПАСНОЙ список: основной лежит в Supabase (таблица shop_countries).
# ══════════════════════════════════════
COUNTRIES: dict[str, dict] = {
    "us": {"flag": "🇺🇸", "name": "США", "iso": "US", "code": "+1"},
    "mm": {"flag": "🇲🇲", "name": "Мьянма", "iso": "MM", "code": "+95"},
    "idn": {"flag": "🇮🇩", "name": "Индонезия", "iso": "ID", "code": "+62"},
    "ind": {"flag": "🇮🇳", "name": "Индия", "iso": "IN", "code": "+91"},
    "bd": {"flag": "🇧🇩", "name": "Бангладеш", "iso": "BD", "code": "+880"},
    "ph": {"flag": "🇵🇭", "name": "Филиппины", "iso": "PH", "code": "+63"},
    "vn": {"flag": "🇻🇳", "name": "Вьетнам", "iso": "VN", "code": "+84"},
    "br": {"flag": "🇧🇷", "name": "Бразилия", "iso": "BR", "code": "+55"},
    "pk": {"flag": "🇵🇰", "name": "Пакистан", "iso": "PK", "code": "+92"},
    "ng": {"flag": "🇳🇬", "name": "Нигерия", "iso": "NG", "code": "+234"},
    "eg": {"flag": "🇪🇬", "name": "Египет", "iso": "EG", "code": "+20"},
    "tr": {"flag": "🇹🇷", "name": "Турция", "iso": "TR", "code": "+90"},
    "kz": {"flag": "🇰🇿", "name": "Казахстан", "iso": "KZ", "code": "+7"},
    "uz": {"flag": "🇺🇿", "name": "Узбекистан", "iso": "UZ", "code": "+998"},
    "ca": {"flag": "🇨🇦", "name": "Канада", "iso": "CA", "code": "+1"},
    "mx": {"flag": "🇲🇽", "name": "Мексика", "iso": "MX", "code": "+52"},
    "co": {"flag": "🇨🇴", "name": "Колумбия", "iso": "CO", "code": "+57"},
    "ar": {"flag": "🇦🇷", "name": "Аргентина", "iso": "AR", "code": "+54"},
    "ke": {"flag": "🇰🇪", "name": "Кения", "iso": "KE", "code": "+254"},
    "th": {"flag": "🇹🇭", "name": "Таиланд", "iso": "TH", "code": "+66"},
    "my": {"flag": "🇲🇾", "name": "Малайзия", "iso": "MY", "code": "+60"},
    "kh": {"flag": "🇰🇭", "name": "Камбоджа", "iso": "KH", "code": "+855"},
    "np": {"flag": "🇳🇵", "name": "Непал", "iso": "NP", "code": "+977"},
    "et": {"flag": "🇪🇹", "name": "Эфиопия", "iso": "ET", "code": "+251"},
    "za": {"flag": "🇿🇦", "name": "ЮАР", "iso": "ZA", "code": "+27"},
    "pe": {"flag": "🇵🇪", "name": "Перу", "iso": "PE", "code": "+51"},
    "gb": {"flag": "🇬🇧", "name": "Великобритания", "iso": "GB", "code": "+44"},
    "de": {"flag": "🇩🇪", "name": "Германия", "iso": "DE", "code": "+49"},
    "ua": {"flag": "🇺🇦", "name": "Украина", "iso": "UA", "code": "+380"},
    "ru": {"flag": "🇷🇺", "name": "Россия", "iso": "RU", "code": "+7"},
}

# ══════════════════════════════════════
# ПРЕМИУМ ЭМОДЗИ (ID — только из https://emoji.wivvi.net, см. emoji.py)
# ══════════════════════════════════════
from emoji import tag as _t

PEPE          = _t("store", "🏪")
DIAMOND       = _t("diamond", "💎")
PLANE         = _t("telegram", "✈️")
USDT          = _t("dollar", "💵")
QUESTION      = _t("question", "❓")
SPARKLE_BALL  = _t("sparkles", "✨")
SPARKLE_STARS = _t("party", "🎉")
BULB          = _t("bulb", "💡")

EMOJI_HEART     = _t("heart", "❤️")
EMOJI_CHECK     = _t("ok", "✅")
EMOJI_GLOBE     = _t("globe", "🌐")
EMOJI_INFO      = _t("info", "ℹ️")
EMOJI_CRYPTOBOT = _t("wallet", "👛")
EMOJI_TON       = _t("ton", "💠")
EMOJI_GOLD      = _t("gold", "🥇")
EMOJI_STARS     = _t("stars", "⭐")
EMOJI_CARD      = _t("atm", "💳")
