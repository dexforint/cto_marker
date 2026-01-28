# Модуль для создания документов из исходных файлов
# Содержит DocumentBuilder - основной builder для создания структурированного документа

from typing import Annotated

# Локальные импорты - все builders и схемы
from marker.builders import BaseBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class


class DocumentBuilder(BaseBuilder):
    """
    Основной builder для создания структурированного документа.
    
    Отвечает за создание полного документа из исходного PDF файла с использованием
    различных специализированных builders. Выполняет последовательное построение:
    1. Создание базовой структуры документа
    2. Определение layout (структуры страницы)
    3. Построение линий и блоков текста
    4. Выполнение OCR (опционально)
    
    Аргументы:
        config: Конфигурация builder
    """
    
    # Настройки DPI для изображений разного разрешения
    lowres_image_dpi: Annotated[
        int,
        "Настройка DPI для низкоразрешающих изображений страниц, используемых для определения layout и линий.",
    ] = 96
    
    highres_image_dpi: Annotated[
        int,
        "Настройка DPI для высокоразрешающих изображений страниц, используемых для OCR.",
    ] = 192
    
    # Флаг для отключения OCR
    disable_ocr: Annotated[
        bool,
        "Отключить обработку OCR.",
    ] = False

    def __call__(self, provider: PdfProvider, layout_builder: LayoutBuilder, line_builder: LineBuilder, ocr_builder: OcrBuilder):
        """
        Основной метод построения документа.
        
        Выполняет полный цикл создания документа от исходного PDF до
        структурированного представления с OCR результатами.
        
        Аргументы:
            provider: Провайдер для работы с исходным PDF файлом
            layout_builder: Builder для определения структуры страниц
            line_builder: Builder для создания линий и текстовых блоков
            ocr_builder: Builder для распознавания текста
        
        Возвращает:
            Document: Полностью структурированный документ
        """
        # Создаем базовую структуру документа из provider
        document = self.build_document(provider)
        
        # Определяем layout (структуру) каждой страницы
        layout_builder(document, provider)
        
        # Строим линии и текстовые блоки
        line_builder(document, provider)
        
        # Выполняем OCR если не отключен
        if not self.disable_ocr:
            ocr_builder(document, provider)
        
        return document

    def build_document(self, provider: PdfProvider):
        """
        Создает базовую структуру документа из PDF провайдера.
        
        Инициализирует документ с набором страниц, каждая из которых содержит:
        - Изображения низкого и высокого разрешения
        - Координаты страницы (polygon)
        - Ссылки на исходные элементы (refs)
        
        Аргументы:
            provider: Провайдер PDF для извлечения данных
        
        Возвращает:
            Document: Базовый документ с инициализированными страницами
        """
        # Получаем класс для создания групп страниц
        PageGroupClass: PageGroup = get_block_class(BlockTypes.Page)
        
        # Извлекаем изображения низкого разрешения для layout анализа
        lowres_images = provider.get_images(provider.page_range, self.lowres_image_dpi)
        
        # Извлекаем изображения высокого разрешения для OCR
        highres_images = provider.get_images(provider.page_range, self.highres_image_dpi)
        
        # Создаем начальные страницы с полным набором данных
        initial_pages = [
            PageGroupClass(
                page_id=p,                          # Уникальный ID страницы
                lowres_image=lowres_images[i],      # Изображение для layout анализа
                highres_image=highres_images[i],    # Изображение для OCR
                polygon=provider.get_page_bbox(p),   # Координаты границ страницы
                refs=provider.get_page_refs(p)       # Ссылки на исходные элементы PDF
            ) for i, p in enumerate(provider.page_range)
        ]
        
        # Получаем класс документа и создаем экземпляр
        DocumentClass: Document = get_block_class(BlockTypes.Document)
        return DocumentClass(filepath=provider.filepath, pages=initial_pages)