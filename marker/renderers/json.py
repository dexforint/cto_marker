"""
Модуль рендеринга документов в иерархический JSON формат.

Предоставляет рендерер для преобразования внутреннего представления документа
в JSON формат с сохранением иерархии блоков. Включает координаты полигонов,
bbox, section hierarchy и изображения в base64.

Основные возможности:
- Сохранение полной иерархии блоков документа
- Координаты и bbox для каждого блока
- Section hierarchy для навигации по документу
- Встроенные изображения в base64
- Метаданные документа и страниц
"""

from typing import Annotated, Dict, List, Tuple

from pydantic import BaseModel

from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput
from marker.schema.document import Document
from marker.schema.registry import get_block_class


class JSONBlockOutput(BaseModel):
    """
    Модель JSON представления блока.
    
    Атрибуты:
        id: Строковый ID блока
        block_type: Тип блока (Page, Text, Table и т.д.)
        html: HTML содержимое блока
        polygon: Координаты полигона блока [[x1,y1], [x2,y2], ...]
        bbox: Ограничивающий прямоугольник [x1, y1, x2, y2]
        children: Список дочерних блоков (для контейнерных блоков)
        section_hierarchy: Иерархия секций для навигации {level: heading}
        images: Словарь изображений в base64 {block_id: base64_string}
    """
    id: str
    block_type: str
    html: str
    polygon: List[List[float]]
    bbox: List[float]
    children: List["JSONBlockOutput"] | None = None
    section_hierarchy: Dict[int, str] | None = None
    images: dict | None = None


class JSONOutput(BaseModel):
    """
    Модель выходных данных JSON рендеринга.
    
    Атрибуты:
        children: Список страниц (JSONBlockOutput) документа
        block_type: Тип корневого блока (всегда "Document")
        metadata: Метаданные документа
    """
    children: List[JSONBlockOutput]
    block_type: str = str(BlockTypes.Document)
    metadata: dict


def reformat_section_hierarchy(section_hierarchy):
    """
    Реформатирует section hierarchy для JSON сериализации.
    
    Конвертирует значения в строки для совместимости с JSON.
    
    Аргументы:
        section_hierarchy: Словарь section hierarchy
        
    Возвращает:
        dict: Реформатированный словарь со строковыми значениями
    """
    new_section_hierarchy = {}
    for key, value in section_hierarchy.items():
        new_section_hierarchy[key] = str(value)
    return new_section_hierarchy


class JSONRenderer(BaseRenderer):
    """
    Рендерер для преобразования документов в JSON формат.
    
    Создает иерархическое JSON представление документа с полными данными
    о каждом блоке (координаты, тип, содержимое, изображения).
    
    Атрибуты:
        image_blocks: Типы блоков, которые считаются изображениями
        page_blocks: Типы блоков, которые считаются страницами
    """

    image_blocks: Annotated[
        Tuple[BlockTypes],
        "The list of block types to consider as images.",
    ] = (BlockTypes.Picture, BlockTypes.Figure)
    page_blocks: Annotated[
        Tuple[BlockTypes],
        "The list of block types to consider as pages.",
    ] = (BlockTypes.Page,)

    def extract_json(self, document: Document, block_output: BlockOutput):
        """
        Рекурсивно извлекает JSON представление блока.
        
        Для листовых блоков (наследников Block) извлекает HTML и изображения.
        Для контейнерных блоков рекурсивно обрабатывает дочерние блоки.
        
        Аргументы:
            document: Документ для извлечения данных
            block_output: Выходные данные блока для обработки
            
        Возвращает:
            JSONBlockOutput: JSON представление блока
        """
        # Получаем класс блока
        cls = get_block_class(block_output.id.block_type)
        # Листовой блок (прямой наследник Block)
        if cls.__base__ == Block:
            # Извлекаем HTML и изображения
            html, images = self.extract_block_html(document, block_output)
            return JSONBlockOutput(
                html=html,
                polygon=block_output.polygon.polygon,
                bbox=block_output.polygon.bbox,
                id=str(block_output.id),
                block_type=str(block_output.id.block_type),
                images=images,
                section_hierarchy=reformat_section_hierarchy(
                    block_output.section_hierarchy
                ),
            )
        else:
            # Контейнерный блок - рекурсивно обрабатываем детей
            children = []
            for child in block_output.children:
                child_output = self.extract_json(document, child)
                children.append(child_output)

            return JSONBlockOutput(
                html=block_output.html,
                polygon=block_output.polygon.polygon,
                bbox=block_output.polygon.bbox,
                id=str(block_output.id),
                block_type=str(block_output.id.block_type),
                children=children,
                section_hierarchy=reformat_section_hierarchy(
                    block_output.section_hierarchy
                ),
            )

    def __call__(self, document: Document) -> JSONOutput:
        """
        Рендерит документ в JSON формат.
        
        Аргументы:
            document: Document для рендеринга
            
        Возвращает:
            JSONOutput: Объект с JSON данными и метаданными
        """
        # Рендерим документ в BlockOutput структуру
        document_output = document.render(self.block_config)
        # Извлекаем JSON для каждой страницы
        json_output = []
        for page_output in document_output.children:
            json_output.append(self.extract_json(document, page_output))
        # Возвращаем результат с метаданными
        return JSONOutput(
            children=json_output,
            metadata=self.generate_document_metadata(document, document_output),
        )
