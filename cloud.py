from abc import ABC, abstractmethod


class Cloud(ABC):

    def __init__(self, token: str, name_folder_cloud: str):
        self.name_folder_cloud = name_folder_cloud
        self._token = token

    @abstractmethod
    async def upload_file(self, path: str, file_name: str) -> None:
        """
        Загрузка файла в облако. Если все прошло успешно,
        то ничего не возвращается, если запрос завершился неудачно
        пробрасывается ошибка.
        :raises RequestError: С описанием ошибки.
        """
        pass

    @abstractmethod
    async def update_file(self, path: str, file_name: str) -> None:
        """
        Обновление файла в облаке. Если все прошло успешно,
        то ничего не возвращается, если запрос завершился неудачно
        пробрасывается ошибка.
        :raises RequestError: С описанием ошибки.
        """
        pass

    @abstractmethod
    async def delete_file(self, filename: str) -> None:
        """
        Удаление файла в облаке.
        :raises RequestError: С описанием ошибки.
        """
        pass

    @abstractmethod
    async def get_info(self) -> dict[str, float]:
        """
        Получение информации о синхронизируемой папке. То есть
        какие файлы и папки содержаться и дата последнего изменения.
        :returns dict: Словарь с именем файла и датой изменения файла.
        :raises RequestError: С описанием ошибки.
        """
        pass

    @abstractmethod
    async def is_exists_folder(self, folder: str) -> bool:
        """
        Проверка существования папки. Возвращает True или False.
        :returns True: Если папка существует.
        """
        pass

    @abstractmethod
    async def create_folder(self, folder: str = None) -> None:
        """
        Запрос на создание папки в облаке.
        :raises RequestError: С описанием ошибки.
        """
        pass
