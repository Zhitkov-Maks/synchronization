import json
import os.path
from datetime import datetime as dt
from typing import Dict
from http import HTTPStatus

import requests

from util import AuthorizationError, RequestError


class YandexCloud:
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
        self._name_folder_cloud = name_folder_cloud
        self._headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
            "Authorization": f"OAuth {token}",
        }

    def _save(self, url: str, path: str, file_name: str, reload=False) -> None:
        """
        Метод для сохранения файла в облаке, нужен для методов load и reload,
        так как методы практически одинаковые.

        :param url: Сформированный url для загрузки файла.
        :param path: Путь к файлу на пк.
        :param file_name: Имя файла который нужно сохранить.
        :raise RequestError: Если запрос завершился кодом отличным от 200,
            пробрасываем исключение.
        """
        response = requests.get(url, headers=self._headers, timeout=30)
        if response.status_code == HTTPStatus.OK:
            data: json = response.json()
            path = os.path.join(path, file_name)
            with open(path, "rb") as file:
                requests.put(data["href"], files={"file": file}, timeout=60)
        else:
            save_or_reload = "перезаписан" if reload else "сохранен"
            raise RequestError(
                f"Файл: {file_name} не был {save_or_reload}, "
                f"{response.json().get('message')}"
            )

    def load(self, path: str, file_name: str) -> None:
        """
        Метод формирует url для загрузки файла, и отправляет непосредственно на
            сохранение.
        :param path: Путь к файлу.
        :param file_name: Имя файла для сохранения в облаке.
        """
        url: str = (f"{self.url}/upload?path={self._name_folder_cloud}/"
                    f"{file_name}&overwrite=False")
        self._save(url, path, file_name)

    def reload(self, path: str, file_name: str) -> None:
        """
        Метод формирует url для перезаписи файла, и отправляет непосредственно
        на сохранение.

        :param path: Путь к файлу.
        :param file_name: Имя файла для сохранения в облаке.
        """
        url = (f"{self.url}/upload?path={self._name_folder_cloud}/"
               f"{file_name}&overwrite=True")
        self._save(url, path, file_name, reload=True)

    def delete(self, filename: str) -> None:
        """
        Метод для удаления файла в облаке.

        :param filename: Имя удаляемого файла.
        :raise RequestError: Если запрос завершился кодом отличным от 204,
            пробрасываем исключение.
        """
        url: str = (f"{self.url}?path={self._name_folder_cloud}/"
                    f"{filename}&force_async=False&permanently=False")
        response = requests.delete(url, headers=self._headers, timeout=20)

        if response.status_code != HTTPStatus.NO_CONTENT:
            raise RequestError(
                f"Файл {filename} не был удален, "
                f"{response.json().get('message')}"
            )

    def get_info(self) -> Dict[str, float]:
        """
        Метод для получения списка файлов в облачной папке.

        :return dict: Возвращает словарь, где ключ имя файла, значение
            последнее изменение файла.
        :raise RequestError: Если запрос завершился кодом отличным от 200,
                пробрасываем исключение с указанием ошибки.
        """
        url: str = (f"{self.url}?path={self._name_folder_cloud}"
                    f"&fields=items&limit=10000&preview_crop=True")
        response = requests.get(url, headers=self._headers, timeout=30)

        if response.status_code == HTTPStatus.OK:
            files: dict = {}
            for item in response.json()["_embedded"]["items"]:
                files[item.get("name")] = dt.fromisoformat(
                    item.get("modified")
                ).timestamp()
            return files

        else:
            raise RequestError(f"{response.json().get('message')}")

    def create_folder_cloud(self) -> None:
        """
        Метод для создания папки в облаке. Заодно и проверяем авторизацию.
        Если вернет код 401, то нужно проверить работоспособность токена.
        Если папка уже существует в облаке, то вернется код 409,
        но обрабатывать его нет смысла так как нас это устраивает.

        :raise AuthorizationError: Прокидываем, если не рабочий токен.
        :raise RequestError: Если запрос завершился кодом отличным от
            указанных.
        """
        url = f"{self.url}?path={self._name_folder_cloud}"
        response = requests.put(url, headers=self._headers, timeout=30)

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise AuthorizationError(
                f"{response.json().get('message')} Проверьте ваш токен."
            )

        elif response.status_code not in (
                HTTPStatus.CREATED,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.CONFLICT,
        ):
            raise RequestError(response.json().get("message"))
