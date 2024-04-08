import os
import sys
import time
from typing import Dict, Any

from dotenv import dotenv_values
from loguru import logger
from requests import ConnectionError, ReadTimeout

from util import create_folder_in_cloud, cloud_load, delete_file
from yandex_cloud import YandexCloud

CONFIG = dotenv_values(".env")
PATH_LOG_FILE: str = CONFIG.get("PATH_FILE_LOG")
logger.add(
    f"{PATH_LOG_FILE}/cloud.log",
    format="synchronization {time} {level} {message}",
    level="INFO",
    rotation="100 MB"
)


def check_sleep_period(period: str) -> None:
    """
    Проверяем что в конфигурации указан правильный период времени,
    через который будет проходить синхронизация.

    :param period: Период который указан в файле dotenv.
    """
    if not period.isdigit():
        logger.error(
            "Неверно указан период синхронизации, это должно быть целое число(измерение в секундах)."
        )
        sys.exit(1)


def check_path_exists(path: str) -> None:
    """
    Проверяем существует ли путь указанный в dotenv.
    Если нет, то завершаем работу приложения.

    :param path: Путь к папке, которую нужно синхронизировать.
    """
    check: bool = os.path.exists(path)
    if not check:
        logger.error(f"Указанный путь к {path} не существует. Введите корректный путь.")
        sys.exit(1)


def synchronization(
    path_on_pc: str,
    cloud: Any
) -> None:
    """
    Функция сравнивает файлы на пк и в облаке, если файла нет в облаке или дата изменения файла
    больше чем в облаке, то отправляем на сохранение в облако.

    :param path_on_pc: Путь к папке на компьютере, с которой будет синхронизировано облако.
    :param cloud: Экземпляр класса для работы с облаком.
    """
    # Инициализируем переменные для подсчета сделанных операций при синхронизации
    download_files: int = 0
    deleted_files: int = 0
    rewrite_files: int = 0
    try:
        files_cloud: Dict[str, float] = cloud.get_info()

        # Проходимся циклом по списку файлов которые есть на пк в нашей папке
        for file in os.listdir(path_on_pc):
            modified: float = os.path.getmtime(f"{path_on_pc}/{file}")
            file_cloud: float | None = files_cloud.pop(file) if file in files_cloud else None

            # Файла нет в облаке, значит сохраняем его
            if not file_cloud:
                result: bool = cloud_load(cloud, path_on_pc, file, logger)
                download_files += 1 if result else 0

            # Дата изменения в облаке меньше чем в папке на пк, значит перезаписываем
            elif file_cloud and modified > file_cloud:
                result: bool = cloud_load(cloud, path_on_pc, file, logger, reload=True)
                rewrite_files += 1 if result else 0

        # Если в словаре еще остались файлы, значит их нужно удалить, так как на пк их нет.
        if len(files_cloud) > 0:
            for filename in files_cloud.keys():
                result: bool = delete_file(cloud, filename, logger)
                deleted_files += 1 if result else 0

        logger.info(
            f"Загружено: {download_files}, Перезаписано: {rewrite_files}, Удалено: {deleted_files}"
        )
    except (ConnectionError, ReadTimeout):
        logger.error("Нет соединения, проверьте подключение.")


def main():
    """
    Функция собирает переменные окружения, инициализирует объект и запускает бесконечный цикл.
    """
    # Получаем нужные данные для работы.
    token: str = CONFIG.get("YANDEX_TOKEN")
    sleep_period: str = CONFIG.get("SYNCHRONIZATION_PERIOD")
    path_to_folder_on_pc: str = CONFIG.get("PATH_TO_FOLDER_ON_PC")
    name_folder_cloud: str = CONFIG.get("NAME_FOLDER_CLOUD")

    # Инициализируем yandex
    yandex: YandexCloud = YandexCloud(token, name_folder_cloud)

    # При запуске проверяем наличие указанной папки в облаке, если ее нет то она будет создана
    create_folder_in_cloud(yandex, name_folder_cloud, logger)

    # Небольшие проверки для корректности работы.
    check_path_exists(path_to_folder_on_pc)
    check_sleep_period(sleep_period)

    while True:
        logger.info("Запущен процесс синхронизации...")
        synchronization(path_to_folder_on_pc, yandex)
        logger.info("Синхронизация завершена!")
        time.sleep(int(sleep_period))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Приложение принудительно остановлено.")
