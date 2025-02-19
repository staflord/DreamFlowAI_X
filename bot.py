import os
import sys
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

logging.basicConfig(level=logging.INFO)

# Подключаемся к БД
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицы, если их нет
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    language TEXT DEFAULT 'ru'
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    complaint_text TEXT
);
""")
conn.commit()

# Настройки
ADMIN_ID = 6111969965  # Укажите свой Telegram ID
TOKEN = "7591135321:AAHZ-wpQ5_MrmRlItWw9Y479ALHvNZLhSqs"

# Создаем бота и диспетчер
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния
class ComplaintState(StatesGroup):
    waiting_for_text = State()

# Локализованные тексты
texts = {
    "greeting": {
        "ru": "\U0001F916 Привет! Я DreamFlowAI_X – ваш помощник на базе искусственного интеллекта.\n\n\U0001F30D Выберите язык, чтобы продолжить:",
        "en": "\U0001F916 Hello! I am DreamFlowAI_X – your AI-based assistant.\n\n\U0001F30D Choose a language to continue:"
    },
    "language_changed": {
        "ru": "✅ Язык изменен на русский! Выберите нужный раздел ⬇️",
        "en": "✅ Language changed to English! Choose the section you need ⬇️"
    },
    "faq": {
        "ru": (
            "📌 *Часто задаваемые вопросы:*\n\n"
            "1️⃣ *Как пользоваться ботом?*\n"
            "— Просто используйте кнопки меню для навигации.\n\n"
            "2️⃣ *Какие функции поддерживает бот?*\n"
            "— Бот может отвечать на вопросы, помогать с задачами и выполнять команды.\n\n"
            "3️⃣ *Как изменить язык бота?*\n"
            "— Нажмите /start и выберите язык.\n\n"
            "4️⃣ *Как связаться с поддержкой?*\n"
            "— Вы можете оставить жалобу или предложение в разделе \"📝 Оставить жалобу/предложение\".\n\n"
            "5️⃣ *Как удалить свою учётную запись?*\n"
            "— Напишите в поддержку, и мы обработаем ваш запрос.\n\n"
            "6️⃣ *Как купить токены?*\n"
            "— Перейдите на сайт DreamFlow AI и выберите удобный способ оплаты.\n\n"
            "7️⃣ *Как проверить баланс токенов?*\n"
            "— Воспользуйтесь командой /balance."
        ),
        "en": (
            "📌 *Frequently Asked Questions:*\n\n"
            "1️⃣ *How to use the bot?*\n"
            "— Just use the menu buttons for navigation.\n\n"
            "2️⃣ *What features does the bot support?*\n"
            "— The bot can answer questions, assist with tasks, and execute commands.\n\n"
            "3️⃣ *How to change the bot language?*\n"
            "— Press /start and select a language.\n\n"
            "4️⃣ *How to contact support?*\n"
            "— You can submit a complaint or suggestion in the \"📝 Submit a Complaint/Suggestion\" section.\n\n"
            "5️⃣ *How to delete my account?*\n"
            "— Contact support, and we will process your request.\n\n"
            "6️⃣ *How to buy tokens?*\n"
            "— Go to the DreamFlow AI website and choose a payment method.\n\n"
            "7️⃣ *How to check my token balance?*\n"
            "— Use the command /balance."
        )
    },
    "complaint_prompt": {
        "ru": "Вы можете оставить свою жалобу или предложение, нажав на кнопку ниже.",
        "en": "You can submit your complaint or suggestion by clicking the button below."
    },
    "complaint_request": {
        "ru": "📝 Пожалуйста, опишите вашу жалобу или предложение:",
        "en": "📝 Please describe your complaint or suggestion:"
    },
    "complaint_saved": {
        "ru": "✅ Ваше сообщение сохранено! Спасибо за обратную связь.",
        "en": "✅ Your message has been saved! Thank you for your feedback."
    },
    "new_complaint": {
        "ru": "📩 Новая жалоба от @{user} (ID: {user_id}):\n{text}",
        "en": "📩 New complaint from @{user} (ID: {user_id}):\n{text}"
    }
}

# Клавиатуры
lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")]],
    resize_keyboard=True
)

keyboards = {
    "ru": ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❓ Часто задаваемые вопросы")],
            [KeyboardButton(text="📝 Оставить жалобу/предложение")]
        ],
        resize_keyboard=True
    ),
    "en": ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❓ Frequently Asked Questions")],
            [KeyboardButton(text="📝 Submit a Complaint/Suggestion")]
        ],
        resize_keyboard=True
    )
}

complaint_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✉ Оставить жалобу/предложение", callback_data="leave_complaint")]
    ]
)

# Функция для получения языка пользователя
def get_user_language(user_id):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    lang = cursor.fetchone()
    return lang[0] if lang else "ru"

# Обработчики
@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name or "NoName"

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                   (user_id, username, first_name))
    conn.commit()

    lang = get_user_language(user_id)  # Получаем язык пользователя из БД
    greeting_text = (
        f"{texts['greeting']['ru']}\n\n"
        f"{texts['greeting']['en']}"
    )

    await message.answer(greeting_text, reply_markup=lang_keyboard)

@dp.message(F.text.in_(["📝 Оставить жалобу/предложение", "📝 Submit a Complaint/Suggestion"]))
async def complaint_menu(message: Message):
    lang = get_user_language(message.from_user.id)
    complaint_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉ Оставить жалобу/предложение" if lang == "ru" else "✉ Submit a Complaint/Suggestion", callback_data="leave_complaint")]
        ]
    )
    await message.answer(texts["complaint_prompt"][lang], reply_markup=complaint_keyboard)

@dp.message(F.text.in_(["🇷🇺 Русский", "🇬🇧 English"]))
async def change_language(message: Message):
    user_id = message.from_user.id
    lang = "ru" if message.text == "🇷🇺 Русский" else "en"
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    await message.answer(texts["language_changed"][lang], reply_markup=keyboards[lang])

@dp.message(F.text.in_(["❓ Часто задаваемые вопросы", "❓ Frequently Asked Questions"]))
async def faq(message: Message):
    lang = get_user_language(message.from_user.id)
    await message.answer(texts["faq"][lang])

@dp.message(F.text.in_(["📝 Оставить жалобу/предложение", "📝 Submit a Complaint/Suggestion"]))
async def complaint_menu(message: Message):
    lang = get_user_language(message.from_user.id)
    await message.answer(texts["complaint_prompt"][lang], reply_markup=complaint_keyboard)

@dp.callback_query(F.data == "leave_complaint")
async def ask_for_complaint(callback: CallbackQuery, state: FSMContext):
    lang = get_user_language(callback.from_user.id)
    await callback.message.answer(texts["complaint_request"][lang])
    await state.set_state(ComplaintState.waiting_for_text)

@dp.message(ComplaintState.waiting_for_text)
async def receive_complaint(message: Message, state: FSMContext):
    user_id = message.from_user.id
    complaint_text = message.text
    lang = get_user_language(user_id)
    cursor.execute("INSERT INTO complaints (user_id, complaint_text) VALUES (?, ?)", (user_id, complaint_text))
    conn.commit()
    await message.answer(texts["complaint_saved"][lang])
    await bot.send_message(ADMIN_ID, texts["new_complaint"][lang].format(user=message.from_user.username, user_id=user_id, text=complaint_text))
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())