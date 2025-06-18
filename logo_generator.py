import os
import time
import base64
import requests
from dotenv import load_dotenv
from token_updater import get_iam_token

# Загружаем переменные окружения из файла .env (для CATALOG_ID и др.)
load_dotenv()

# Берём CATALOG_ID из .env (это ID каталога Yandex Cloud)
CATALOG_ID = os.getenv("CATALOG_ID")

# Проверка, чтобы избежать неожиданных тихих ошибок — без CATALOG_ID не продолжаем
if not CATALOG_ID:
    raise Exception("❌ Не найден CATALOG_ID в .env! Проверьте конфигурацию.")

def generate_logo(prompt: str) -> bytes:
    """
    Генерирует изображение логотипа через Yandex Cloud API по текстовому описанию.

    Аргументы:
        prompt (str): Описание логотипа, которое будет отправлено в Yandex ART.

    Возвращает:
        bytes: Сгенерированное изображение (готово для сохранения на диск или отправки пользователю).

    Исключения:
        Exception: Если API Яндекса вернул ошибку или нет результата.
    """
    # Получаем IAM-токен. Если просрочен — автоматически обновляется (реализовано в get_iam_token)
    iam_token = get_iam_token()

    # Формируем запрос на генерацию изображения
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json"
    }
    data = {
        "modelUri": f"art://{CATALOG_ID}/yandex-art/latest",  # Используем актуальную модель Yandex ART
        "generationOptions": {
            "seed": str(int(time.time())),                    # "Семя" для уникальности результата (можно убрать для повторяемости)
            "aspectRatio": {"widthRatio": "2", "heightRatio": "1"}  # Соотношение сторон (по ТЗ)
        },
        "messages": [{"weight": "1", "text": prompt}]         # Передаём промпт
    }

    # 1. Запускаем генерацию (POST)
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Ошибка генерации: {response.status_code} {response.text}")

    # 2. Получаем ID задачи (request_id)
    request_id = response.json().get("id")
    if not request_id:
        raise Exception("Yandex Cloud не вернул ID задачи. Ответ: " + response.text)

    # 3. Делаем паузу — ждём, пока картинка сгенерируется
    time.sleep(10)  # Можно уменьшать, если будет достаточно быстро

    # 4. Проверяем статус и результат
    url_check = f"https://llm.api.cloud.yandex.net/operations/{request_id}"
    headers_check = {"Authorization": f"Bearer {iam_token}"}
    response_check = requests.get(url_check, headers=headers_check)

    # 5. Если картинка готова, декодируем из base64
    if (
        response_check.status_code == 200
        and "response" in response_check.json()
        and "image" in response_check.json()["response"]
    ):
        image_base64 = response_check.json()["response"]["image"]
        try:
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            raise Exception("Ошибка декодирования base64: " + str(e))
        return image_data
    else:
        # Полная информация об ошибке (для лога)
        raise Exception(
            "Картинка не готова или ошибка в ответе Яндекса. "
            f"status_code={response_check.status_code}, response={response_check.text}"
        )
