import functools
import os
import sys
import time
from typing import Dict, Any, Callable

from dotenv import dotenv_values
from loguru import logger
from requests import ConnectionError, ReadTimeout, RequestException

from util import (
    AuthorizationError,
    check_path_exists,
    check_sleep_period,
    RequestError,
    func_error_logging,
)
from yandex_cloud import YandexCloud

CONFIG = dotenv_values(".env")
PATH_LOG_FILE: str = CONFIG.get("PATH_FILE_LOG")
logger.add(
    f"{PATH_LOG_FILE}/cloud.log",
    format="synchronization {time} {level} {message}",
    level="INFO",
    rotation="100 MB",
)


def connect_error(func: Callable) -> Callable:
    """Декоратор для обработки возможных ошибок."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except RequestError as err:
            logger.error(err)

        except (ConnectionError, ReadTimeout):
            func_error_logging(func.__name__, args, logger)

    return wrapper


@connect_error
def delete_file(cloud: Any, file: str) -> bool:
    """Функция для запроса на удаление файла.

    :param cloud: Облако для удаления
    :param file: Имя файла для удаления.
    :return bool: Возвращаем True, нужно для подсчета удаленных файлов.
    """
    cloud.delete(file)
    logger.info(f"Файл {file}, был удален.")
    return True


@connect_error
def cloud_load(cloud: Any, path_on_pc: str, file: str, reload=False) -> bool:
    """Функция для запроса на сохранение файла. Нужна для отлова возможных ошибок.

    :param cloud: Облако для удаления.
    :param file: Имя файла для удаления.
    :param path_on_pc: Путь к файлу на пк.
    :param reload: Нужен, чтобы использовать одну функцию для сохранения и перезаписи.
    :return bool: Возвращаем True, нужно для подсчета удаленных файлов.
    """
    try:
        cloud.load(path_on_pc, file) if not reload else cloud.reload(path_on_pc, file)
        logger.info(f"Файл {file}, был {'сохранен' if not reload else 'перезаписан'}.")
        return True
    except PermissionError:
        logger.error(
            f"Файл {file} не был {'перезаписан' if reload else 'сохранен'}. Недостаточно прав!"
        )


@connect_error
def create_folder_in_cloud(cloud: Any) -> None:
    """
    Функция для создания папки в облаке. Заодно сразу проверку проходит указанный токен.
    Если указанной папки не существует, то она будет создана.
    Если неверно указан токен, то приложение будет остановлено.

    :param cloud: Облако в котором нужно создать папку.
    """
    try:
        cloud.create_folder_cloud()
    except RequestException as err:
        logger.error(err)
        if isinstance(err, AuthorizationError):
            sys.exit(1)


@connect_error
def synchronization(path_on_pc: str, cloud: Any) -> None:
    """
    Функция сравнивает файлы на пк и в облаке, если файла нет в облаке или дата изменения файла
    больше чем в облаке, то отправляем на сохранение в облако. Если файл есть в облаке, но нет
    на пк, то файл в облаке удаляем.

    :param path_on_pc: Путь к папке на компьютере, с которой будет синхронизировано облако.
    :param cloud: Экземпляр класса для работы с облаком.
    """
    # Инициализируем переменные для подсчета сделанных операций при синхронизации
    download_files: int = 0
    deleted_files: int = 0
    rewritten_files: int = 0
    files_cloud: Dict[str, float] = cloud.get_info()

    # Проходимся циклом по списку файлов которые есть на пк в нашей папке
    for file in os.listdir(path_on_pc):
        modified: float = os.path.getmtime(f"{path_on_pc}/{file}")
        file_cloud: float | None = (
            files_cloud.pop(file) if file in files_cloud else None
        )

        # Файла нет в облаке, значит сохраняем его
        if not file_cloud:
            result: bool | None = cloud_load(cloud, path_on_pc, file)
            download_files += 1 if result else 0

        # Дата изменения в облаке меньше чем в папке на пк, значит перезаписываем
        elif file_cloud and modified > file_cloud:
            result: bool | None = cloud_load(cloud, path_on_pc, file, 1)
            rewritten_files += 1 if result else 0

    # Если в словаре еще остались файлы, значит их нужно удалить, так как на пк их нет.
    if len(files_cloud) > 0:
        for filename in files_cloud.keys():
            result: bool | None = delete_file(cloud, filename)
            deleted_files += 1 if result else 0

    logger.info(
        f"Загружено: {download_files}, Перезаписано: {rewritten_files}, Удалено: {deleted_files}"
    )


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
    create_folder_in_cloud(yandex)

    # Небольшие проверки для корректности работы.
    check_path_exists(path_to_folder_on_pc, logger)
    check_sleep_period(sleep_period, logger)

    while True:
        logger.info(
            f"Запущен процесс синхронизации директории "
            f"{path_to_folder_on_pc} и папка {name_folder_cloud} в облаке."
        )
        synchronization(path_to_folder_on_pc, yandex)
        logger.info(f"Процесс синхронизации завершен!")
        time.sleep(int(sleep_period))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Приложение принудительно остановлено.")
