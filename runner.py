import os
import time
import psutil
import subprocess
import traceback
import requests
import logging
import gc

# ---------------------- Настройки ----------------------
BOT_FILE = "bot.py"          # твой бот
RESTART_DELAY = 10           # пауза перед перезапуском
MEMORY_LIMIT_MB = 450        # лимит памяти
CPU_LIMIT = 90               # лимит CPU %
CHECK_INTERVAL = 5           # проверка каждые N секунд
LOG_FILE = "bot.log"         # лог-файл
KEEPALIVE_INTERVAL = 300     # 5 минут ping самому себе

# Git
GIT_REPO_DIR = "/home/deploy/discordbot"
GIT_BRANCH = "main"

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ---------------------- Функции ----------------------
def git_pull():
    """Обновляем код из Git"""
    try:
        subprocess.run(["git", "fetch", "--all"], cwd=GIT_REPO_DIR, check=True)
        subprocess.run(["git", "reset", "--hard", f"origin/{GIT_BRANCH}"], cwd=GIT_REPO_DIR, check=True)
        logging.info("✅ Git обновлён успешно")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Ошибка при git pull: {e}")
        return False

def ping_self():
    """Лёгкий HTTP-запрос к локальному серверу, чтобы VPS не засыпала"""
    try:
        requests.get("http://localhost", timeout=2)
        logging.info("💓 Ping самому себе отправлен")
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
            logging.warning("⚠️ Процесс завершён")
            return False
        try:
            mem = ps_proc.memory_info().rss / (1024 * 1024)  # MB
            cpu = ps_proc.cpu_percent(interval=1)            # % CPU
            if mem > MEMORY_LIMIT_MB:
                logging.warning(f"⚠️ Процесс использует слишком много памяти: {mem:.2f} MB")
                process.kill()
                return False
            if cpu > CPU_LIMIT:
                logging.warning(f"⚠️ CPU перегружен: {cpu:.2f}%")
                process.kill()
                return False
        except psutil.NoSuchProcess:
            logging.warning("⚠️ Процесс завершён")
            return False
        except Exception:
            logging.error(f"❌ Ошибка мониторинга:\n{traceback.format_exc()}")
            return False

# ---------------------- Основной цикл ----------------------
if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    last_ping = 0

    while True:
        try:
            logging.info("♻️ Проверка обновлений Git...")
            git_pull()  # обновляем код перед запуском

            logging.info("🚀 Запуск бота")
            process = subprocess.Popen(["python3", BOT_FILE])

            while True:
                # Пинг VPS каждые KEEPALIVE_INTERVAL секунд
                if time.time() - last_ping > KEEPALIVE_INTERVAL:
                    ping_self()
                    last_ping = time.time()

                # Проверяем процесс
                if process.poll() is not None:
                    logging.warning("⚠️ Процесс бота завершён")
                    break

                mem = psutil.Process(process.pid).memory_info().rss / (1024*1024)
                cpu = psutil.Process(process.pid).cpu_percent(interval=1)
                if mem > MEMORY_LIMIT_MB or cpu > CPU_LIMIT:
                    logging.warning(f"⚠️ Перезапуск: mem={mem:.2f}MB cpu={cpu:.2f}%")
                    process.kill()
                    break

                time.sleep(CHECK_INTERVAL)

        except Exception:
            logging.error(f"❌ Ошибка в основном цикле:\n{traceback.format_exc()}")

        logging.info(f"♻️ Перезапуск бота через {RESTART_DELAY} секунд...")
        time.sleep(RESTART_DELAY)
        gc.collect()
