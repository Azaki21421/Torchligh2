import pyautogui
import shutil
import os
import time
import logging
import threading
import psutil

LOG_FILE = 'log.log'
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

SOURCE_FOLDER = os.path.expandvars(r'%USERPROFILE%\Documents\My Games\Runic Games\Torchlight 2\Save')
DEST_FOLDER = os.path.expandvars(r'%USERPROFILE%\Desktop\torch2')
FIRST_FOLDER = os.path.join(DEST_FOLDER, 'backup_1')
SECOND_FOLDER = os.path.join(DEST_FOLDER, 'backup_2')
TARGET_IMAGE = os.path.expandvars(r'%USERPROFILE%\Desktop\Python\torch2\save.png')
CHECK_INTERVAL = 30
FILE_CHECK_INTERVAL = 60
GAME_PROCESS_NAME = 'Torchlight2.exe'

save_lock = threading.Lock()
save_performed = False


def log_and_print(message, level='info'):
    """Логирует и выводит сообщение в консоль."""
    print(message)
    if level == 'info':
        logging.info(message)
    elif level == 'error':
        logging.error(message)


def delete_folder(folder_path):
    """Удаляет папку, если она существует."""
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            log_and_print(f"Старая папка удалена: {folder_path}")
        except Exception as e:
            log_and_print(f"Ошибка при удалении папки {folder_path}: {e}", level='error')


def copy_to_first_folder():
    """Копирует исходную папку в первую папку назначения."""
    try:
        delete_folder(FIRST_FOLDER)
        shutil.copytree(SOURCE_FOLDER, FIRST_FOLDER)
        log_and_print(f"Папка успешно скопирована в первую папку: {FIRST_FOLDER}")
    except Exception as e:
        log_and_print(f"Ошибка при копировании в первую папку: {e}", level='error')


def move_first_to_second_folder():
    """Перемещает содержимое первой папки во вторую папку."""
    try:
        delete_folder(SECOND_FOLDER)
        shutil.move(FIRST_FOLDER, SECOND_FOLDER)
        log_and_print(f"Первая папка перемещена во вторую папку: {SECOND_FOLDER}")
    except Exception as e:
        log_and_print(f"Ошибка при перемещении во вторую папку: {e}", level='error')


def has_enough_files():
    """Проверяет, содержит ли хотя бы одна подпапка более 4 файлов."""
    try:
        subfolders = [os.path.join(SOURCE_FOLDER, d) for d in os.listdir(SOURCE_FOLDER) if os.path.isdir(os.path.join(SOURCE_FOLDER, d))]
        for subfolder in subfolders:
            files = [f for f in os.listdir(subfolder) if os.path.isfile(os.path.join(subfolder, f))]
            if len(files) > 4:
                log_and_print(f"В подпапке '{subfolder}' найдено {len(files)} файлов. Копирование разрешено.")
                return True
        log_and_print("Ни в одной из подпапок нет более 4 файлов. Копирование отменено.")
        return False
    except Exception as e:
        log_and_print(f"Ошибка при проверке количества файлов в подпапках: {e}", level='error')
        return False


def perform_backup():
    """Выполняет копирование с перемещением, если обнаружено обновление и файлов достаточно."""
    global save_performed
    with save_lock:
        if save_performed:
            return

        if has_enough_files():
            log_and_print("Начинается процесс копирования...")
            if os.path.exists(FIRST_FOLDER):
                move_first_to_second_folder()
            copy_to_first_folder()
            save_performed = True


def find_image_on_screen():
    """Поток для поиска изображения на экране."""
    global save_performed
    while True:
        try:
            if pyautogui.locateOnScreen(TARGET_IMAGE, confidence=0.8):
                log_and_print(f"Изображение '{TARGET_IMAGE}' обнаружено!")
                perform_backup()
        except Exception as e:
            log_and_print(f"Ошибка при поиске изображения: {e}", level='error')

        time.sleep(CHECK_INTERVAL)


def is_save_file_updated():
    """Поток для проверки обновления файла сохранения."""
    global save_performed
    while True:
        try:
            files = [os.path.join(SOURCE_FOLDER, f) for f in os.listdir(SOURCE_FOLDER)]
            if files:
                latest_file = max(files, key=os.path.getmtime)
                modified_time = os.path.getmtime(latest_file)
                current_time = time.time()

                if abs(current_time - modified_time) <= 60:
                    log_and_print(f"Файл сохранения '{latest_file}' обновлён недавно.")
                    perform_backup()
        except Exception as e:
            log_and_print(f"Ошибка при проверке времени обновления файла: {e}", level='error')

        time.sleep(FILE_CHECK_INTERVAL)


def restore_save_if_needed():
    """Восстанавливает сохранение, если в исходной папке не хватает файлов."""
    try:
        subfolders = [os.path.join(SOURCE_FOLDER, d) for d in os.listdir(SOURCE_FOLDER) if os.path.isdir(os.path.join(SOURCE_FOLDER, d))]
        for subfolder in subfolders:
            files = [f for f in os.listdir(subfolder) if os.path.isfile(os.path.join(subfolder, f))]
            if len(files) <= 4:
                log_and_print("Недостаточно файлов в папке сохранений. Восстанавливаем из резервной копии.")
                shutil.copytree(FIRST_FOLDER, SOURCE_FOLDER, dirs_exist_ok=True)
                log_and_print("Восстановление завершено.")
                return
        log_and_print("Восстановление не требуется. Достаточно файлов в папке сохранений.")
    except Exception as e:
        log_and_print(f"Ошибка при восстановлении сохранений: {e}", level='error')


def monitor_game_process():
    """Отслеживает процесс игры и восстанавливает сохранение после его завершения."""
    while True:
        game_running = any(proc.name() == GAME_PROCESS_NAME for proc in psutil.process_iter())
        if not game_running:
            log_and_print(f"Игра '{GAME_PROCESS_NAME}' закрыта. Проверяем сохранения...")
            restore_save_if_needed()
        time.sleep(30)


def reset_backup_flag():
    """Сбрасывает флаг сохранения каждые 5 минут."""
    global save_performed
    while True:
        time.sleep(300)
        with save_lock:
            save_performed = False
        log_and_print("Флаг сохранения сброшен. Можно выполнять новые сохранения.")


if __name__ == "__main__":
    threading.Thread(target=find_image_on_screen, daemon=True).start()
    threading.Thread(target=is_save_file_updated, daemon=True).start()
    threading.Thread(target=monitor_game_process, daemon=True).start()
    threading.Thread(target=reset_backup_flag, daemon=True).start()

    while True:
        time.sleep(1)
