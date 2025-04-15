import os.path
from abc import ABC
from datetime import datetime as dt
from pathlib import Path
from typing import Dict
from http import HTTPStatus

import aiohttp
import aiofiles
from aiohttp import ClientTimeout
from dotenv import load_dotenv
from loguru import logger

from cloud import Cloud
from util import AuthorizationError, RequestError

env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)
PATH_LOG_FILE = os.getenv('PATH_FILE_LOG')

logger.add(
    f"{PATH_LOG_FILE}/cloud.log",
    format="synchronization {time} {level} {message}",
    level="INFO",
    rotation="100 MB",
)


class YandexCloud(Cloud):
    """
    Класс для работы с яндекс облаком.

    Args:
        token (str): Передается токен для аутентификации с яндекс диском.
        name_folder_cloud (str): Папка в облаке с которой будет синхронизация.

    Attributes:
        url (str): Базовый url для запросов к диску.
    """

    url = "https://cloud-api.yandex.net/v1/disk/resources"

    def __init__(self, token: str, name_folder_cloud: str):
        self.name_folder_cloud = name_folder_cloud
        self._headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
            "Authorization": f"OAuth {token}",
        }

    async def _save(self, url: str, path: str, file_name: str) -> None:
        """
        Метод для сохранения файла в облаке, нужен для методов load и reload.

        :param url: Сформированный url для загрузки файла.
        :param path: Путь к файлу на пк.
        :param file_name: Имя файла который нужно сохранить.
        :raise RequestError: Если запрос завершился кодом отличным от 200.
        """
        # Настройки загрузки
        timeout: ClientTimeout = aiohttp.ClientTimeout(
            total=1800, sock_connect=60, sock_read=600
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self._headers) as response:
                    if response.status != HTTPStatus.OK:
                        error = await response.text()
                        raise RequestError(
                            f"Ошибка получения URL загрузки: {error}"
                        )

                    upload_data: dict = await response.json()
                    upload_url: str = upload_data.get("href")

                    if not upload_url:
                        raise RequestError("Не получен URL для загрузки")

                file_path = os.path.join(path, file_name)
                file_size = os.path.getsize(file_path)
                logger.info(
                    f"Начинаем загрузку {file_name} "
                    f"({file_size / 1024 / 1024:.2f} MB)"
                )

                async with aiofiles.open(file_path, 'rb') as f:
                    async with session.put(
                            upload_url,
                            data={"file": await f.read()},
                    ) as upload_response:
                        if upload_response.status not in (
                        HTTPStatus.OK, HTTPStatus.CREATED):
                            error = await upload_response.text()
                            raise RequestError(
                                f"Ошибка загрузки файла: {error}"
                            )
        except aiohttp.ClientError as e:
            raise RequestError(f"Сетевая ошибка: {str(e)}")

    async def upload_file(self, path: str, file_name: str) -> None:
        """
        Метод формирует url для загрузки файла, и отправляет непосредственно на
            сохранение.
        :param path: Путь к файлу.
        :param file_name: Имя файла для сохранения в облаке.
        """
        url: str = (f"{self.url}/upload?path={self.name_folder_cloud}/"
                    f"{file_name}&overwrite=False")
        await self._save(url, path, file_name)

    async def update_file(self, path: str, file_name: str) -> None:
        """
        Метод формирует url для перезаписи файла, и отправляет непосредственно
        на сохранение.

        :param path: Путь к файлу.
        :param file_name: Имя файла для сохранения в облаке.
        """
        url: str = (f"{self.url}/upload?path={self.name_folder_cloud}/"
                    f"{file_name}&overwrite=True")
        await self._save(url, path, file_name)

    async def delete_file(self, filename: str) -> None:
        """
        Метод для удаления файла в облаке.

        :param filename: Имя удаляемого файла.
        :raise RequestError: Если запрос завершился кодом отличным от 204,
            пробрасываем исключение.
        """
        url: str = (f"{self.url}?path={self.name_folder_cloud}/"
                    f"{filename}&force_async=False&permanently=False")

        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(60)
        ) as client:
            async with client.delete(
                    url=url, headers=self._headers) as response:
                        if response.status not in [
                            HTTPStatus.NO_CONTENT, HTTPStatus.ACCEPTED
                        ]:
                            raise RequestError(
                                f"Файл {filename} не был удален, "
                                f"{(await response.json()).get('message')}"
                            )

    async def get_info(self) -> Dict[str, float]:
        """
        Метод для получения списка файлов в облачной папке.

        :return dict: Возвращает словарь, где ключ имя файла, значение
            последнее изменение файла.
        :raise RequestError: Если запрос завершился кодом отличным от 200,
            пробрасываем исключение с указанием ошибки.
        """
        url: str = (f"{self.url}?path={self.name_folder_cloud}"
                    f"&fields=items&limit=10000&preview_crop=True")
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(60)
        ) as client:
            async with client.get(
                    url=url,
                    headers=self._headers
            ) as response:
                if response.status == HTTPStatus.OK:
                    files: dict = {}
                    for item in (await response.json())["_embedded"]["items"]:
                        files[item.get("name")] = dt.fromisoformat(
                            item.get("modified")
                        ).timestamp()
                    return files

                else:
                    raise RequestError(
                        f"{(await response.json()).get('message')}"
                    )

    async def is_exists_folder(self, folder) -> bool:
        url: str = f"{self.url}?path={self.name_folder_cloud}/{folder}"
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(60)
        ) as client:
            async with client.get(
                    url=url,
                    headers=self._headers
            ) as response:
                if response.status == HTTPStatus.OK:
                    return True
                return False

    async def create_folder(self, folder=None) -> None:
        """
        Метод для создания папки в облаке. Заодно и проверяем авторизацию.
        Если вернет код 401, то нужно проверить работоспособность токена.
        Если папка уже существует в облаке, то вернется код 409,
        но обрабатывать его нет смысла так как нас это устраивает.

        :raise AuthorizationError: Прокидываем, если не рабочий токен.
        :raise RequestError: Если запрос завершился кодом отличным от
            указанных.
        """
        url: str = (f"{self.url}?path={self.name_folder_cloud}"
                    f"{f"/{folder}"if folder else ''}")

        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(60)
        ) as client:
            async with client.put(
                    url=url,
                    headers=self._headers
            ) as response:

                if response.status == HTTPStatus.UNAUTHORIZED:
                    raise AuthorizationError(
                        f"{
                        (await response.json()).get('message')
                        } Проверьте ваш токен."
                    )

                elif response.status not in (
                        HTTPStatus.CREATED,
                        HTTPStatus.UNAUTHORIZED,
                        HTTPStatus.CONFLICT,
                ):
                    raise RequestError((await response.json()).get("message"))
