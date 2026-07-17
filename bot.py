"""
DonatBazar Telegram bot — o'yin donatlari (Mobile Legends, PUBG, Free Fire)
============================================================================

O'RNATISH:
    pip install -r requirements.txt

ISHGA TUSHIRISH:
    1. config.py faylida BOT_TOKEN va ADMIN_ID ni to'ldiring
    2. python bot.py

ESLATMA (to'lov haqida):
    Bu fayl buyurtma qabul qilish oqimini (mahsulot tanlash -> ID kiritish ->
    to'lov usuli -> admin'ga xabar) to'liq ishlaydigan holda beradi.

    Ammo REAL pul o'tkazish (Click/Payme) uchun sizga alohida BACKEND SERVER
    kerak bo'ladi — chunki Click/Payme har doim o'z serveringizga "to'lov
    haqiqatan bo'ldi" degan webhook (POST so'rov) yuboradi va SHUNDAN KEYIN
    olmos berish kerak. Buni faqat botning o'zida (webhook'siz) xavfsiz
    qilib bo'lmaydi — aks holda birov to'lov qilmay ham "to'ladim" deb
    yozib, olmos olib ketishi mumkin.

    Shu sabab bu versiyada to'lov qismi ikki bosqichli:
      1) Bot foydalanuvchiga Click/Payme'ning rasmiy to'lov havolasini beradi
      2) Admin (siz) Click/Payme ilovangizda pul tushganini ko'rgach,
         botda /confirm <order_id> buyrug'i bilan buyurtmani tasdiqlaysiz,
         shundan keyingina bot mijozga "olmos yuborildi" deb yozadi.

    Agar to'liq avtomatlashtirmoqchi bo'lsangiz (webhook orqali), menga
    ayting — Flask/FastAPI backend qismini alohida yozib beraman, u esa
    Click/Payme merchant kalitlaringizni talab qiladi.
"""

import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)

import config_env as config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

# ============================================================
# MAHSULOTLAR VA NARXLAR — o'zingizning ta'minot narxingizga
# qarab shu yerni tahrirlang
# ============================================================
GAMES = {
    "mlbb": {
        "title": "Mobile Legends: Bang Bang",
        "packages": [
            ("50 olmos", 9000),
            ("100 olmos", 17500),
            ("250 olmos", 42000),
            ("500 olmos", 82000),
            ("1000 olmos", 160000),
            ("Haftalik pass", 45000),
        ],
    },
    "pubg": {
        "title": "PUBG Mobile",
        "packages": [
            ("60 UC", 12000),
            ("325 UC", 58000),
            ("660 UC", 110000),
        ],
    },
    "ff": {
        "title": "Free Fire",
        "packages": [
            ("100 olmos", 15000),
            ("310 olmos", 42000),
            ("520 olmos", 68000),
        ],
    },
}

# Xotirada saqlanadigan buyurtmalar (real loyihada bazaga -> SQLite/Postgres)
ORDERS: dict[str, dict] = {}


class OrderFlow(StatesGroup):
    choosing_game = State()
    choosing_package = State()
    entering_player_id = State()
    entering_server_id = State()
    choosing_payment = State()
    waiting_payment_confirmation = State()


def games_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=g["title"], callback_data=f"game:{key}")]
        for key, g in GAMES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def packages_keyboard(game_key: str) -> InlineKeyboardMarkup:
    rows = []
    for i, (label, price) in enumerate(GAMES[game_key]["packages"]):
        rows.append([InlineKeyboardButton(
            text=f"{label} — {price:,} so'm".replace(",", " "),
            callback_data=f"pkg:{game_key}:{i}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:games")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Click orqali to'lash", callback_data="pay:click")],
        [InlineKeyboardButton(text="💳 Payme orqali to'lash", callback_data="pay:payme")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>GETOO SHOP</b>ga xush kelibsiz!\n\n"
        "Bu yerda Mobile Legends, PUBG Mobile va Free Fire uchun "
        "olmos/UC arzon narxda sotib olishingiz mumkin.\n\n"
        "O'yiningizni tanlang:",
        reply_markup=games_keyboard(),
    )
    await state.set_state(OrderFlow.choosing_game)


@router.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery, state: FSMContext):
    game_key = callback.data.split(":")[1]
    await state.update_data(game=game_key)
    await callback.message.edit_text(
        f"<b>{GAMES[game_key]['title']}</b>\n\nPaket tanlang:",
        reply_markup=packages_keyboard(game_key),
    )
    await state.set_state(OrderFlow.choosing_package)
    await callback.answer()


@router.callback_query(F.data == "back:games")
async def back_to_games(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("O'yiningizni tanlang:", reply_markup=games_keyboard())
    await state.set_state(OrderFlow.choosing_game)
    await callback.answer()


@router.callback_query(F.data.startswith("pkg:"))
async def choose_package(callback: CallbackQuery, state: FSMContext):
    _, game_key, idx = callback.data.split(":")
    label, price = GAMES[game_key]["packages"][int(idx)]
    await state.update_data(package_label=label, price=price)
    await callback.message.edit_text(
        f"Tanlandi: <b>{label}</b> — {price:,} so'm\n\n"
        "Endi o'yin ichidagi <b>Player ID</b> raqamingizni yuboring:".replace(",", " ")
    )
    await state.set_state(OrderFlow.entering_player_id)
    await callback.answer()


@router.message(OrderFlow.entering_player_id)
async def enter_player_id(message: Message, state: FSMContext):
    data = await state.get_data()
    if data["game"] == "mlbb":
        await state.update_data(player_id=message.text.strip())
        await message.answer("Endi <b>Server ID</b> (Zone) raqamini yuboring:")
        await state.set_state(OrderFlow.entering_server_id)
    else:
        await state.update_data(player_id=message.text.strip(), server_id="-")
        await message.answer(
            "To'lov usulini tanlang:",
            reply_markup=payment_keyboard(),
        )
        await state.set_state(OrderFlow.choosing_payment)


@router.message(OrderFlow.entering_server_id)
async def enter_server_id(message: Message, state: FSMContext):
    await state.update_data(server_id=message.text.strip())
    await message.answer(
        "To'lov usulini tanlang:",
        reply_markup=payment_keyboard(),
    )
    await state.set_state(OrderFlow.choosing_payment)


@router.callback_query(F.data.startswith("pay:"))
async def choose_payment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    method = callback.data.split(":")[1]
    data = await state.get_data()

    order_id = f"ORD{int(datetime.now().timestamp())}"
    ORDERS[order_id] = {
        "user_id": callback.from_user.id,
        "username": callback.from_user.username,
        "game": data["game"],
        "package": data["package_label"],
        "price": data["price"],
        "player_id": data["player_id"],
        "server_id": data.get("server_id", "-"),
        "method": method,
        "status": "kutilmoqda",
        "created_at": datetime.now().isoformat(),
    }

    # Haqiqiy loyihada bu yerda Click/Payme'ning rasmiy to'lov havolasi
    # generatsiya qilinadi (merchant_id, amount, order_id parametrlari bilan).
    pay_link = (
        config.CLICK_PAY_LINK_TEMPLATE.format(order_id=order_id, amount=data["price"])
        if method == "click"
        else config.PAYME_PAY_LINK_TEMPLATE.format(order_id=order_id, amount=data["price"])
    )

    await callback.message.edit_text(
        f"🧾 <b>Buyurtma:</b> {order_id}\n"
        f"🎮 {GAMES[data['game']]['title']}\n"
        f"💎 {data['package_label']}\n"
        f"🆔 {data['player_id']} / {data.get('server_id', '-')}\n"
        f"💰 {data['price']:,} so'm\n\n".replace(",", " ") +
        f"To'lash uchun havola:\n{pay_link}\n\n"
        "To'lovni amalga oshirgach, buyurtmangiz admin tomonidan tekshirilib, "
        "olmoslar hisobingizga tushiriladi. Bu odatda 5–15 daqiqa vaqt oladi."
    )

    await bot.send_message(
        config.ADMIN_ID,
        f"🆕 Yangi buyurtma: <b>{order_id}</b>\n"
        f"👤 @{callback.from_user.username or callback.from_user.id}\n"
        f"🎮 {GAMES[data['game']]['title']} — {data['package_label']}\n"
        f"🆔 {data['player_id']} / {data.get('server_id', '-')}\n"
        f"💰 {data['price']:,} so'm | {method.upper()}\n\n".replace(",", " ") +
        f"To'lov tushganini tasdiqlash uchun: /confirm {order_id}",
    )

    await state.clear()
    await callback.answer()


@router.message(Command("confirm"))
async def confirm_order(message: Message, bot: Bot):
    """Faqat admin ishlatadi: /confirm ORD1234567890"""
    if message.from_user.id != config.ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Foydalanish: /confirm ORD1234567890")
        return
    order_id = parts[1]
    order = ORDERS.get(order_id)
    if not order:
        await message.answer("Bunday buyurtma topilmadi.")
        return
    order["status"] = "bajarildi"
    await bot.send_message(
        order["user_id"],
        f"✅ Buyurtmangiz <b>{order_id}</b> tasdiqlandi!\n"
        f"{order['package']} hisobingizga yuborildi. Xaridingiz uchun rahmat!",
    )
    await message.answer(f"{order_id} tasdiqlandi va mijozga xabar yuborildi.")


@router.message(Command("myorders"))
async def my_orders(message: Message):
    user_orders = [o for o in ORDERS.values() if o["user_id"] == message.from_user.id]
    if not user_orders:
        await message.answer("Sizda buyurtmalar yo'q.")
        return
    text = "\n\n".join(
        f"🎮 {GAMES[o['game']]['title']} — {o['package']}\n"
        f"Holat: {o['status']}"
        for o in user_orders
    )
    await message.answer(text)


async def main():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
