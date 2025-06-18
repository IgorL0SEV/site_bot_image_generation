# --- run_all.py: Одновременный запуск Flask и Telegram бота с обработкой Ctrl+C ---
import threading
import subprocess
import sys
import signal

# Храним процессы для последующего завершения
processes = []

# Запуск отдельного подпроцесса (Flask или bot_runner)
def run_process(command: str):
    proc = subprocess.Popen([sys.executable, command])
    processes.append(proc)
    proc.wait()  # ждём завершения процесса

# Обработка сигналов остановки (Ctrl+C, SIGTERM)
def shutdown(signum, frame):
    print("\n⛔ Получен сигнал остановки. Завершаем все процессы...")
    for proc in processes:
        if proc.poll() is None:  # процесс ещё жив
            proc.terminate()
    sys.exit(0)

if __name__ == "__main__":
    # Назначаем обработчики сигналов
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Запускаем Flask и Telegram в отдельных потоках
    t1 = threading.Thread(target=run_process, args=("app.py",))
    t2 = threading.Thread(target=run_process, args=("bot_runner.py",))

    t1.start()
    t2.start()

    t1.join()
    t2.join()