# Модуль для определения структуры страниц (Layout Detection)
# Содержит LayoutBuilder - builder для анализа и структурирования макета страниц

from typing import Annotated, List

# Импорты из библиотеки Surya для работы с layout detection
from surya.layout import LayoutPredictor
from surya.layout.schema import LayoutResult, LayoutBox

# Локальные импорты
from marker.builders import BaseBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.settings import settings


class LayoutBuilder(BaseBuilder):
    """
    Builder для выполнения определения структуры (layout detection) на страницах PDF.
    
    Использует модели машинного обучения для анализа макета страниц и определения
    различных типов контента: текст, таблицы, рисунки, заголовки и т.д.
    Результаты интегрируются в структуру документа для дальнейшей обработки.
    
    Основные возможности:
    - Анализ структуры страниц с помощью ML моделей Surya
    - Определение границ различных типов контента
    - Интеграция результатов в документ
    - Поддержка принудительного назначения типов блоков
    - Расширение границ для определенных типов контента
    """
    
    # Настройки размера батча для модели layout
    layout_batch_size: Annotated[
        int,
        "Размер батча для использования в модели layout. По умолчанию None - используется размер по умолчанию модели.",
    ] = None
    
    # Принудительное назначение типа блока
    force_layout_block: Annotated[
        str,
        "Пропустить определение layout и принудительно обрабатывать каждую страницу как определенный тип блока.",
    ] = None
    
    # Отключение прогресс-баров
    disable_tqdm: Annotated[
        bool,
        "Отключить прогресс-бары tqdm.",
    ] = False
    
    # Типы блоков, для которых нужно расширять границы
    expand_block_types: Annotated[
        List[BlockTypes],
        "Типы блоков, границы которых должны быть расширены для учета недостающих регионов",
    ] = [
        BlockTypes.Picture,       # Рисунки
        BlockTypes.Figure,         # Диаграммы
        BlockTypes.ComplexRegion,  # Сложные области
    ]  # Не включает группы, так как они добавляются позже
    
    # Максимальная доля для расширения границ layout
    max_expand_frac: Annotated[
        float, 
        "Максимальная доля для расширения границ layout блоков"
    ] = 0.05

    def __init__(self, layout_model: LayoutPredictor, config=None):
        """
        Инициализирует LayoutBuilder с моделью определения структуры.
        
        Аргументы:
            layout_model: Обученная модель LayoutPredictor для анализа структуры страниц
            config: Опциональная конфигурация для настройки параметров builder
        """
        self.layout_model = layout_model
        super().__init__(config)