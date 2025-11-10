import os
import time
import psutil
import subprocess
import traceback
import requests
import gc

# ---------------------- Настройки ----------------------
BOT_FILE = "bot.py"                  # Файл бота
RESTART_DELAY = 10                   # Пауза перед перезапуском
MEMORY_LIMIT_MB = 450                # Лимит памяти
CPU_LIMIT = 90                       # Лимит CPU %
CHECK_INTERVAL = 5                   # Проверка каждые N секунд
LOG_FILE = "bot.log"                 # Лог контроллера
BOT_OUTPUT_LOG = "bot_output.log"    # Лог самого бота
KEEPALIVE_INTERVAL = 300             # 5 минут ping самому себе
GIT_REPO = "origin"                  # удалённый репозиторий
GIT_BRANCH = "main"                  # ветка для автопула
GIT_CHECK_INTERVAL = 60              # Проверка обновлений каждые N секунд

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
    try:
        subprocess.Popen(AUTOSSH_CMD)
        log("✅ SSH keep-alive запущен через autossh")
    except Exception as e:
        log(f"❌ Ошибка при запуске SSH keep-alive: {e}")

def ping_self():
    try:
        requests.get("http://localhost", timeout=2)
        log("💓 Ping самому себе отправлен")
    except:
        pass

def monitor_process(process):
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
            mem = ps_proc.memory_info().rss / (1024 * 1024)
            cpu = ps_proc.cpu_percent(interval=1)
            if mem > MEMORY_LIMIT_MB:
                log(f"⚠️ Перезапуск из-за памяти: {mem:.2f} MB")
                process.kill()
                return False
            if cpu > CPU_LIMIT:
                log(f"⚠️ Перезапуск из-за CPU: {cpu:.2f}%")
                process.kill()
                return False
        except psutil.NoSuchProcess:
            log("⚠️ Процесс завершён")
            return False
        except Exception:
            log(f"❌ Ошибка мониторинга:\n{traceback.format_exc()}")
            return False

def git_pull_update():
    """Проверяет и подтягивает обновления из Git"""
    try:
        # Проверяем наличие новых коммитов
        subprocess.run(["git", "fetch", GIT_REPO], check=True)
        local = subprocess.check_output(["git", "rev-parse", GIT_BRANCH]).decode().strip()
        remote = subprocess.check_output(["git", "rev-parse", f"{GIT_REPO}/{GIT_BRANCH}"]).decode().strip()
        if local != remote:
            log("🔄 Найдены обновления на GitHub, выполняем pull...")
            subprocess.run(["git", "pull", GIT_REPO, GIT_BRANCH], check=True)
            log("✅ Обновления подтянуты, перезапускаем бота")
            return True
    except Exception as e:
        log(f"❌ Ошибка при git pull: {e}")
    return False

# ---------------------- Основной цикл ----------------------
if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    start_ssh_keepalive()
    last_ping = 0
    last_git_check = 0

    while True:
        try:
            # Проверка обновлений из Git
            if time.time() - last_git_check > GIT_CHECK_INTERVAL:
                if git_pull_update():
                    # если есть обновления, перезапускаем сразу
                    time.sleep(RESTART_DELAY)
                    continue
                last_git_check = time.time()

            log("🚀 Запуск бота")
            process = subprocess.Popen(
                ["python3", BOT_FILE],
                stdout=open(BOT_OUTPUT_LOG, "a"),
                stderr=subprocess.STDOUT
            )

            while True:
                if time.time() - last_ping > KEEPALIVE_INTERVAL:
                    ping_self()
                    last_ping = time.time()

                # Проверка процесса
                if process.poll() is not None:
                    log("⚠️ Процесс бота завершён")
                    break

                mem = psutil.Process(process.pid).memory_info().rss / (1024*1024)
                cpu = psutil.Process(process.pid).cpu_percent(interval=1)
                if mem > MEMORY_LIMIT_MB or cpu > CPU_LIMIT:
                    log(f"⚠️ Перезапуск из-за лимитов: mem={mem:.2f}MB cpu={cpu:.2f}%")
                    process.kill()
                    break

                # Проверка Git на обновления
                if time.time() - last_git_check > GIT_CHECK_INTERVAL:
                    if git_pull_update():
                        process.kill()
                        break
                    last_git_check = time.time()

                time.sleep(CHECK_INTERVAL)

        except Exception:
            log(f"❌ Ошибка в основном цикле:\n{traceback.format_exc()}")

        log(f"♻️ Перезапуск бота через {RESTART_DELAY} секунд...")
        time.sleep(RESTART_DELAY)
        gc.collect()
