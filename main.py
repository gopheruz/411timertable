import os
import logging
import sqlite3
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))  # Admin's Telegram user ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Database setup
conn = sqlite3.connect('schedule.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS schedule (
    day TEXT,
    para INTEGER,
    subject TEXT,
    teacher TEXT,
    room TEXT,
    start_time TEXT,
    end_time TEXT,
    PRIMARY KEY (day, para)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS cancellations (
    day TEXT,
    para INTEGER,
    status TEXT DEFAULT 'cancelled',
    rescheduled_time TEXT,
    rescheduled_room TEXT,
    rescheduled_day TEXT,
    FOREIGN KEY (day, para) REFERENCES schedule (day, para)
)
''')

# Fixed times for paras
PARA_TIMES = {
    1: (time(14, 20), time(15, 40)),
    2: (time(15, 50), time(17, 10)),
    3: (time(17, 20), time(18, 40)),
}

# Days mapping
DAYS = {
    'Dushanba': 0,
    'Seshanba': 1,
    'Chorshanba': 2,
    'Payshanba': 3,
    'Juma': 4,
}

# Insert schedule if not exists
schedule_data = [
    ('Dushanba', 1, "O’zbekistonning eng yangi tarixi", "Sayfuddinova Shahnoza", "238", "14:20", "15:40"),
    ('Dushanba', 2, "Professional Practice in the Digital Economy", "Abdullayev A'zamjon", "325", "15:50", "17:10"),
    ('Dushanba', 3, None, None, None, None, None),
    ('Seshanba', 1, None, None, None, None, None),
    ('Seshanba', 2, "English L4", "Sobirov Nosirjon", "317", "15:50", "17:10"),
    ('Seshanba', 3, None, None, None, None, None),
    ('Chorshanba', 1, "Database design and development", "Uzoqov Lochinbek", "326", "14:20", "15:40"),
    ('Chorshanba', 2, "Programming practice", "Abdumajidov Doston", "318", "15:50", "17:10"),
    ('Chorshanba', 3, "Programming lecture", "Abdumajidov Doston", "234", "17:20", "18:40"),
    ('Payshanba', 1, "Database design and development", "Uzoqov Lochinbek", "319", "14:20", "15:40"),
    ('Payshanba', 2, "Programming practice", "Abdumajidov Doston", "319", "15:50", "17:10"),
    ('Payshanba', 3, "Programming practice", "Abdumajidov Doston", "318", "17:20", "18:40"),
    ('Juma', 1, "Big data and visualisation", "Behzod Qurbonov", "320", "14:20", "15:40"),
    ('Juma', 2, "Database design and development", "Uzoqov Lochibek", "320", "15:50", "17:10"),
    ('Juma', 3, "O’zbekistonning eng yangi tarixi", "Sayfiddinova Shahnoza", "234", "17:20", "18:40"),
]

for data in schedule_data:
    if data[2]:
        cursor.execute('''
        INSERT OR IGNORE INTO schedule (day, para, subject, teacher, room, start_time, end_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', data)
conn.commit()

# Helper functions
def get_schedule(day: str, para: Optional[int] = None) -> List[Dict]:
    if para:
        cursor.execute('SELECT * FROM schedule WHERE day = ? AND para = ?', (day, para))
    else:
        cursor.execute('SELECT * FROM schedule WHERE day = ?', (day,))
    rows = cursor.fetchall()
    schedule = []
    for row in rows:
        if row[2]:
            cancel = cursor.execute('SELECT * FROM cancellations WHERE day = ? AND para = ?', (day, row[1])).fetchone()
            status = '🚫 Bekor qilingan' if cancel and not cancel[3] else '✅ O\'tkaziladi' if cancel else '✅ Normal'
            rescheduled = f"🕒 Yangilangan: {cancel[5]} kuni, {cancel[3]}, 📍 Xona: {cancel[4]}" if cancel and cancel[3] else ""
            schedule.append({
                'para': row[1],
                'subject': row[2],
                'teacher': row[3],
                'room': row[4],
                'start': row[5],
                'end': row[6],
                'status': status,
                'rescheduled': rescheduled
            })
    return schedule

def check_schedule_conflict(new_day: str, new_time: str) -> str:
    try:
        start_time, end_time = new_time.split('-')
        start = datetime.strptime(start_time, '%H:%M').time()
        end = datetime.strptime(end_time, '%H:%M').time()
    except:
        return "❌ Noto'g'ri vaqt formati! (masalan: 14:20-15:40)"
    
    for para, (para_start, para_end) in PARA_TIMES.items():
        if (start <= para_end and end >= para_start):
            sch = get_schedule(new_day, para)
            if sch:
                s = sch[0]
                return f"⚠️ {new_day} kuni {new_time} vaqtida dars bor: {s['subject']} ({s['start']}-{s['end']}). Boshqa vaqt yoki kun tanlang."
    return ""

def get_current_class() -> str:
    now = datetime.now()
    weekday = now.weekday()
    if weekday > 4:
        return "📅 Bugun dars yo'q (dam olish kuni)"
    day_name = list(DAYS.keys())[weekday]
    current_time = now.time()
    
    for para, (start, end) in PARA_TIMES.items():
        if start <= current_time <= end:
            sch = get_schedule(day_name, para)
            if sch:
                s = sch[0]
                if 'Bekor' in s['status']:
                    return f"🚫 Hozirgi dars bekor qilingan: {s['subject']}. {s['rescheduled']}"
                return f"📚 Hozirgi dars: {s['subject']}\n👨‍🏫 Ustoz: {s['teacher']}\n📍 Xona: {s['room']}\n🕒 Vaqt: {s['start']}-{s['end']}"
    return "⏳ Hozir dars yo'q"

def get_next_class() -> str:
    now = datetime.now()
    weekday = now.weekday()
    if weekday > 4:
        return "📅 Keyingi dars Dushanba kuni"
    
    day_name = list(DAYS.keys())[weekday]
    current_time = now.time()
    next_para = None
    for para, (start, _) in sorted(PARA_TIMES.items()):
        if current_time < start:
            next_para = para
            break
    
    if next_para:
        sch = get_schedule(day_name, next_para)
        if sch:
            s = sch[0]
            status = f"\n{s['status']} {s['rescheduled']}" if 'Normal' not in s['status'] else ""
            return f"⏭ Eng yaqin dars: {s['subject']}\n👨‍🏫 Ustoz: {s['teacher']}\n📍 Xona: {s['room']}\n🕒 Vaqt: {s['start']}-{s['end']}{status}"
    
    next_day = (now + timedelta(days=1)).weekday()
    now_plus = now + timedelta(days=1)
    while next_day > 4:
        next_day = (now_plus + timedelta(days=1)).weekday()
        now_plus += timedelta(days=1)
    next_day_name = list(DAYS.keys())[next_day]
    sch = get_schedule(next_day_name)
    if sch:
        first = sch[0]
        status = f"\n{first['status']} {first['rescheduled']}" if 'Normal' not in first['status'] else ""
        return f"⏭ Eng yaqin dars ({next_day_name}): {first['subject']}\n👨‍🏫 Ustoz: {first['teacher']}\n📍 Xona: {first['room']}\n🕒 Vaqt: {first['start']}-{first['end']}{status}"
    return "🔍 Keyingi dars topilmadi"

def get_weekly_schedule() -> str:
    text = "📅 Haftalik dars jadvali:\n\n"
    for day in DAYS:
        text += f"📆 {day}:\n"
        sch = get_schedule(day)
        if not sch:
            text += "🚫 Dars yo'q\n"
        for s in sch:
            status = f"\n{s['status']} {s['rescheduled']}" if 'Normal' not in s['status'] else ""
            text += f"{s['para']}-para:{s['subject']}\n👨‍🏫 Ustoz: {s['teacher']}\n📍 Xona: {s['room']}\n🕒 Vaqt: {s['start']}-{s['end']}{status}\n"
        text += "\n\n"
    return text

def get_day_schedule(day: str) -> str:
    if day not in DAYS:
        return "❌ Noto'g'ri kun kiritildi!"
    sch = get_schedule(day)
    text = f"📆 {day} darslari:\n\n"
    if not sch:
        return f"📅 {day} kuni dars yo'q"
    for s in sch:
        status = f"\n{s['status']} {s['rescheduled']}" if 'Normal' not in s['status'] else ""
        text += f"{s['para']}-para:{s['subject']}\n👨‍🏫 Ustoz: {s['teacher']}\n📍 Xona: {s['room']}\n🕒 Vaqt: {s['start']}-{s['end']}{status}\n"
    return text

# FSM for admin actions
class CancelClass(StatesGroup):
    day = State()
    para = State()

class RescheduleClass(StatesGroup):
    day = State()
    para = State()
    new_day = State()
    new_time = State()
    new_room = State()

# User commands
@dp.message(Command('start'))
async def start(message: Message):
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📚 Hozirgi dars"),]
        [KeyboardButton(text="📅 Haftalik jadval")],
        [KeyboardButton(text="📆 Dushanba"), KeyboardButton(text="📆 Seshanba")],
        [KeyboardButton(text="📆 Chorshanba"), KeyboardButton(text="📆 Payshanba")],
        [KeyboardButton(text="📆 Juma")]
    ], resize_keyboard=True)
    await message.answer("Salom! 🎉 Dars jadvali botiga xush kelibsiz!", reply_markup=keyboard)

@dp.message(lambda message: message.text in ["📚 Hozirgi dars", "⏭ Eng yaqin dars", "📅 Haftalik jadval"] or message.text.startswith("📆 "))
async def handle_text(message: Message):
    text = message.text
    if text == "📚 Hozirgi dars":
        await message.answer(get_current_class())
    elif text == "⏭ Eng yaqin dars":
        await message.answer(get_next_class())
    elif text == "📅 Haftalik jadval":
        await message.answer(get_weekly_schedule())
    elif text.startswith("📆 "):
        day = text[2:]  # Remove emoji and space
        await message.answer(get_day_schedule(day))

# Admin commands
@dp.message(Command('cancel'))
async def start_cancel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=day) for day in DAYS]
    ], resize_keyboard=True)
    await message.answer("Qaysi kun darsini bekor qilmoqchisiz? 📅", reply_markup=keyboard)
    await state.set_state(CancelClass.day)

@dp.message(CancelClass.day)
async def select_cancel_day(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    day = message.text
    if day not in DAYS:
        await message.answer("❌ Noto'g'ri kun! Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(day=day)
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"{para}-para") for para in [1,2,3]]
    ], resize_keyboard=True)
    await message.answer(f"{day} uchun qaysi para? ⏰", reply_markup=keyboard)
    await state.set_state(CancelClass.para)

@dp.message(CancelClass.para)
async def do_cancel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    para_text = message.text
    if not para_text.endswith("-para"):
        await message.answer("❌ Noto'g'ri para! Iltimos, ro'yxatdan tanlang.")
        return
    para = int(para_text[0])
    data = await state.get_data()
    day = data['day']
    cursor.execute('INSERT OR REPLACE INTO cancellations (day, para, status) VALUES (?, ?, ?)', (day, para, 'cancelled'))
    conn.commit()
    await message.answer(f"🚫 {day} {para}-para darsi bekor qilindi.")
    logging.info(f"Cancelled: {day} {para}")
    await state.clear()

@dp.message(Command('reschedule'))
async def start_reschedule(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    cancelled = cursor.execute('SELECT day, para FROM cancellations WHERE rescheduled_time IS NULL').fetchall()
    if not cancelled:
        await message.answer("🚫 Bekor qilingan darslar yo'q.")
        return
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"{day} {para}-para") for day, para in cancelled]
    ], resize_keyboard=True)
    await message.answer("Qaysi bekor darsni qayta rejalashtirmoqchisiz? 📅", reply_markup=keyboard)
    await state.set_state(RescheduleClass.day)

@dp.message(RescheduleClass.day)
async def select_res_day_para(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text
    try:
        day, para_text = text.rsplit(' ', 1)
        para = int(para_text.split('-')[0])
        if day not in DAYS:
            raise ValueError
    except:
        await message.answer("❌ Noto'g'ri tanlov! Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(day=day, para=para)
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=day) for day in DAYS]
    ], resize_keyboard=True)
    await message.answer("Qaysi kunga rejalashtirmoqchisiz? 📅", reply_markup=keyboard)
    await state.set_state(RescheduleClass.new_day)

@dp.message(RescheduleClass.new_day)
async def select_new_day(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_day = message.text
    if new_day not in DAYS:
        await message.answer("❌ Noto'g'ri kun! Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(new_day=new_day)
    await message.answer("Yangi vaqtni kiriting (masalan: 14:20-15:40) 🕒")
    await state.set_state(RescheduleClass.new_time)

@dp.message(RescheduleClass.new_time)
async def set_new_time(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_time = message.text
    data = await state.get_data()
    new_day = data['new_day']
    conflict = check_schedule_conflict(new_day, new_time)
    if conflict:
        await message.answer(conflict)
        return
    await state.update_data(new_time=new_time)
    await message.answer("Yangi xonani kiriting (masalan: 238) 📍")
    await state.set_state(RescheduleClass.new_room)

@dp.message(RescheduleClass.new_room)
async def set_new_room(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_room = message.text
    data = await state.get_data()
    day = data['day']
    para = data['para']
    new_day = data['new_day']
    new_time = data['new_time']
    cursor.execute('UPDATE cancellations SET rescheduled_time = ?, rescheduled_room = ?, rescheduled_day = ? WHERE day = ? AND para = ?', 
                   (new_time, new_room, new_day, day, para))
    conn.commit()
    await message.answer(f"✅ {day} {para}-para darsi yangi vaqtga o'tkazildi: {new_day}, {new_time}, Xona: {new_room}")
    logging.info(f"Rescheduled: {day} {para} to {new_day} {new_time} {new_room}")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())