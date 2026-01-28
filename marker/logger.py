# Модуль конфигурации логирования для Marker
# Настраивает логгеры для основного приложения и зависимостей

import logging
import warnings

from marker.settings import settings


def configure_logging():
    """
    Настраивает систему логирования для Marker.
    Конфигурирует основной logger и устанавливает уровни для зависимостей.
    """
    # Получаем основной logger для marker
    logger = get_logger()

    # Добавляем handler только если его еще нет (избегаем дублирования)
    if not logger.handlers:
        # StreamHandler выводит логи в консоль (stdout/stderr)
        handler = logging.StreamHandler()
        # Форматтер определяет формат сообщений логов
        # Формат: "2024-01-01 12:00:00 [INFO] marker: Сообщение"
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Устанавливаем уровень логирования из настроек (по умолчанию INFO)
    logger.setLevel(settings.LOGLEVEL)

    # Игнорируем FutureWarning от библиотек (уменьшает шум в логах)
    warnings.simplefilter(action="ignore", category=FutureWarning)

    # Настраиваем уровни логирования для зависимых библиотек
    # Отключаем verbose логи от библиотек обработки изображений и шрифтов
    # PIL/Pillow - библиотека обработки изображений
    logging.getLogger("PIL").setLevel(logging.ERROR)
    # fontTools - работа со шрифтами
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
    logging.getLogger("fontTools.ttLib.ttFont").setLevel(logging.ERROR)
    # weasyprint - библиотека для рендеринга HTML в PDF
    logging.getLogger("weasyprint").setLevel(logging.CRITICAL)


def get_logger():
    """
    Возвращает logger для Marker.
    
    Возвращает:
        logging.Logger: Настроенный logger с именем "marker"
    """
    return logging.getLogger("marker")
