"""
Реестр и фабрика провайдеров для автоматического определения типа файла.

Модуль отвечает за:
- Сопоставление типов файлов с соответствующими провайдерами
- Определение типа файла по расширению и содержимому
- Предоставление фабричных функций для создания провайдеров
- Поддержка множества форматов: PDF, изображения, документы, таблицы, презентации, HTML, EPUB

Автор: Marker Team
"""

import filetype
import filetype.match as file_match
from bs4 import BeautifulSoup
from filetype.types import archive, document, IMAGE

from marker.providers.document import DocumentProvider
from marker.providers.epub import EpubProvider
from marker.providers.html import HTMLProvider
from marker.providers.image import ImageProvider
from marker.providers.pdf import PdfProvider
from marker.providers.powerpoint import PowerPointProvider
from marker.providers.spreadsheet import SpreadSheetProvider

# Словарь соответствий типов документов и их обработчиков
# Ключ: строка типа документа, Значение: список классов-обработчиков из библиотеки filetype
DOCTYPE_MATCHERS = {
    # Обработчики для изображений (PNG, JPG, GIF, BMP, WebP, etc.)
    "image": IMAGE,
    # Обработчики для PDF документов
    "pdf": [
        archive.Pdf,
    ],
    # Обработчики для EPUB книг
    "epub": [
        archive.Epub,
    ],
    # Обработчики для документов (DOCX, ODT)
    "doc": [document.Docx],
    # Обработчики для электронных таблиц (XLSX, XLS)
    "xls": [document.Xlsx],
    # Обработчики для презентаций (PPTX)
    "ppt": [document.Pptx],
}


def load_matchers(doctype: str):
    """
    Загружает список обработчиков для указанного типа документа.
    
    Args:
        doctype (str): Тип документа ("image", "pdf", "epub", "doc", "xls", "ppt")
        
    Returns:
        list: Список экземпляров классов-обработчиков для библиотеки filetype
    """
    return [cls() for cls in DOCTYPE_MATCHERS[doctype]]


def load_extensions(doctype: str):
    """
    Возвращает список расширений файлов для указанного типа документа.
    
    Args:
        doctype (str): Тип документа ("image", "pdf", "epub", "doc", "xls", "ppt")
        
    Returns:
        list: Список строк с расширениями файлов
    """
    return [cls.EXTENSION for cls in DOCTYPE_MATCHERS[doctype]]


def provider_from_ext(filepath: str):
    """
    Определяет провайдера на основе расширения файла.
    
    Анализирует расширение файла и возвращает соответствующий класс провайдера.
    Используется как быстрый метод определения типа файла без чтения содержимого.
    
    Args:
        filepath (str): Путь к файлу
        
    Returns:
        type: Класс провайдера для данного типа файла
    """
    # Извлекаем расширение файла (все символы после последней точки)
    ext = filepath.rsplit(".", 1)[-1].strip()
    
    # Если расширение отсутствует или пустое, используем PDF провайдер по умолчанию
    if not ext:
        return PdfProvider

    # Проверяем соответствие расширения типу "изображение" и возвращаем ImageProvider
    if ext in load_extensions("image"):
        return ImageProvider
    # Проверяем соответствие расширения типу "PDF" и возвращаем PdfProvider
    if ext in load_extensions("pdf"):
        return PdfProvider
    # Проверяем соответствие расширения типу "документ" и возвращаем DocumentProvider
    if ext in load_extensions("doc"):
        return DocumentProvider
    # Проверяем соответствие расширения типу "таблица" и возвращаем SpreadSheetProvider
    if ext in load_extensions("xls"):
        return SpreadSheetProvider
    # Проверяем соответствие расширения типу "презентация" и возвращаем PowerPointProvider
    if ext in load_extensions("ppt"):
        return PowerPointProvider
    # Проверяем соответствие расширения типу "EPUB" и возвращаем EpubProvider
    if ext in load_extensions("epub"):
        return EpubProvider
    # Особый случай для HTML файлов
    if ext in ["html"]:
        return HTMLProvider

    # Если тип файла не распознан, возвращаем PDF провайдер как fallback
    return PdfProvider


def provider_from_filepath(filepath: str):
    """
    Определяет провайдера на основе анализа содержимого файла.
    
    Анализирует магические числа и структуру файла для точного определения типа.
    Более надежный метод определения типа файла, чем анализ расширения.
    
    Args:
        filepath (str): Путь к файлу
        
    Returns:
        type: Класс провайдера для данного типа файла
    """
    # Проверяем, является ли файл изображением по его содержимому
    if filetype.image_match(filepath) is not None:
        return ImageProvider
    # Проверяем, является ли файл PDF документом
    if file_match(filepath, load_matchers("pdf")) is not None:
        return PdfProvider
    # Проверяем, является ли файл EPUB книгой
    if file_match(filepath, load_matchers("epub")) is not None:
        return EpubProvider
    # Проверяем, является ли файл документом (DOCX, ODT)
    if file_match(filepath, load_matchers("doc")) is not None:
        return DocumentProvider
    # Проверяем, является ли файл электронной таблицей (XLSX, XLS)
    if file_match(filepath, load_matchers("xls")) is not None:
        return SpreadSheetProvider
    # Проверяем, является ли файл презентацией (PPTX)
    if file_match(filepath, load_matchers("ppt")) is not None:
        return PowerPointProvider

    # Попытка определить HTML файл по его содержимому
    try:
        # Открываем файл как текст с кодировкой UTF-8
        with open(filepath, "r", encoding="utf-8") as f:
            # Парсим содержимое с помощью BeautifulSoup
            soup = BeautifulSoup(f.read(), "html.parser")
            # Проверяем, есть ли HTML теги в содержимом
            if bool(soup.find()):
                return HTMLProvider
    except Exception:
        # Если чтение файла не удалось, игнорируем ошибку
        pass

    # Fallback: если не удалось определить тип файла,
    # используем метод определения по расширению
    return provider_from_ext(filepath)
