import os
import time
import json
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")
IAM_TOKEN_LIFETIME_SEC = int(os.getenv("IAM_TOKEN_LIFETIME_SEC", 7200))  # 2 часа по умолчанию

CACHE_FILE = ".iam_token_cache"  # Имя файла для хранения токена

if not OAUTH_TOKEN:
    raise Exception("❌ Не найден OAUTH_TOKEN в .env! Проверьте конфигурацию.")

def get_iam_token():
    """
    Получает IAM токен по OAUTH токену, кэширует в файл.
    Возвращает: str — IAM токен
    """
    # 1. Пытаемся взять токен из файла, если не просрочен
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            token = data.get("iam_token")
            ts = data.get("timestamp")
            # Если токен не просрочен — используем его
            if token and ts and time.time() - ts < IAM_TOKEN_LIFETIME_SEC:
                return token
        except Exception:
            pass  # В случае ошибки просто запросим новый токен

    # 2. Запрашиваем новый токен
    url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    resp = requests.post(url, json={"yandexPassportOauthToken": OAUTH_TOKEN})
    if resp.status_code == 200:
        token = resp.json().get("iamToken")
        # Кэшируем
        with open(CACHE_FILE, "w") as f:
            json.dump({"iam_token": token, "timestamp": time.time()}, f)
        return token
    else:
        raise Exception(f"Ошибка получения IAM_TOKEN: {resp.status_code} {resp.text}")

# Если файл запущен напрямую, выводим токен
if __name__ == "__main__":
    print(get_iam_token())

