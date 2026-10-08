"""
ton_wallet.py — свой TON-кошелёк бота (v4R2 из seed-фразы) + отправка транзакций через toncenter.
Нужен для оплаты заказов на Fragment. Фраза хранится ТОЛЬКО в .env (TON_MNEMONIC).
Рекомендация: отдельный «горячий» кошелёк, на котором лежит немного TON.
"""
from __future__ import annotations
import asyncio
import base64
import logging
import time
from dataclasses import dataclass

import aiohttp

import config as cfg

log = logging.getLogger("ton_wallet")

_send_lock = asyncio.Lock()      # одна транзакция за раз (иначе конфликт seqno)


def is_configured() -> bool:
    """Задана ли seed-фраза горячего кошелька (нужна для покупки TON клиентами и для Fragment)."""
    return bool(cfg.TON_MNEMONIC)


def _errors():
    import fragment                      # поздний импорт: избегаем циклов
    return fragment.FragmentError, fragment.FragmentUncertain


@dataclass
class Wallet:
    obj: object
    raw_address: str
    friendly: str
    public_key_hex: str
    state_init_b64: str


_wallet: Wallet | None = None


def get_wallet() -> Wallet:
    global _wallet
    if _wallet is not None:
        return _wallet
    FragmentError, _ = _errors()
    try:
        from tonsdk.contract.wallet import Wallets, WalletVersionEnum
        from tonsdk.utils import bytes_to_b64str
    except ImportError:
        raise FragmentError("Не установлен tonsdk (pip install tonsdk)")
    words = cfg.TON_MNEMONIC.split()
    if len(words) != 24:
        raise FragmentError("TON_MNEMONIC должен содержать 24 слова")
    ver = {"v3r2": WalletVersionEnum.v3r2, "v4r2": WalletVersionEnum.v4r2}.get(cfg.TON_WALLET_VERSION)
    if ver is None:
        raise FragmentError("TON_WALLET_VERSION: v3r2 или v4r2 (v5/W5 tonsdk не поддерживает)")
    _, pub, _priv, w = Wallets.from_mnemonics(words, ver, 0)
    state_init = w.create_state_init()["state_init"]
    _wallet = Wallet(
        obj=w,
        raw_address=w.address.to_string(False, False, False),
        friendly=w.address.to_string(True, True, False),
        public_key_hex=pub.hex() if isinstance(pub, (bytes, bytearray)) else str(pub),
        state_init_b64=bytes_to_b64str(state_init.to_boc(False)),
    )
    return _wallet


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if cfg.TONCENTER_API_KEY:
        h["X-API-Key"] = cfg.TONCENTER_API_KEY
    return h


async def _get_info(sess: aiohttp.ClientSession, address: str) -> dict:
    for attempt in range(4):
        async with sess.get(f"{cfg.TONCENTER_URL}/getWalletInformation",
                            params={"address": address}, headers=_headers()) as r:
            if r.status == 429:
                await asyncio.sleep(1.2 * (attempt + 1))
                continue
            js = await r.json()
            if not js.get("ok"):
                raise RuntimeError(f"toncenter: {js}")
            return js["result"]
    raise RuntimeError("toncenter: rate limit")


async def get_balance_ton() -> float:
    w = get_wallet()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as sess:
        info = await _get_info(sess, w.friendly)
    return int(info.get("balance") or 0) / 1e9


def _payload_cell(payload: str | None):
    if not payload:
        return None
    from tonsdk.boc import Cell
    s = payload.strip().replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    return Cell.one_from_boc(base64.b64decode(s))


async def send_messages(messages: list[dict]) -> str:
    """
    Подписывает и отправляет транзакцию из ответа Fragment. Возвращает base64-BOC.
    До broadcast любая ошибка = FragmentError (деньги вернуть можно).
    После broadcast неизвестный итог = FragmentUncertain.
    """
    FragmentError, FragmentUncertain = _errors()
    if len(messages) != 1:
        raise FragmentError(f"Fragment вернул {len(messages)} сообщений, поддерживается 1")
    msg = messages[0]
    amount = int(msg["amount"])
    w = get_wallet()

    async with _send_lock:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            try:
                info = await _get_info(sess, w.friendly)
            except Exception as e:
                raise FragmentError(f"toncenter недоступен: {e!r}")
            balance = int(info.get("balance") or 0)
            seqno = int(info.get("seqno") or 0)
            if balance < amount + 50_000_000:        # + ~0.05 TON на комиссию
                raise FragmentError(
                    f"На TON-кошельке бота мало средств: {balance / 1e9:.3f} TON, "
                    f"нужно ≈ {(amount + 50_000_000) / 1e9:.3f} TON")
            if seqno == 0:
                raise FragmentError("TON-кошелёк не активирован (seqno=0): переведите на него немного TON")

            try:
                query = w.obj.create_transfer_message(
                    to_addr=msg["address"], amount=amount, seqno=seqno,
                    payload=_payload_cell(msg.get("payload")))
                from tonsdk.utils import bytes_to_b64str
                boc = bytes_to_b64str(query["message"].to_boc(False))
            except Exception as e:
                raise FragmentError(f"Не смог собрать транзакцию: {e!r}")

            # ── broadcast ──
            try:
                async with sess.post(f"{cfg.TONCENTER_URL}/sendBoc", json={"boc": boc},
                                     headers=_headers()) as r:
                    js = await r.json()
                    status = r.status
            except Exception as e:
                raise FragmentUncertain(f"sendBoc: нет ответа ({e!r}), транзакция могла уйти")
            if not js.get("ok"):
                if status in (400, 422):                # явный отказ ноды
                    raise FragmentError(f"toncenter отклонил транзакцию: {js}")
                raise FragmentUncertain(f"sendBoc: неясный ответ {js}")

            # ── ждём, пока seqno вырастет (транзакция принята сетью) ──
            deadline = time.time() + 90
            while time.time() < deadline:
                await asyncio.sleep(4)
                try:
                    info2 = await _get_info(sess, w.friendly)
                    if int(info2.get("seqno") or 0) > seqno:
                        return boc
                except Exception:
                    pass
            raise FragmentUncertain("seqno не вырос за 90 секунд — проверьте кошелёк вручную")


async def send_ton(address: str, amount_ton: float) -> str:
    """Простой перевод TON с горячего кошелька бота (без комментария). Ошибки — как в send_messages:
    FragmentError = точно НЕ ушло (деньги клиенту вернуть можно), FragmentUncertain = могло уйти."""
    FragmentError, _ = _errors()
    nano = int(round(float(amount_ton) * 1e9))
    if nano <= 0:
        raise FragmentError("Нулевая сумма перевода")
    return await send_messages([{"address": address, "amount": nano}])
