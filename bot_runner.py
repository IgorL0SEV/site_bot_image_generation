# Запускается через run_all.py
# функция - перезапускать при сбоях Telegram бот
import time
import subprocess
import sys
from datetime import datetime

LOG_FILE = "bot_errors.log"

def log_error(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {msg}\n")

def run_bot_forever():
    while True:
        try:
            # Запускаем bot.py как отдельный процесс
            print("Стартую бот...")
            result = subprocess.run([sys.executable, "bot.py"])
            if result.returncode == 0:
                print("Бот завершился штатно. Перезапуск не требуется.")
                break  # Если бот завершился штатно — выходим
            else:
                err_msg = f"Бот завершился с кодом {result.returncode}"
                print(err_msg)
                log_error(err_msg)
        except Exception as e:
            err_msg = f"Исключение при запуске бота: {e}"
            print(err_msg)
            log_error(err_msg)
        print("Перезапуск бота через 10 секунд...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot_forever()
