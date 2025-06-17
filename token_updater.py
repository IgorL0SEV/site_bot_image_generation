import os
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Берём OAUTH_TOKEN из .env
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")

# Проверяем наличие OAUTH_TOKEN — иначе скрипт не сможет получить IAM токен!
if not OAUTH_TOKEN:
    raise Exception("❌ Не найден OAUTH_TOKEN в .env! Проверьте конфигурацию.")

def get_iam_token():
    """
    Получает IAM токен по OAUTH токену для доступа к API Яндекс.Облака.

    Возвращает:
        str: Строка IAM токена для подстановки в API-запросы.
    Вызывает:
        Exception: Если не удалось получить токен (например, неверный OAUTH токен).
    """
    url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    data = {"yandexPassportOauthToken": OAUTH_TOKEN}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        iam_token = response.json().get("iamToken")
        if not iam_token:
            raise Exception("IAM токен не найден в ответе сервера.")
        return iam_token
    else:
        raise Exception(f"Ошибка получения IAM_TOKEN: {response.status_code} {response.text}")

# Тестовый запуск: если этот файл запускается напрямую,
# выведем IAM токен в консоль (для ручной проверки)
if __name__ == "__main__":
    try:
        token = get_iam_token()
        print(f"Ваш IAM_TOKEN:\n{token}")
    except Exception as err:
        print(f"❌ {err}")
