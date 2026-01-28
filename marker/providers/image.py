"""
Провайдер для обработки изображений (PNG, JPG и других форматов).

Модуль предоставляет ImageProvider, который обрабатывает изображения
как документы, создавая виртуальные страницы и строки для последующей
обработки OCR и другими компонентами системы.

Автор: Marker Team
"""

from typing import List, Annotated
from PIL import Image

from marker.providers import ProviderPageLines, BaseProvider
from marker.schema.polygon import PolygonBox
from marker.schema.text import Line
from pdftext.schema import Reference


class ImageProvider(BaseProvider):
    """
    Провайдер для обработки изображений как документов.
    
    Позволяет обрабатывать изображения (PNG, JPG, GIF, etc.) как страницы
    документов, создавая виртуальные строки и поддерживая тот же интерфейс,
    что и другие провайдеры документов.
    
    Атрибуты:
        page_range (List[int]): Диапазон страниц для обработки
        image_count (int): Количество изображений/страниц (всегда 1 для изображений)
    """
    # Диапазон страниц для обработки (по умолчанию все страницы)
    page_range: Annotated[
        List[int],
        "Диапазон страниц для обработки.",
        "По умолчанию None, что означает обработку всех страниц.",
    ] = None

    # Количество изображений/страниц (всегда 1 для обычных изображений)
    image_count: int = 1

    def __init__(self, filepath: str, config=None):
        """
        Инициализация провайдера изображений.
        
        Args:
            filepath (str): Путь к файлу изображения
            config: Конфигурация провайдера (опционально)
        """
        # Вызываем конструктор родительского класса
        super().__init__(filepath, config)

        # Открываем и сохраняем изображение
        self.images = [Image.open(filepath)]
        # Инициализируем словарь для хранения строк страниц
        self.page_lines: ProviderPageLines = {i: [] for i in range(self.image_count)}

        # Если диапазон страниц не указан, обрабатываем все страницы
        if self.page_range is None:
            self.page_range = range(self.image_count)

        # Проверяем корректность диапазона страниц
        assert max(self.page_range) < self.image_count and min(self.page_range) >= 0, (
            f"Invalid page range, values must be between 0 and {len(self.doc) - 1}.  Min of provided page range is {min(self.page_range)} and max is {max(self.page_range)}."
        )

        # Создаем ограничивающие прямоугольники для каждой страницы
        # Используем размеры изображения как границы страницы
        self.page_bboxes = {
            i: [0, 0, self.images[i].size[0], self.images[i].size[1]]
            for i in self.page_range
        }

    def __len__(self):
        """
        Возвращает количество страниц в изображении.
        
        Returns:
            int: Количество страниц (всегда 1 для изображений)
        """
        return self.image_count

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        """
        Возвращает изображения по списку индексов.
        
        Args:
            idxs (List[int]): Список индексов страниц для получения
            dpi (int): Разрешение (игнорируется для изображений)
            
        Returns:
            List[Image.Image]: Список изображений PIL
        """
        return [self.images[i] for i in idxs]

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        """
        Возвращает ограничивающий прямоугольник страницы.
        
        Args:
            idx (int): Индекс страницы
            
        Returns:
            PolygonBox | None: Ограничивающий прямоугольник страницы
        """
        bbox = self.page_bboxes[idx]
        if bbox:
            return PolygonBox.from_bbox(bbox)

    def get_page_lines(self, idx: int) -> List[Line]:
        """
        Возвращает список строк на указанной странице.
        
        Args:
            idx (int): Индекс страницы
            
        Returns:
            List[Line]: Список строк страницы (пустой для изображений)
        """
        return self.page_lines[idx]

    def get_page_refs(self, idx: int) -> List[Reference]:
        """
        Возвращает список ссылок на указанной странице.
        
        Args:
            idx (int): Индекс страницы
            
        Returns:
            List[Reference]: Пустой список (в изображениях нет ссылок)
        """
        return []
