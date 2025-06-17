import threading
import subprocess
import sys

print("PYTHON:", sys.executable)


def run_flask():
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except Exception as e:
        print(f"[Flask] Ошибка: {e}")


def run_bot():
    try:
        subprocess.run([sys.executable, "bot.py"], check=True)
    except Exception as e:
        print(f"[Bot] Ошибка: {e}")


if __name__ == "__main__":
    t1 = threading.Thread(target=run_flask)
    t2 = threading.Thread(target=run_bot)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
