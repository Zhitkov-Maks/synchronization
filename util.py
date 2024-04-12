import os
import sys

from requests import RequestException


class AuthorizationError(RequestException):
    pass


class RequestError(RequestException):
    pass


def check_sleep_period(period: str, logger) -> None:
    """
    Проверяем что в конфигурации указан правильный период времени(целое число),
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


def func_error_logging(name: str, args: tuple, logger) -> None:
    """
    Функция для записи лога об ошибке в зависимости от типа
    операции(удаление, сохранение, перезапись).

    :param name: Имя функции.
    :param args: Кортеж с аргументами переданными в функцию, нужен для получения имени файла.
    :param logger: Логгер для записи логов.
    """
    if name == "cloud_load" and len(args) == 3:
        logger.error(
            f"Файл {args[-1]} не был сохранен. Проверьте соединение с интернетом."
        )

    elif name == "cloud_load" and len(args) == 4:
        logger.error(
            f"Файл {args[-2]} не был перезаписан. Проверьте соединение с интернетом."
        )

    elif name == "delete_file":
        logger.error(
            f"Файл {args[-1]} не был удален. Проверьте соединение с интернетом."
        )
