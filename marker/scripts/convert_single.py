"""
CLI скрипт для одиночной конвертации документов.

Упрощенный скрипт для конвертации одного документа в Markdown,
HTML или JSON без использования многопроцессорной обработки.
Подходит для обработки отдельных файлов или тестирования.

Автор: Marker Team
"""

import os

# Настройка переменных окружения для оптимизации производительности
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # Transformers использует .isin для простой операции, не поддерживаемой на MPS
)

import time
import click

from marker.config.parser import ConfigParser
from marker.config.printer import CustomClickPrinter
from marker.logger import configure_logging, get_logger
from marker.models import create_model_dict
from marker.output import save_output

# Настройка системы логирования
configure_logging()
logger = get_logger()


@click.command(cls=CustomClickPrinter, help="Конвертирует один PDF в markdown.")
@click.argument("fpath", type=str)
@ConfigParser.common_options
def convert_single_cli(fpath: str, **kwargs):
    """
    Основная функция для конвертации одного файла.
    
    Args:
        fpath (str): Путь к файлу для конвертации
        **kwargs: Дополнительные параметры из ConfigParser
    """
    # Создаем словарь моделей для обработки документов
    models = create_model_dict()
    start = time.time()
    
    # Инициализируем парсер конфигурации с дополнительными параметрами
    config_parser = ConfigParser(kwargs)

    # Получаем класс конвертера на основе типа входного файла
    converter_cls = config_parser.get_converter_cls()
    
    # Создаем экземпляр конвертера с настройками
    converter = converter_cls(
        config=config_parser.generate_config_dict(),  # Словарь конфигурации
        artifact_dict=models,  # Словарь моделей ИИ
        processor_list=config_parser.get_processors(),  # Список процессоров
        renderer=config_parser.get_renderer(),  # Рендерер для вывода
        llm_service=config_parser.get_llm_service(),  # LLM сервис для улучшений
    )
    
    # Выполняем конвертацию файла
    rendered = converter(fpath)
    
    # Определяем папку для сохранения результата
    out_folder = config_parser.get_output_folder(fpath)
    
    # Сохраняем результат конвертации
    save_output(rendered, out_folder, config_parser.get_base_filename(fpath))

    # Логируем информацию о сохранении и времени выполнения
    logger.info(f"Saved markdown to {out_folder}")
    logger.info(f"Total time: {time.time() - start}")
