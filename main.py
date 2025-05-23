import asyncio
import functools
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from aiohttp import ClientConnectionError, ConnectionTimeoutError, ClientError
from dotenv import load_dotenv
from loguru import logger

from cloud import Cloud
from util import (
    AuthorizationError,
    check_path_exists,
    check_sleep_period,
    func_error_logging,
)
from yandex_cloud import YandexCloud

env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

PATH_LOG_FILE = os.getenv('PATH_FILE_LOG')

logger.add(
    f"{PATH_LOG_FILE}/cloud.log",
    format="synchronization {time} {level} {message}",
    level="INFO",
    rotation="100 MB",
)


def connect_error(func: Callable) -> Callable:
    """Декоратор для обработки возможных ошибок."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)

        except (ClientConnectionError, ConnectionTimeoutError):
            await func_error_logging(func.__name__, args, logger)

    return wrapper


@connect_error
async def delete_file(cloud: Any, file: str) -> bool:
    """Функция для запроса на удаление файла.

    :param cloud: Облако для удаления
    :param file: Имя файла для удаления.
    :return bool: Возвращаем True, нужно для подсчета удаленных файлов.
    """
    await cloud.delete_file(file)
    return True


@connect_error
async def cloud_load(
        cloud: YandexCloud, path_on_pc: str, file: str, reload=False
) -> bool | None:
    """Функция для запроса на сохранение файла.
    Нужна для отлова возможных ошибок.

    :param cloud: Облако для удаления.
    :param file: Имя файла для удаления.
    :param path_on_pc: Путь к файлу на пк.
    :param reload: Нужен, чтобы использовать одну функцию
        для сохранения и перезаписи.
    :return bool: Возвращаем True, нужно для подсчета удаленных файлов.
    """
    try:
        await cloud.upload_file(path_on_pc, file) if not reload \
            else await cloud.update_file(path_on_pc, file)
        return True
    except PermissionError:
        logger.error(
            f"Файл {file} не был {'перезаписан' if reload else 'сохранен'}."
            f"Недостаточно прав!"
        )


@connect_error
async def create_folder_in_cloud(cloud: Any, folder=None) -> None:
    """
    Функция для создания папки в облаке. Заодно сразу проверку проходит
    указанный токен. Если указанной папки не существует, то она будет создана.
    Если неверно указан токен, то приложение будет остановлено.

    :param cloud: Облако в котором нужно создать папку.

    :param folder: Вложенная папка в облаке.
    """
    try:
        if folder is None:
            await cloud.create_folder()
        else:
            await cloud.create_folder(folder)
    except ClientError as err:
        logger.error(err)
        if isinstance(err, AuthorizationError):
            sys.exit(1)


@connect_error
async def synchronization(path_on_pc: str, cloud: Cloud):
    """
    Функция сравнивает файлы на пк и в облаке.

    :param path_on_pc: Путь к папке на компьютере
    :param cloud: Экземпляр класса для работы с облаком
    :return: Кортеж с количеством
    (загруженных, удаленных, перезаписанных) файлов
    """
    cloud_files: dict[str, float] = await cloud.get_info()

    # Обрабатываем файлы и папки на ПК
    tasks: list = []
    for item in os.listdir(path_on_pc):
        item_path = os.path.join(path_on_pc, item)

        if os.path.isdir(item_path):
            # Обработка папки - рекурсивный вызов
            original_folder = cloud.name_folder_cloud

            # Создаем папку в облаке (если еще не существует)
            if not await cloud.is_exists_folder(item):
                await create_folder_in_cloud(cloud, item)

            cloud.name_folder_cloud = f"{cloud.name_folder_cloud}/{item}"
            await synchronization(item_path, cloud)
            cloud.name_folder_cloud = original_folder
            continue

        # Обработка файла
        modified = os.path.getmtime(item_path)
        cloud_time = cloud_files.pop(item, None)

        if cloud_time is None:
            # Файла нет в облаке - загружаем
            tasks.append(cloud_load(cloud, path_on_pc, item))

        elif modified > cloud_time:
            # Файл в облаке устарел - перезаписываем
            tasks.append(cloud_load(cloud, path_on_pc, item, reload=True))

    # Удаляем оставшиеся файлы в облаке (только файлы, не папки)
    for filename in cloud_files:
        path: str = os.path.join(path_on_pc, filename)
        # Это так же работает если мы удалили всю папку на pc, то такой
        # директории у нас не будет и будет запрос на удаление всей папки в
        # облаке, что нам и нужно.
        if not os.path.isdir(path):
            tasks.append(delete_file(cloud, filename))

    await asyncio.gather(*tasks)
    return


async def main():
    """
    Функция собирает переменные окружения, инициализирует объект и запускает
    бесконечный цикл.
    """
    # Получаем нужные данные для работы.
    token: str = os.getenv("YANDEX_TOKEN")
    sleep_period: str = os.getenv("SYNCHRONIZATION_PERIOD")
    path_to_folder_on_pc: str = os.getenv("PATH_TO_FOLDER_ON_PC")
    name_folder_cloud: str = os.getenv("NAME_FOLDER_CLOUD")

    # Инициализируем yandex
    yandex: Cloud = YandexCloud(token, name_folder_cloud)

    # При запуске проверяем наличие указанной папки в облаке,
    # если ее нет то она будет создана
    await create_folder_in_cloud(yandex)

    # Небольшие проверки для корректности работы.
    await check_path_exists(path_to_folder_on_pc, logger)
    await check_sleep_period(sleep_period, logger)

    while True:
        start = time.time()
        try:
            yandex.name_folder_cloud = name_folder_cloud
            logger.info(
                f"Запущен процесс синхронизации директории "
                f"{path_to_folder_on_pc} и папка {name_folder_cloud} в облаке."
            )
            await synchronization(path_to_folder_on_pc, yandex)

        except asyncio.TimeoutError:
            logger.error("TimeOutError, файл не успел загрузиться.")

        except ConnectionError as err:
            logger.error(err)

        finally:
            logger.info(
                f"Процесс синхронизации завершен! Время выполнения "
                f"{time.time() - start}"
            )
            await asyncio.sleep(int(sleep_period) - (time.time() - start))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение было принудительно остановлено.")
