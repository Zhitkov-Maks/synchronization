import os
import sys

from requests import HTTPError


class AuthorizationError(HTTPError):
    pass


def check_sleep_period(period: str, logger) -> None:
    """
    Проверяем что в конфигурации указан правильный период времени,
    через который будет проходить синхронизация.

    :param period: Период который указан в файле dotenv.
    :param logger: Логгер для сохранения лога в файл.
    """
    if not period.isdigit():
        logger.error(
            "Неверно указан период синхронизации, это должно быть целое число(измерение в секундах)."
        )
        sys.exit(1)


def check_path_exists(path: str, logger) -> None:
    """
    Проверяем существует ли путь указанный в dotenv.
    Если нет, то завершаем работу приложения.

    :param path: Путь к папке, которую нужно синхронизировать.
    :param logger: Логгер для сохранения лога в файл.
    """
    check: bool = os.path.exists(path)
    if not check:
        logger.error(f"Указанный путь к {path} не существует. Введите корректный путь.")
        sys.exit(1)
