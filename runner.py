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

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def log(message):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def monitor_process(process):
    """Следим за процессом, пока он работает"""
    try:
        ps_proc = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return False

    while True:
        time.sleep(CHECK_INTERVAL)
        if process.poll() is not None:  # бот завершился
            log("⚠️ Подпроцесс завершён.")
            return False

        try:
            cpu = ps_proc.cpu_percent(interval=None) / psutil.cpu_count()
            mem = ps_proc.memory_info().rss / 1024 / 1024

            if mem > MEMORY_LIMIT_MB:
                log(f"🚨 Превышен лимит памяти ({mem:.0f} MB > {MEMORY_LIMIT_MB}) — перезапуск.")
                ps_proc.terminate()
                return True

            if cpu > CPU_LIMIT:
                log(f"🚨 Высокая загрузка CPU ({cpu:.0f}% > {CPU_LIMIT}%) — перезапуск.")
                ps_proc.terminate()
                return True

        except psutil.NoSuchProcess:
            return False
        except Exception as e:
            log(f"Ошибка мониторинга: {e}")
            return False

def run_bot():
    """Запускаем бот как подпроцесс и пишем лог в файл"""
    out_path = Path("bot_output.log")
    with out_path.open("a", encoding="utf-8") as out:
        process = subprocess.Popen(
            ["python", BOT_FILE],
            stdout=out,
            stderr=subprocess.STDOUT,
            text=True
        )
    return process

if __name__ == "__main__":
    log("🟢 Watchdog запущен")
    while True:
        try:
            process = run_bot()
            log("🚀 Бот запущен")
            restart_needed = monitor_process(process)
            gc.collect()
            log(f"♻️ Перезапуск через {RESTART_DELAY} сек...\n")
            time.sleep(RESTART_DELAY)

        except KeyboardInterrupt:
            log("⛔ Завершение по Ctrl+C")
            break
        except Exception:
            log(f"❌ Ошибка Watchdog: {traceback.format_exc()}")
            time.sleep(RESTART_DELAY)
