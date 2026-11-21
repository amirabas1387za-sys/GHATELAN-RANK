import os
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from db import init_db, add_player, find_players, list_players, add_score, weekly_board, all_time_board, player_history, get_player, get_week_key, get_decks

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
BOT_TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tehran"))
DECKS = [x.strip() for x in os.getenv("DECKS", "دک ۱,دک ۲,دک ۳,دک ۴").split(",") if x.strip()]

if not TOKEN:
    raise RuntimeError("BOT_TOKEN تنظیم نشده است. آن را در Environment هاست وارد کنید.")

class AddPlayer(StatesGroup):
    name = State()
    username = State()

class ScoreFlow(StatesGroup):
    deck = State()
    player = State()
    points = State()
    confirm = State()

class SearchFlow(StatesGroup):
    query = State()

def menu(is_admin=False):
    rows = [
        [KeyboardButton(text="🏆 جدول هفتگی"), KeyboardButton(text="🥇 سه نفر برتر")],
        [KeyboardButton(text="👤 پروفایل بازیکن"), KeyboardButton(text="📚 سوابق بازیکن")],
        [KeyboardButton(text="📊 جدول کل"), KeyboardButton(text="ℹ️ راهنما")],
    ]
    if is_admin:
        rows += [[KeyboardButton(text="➕ افزودن بازیکن"), KeyboardButton(text="✍️ ثبت امتیاز")],
                 [KeyboardButton(text="📋 فهرست بازیکنان"), KeyboardButton(text="🗂 دک‌ها")]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def week_label():
    return get_week_key(datetime.now(BOT_TZ))

async def send_board(message, rows, title):
    if not rows:
        await message.answer(f"{title}\n\nهنوز امتیازی ثبت نشده است.", reply_markup=menu(is_admin(message.from_user.id)))
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [title, ""]
    for i, row in enumerate(rows, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {row['name']}  —  {row['points']} امتیاز  ({row['games']} بازی)")
    await message.answer("\n".join(lines), reply_markup=menu(is_admin(message.from_user.id)))

async def main():
    await init_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(m: Message, state: FSMContext):
        await state.clear()
        await m.answer(
            "🏆 <b>GHATELAN RANK | خانواده قاتلان</b>\n\n"
            "به بات تلگرامی خانواده قاتلان خوش آمدید.\n"
            "امتیازهای تمام بازی‌های ثبت‌شده در جدول هفتگی جمع می‌شوند. هیچ محدودیتی برای تعداد ران روزانه یا هفتگی وجود ندارد.\n"
            "در پایان هر هفته رقابت تازه آغاز می‌شود و سوابق هفته‌های گذشته محفوظ می‌ماند.",
            reply_markup=menu(is_admin(m.from_user.id))
        )

    @dp.message(Command("help"))
    @dp.message(F.text == "ℹ️ راهنما")
    async def help_cmd(m: Message):
        await m.answer("راهنما:\n• جدول هفتگی: رتبه‌بندی هفته جاری\n• جدول کل: مجموع امتیازات ثبت‌شده\n• پروفایل و سوابق: جست‌وجوی بازیکن\n\nثبت امتیاز و افزودن بازیکن فقط برای مدیران فعال است.")

    @dp.message(F.text == "🏆 جدول هفتگی")
    @dp.message(Command("leaderboard"))
    async def weekly(m: Message):
        await send_board(m, await weekly_board(week_label()), "🏆 جدول هفتگی")

    @dp.message(F.text == "🥇 سه نفر برتر")
    @dp.message(Command("top"))
    async def top(m: Message):
        await send_board(m, (await weekly_board(week_label()))[:3], "🥇 سه نفر برتر هفته")

    @dp.message(F.text == "📊 جدول کل")
    async def total(m: Message):
        await send_board(m, await all_time_board(), "📊 جدول کل")

    @dp.message(F.text == "➕ افزودن بازیکن")
    async def add_start(m: Message, state: FSMContext):
        if not is_admin(m.from_user.id):
            return await m.answer("⛔ این بخش مخصوص مدیران است.")
        await state.set_state(AddPlayer.name)
        await m.answer("نام و نام خانوادگی بازیکن را بفرست:")

    @dp.message(AddPlayer.name)
    async def add_name(m: Message, state: FSMContext):
        await state.update_data(name=m.text.strip())
        await state.set_state(AddPlayer.username)
        await m.answer("حالا نام کاربری تلگرام را بفرست (با @ یا بدون @). اگر ندارد، فقط بنویس: ندارد")

    @dp.message(AddPlayer.username)
    async def add_username(m: Message, state: FSMContext):
        data = await state.get_data()
        username = m.text.strip().lstrip("@")
        if username == "ندارد":
            username = ""
        player_id = await add_player(data["name"], username)
        await state.clear()
        await m.answer(f"✅ بازیکن ثبت شد.\nشناسه اختصاصی: <code>{player_id}</code>", reply_markup=menu(True))

    @dp.message(F.text == "✍️ ثبت امتیاز")
    async def score_start(m: Message, state: FSMContext):
        if not is_admin(m.from_user.id):
            return await m.answer("⛔ این بخش مخصوص مدیران است.")
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=d)] for d in DECKS] + [[KeyboardButton(text="لغو")]], resize_keyboard=True)
        await state.set_state(ScoreFlow.deck)
        await m.answer("دک بازی را انتخاب کن:", reply_markup=kb)

    @dp.message(ScoreFlow.deck)
    async def score_deck(m: Message, state: FSMContext):
        if m.text == "لغو":
            await state.clear()
            return await m.answer("لغو شد.", reply_markup=menu(True))
        if m.text not in DECKS:
            return await m.answer("لطفاً یکی از دک‌های فهرست را انتخاب کن.")
        await state.update_data(deck=m.text)
        await state.set_state(ScoreFlow.player)
        players = await list_players()
        if not players:
            await state.clear()
            return await m.answer("هنوز بازیکنی ثبت نشده. ابتدا بازیکن اضافه کن.", reply_markup=menu(True))
        lines = ["بازیکن را با شناسه یا نام انتخاب کن:", ""]
        lines += [f"{p['player_id']} — {p['name']}" for p in players[:80]]
        await m.answer("\n".join(lines))

    @dp.message(ScoreFlow.player)
    async def score_player(m: Message, state: FSMContext):
        matches = await find_players(m.text.strip())
        if len(matches) != 1:
            return await m.answer("بازیکن دقیق پیدا نشد یا چند نتیجه وجود دارد. شناسه اختصاصی مثل KR-000001 را بفرست.")
        p = matches[0]
        await state.update_data(player_id=p["player_id"], player_name=p["name"])
        await state.set_state(ScoreFlow.points)
        await m.answer(f"بازیکن: <b>{p['name']}</b>\nامتیاز عددی را وارد کن:")

    @dp.message(ScoreFlow.points)
    async def score_points(m: Message, state: FSMContext):
        try:
            points = int(m.text.strip())
            if points < 0 or points > 100000:
                raise ValueError()
        except Exception:
            return await m.answer("فقط عدد صحیح بین صفر تا ۱۰۰۰۰۰ وارد کن.")
        await state.update_data(points=points)
        d = await state.get_data()
        await state.set_state(ScoreFlow.confirm)
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ تأیید ثبت"), KeyboardButton(text="❌ لغو")]], resize_keyboard=True)
        await m.answer(f"لطفاً اطلاعات را بررسی کن:\n\nدک: {d['deck']}\nبازیکن: {d['player_name']}\nامتیاز: {points}\n\nثبت شود؟", reply_markup=kb)

    @dp.message(ScoreFlow.confirm)
    async def score_confirm(m: Message, state: FSMContext):
        if m.text == "❌ لغو":
            await state.clear()
            return await m.answer("ثبت لغو شد.", reply_markup=menu(True))
        if m.text != "✅ تأیید ثبت":
            return await m.answer("برای ادامه «تأیید ثبت» یا «لغو» را انتخاب کن.")
        d = await state.get_data()
        await add_score(d["player_id"], d["deck"], d["points"], m.from_user.id, week_label())
        await state.clear()
        await m.answer("✅ امتیاز با موفقیت ثبت شد و در جدول هفتگی محاسبه می‌شود.", reply_markup=menu(True))

    @dp.message(F.text == "📋 فهرست بازیکنان")
    async def players_list(m: Message):
        if not is_admin(m.from_user.id):
            return await m.answer("⛔ این بخش مخصوص مدیران است.")
        players = await list_players()
        await m.answer("👥 فهرست بازیکنان\n\n" + ("\n".join(f"{p['player_id']} — {p['name']}" for p in players[:100]) if players else "فهرست خالی است."))

    @dp.message(F.text == "🗂 دک‌ها")
    async def decks(m: Message):
        await m.answer("🎮 دک‌های فعال:\n" + "\n".join(f"• {d}" for d in DECKS))

    @dp.message(F.text.in_({"👤 پروفایل بازیکن", "📚 سوابق بازیکن"}))
    async def search_start(m: Message, state: FSMContext):
        await state.update_data(mode="profile" if m.text.startswith("👤") else "history")
        await state.set_state(SearchFlow.query)
        await m.answer("نام بازیکن یا شناسه اختصاصی او را بفرست:")

    @dp.message(SearchFlow.query)
    async def search_result(m: Message, state: FSMContext):
        data = await state.get_data()
        matches = await find_players(m.text.strip())
        await state.clear()
        if len(matches) != 1:
            return await m.answer("بازیکن پیدا نشد یا چند نتیجه وجود دارد. با شناسه اختصاصی جست‌وجو کن.", reply_markup=menu(is_admin(m.from_user.id)))
        p = matches[0]
        if data["mode"] == "history":
            rows = await player_history(p["player_id"])
            body = "\n".join(f"• {r['created_at']} | {r['deck']} | {r['points']} امتیاز" for r in rows) or "هنوز سابقه‌ای ندارد."
            await m.answer(f"📚 سوابق {p['name']}\n\n{body}", reply_markup=menu(is_admin(m.from_user.id)))
        else:
            rows = await player_history(p["player_id"])
            total_points = sum(r["points"] for r in rows)
            await m.answer(f"👤 <b>{p['name']}</b>\nشناسه: <code>{p['player_id']}</code>\nنام کاربری: @{p['username'] or 'ندارد'}\nمجموع امتیازات ثبت‌شده: {total_points}", reply_markup=menu(is_admin(m.from_user.id)))

    @dp.message()
    async def fallback(m: Message):
        await m.answer("از دکمه‌های منو استفاده کن یا /start را بزن.", reply_markup=menu(is_admin(m.from_user.id)))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
