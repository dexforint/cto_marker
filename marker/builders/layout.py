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

    def __init__(self, layout_model: LayoutPredictor, config=None):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        if self.force_layout_block is not None:
            # Assign the full content of every page to a single layout type
            layout_results = self.forced_layout(document.pages)
        else:
            layout_results = self.surya_layout(document.pages)
        self.add_blocks_to_pages(document.pages, layout_results)
        self.expand_layout_blocks(document)

    def get_batch_size(self):
        if self.layout_batch_size is not None:
            return self.layout_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 12
        return 6

    def forced_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        layout_results = []
        for page in pages:
            layout_results.append(
                LayoutResult(
                    image_bbox=page.polygon.bbox,
                    bboxes=[
                        LayoutBox(
                            label=self.force_layout_block,
                            position=0,
                            top_k={self.force_layout_block: 1},
                            polygon=page.polygon.polygon,
                        ),
                    ],
                    sliced=False,
                )
            )
        return layout_results

    def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        self.layout_model.disable_tqdm = self.disable_tqdm
        layout_results = self.layout_model(
            [p.get_image(highres=False) for p in pages],
            batch_size=int(self.get_batch_size()),
        )
        return layout_results

    def expand_layout_blocks(self, document: Document):
        for page in document.pages:
            # Collect all blocks on this page as PolygonBox for easy access
            page_blocks = [document.get_block(bid) for bid in page.structure]
            page_size = page.polygon.size

            for block_id in page.structure:
                block = document.get_block(block_id)
                if block.block_type in self.expand_block_types:
                    other_blocks = [b for b in page_blocks if b != block]
                    if not other_blocks:
                        block.polygon = block.polygon.expand(
                            self.max_expand_frac, self.max_expand_frac
                        ).fit_to_bounds((0, 0, *page_size))
                        continue

                    min_gap = min(
                        block.polygon.minimum_gap(other.polygon)
                        for other in other_blocks
                    )
                    if min_gap <= 0:
                        continue

                    x_expand_frac = (
                        min_gap / block.polygon.width if block.polygon.width > 0 else 0
                    )
                    y_expand_frac = (
                        min_gap / block.polygon.height
                        if block.polygon.height > 0
                        else 0
                    )

                    block.polygon = block.polygon.expand(
                        min(self.max_expand_frac, x_expand_frac),
                        min(self.max_expand_frac, y_expand_frac),
                    ).fit_to_bounds((0, 0, *page_size))

    def add_blocks_to_pages(
        self, pages: List[PageGroup], layout_results: List[LayoutResult]
    ):
        for page, layout_result in zip(pages, layout_results):
            layout_page_size = PolygonBox.from_bbox(layout_result.image_bbox).size
            provider_page_size = page.polygon.size
            page.layout_sliced = (
                layout_result.sliced
            )  # This indicates if the page was sliced by the layout model
            for bbox in sorted(layout_result.bboxes, key=lambda x: x.position):
                block_cls = get_block_class(BlockTypes[bbox.label])
                layout_block = page.add_block(
                    block_cls, PolygonBox(polygon=bbox.polygon)
                )
                layout_block.polygon = layout_block.polygon.rescale(
                    layout_page_size, provider_page_size
                ).fit_to_bounds((0, 0, *provider_page_size))
                layout_block.top_k = {
                    BlockTypes[label]: prob
                    for (label, prob) in bbox.top_k.items()
                    if label in BlockTypes.__members__
                }
                page.add_structure(layout_block)

            # Ensure page has non-empty structure
            if page.structure is None:
                page.structure = []

            # Ensure page has non-empty children
            if page.children is None:
                page.children = []        
