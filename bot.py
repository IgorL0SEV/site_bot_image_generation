import os
import datetime
from dotenv import load_dotenv

from openai import OpenAI

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile

from logo_generator import generate_logo

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

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот с искусственным интеллектом.\n"
        "Напиши что-нибудь, чтобы поговорить со мной, или используй команду /image для генерации картинки."
    )

@dp.message(Command("help"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот с искусственным интеллектом.\n"
        "Напиши что-нибудь, чтобы поговорить со мной, или используй команду /image для генерации картинки."
    )

@dp.message(Command("image"))
async def image_command(message: types.Message, state: FSMContext):
    await message.answer("Отправь мне описание картинки (промпт):")
    await state.set_state(ImageStates.waiting_for_prompt)

@dp.message(ImageStates.waiting_for_prompt)
async def handle_image_prompt(message: types.Message, state: FSMContext):
    prompt = message.text
    await message.answer("⏳ Генерирую изображение...")
    try:
        image_data = generate_logo(prompt)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"image_{timestamp}.jpeg"
        with open(filename, "wb") as file:
            file.write(image_data)
        photo = FSInputFile(filename)
        await message.answer_photo(
            photo,
            caption=f"Вот твоя картинка по запросу:\n<code>{prompt}</code>",
            parse_mode=ParseMode.HTML
        )
        os.remove(filename)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

@dp.message()
async def chat_handler(message: types.Message):
    text = message.text.lower()
    # Если пользователь спрашивает про дату/время
    if any(word in text for word in ["время", "дата", "число", "какой сегодня день", "какое сейчас время"]):
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        await message.answer(f"Сегодня {now}")
        return

    # В остальных случаях — ответ через GPT
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": message.text}],
            max_tokens=400
        )
        answer = response.choices[0].message.content
        await message.answer(answer)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка OpenAI: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))

