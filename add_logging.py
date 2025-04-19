from functools import wraps
import inspect
from pathlib import Path
import os
from typing import Callable
import time

from dotenv import load_dotenv
from loguru import logger

from util import RequestError


env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)
PATH_LOG_FILE = os.getenv('PATH_FILE_LOG')

logger.add(
    f"{PATH_LOG_FILE}/cloud.log",
    format="synchronization {time} {level} {message}",
    level="INFO",
    rotation="100 MB",
)


class LoggingMeta(type):
    """
    Метакласс, добавляющий детальное логирование вызовов методов.
    """

    def __new__(cls, name, bases, namespace):
        new_class = super().__new__(cls, name, bases, namespace)

        for attr_name, attr_value in namespace.items():
            if inspect.isfunction(attr_value) and not attr_name.startswith('_'):
                setattr(
                    new_class, attr_name, cls._add_enhanced_logging(attr_value)
                    )

        return new_class

    @staticmethod
    def _add_enhanced_logging(method: Callable) -> Callable:
        """
        Декоратор с расширенным логированием,
        включая информацию о файлах.
        """
        @wraps(method)
        async def async_wrapper(*args, **kwargs):
            # Получаем информацию о файле из аргументов
            file_name = ""
            is_name = ""

            if len(args) == 2:
                file_name = args[1]
                is_name = "File " if method.__name__.split("_")[-1] == "file" \
                    else ""

            elif len(args) == 3:
                file_name = args[2]
                is_name = "File " if method.__name__.split("_")[-1] == "file" \
                    else ""

            try:
                start_time = time.time()
                result = await method(*args, **kwargs)
                duration = time.time() - start_time

                logger.success(
                    f"Метод {method.__name__}() выполнен успешно. "
                    f"{is_name} - {file_name}. "
                    f"За время {duration:.2f} сек"
                )
                return result

            except RequestError as e:
                logger.error(
                    f"Ошибка в {method.__name__}(). "
                    f"{is_name} - {file_name}: {str(e)}"
                )

            except Exception as e:
                logger.critical(
                    f"Критическая ошибка в {method.__name__}(): "
                    f"{is_name} - {file_name}"
                    f"{type(e).__name__}: {str(e)}"
                )
                raise

        return async_wrapper
