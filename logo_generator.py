import os
import time
import base64
import requests
from dotenv import load_dotenv
from token_updater import get_iam_token

# Загружаем переменные окружения из файла .env
load_dotenv()

# Берем CATALOG_ID из переменных окружения
CATALOG_ID = os.getenv("CATALOG_ID")

# Проверяем наличие CATALOG_ID, чтобы не было тихих ошибок
if not CATALOG_ID:
    raise Exception("❌ Не найден CATALOG_ID в .env! Проверьте конфигурацию.")

def generate_logo(prompt):
    """
    Генерирует картинку по текстовому описанию через Yandex Cloud API.

    Аргументы:
        prompt (str): Текстовое описание (промпт) для генерации картинки.

    Возвращает:
        bytes: Данные сгенерированного изображения (для сохранения в файл/отправки в чат).

    Вызывает:
        Exception: Если произошла ошибка на любом этапе генерации.
    """
    # Получаем актуальный IAM-токен (автоматически обновляется)
    iam_token = get_iam_token()

    # Подготавливаем запрос к Yandex Cloud
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json"
    }
    data = {
        "modelUri": f"art://{CATALOG_ID}/yandex-art/latest",   # Указываем модель
        "generationOptions": {
            "seed": str(int(time.time())),                     # Для уникальности результата
            "aspectRatio": {"widthRatio": "2", "heightRatio": "1"}  # Соотношение сторон
        },
        "messages": [{"weight": "1", "text": prompt}]          # Сам текст-промпт
    }

    # Отправляем POST-запрос для запуска генерации
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Ошибка генерации: {response.status_code} {response.text}")

    # Получаем ID задачи на генерацию
    request_id = response.json().get("id")

    # Даем время на генерацию картинки (10 секунд)
    time.sleep(10)

    # Проверяем статус готовности и получаем результат
    url_check = f"https://llm.api.cloud.yandex.net/operations/{request_id}"
    headers_check = {"Authorization": f"Bearer {iam_token}"}
    response_check = requests.get(url_check, headers=headers_check)

    # Если всё ок — декодируем картинку и возвращаем как bytes
    if (
        response_check.status_code == 200
        and "response" in response_check.json()
        and "image" in response_check.json()["response"]
    ):
        image_base64 = response_check.json()["response"]["image"]
        image_data = base64.b64decode(image_base64)
        return image_data
    else:
        # Обработка ошибок генерации/получения картинки
        raise Exception("Картинка не готова или ошибка в ответе Яндекса.")

