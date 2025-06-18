# Yandex ART LOGOgenerator

Генератор логотипов и изображений на базе Yandex ART API с веб-интерфейсом (Flask) и Telegram-ботом.

## 🚀 Возможности

* Генерация изображений по текстовому описанию (prompt) через Yandex ART
* Устойчивость к сбоям API (повторные попытки, polling)
* Telegram-бот с возможностью генерации прямо в чате
* Личный кабинет на сайте с историей генераций (последние 10 логотипов)
* Лимит генераций — не более 7 в час на пользователя
* Авторизация через веб-интерфейс (регистрация, вход)
* API-доступ с авторизацией по API-ключу
* Корректное локальное время (Europe/Minsk) и уникальные ID в истории
* Обработка сигналов Ctrl+C при запуске (graceful shutdown)

## 🛠️ Быстрый старт

### 1. Клонируй репозиторий

```bash
git clone https://github.com/IgorL0SEV/site_bot_image_generation.git
cd site_bot_image_generation
```

### 2. Создай виртуальное окружение и установи зависимости

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux/MacOS
pip install -r requirements.txt
```

### 3. Настрой .env

Создай файл `.env` в корне проекта и заполни:

```dotenv
SECRET_KEY=your_flask_secret_key
CATALOG_ID=your_yandex_catalog_id
OAUTH_TOKEN=your_yandex_oauth_token
MY_API_KEY=your_api_key_for_api_access
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_key
```

### 4. Запусти сайт и бота

#### В отдельных терминалах:

```bash
python app.py        # запуск Flask-сайта
python bot.py        # запуск Telegram-бота
```

#### Или оба вместе:

```bash
python run_all.py
```

## 🌐 Использование

### Сайт

1. Перейди на [http://localhost:5000](http://localhost:5000)
2. Зарегистрируйся и войди
3. Введи промпт → нажми “Сгенерировать”
4. Смотри результат и историю

### Telegram-бот

* Отправь /start или /image
* Следуй инструкциям
* Получай логотипы прямо в чат

## ⚡ API

### POST `/api/generate`

**Заголовок**:

```
X-API-KEY: <your_api_key>
```

**Тело запроса (JSON)**:

```json
{
  "prompt": "логотип компании с синим кругом и буквой A",
  "tg_user_id": 123456789
}
```

**Ответ**:

```json
{
  "status": "ok",
  "filename": "2025-06-18_12-00-00_<uuid>.jpg"
}
```

## 📁 Структура проекта

```
site_bot_image_generation/
├── .venv/                   # Виртуальное окружение Python
├── instance/
│   ├── site.db              # SQLite-база сайта
│   └── results/             # Сгенерированные картинки
├── templates/               # HTML-шаблоны Flask
├── .env                     # Переменные окружения
├── .gitignore               # Исключения Git
├── .iam_token_cache         # Кэш IAM-токена
├── app.py                   # Flask-приложение
├── bot.py                   # Telegram-бот (на aiogram)
├── bot_runner.py            # Перезапуск бота при сбоях
├── run_all.py               # Одновременный запуск сайта и бота
├── logo_generator.py        # Генерация изображений через Yandex API
├── models.py                # SQLAlchemy-модели
├── token_updater.py         # Получение IAM токена
├── bot_errors.log           # Логи Telegram-бота
├── LICENSE                  # Лицензия
└── README.md                # Документация
```

## ⚙️ Оптимизации и улучшения

- Устойчивость к ошибкам Yandex ART API (повторы, ожидание готовности)
- Обработка сигналов остановки сервера (Ctrl+C)
- Расширенные лимиты и параметры через .env
- Улучшен Telegram-бот: FSM, логирование, статус, история


## 💡 TODO / Планы

* Настроить rate-limit API для защиты в production
* Адаптировать интерфейс под мобильные устройства
* Добавить статистику генераций и админ-панель
* Интеграция с другими LLM (fallback на OpenAI)
* Отправка уведомлений о сбоях (например, через Telegram)


<img alt="img_2.png" src="img_2.png" title="Пример бот"/>
<img alt="img.png" src="img.png" title="Пример"/>
