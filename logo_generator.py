import os
import time
import base64
import requests
import logging
from dotenv import load_dotenv
from token_updater import get_iam_token

# --- Логирование ошибок и прогресса ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения из файла .env (для CATALOG_ID и др.)
load_dotenv()
CATALOG_ID = os.getenv("CATALOG_ID")

if not CATALOG_ID:
    raise Exception("❌ Не найден CATALOG_ID в .env! Проверьте конфигурацию.")

def generate_logo(prompt: str) -> bytes:
    """
    Генерация логотипа через Yandex ART API с устойчивостью к сбоям.
    Выполняется polling + повторные попытки при временных ошибках.
    """
    iam_token = get_iam_token()
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json"
    }
    data = {
        "modelUri": f"art://{CATALOG_ID}/yandex-art/latest",
        "generationOptions": {
            "seed": str(int(time.time())),
            "aspectRatio": {"widthRatio": "2", "heightRatio": "1"}
        },
        "messages": [{"weight": "1", "text": prompt[:250]}]  # обрезаем до 250 символов
    }

    # --- Повторная попытка генерации (макс. 3 раза) ---
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            if response.status_code != 200:
                logger.warning(f"[Yandex ART] Ошибка генерации: {response.status_code} {response.text}")
                time.sleep(1)
                continue

            request_id = response.json().get("id")
            if not request_id:
                raise Exception("Yandex не вернул ID задачи. Ответ: " + response.text)

            logger.info(f"[Yandex ART] Старт генерации. request_id={request_id}")
            # --- Polling: ожидание завершения генерации ---
            url_check = f"https://llm.api.cloud.yandex.net/operations/{request_id}"
            headers_check = {"Authorization": f"Bearer {iam_token}"}

            for poll_attempt in range(10):
                time.sleep(2)
                try:
                    response_check = requests.get(url_check, headers=headers_check, timeout=10)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"[Yandex ART] Ошибка при опросе: {e}")
                    continue

                if (
                    response_check.status_code == 200 and
                    "response" in response_check.json() and
                    "image" in response_check.json()["response"]
                ):
                    image_base64 = response_check.json()["response"]["image"]
                    logger.info("[Yandex ART] Картинка готова. Декодируем...")
                    try:
                        return base64.b64decode(image_base64)
                    except Exception as e:
                        raise Exception("Ошибка декодирования base64: " + str(e))

            raise Exception("Истёк таймер ожидания генерации (polling timeout)")

        except requests.exceptions.RequestException as e:
            logger.warning(f"[Yandex ART] Ошибка подключения: {e}")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"[Yandex ART] Ошибка генерации: {e}")
            time.sleep(2)

    raise Exception("❌ Не удалось получить изображение после 3 попыток")
