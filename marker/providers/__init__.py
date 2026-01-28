"""
Модуль providers - провайдеры для работы с различными форматами исходных документов.

Данный модуль содержит базовые классы и типы данных для всех провайдеров,
которые отвечают за извлечение содержимого из различных форматов файлов
(PDF, изображения, документы, таблицы, презентации, HTML, EPUB).

Провайдеры обеспечивают единообразный интерфейс для работы с разными типами
исходных документов, предоставляя методы для получения текста, изображений,
геометрической информации и других метаданных.

Автор: Marker Team
"""

from copy import deepcopy
from typing import List, Optional, Dict

from PIL import Image
from pydantic import BaseModel

from pdftext.schema import Reference

from marker.logger import configure_logging
from marker.schema.polygon import PolygonBox
from marker.schema.text import Span
from marker.schema.text.char import Char
from marker.schema.text.line import Line
from marker.settings import settings
from marker.util import assign_config

# Инициализация системы логирования для модуля
configure_logging()


class ProviderOutput(BaseModel):
    """
    Базовый класс для вывода данных провайдера.
    
    Содержит результат обработки одной строки документа с метаданными
    о тексте, геометрическом положении и символах.
    
    Атрибуты:
        line (Line): Объект строки с геометрической информацией
        spans (List[Span]): Список текстовых фрагментов (спанов) в строке
        chars (Optional[List[List[Char]]]): Детализированные символы строки (опционально)
    """
    line: Line
    spans: List[Span]
    chars: Optional[List[List[Char]]] = None

    @property
    def raw_text(self):
        """
        Возвращает сырой текст без форматирования, объединяя все спанов.
        
        Returns:
            str: Объединенный текст всех спанов в строке
        """
        return "".join(span.text for span in self.spans)

    def __hash__(self):
        """
        Вычисляет хеш объекта на основе ограничивающего прямоугольника строки.
        
        Returns:
            int: Хеш объекта для использования в множествах и словарях
        """
        return hash(tuple(self.line.polygon.bbox))

    def merge(self, other: "ProviderOutput"):
        """
        Объединяет текущий объект с другим объектом ProviderOutput.
        
        Создает новый объект, содержащий все спанов и символы из обоих объектов,
        а также объединяет их геометрические области.
        
        Args:
            other (ProviderOutput): Другой объект для объединения
            
        Returns:
            ProviderOutput: Новый объект с объединенными данными
        """
        new_output = deepcopy(self)
        other_copy = deepcopy(other)

        # Объединяем списки текстовых фрагментов
        new_output.spans.extend(other_copy.spans)
        
        # Объединяем символы, если они присутствуют в обоих объектах
        if new_output.chars is not None and other_copy.chars is not None:
            new_output.chars.extend(other_copy.chars)
        elif other_copy.chars is not None:
            new_output.chars = other_copy.chars

        # Объединяем геометрические области строк
        new_output.line.polygon = new_output.line.polygon.merge(
            [other_copy.line.polygon]
        )
        return new_output


# Словарь для хранения строк всех страниц документа: номер_страницы -> список_объектов_провайдера
ProviderPageLines = Dict[int, List[ProviderOutput]]


class BaseProvider:
    """
    Базовый класс для всех провайдеров документов.
    
    Определяет единый интерфейс для работы с различными форматами файлов.
    Все конкретные провайдеры (PDF, изображения, документы и т.д.) должны
    наследоваться от этого класса и реализовывать его абстрактные методы.
    
    Атрибуты:
        filepath (str): Путь к обрабатываемому файлу
    """
    def __init__(self, filepath: str, config: Optional[BaseModel | dict] = None):
        """
        Инициализация базового провайдера.
        
        Args:
            filepath (str): Путь к файлу для обработки
            config (Optional[BaseModel | dict]): Конфигурация провайдера (опционально)
        """
        assign_config(self, config)  # Присваиваем конфигурацию объекту
        self.filepath = filepath  # Сохраняем путь к файлу

    def __len__(self):
        """
        Возвращает количество страниц в документе.
        
        Returns:
            int: Количество страниц
        """
        pass

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        """
        Извлекает изображения с указанных страниц.
        
        Args:
            idxs (List[int]): Список номеров страниц для извлечения изображений
            dpi (int): Разрешение изображений в точках на дюйм
            
        Returns:
            List[Image.Image]: Список изображений PIL
        """
        pass

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        """
        Возвращает ограничивающий прямоугольник страницы.
        
        Args:
            idx (int): Номер страницы (начиная с 0)
            
        Returns:
            PolygonBox | None: Геометрические границы страницы или None
        """
        pass

    def get_page_lines(self, idx: int) -> List[Line]:
        """
        Возвращает список строк на указанной странице.
        
        Args:
            idx (int): Номер страницы (начиная с 0)
            
        Returns:
            List[Line]: Список объектов Line, представляющих строки страницы
        """
        pass

    def get_page_refs(self, idx: int) -> List[Reference]:
        """
        Возвращает список ссылок на указанной странице.
        
        Args:
            idx (int): Номер страницы (начиная с 0)
            
        Returns:
            List[Reference]: Список объектов Reference на странице
        """
        pass

    def __enter__(self):
        """
        Поддержка контекстного менеджера (with statement).
        
        Returns:
            BaseProvider: Возвращает себя для использования в with-блоках
        """
        return self

    @staticmethod
    def get_font_css():
        """
        Генерирует CSS для корректного отображения шрифтов в HTML.
        
        Использует настройки шрифтов из конфигурации приложения для
        создания CSS-стилей с подключением шрифта GoNotoCurrent.
        
        Returns:
            CSS: Объект CSS для библиотеки WeasyPrint
        """
        from weasyprint import CSS
        from weasyprint.text.fonts import FontConfiguration

        # Создаем конфигурацию шрифтов
        font_config = FontConfiguration()
        
        # Генерируем CSS с настройками шрифта и отображения текста
        css = CSS(
            string=f"""
            @font-face {{
                font-family: GoNotoCurrent-Regular;
                src: url({settings.FONT_PATH});
                font-display: swap;
            }}
            body {{
                font-family: {settings.FONT_NAME.split(".")[0]}, sans-serif;
                font-variant-ligatures: none;
                font-feature-settings: "liga" 0;
                text-rendering: optimizeLegibility;
            }}
            """,
            font_config=font_config,
        )
        return css
