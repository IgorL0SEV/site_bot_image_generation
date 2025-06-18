import os
import datetime
from dotenv import load_dotenv

from app import app, db

from openai import OpenAI

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile

from logo_generator import generate_logo
from models import db, ImageHistory

# --- Загрузка переменных окружения ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Инициализация клиентов ---
client = OpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- FSM для генерации картинки ---
class ImageStates(StatesGroup):
    waiting_for_prompt = State()

HELP_TEXT = (
    "💡 Я бот-ассистент! Команды:\n"
    "✨ /start — инструкция по использованию\n"
    "❓ /help — повторяет эту инструкцию\n"
    "🎨 /image — генерация логотипа по описанию\n"
    "🖼️ /history — посмотреть последние 10 логотипов\n"
    "⏳ /limit — узнать, сколько генераций осталось в этом часу\n"
    "✍️ Просто напишите текст — я поддержу разговор или подскажу дату/время!"
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Привет! Я 🤖 бот-ассистент по генерации логотипов с помощью Yandex ART и OpenAI!\n\n" + HELP_TEXT
    )

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(HELP_TEXT)

@dp.message(Command("image"))
async def image_command(message: types.Message, state: FSMContext):
    await message.answer("🎨 Пришли описание логотипа (промпт):")
    await state.set_state(ImageStates.waiting_for_prompt)

@dp.message(ImageStates.waiting_for_prompt)
async def handle_image_prompt(message: types.Message, state: FSMContext):
    prompt = message.text
    tg_user_id = message.from_user.id

    with app.app_context():
        # --- Лимит: не более 5 генераций в час ---
        one_hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        count = (
            ImageHistory.query
            .filter_by(tg_user_id=tg_user_id, source="bot")
            .filter(ImageHistory.timestamp > one_hour_ago)
            .count()
        )
        if count >= 5:
            await message.answer("🚦 Лимит генераций: не более 5 картинок в час. Попробуйте позже!")
            await state.clear()
            return

    await message.answer("⏳ Генерирую изображение...")
    try:
        image_data = generate_logo(prompt)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"tg_{tg_user_id}_{timestamp}.jpg"
        os.makedirs("results", exist_ok=True)
        filepath = os.path.join("results", filename)
        with open(filepath, "wb") as file:
            file.write(image_data)
        # --- Сохраняем в историю пользователя в БД ---
        with app.app_context():
            record = ImageHistory(
                prompt=prompt,
                filename=filename,
                tg_user_id=tg_user_id,
                source="bot"
            )
            db.session.add(record)
            db.session.commit()
            # --- Храним только 10 последних ---
            all_imgs = (
                ImageHistory.query
                .filter_by(tg_user_id=tg_user_id, source="bot")
                .order_by(ImageHistory.timestamp.desc())
                .all()
            )
            for extra in all_imgs[10:]:
                old_path = os.path.join("results", extra.filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
                db.session.delete(extra)
            db.session.commit()

        photo = FSInputFile(filepath)
        await message.answer_photo(
            photo,
            caption=f"🖼️ Вот твой логотип по запросу:\n<code>{prompt}</code>",
            parse_mode=ParseMode.HTML
        )
        # (Файл НЕ удаляем, теперь он хранится в истории)
    except Exception as e:
        await message.answer(f"❌ Ошибка генерации: {e}")
    await state.clear()

@dp.message(Command("history"))
async def history_handler(message: types.Message):
    tg_user_id = message.from_user.id
    with app.app_context():
        images = (
            ImageHistory.query
            .filter_by(tg_user_id=tg_user_id, source="bot")
            .order_by(ImageHistory.timestamp.desc())
            .limit(10)
            .all()
        )
    if not images:
        await message.answer("😕 У вас пока нет сгенерированных логотипов.")
    else:
        await message.answer(f"🖼️ История последних {len(images)} логотипов:")
        for idx, item in enumerate(images, 1):
            photo_path = os.path.join("results", item.filename)
            if os.path.exists(photo_path):
                photo = FSInputFile(photo_path)
                await message.answer_photo(
                    photo,
                    caption=f"#{idx} — <code>{item.prompt}</code>\nДата: {item.timestamp.strftime('%d.%m.%Y %H:%M')}",
                    parse_mode=ParseMode.HTML
                )

@dp.message(Command("limit"))
async def limit_handler(message: types.Message):
    tg_user_id = message.from_user.id
    with app.app_context():
        one_hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        count = (
            ImageHistory.query
            .filter_by(tg_user_id=tg_user_id, source="bot")
            .filter(ImageHistory.timestamp > one_hour_ago)
            .count()
        )
    await message.answer(
        f"⏳ За последний час вы сгенерировали {count}/5 логотипов.\n"
        f"Следующий лимит обнулится через {60 - datetime.datetime.now().minute} минут."
    )

@dp.message()
async def chat_handler(message: types.Message):
    text = message.text.lower()
    # Если пользователь спрашивает про дату/время
    if any(word in text for word in ["время", "дата", "число", "какой сегодня день", "какое сейчас время"]):
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        await message.answer(f"📅 Сегодня {now}")
        return

    # В остальных случаях — ответ через GPT
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": message.text}],
            max_tokens=400
        )
        answer = response.choices[0].message.content
        await message.answer(f"🤖 {answer}")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка OpenAI: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
