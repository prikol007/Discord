import os
import time
import psutil
import subprocess
import traceback
from pathlib import Path
import gc

BOT_FILE = "bot.py"
RESTART_DELAY = 10        # пауза перед перезапуском
MEMORY_LIMIT_MB = 450     # лимит памяти
CPU_LIMIT = 90            # лимит CPU (%)
LOG_FILE = "bot.log"
CHECK_INTERVAL = 5        # проверка каждые N секунд

# SSH-конфиг
SSH_USER = "deploy"
SSH_HOST = "46.203.233.199"

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def log(message):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def start_ssh_keepalive():
    """Запускаем autossh, чтобы поддерживать SSH-сессию живой"""
    try:
        # -M 0 отключает мониторинг через порт
        subprocess.Popen([
            "autossh",
            "-M", "0",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
            f"{SSH_USER}@{SSH_HOST}"
        ])
        log("✅ SSH keep-alive запущен через autossh")
    except Exception as e:
        log(f"❌ Ошибка при запуске SSH keep-alive: {e}")

def monitor_process(process):
    """Следим за процессом, пока он работает"""
    try:
        ps_proc = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return False

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            mem = ps_proc.memory_info().rss / (1024 * 1024)  # в MB
            cpu = ps_proc.cpu_percent()
            if mem > MEMORY_LIMIT_MB:
                log(f"⚠️ Процесс использует слишком много памяти: {mem:.2f} MB")
                return False
            if cpu > CPU_LIMIT:
                log(f"⚠️ CPU перегружен: {cpu:.2f}%")
                return False
        except psutil.NoSuchProcess:
            log("⚠️ Процесс завершён")
            return False
        except Exception as e:
            log(f"❌ Ошибка мониторинга: {traceback.format_exc()}")
            return False

# Пример использования:
if __name__ == "__main__":
    # Запускаем SSH keep-alive сразу при старте
    start_ssh_keepalive()

    # Запуск бота в отдельном процессе
    while True:
        try:
            log("🚀 Запуск бота")
            process = subprocess.Popen(["python3", BOT_FILE])
            monitor_process(process)
        except Exception as e:
            log(f"❌ Ошибка запуска: {traceback.format_exc()}")
        log(f"♻️ Перезапуск через {RESTART_DELAY} секунд...")
        time.sleep(RESTART_DELAY)
        gc.collect()
