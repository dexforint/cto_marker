"""marker.config.parser

Парсер конфигурации из аргументов командной строки.

Этот модуль связывает CLI (Click) и внутреннюю конфигурацию Marker:
- объявляет «общие» опции (output_dir, output_format, processors и т. п.);
- преобразует значения опций в единый словарь конфигурации, который затем
  передаётся конвертеру/процессорам/рендерерам;
- обеспечивает обратную совместимость для некоторых ключей.

Принцип: код здесь не выполняет конвертацию документов, а только переводит
пользовательские параметры CLI в формат, понятный остальной части системы.
"""

# Стандартная библиотека: работа с JSON и путями.
import json
import os
from typing import Dict

# Сторонняя библиотека: Click используется для построения CLI.
import click

# Локальные импорты: конвертер по умолчанию, рендереры и вспомогательные функции.
from marker.converters.pdf import PdfConverter
from marker.logger import get_logger
from marker.renderers.chunk import ChunkRenderer
from marker.renderers.html import HTMLRenderer
from marker.renderers.json import JSONRenderer
from marker.renderers.markdown import MarkdownRenderer
from marker.settings import settings
from marker.util import classes_to_strings, parse_range_str, strings_to_classes

# Логгер проекта (единый стиль логирования Marker).
logger = get_logger()


class ConfigParser:
    """Утилита для преобразования CLI-опций в конфигурацию Marker.

    Экземпляр хранит словарь, который Click передаёт в обработчик команды, и
    предоставляет методы для:
    - построения итогового словаря конфигурации (`generate_config_dict`);
    - выбора класса конвертера и списка процессоров;
    - выбора рендера и вычисления выходных путей.

    Атрибуты:
        cli_options: Словарь опций, полученных из Click.
    """

    def __init__(self, cli_options: dict):
        """Сохраняет CLI-опции для дальнейшей обработки.

        Аргументы:
            cli_options: Словарь опций (обычно результат работы Click).

        Возвращает:
            None
        """

        # Сохраняем все параметры CLI как есть — преобразования делаем отдельными методами.
        self.cli_options = cli_options

    @staticmethod
    def common_options(fn):
        """Декоратор-помощник: добавляет к Click-команде общий набор опций.

        Click «накручивает» опции как декораторы. Здесь мы централизуем перечень
        параметров, чтобы использовать его в разных CLI-командах.

        Аргументы:
            fn: Исходная функция-обработчик Click-команды.

        Возвращает:
            Обёрнутую функцию `fn` с добавленными Click-опциями.
        """

        # Папка для сохранения результатов.
        fn = click.option(
            "--output_dir",
            type=click.Path(exists=False),
            required=False,
            default=settings.OUTPUT_DIR,
            help="Directory to save output.",
        )(fn)

        # Включение режима отладки.
        fn = click.option("--debug", "-d", is_flag=True, help="Enable debug mode.")(fn)

        # Выбор формата вывода.
        fn = click.option(
            "--output_format",
            type=click.Choice(["markdown", "json", "html", "chunks"]),
            default="markdown",
            help="Format to output results in.",
        )(fn)

        # Явное указание списка процессоров.
        fn = click.option(
            "--processors",
            type=str,
            default=None,
            help="Comma separated list of processors to use.  Must use full module path.",
        )(fn)

        # Дополнительная конфигурация через внешний JSON-файл.
        fn = click.option(
            "--config_json",
            type=str,
            default=None,
            help="Path to JSON file with additional configuration.",
        )(fn)

        # Отключение multiprocessing (полезно для дебага/ограниченных сред).
        fn = click.option(
            "--disable_multiprocessing",
            is_flag=True,
            default=False,
            help="Disable multiprocessing.",
        )(fn)

        # Отключение извлечения изображений из документа.
        fn = click.option(
            "--disable_image_extraction",
            is_flag=True,
            default=False,
            help="Disable image extraction.",
        )(fn)

        # Опции, которые требуют трансформации (например, строка диапазона страниц -> список).
        fn = click.option(
            "--page_range",
            type=str,
            default=None,
            help="Page range to convert, specify comma separated page numbers or ranges.  Example: 0,5-10,20",
        )(fn)

        # Конвертер можно переопределить (по умолчанию используется PDF-конвертер).
        fn = click.option(
            "--converter_cls",
            type=str,
            default=None,
            help="Converter class to use.  Defaults to PDF converter.",
        )(fn)

        # Переопределение сервиса LLM (например, другой провайдер).
        fn = click.option(
            "--llm_service",
            type=str,
            default=None,
            help="LLM service to use - should be full import path, like marker.services.gemini.GoogleGeminiService",
        )(fn)

        return fn

    def generate_config_dict(self) -> Dict[str, any]:
        """Формирует итоговый словарь конфигурации на основе CLI-опций.

        Метод выполняет «склейку» разрозненных CLI-флагов в ключи конфигурации,
        которые ожидают нижележащие компоненты (конвертеры, билдеры, процессоры).

        Аргументы:
            Нет (используются `self.cli_options`).

        Возвращает:
            Словарь конфигурации Marker.
        """

        # Итоговая конфигурация, которую мы будем наполнять.
        config = {}

        # output_dir нужен, например, для debug_data_folder.
        output_dir = self.cli_options.get("output_dir", settings.OUTPUT_DIR)

        # Пробегаемся по всем CLI-опциям.
        for k, v in self.cli_options.items():
            # Пустые/ложные значения не переносим в конфиг.
            if not v:
                continue

            # Специальная обработка некоторых ключей.
            match k:
                case "debug":
                    # В режиме debug включаем несколько разных видов отладочных артефактов.
                    config["debug_pdf_images"] = True
                    config["debug_layout_images"] = True
                    config["debug_json"] = True
                    config["debug_data_folder"] = output_dir
                case "page_range":
                    # Преобразуем строку диапазона в структуру, понятную конвертеру.
                    config["page_range"] = parse_range_str(v)
                case "config_json":
                    # Подмешиваем внешний JSON в общий конфиг.
                    with open(v, "r", encoding="utf-8") as f:
                        config.update(json.load(f))
                case "disable_multiprocessing":
                    # Отключая multiprocessing, уменьшаем число воркеров до 1.
                    config["pdftext_workers"] = 1
                case "disable_image_extraction":
                    # Флагом запрещаем извлечение изображений.
                    config["extract_images"] = False
                case _:
                    # Все остальные ключи переносим как есть.
                    config[k] = v

        # Обратная совместимость: исторически ключ был google_api_key.
        if settings.GOOGLE_API_KEY:
            config["gemini_api_key"] = settings.GOOGLE_API_KEY

        return config

    def get_llm_service(self):
        """Возвращает путь/класс сервиса LLM, если режим LLM включён.

        Логика:
        - если `use_llm` не включён, возвращаем None (не создаём сервис);
        - иначе берём `llm_service` из CLI или используем дефолтный сервис Gemini.

        Возвращает:
            Строку с import-path сервиса или None.
        """

        # Возвращаем сервис только если включена обработка с LLM.
        if not self.cli_options.get("use_llm", False):
            return None

        # Явный сервис из CLI, если задан.
        service_cls = self.cli_options.get("llm_service", None)

        # Если пользователь не указал сервис, используем дефолтный.
        if service_cls is None:
            service_cls = "marker.services.gemini.GoogleGeminiService"

        return service_cls

    def get_renderer(self):
        """Выбирает рендерер по значению `output_format`.

        Возвращает:
            Строку (import-path) класса рендерера.

        Raises:
            ValueError: если указан неизвестный формат.
        """

        # Выбираем класс рендерера по формату.
        match self.cli_options["output_format"]:
            case "json":
                r = JSONRenderer
            case "markdown":
                r = MarkdownRenderer
            case "html":
                r = HTMLRenderer
            case "chunks":
                r = ChunkRenderer
            case _:
                raise ValueError("Invalid output format")

        # Конвертируем класс в строку import-path, чтобы конфиг был сериализуемым.
        return classes_to_strings([r])[0]

    def get_processors(self):
        """Возвращает список процессоров (как строки import-path), если он задан.

        Метод также выполняет валидацию: пытается импортировать каждый процессор,
        чтобы заранее поймать ошибку конфигурации.

        Возвращает:
            Список строковых путей к процессорам или None.

        Raises:
            Exception: если один из процессоров не удаётся импортировать.
        """

        # Достаём значение из CLI.
        processors = self.cli_options.get("processors", None)

        # Если список задан, он приходит строкой «a,b,c».
        if processors is not None:
            processors = processors.split(",")

            # Проверяем, что каждый путь импортируем.
            for p in processors:
                try:
                    strings_to_classes([p])
                except Exception as e:
                    logger.error(f"Error loading processor: {p} with error: {e}")
                    raise

        return processors

    def get_converter_cls(self):
        """Возвращает класс конвертера, указанный в CLI, либо PdfConverter по умолчанию.

        Возвращает:
            Класс конвертера.

        Raises:
            Exception: если указанная строка не может быть преобразована в класс.
        """

        # Путь к классу конвертера (если пользователь явно указал).
        converter_cls = self.cli_options.get("converter_cls", None)

        if converter_cls is not None:
            try:
                return strings_to_classes([converter_cls])[0]
            except Exception as e:
                logger.error(
                    f"Error loading converter: {converter_cls} with error: {e}"
                )
                raise

        # По умолчанию используем PDF-конвертер.
        return PdfConverter

    def get_output_folder(self, filepath: str):
        """Создаёт (при необходимости) и возвращает папку для результата конкретного файла.

        Логика:
        - берём базовую директорию output_dir;
        - создаём подпапку по имени исходного файла (без расширения);
        - гарантируем существование директории.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Путь к директории, куда следует сохранять результаты конвертации.
        """

        # Базовая папка вывода.
        output_dir = self.cli_options.get("output_dir", settings.OUTPUT_DIR)

        # Имя файла без расширения используем как имя подпапки.
        fname_base = os.path.splitext(os.path.basename(filepath))[0]
        output_dir = os.path.join(output_dir, fname_base)

        # Создаём директорию, если её нет.
        os.makedirs(output_dir, exist_ok=True)

        return output_dir

    def get_base_filename(self, filepath: str):
        """Возвращает базовое имя файла (без расширения).

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Имя файла без расширения.
        """

        # Отрезаем директорию.
        basename = os.path.basename(filepath)

        # Отрезаем расширение.
        return os.path.splitext(basename)[0]
