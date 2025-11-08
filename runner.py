import os
import time
import psutil
import subprocess
import traceback
import requests
from pathlib import Path
import gc

# ---------------------- Настройки ----------------------
BOT_FILE = "bot.py"          # твой бот
RESTART_DELAY = 10           # пауза перед перезапуском
MEMORY_LIMIT_MB = 450        # лимит памяти
CPU_LIMIT = 90               # лимит CPU %
CHECK_INTERVAL = 5           # проверка каждые N секунд
LOG_FILE = "bot.log"         # лог-файл
KEEPALIVE_INTERVAL = 300     # 5 минут ping самому себе

# SSH keep-alive (опционально)
SSH_USER = "deploy"
SSH_HOST = "46.203.233.199"
AUTOSSH_CMD = [
    "autossh",
    "-M", "0",
    "-o", "ServerAliveInterval=60",
    "-o", "ServerAliveCountMax=3",
    f"{SSH_USER}@{SSH_HOST}"
]

# ---------------------- Функции ----------------------
def log(message):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def start_ssh_keepalive():
    """Запускаем autossh для поддержания SSH-сессии"""
    try:
        subprocess.Popen(AUTOSSH_CMD)
        log("✅ SSH keep-alive запущен через autossh")
    except Exception as e:
        log(f"❌ Ошибка при запуске SSH keep-alive: {e}")

def ping_self():
    """Лёгкий HTTP-запрос к локальному серверу, чтобы VPS не засыпала"""
    try:
        requests.get("http://localhost", timeout=2)
        log("💓 Ping самому себе отправлен")
    except:
        pass

def monitor_process(process):
    """Следим за процессом бота"""
    try:
        ps_proc = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return False

    while True:
        time.sleep(CHECK_INTERVAL)
        if process.poll() is not None:
            log("⚠️ Процесс завершён")
            return False
        try:
            mem = ps_proc.memory_info().rss / (1024 * 1024)  # MB
            cpu = ps_proc.cpu_percent(interval=1)            # % CPU
            if mem > MEMORY_LIMIT_MB:
                log(f"⚠️ Процесс использует слишком много памяти: {mem:.2f} MB")
                process.kill()
                return False
            if cpu > CPU_LIMIT:
                log(f"⚠️ CPU перегружен: {cpu:.2f}%")
                process.kill()
                return False
        except psutil.NoSuchProcess:
            log("⚠️ Процесс завершён")
            return False
        except Exception:
            log(f"❌ Ошибка мониторинга:\n{traceback.format_exc()}")
            return False

# ---------------------- Основной цикл ----------------------
if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Запуск SSH keep-alive
    start_ssh_keepalive()

    # Основной цикл перезапуска бота
    last_ping = 0
    while True:
        try:
            log("🚀 Запуск бота")
            process = subprocess.Popen(["python3", BOT_FILE])

            while True:
                # Пинг VPS каждые KEEPALIVE_INTERVAL секунд
                if time.time() - last_ping > KEEPALIVE_INTERVAL:
                    ping_self()
                    last_ping = time.time()

                # Проверяем процесс
                if process.poll() is not None:
                    log("⚠️ Процесс бота завершён")
                    break

                mem = psutil.Process(process.pid).memory_info().rss / (1024*1024)
                cpu = psutil.Process(process.pid).cpu_percent(interval=1)
                if mem > MEMORY_LIMIT_MB or cpu > CPU_LIMIT:
                    log(f"⚠️ Перезапуск: mem={mem:.2f}MB cpu={cpu:.2f}%")
                    process.kill()
                    break

                time.sleep(CHECK_INTERVAL)

        except Exception:
            log(f"❌ Ошибка в основном цикле:\n{traceback.format_exc()}")

        log(f"♻️ Перезапуск бота через {RESTART_DELAY} секунд...")
        time.sleep(RESTART_DELAY)
        gc.collect()
