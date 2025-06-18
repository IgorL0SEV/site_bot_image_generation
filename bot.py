import os
import datetime
import asyncio
import logging
from dotenv import load_dotenv
from openai import OpenAI

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile

from logo_generator import generate_logo

# --- Инициализация логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Загрузка переменных окружения ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
count_image = int(os.getenv("count_image", 5)) # лимит генераций для бот

# --- Проверка обязательных переменных окружения ---
if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Не заданы BOT_TOKEN или OPENAI_API_KEY в .env")

# --- Импортируем Flask-приложение и базу данных ---
from app import app, db
from models import ImageHistory

# --- Настройки ---
results_dir = os.path.join(app.instance_path, "results")
os.makedirs(results_dir, exist_ok=True)

# --- Инициализация клиентов ---
client = OpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- FSM-состояние для ожидания описания логотипа ---
class ImageStates(StatesGroup):
    waiting_for_prompt = State()

# --- Текст помощи по боту ---
HELP_TEXT = (
    "\n💡 Я бот-ассистент! Команды:\n"
    "✨ /start — инструкция по использованию\n"
    "❓ /help — повторяет эту инструкцию\n"
    "🎨 /image — генерация логотипа по описанию\n"
    "🖼️ /history — посмотреть последние 10 логотипов\n"
    "⏳ /limit — узнать, сколько генераций осталось в этом часу\n"
    "❌ /cancel — отмена генерации\n"
    "✅ /status — узнать статус бота\n"
    "✍️ Просто напишите текст — я поддержу разговор или подскажу дату/время!"
)

# --- Обработчики команд ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("👋 Привет! Я 🤖 бот-ассистент по генерации логотипов с помощью Yandex ART и OpenAI!" + HELP_TEXT)

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(HELP_TEXT)

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Генерация отменена.")

@dp.message(Command("status"))
async def status_handler(message: types.Message):
    await message.answer("✅ Бот работает! Если ждёте картинку — обычно это занимает 10–20 секунд.\nЕсли ответа нет дольше 1–2 минут — возможно, сервис недоступен.")

@dp.message(Command("image"))
async def image_command(message: types.Message, state: FSMContext):
    await message.answer("🎨 Пришли описание логотипа (промпт):")
    await state.set_state(ImageStates.waiting_for_prompt)

@dp.message(ImageStates.waiting_for_prompt)
async def handle_image_prompt(message: types.Message, state: FSMContext):
    prompt = message.text
    tg_user_id = message.from_user.id

    # --- Проверка ограничения по количеству генераций ---
    one_hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    with app.app_context():
        count = ImageHistory.query.filter_by(tg_user_id=tg_user_id, source="bot") \
            .filter(ImageHistory.timestamp > one_hour_ago).count()
    if count >= count_image:
        await message.answer(f"🚦 Лимит генераций: не более {count_image} картинок в час. Попробуйте позже!")
        await state.clear()
        return

    await message.answer("⏳ Генерирую изображение...")
    try:
        image_data = generate_logo(prompt)

        now_utc = datetime.datetime.utcnow()
        timestamp = now_utc.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"tg_{tg_user_id}_{timestamp}.jpg"
        filepath = os.path.join(results_dir, filename)
        with open(filepath, "wb") as file:
            file.write(image_data)

        # --- Сохраняем в БД и удаляем старые записи ---
        with app.app_context():
            record = ImageHistory(prompt=prompt, filename=filename, tg_user_id=tg_user_id, source="bot", timestamp=now_utc)
            db.session.add(record)
            db.session.commit()

            all_imgs = ImageHistory.query.filter_by(tg_user_id=tg_user_id, source="bot") \
                .order_by(ImageHistory.timestamp.desc()).all()
            for extra in all_imgs[10:]:
                old_path = os.path.join(results_dir, extra.filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
                db.session.delete(extra)
            db.session.commit()

        await message.answer_photo(FSInputFile(filepath), caption=f"🖼️ Вот твой логотип по запросу:\n<code>{prompt}</code>", parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.exception("Ошибка при генерации изображения")
        if hasattr(e, "response") and getattr(e.response, "status_code", None) == 500:
            await message.answer("❌ Внутренняя ошибка генерации. Попробуйте позже.")
        else:
            await message.answer(f"❌ Ошибка генерации: {e}")

    await state.clear()

@dp.message(Command("history"))
async def history_handler(message: types.Message):
    tg_user_id = message.from_user.id
    with app.app_context():
        images = ImageHistory.query.filter_by(tg_user_id=tg_user_id, source="bot") \
            .order_by(ImageHistory.timestamp.desc()).limit(10).all()
    if not images:
        await message.answer("😕 У вас пока нет сгенерированных логотипов.")
        return

    await message.answer(f"🖼️ История последних {len(images)} логотипов:")
    for item in images:
        photo_path = os.path.join(results_dir, item.filename)
        if os.path.exists(photo_path):
            await message.answer_photo(
                FSInputFile(photo_path),
                caption=f"ID: {item.id} — <code>{item.prompt}</code>",
                parse_mode=ParseMode.HTML
            )

@dp.message(Command("limit"))
async def limit_handler(message: types.Message):
    tg_user_id = message.from_user.id
    one_hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    with app.app_context():
        count = ImageHistory.query.filter_by(tg_user_id=tg_user_id, source="bot") \
            .filter(ImageHistory.timestamp > one_hour_ago).count()
    await message.answer(
        f"⏳ За последний час вы сгенерировали {count}/{count_image} логотипов.\n"
        f"Следующий лимит обнулится через {60 - datetime.datetime.now().minute} минут."
    )

@dp.message()
async def chat_handler(message: types.Message):
    text = message.text.lower()
    if any(word in text for word in ["время", "дата", "число", "час", "какой сегодня день", "какое сейчас время", "который час", "сколько натикало"]):
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        await message.answer(f"📅 Сегодня {now}")
        return

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": message.text}],
            max_tokens=400
        )
        answer = response.choices[0].message.content
        await message.answer(f"🤖 {answer}")
    except Exception as e:
        logger.exception("Ошибка при запросе к OpenAI")
        await message.answer(f"⚠️ Ошибка OpenAI: {e}")

# --- Точка входа ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
