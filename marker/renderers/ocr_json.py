"""
Модуль рендеринга OCR данных в JSON формат.

Предоставляет рендерер для преобразования низкоуровневых OCR данных
(символы, строки, страницы) в JSON формат с координатами. Используется
для получения детализированной информации об OCR распознавании.

Основные возможности:
- Сохранение иерархии Page -> Line -> Char
- Координаты polygon и bbox для каждого элемента
- Текст каждого символа
- HTML представление строк
- Исключение duplicate lines из уравнений
"""

from typing import Annotated, List, Tuple

from pydantic import BaseModel

from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.document import Document


class OCRJSONCharOutput(BaseModel):
    """
    Модель JSON представления символа OCR.
    
    Атрибуты:
        id: ID блока символа
        block_type: Тип блока (всегда "Char")
        text: Распознанный текст символа
        polygon: Координаты полигона символа
        bbox: Ограничивающий прямоугольник
    """
    id: str
    block_type: str
    text: str
    polygon: List[List[float]]
    bbox: List[float]


class OCRJSONLineOutput(BaseModel):
    """
    Модель JSON представления строки OCR.
    
    Атрибуты:
        id: ID блока строки
        block_type: Тип блока (обычно "Line" или "Equation")
        html: HTML представление строки
        polygon: Координаты полигона строки
        bbox: Ограничивающий прямоугольник
        children: Список символов (OCRJSONCharOutput)
    """
    id: str
    block_type: str
    html: str
    polygon: List[List[float]]
    bbox: List[float]
    children: List["OCRJSONCharOutput"] | None = None


class OCRJSONPageOutput(BaseModel):
    """
    Модель JSON представления страницы OCR.
    
    Атрибуты:
        id: ID блока страницы
        block_type: Тип блока (всегда "Page")
        polygon: Координаты полигона страницы
        bbox: Ограничивающий прямоугольник
        children: Список строк (OCRJSONLineOutput)
    """
    id: str
    block_type: str
    polygon: List[List[float]]
    bbox: List[float]
    children: List[OCRJSONLineOutput] | None = None


class OCRJSONOutput(BaseModel):
    """
    Модель выходных данных OCR JSON рендеринга.
    
    Атрибуты:
        children: Список страниц документа
        block_type: Тип корневого блока (всегда "Document")
        metadata: Метаданные (опционально)
    """
    children: List[OCRJSONPageOutput]
    block_type: str = str(BlockTypes.Document)
    metadata: dict | None = None


class OCRJSONRenderer(BaseRenderer):
    """
    Рендерер для преобразования OCR данных в JSON формат.
    
    Извлекает детальные OCR данные на уровне символов, строк и страниц.
    Полезно для анализа качества OCR и постобработки.
    
    Атрибуты:
        image_blocks: Типы блоков изображений (не используется в OCR режиме)
        page_blocks: Типы блоков страниц
    """

    image_blocks: Annotated[
        Tuple[BlockTypes],
        "The list of block types to consider as images.",
    ] = (BlockTypes.Picture, BlockTypes.Figure)
    page_blocks: Annotated[
        Tuple[BlockTypes],
        "The list of block types to consider as pages.",
    ] = (BlockTypes.Page,)

    def extract_json(self, document: Document) -> List[OCRJSONPageOutput]:
        """
        Извлекает OCR JSON данные из документа.
        
        Обрабатывает каждую страницу, извлекая строки и символы.
        Исключает дубликаты строк из уравнений (они уже включены в Equation блоки).
        
        Аргументы:
            document: Документ для извлечения OCR данных
            
        Возвращает:
            List[OCRJSONPageOutput]: Список страниц с OCR данными
        """
        pages = []
        # Обрабатываем каждую страницу документа
        for page in document.pages:
            page_equations = [
                b for b in page.children if b.block_type == BlockTypes.Equation
                and not b.removed
            ]
            equation_lines = []
            for equation in page_equations:
                if not equation.structure:
                    continue

                equation_lines += [
                    line
                    for line in equation.structure
                    if line.block_type == BlockTypes.Line
                ]

            page_lines = [
                block
                for block in page.children
                if block.block_type == BlockTypes.Line
                and block.id not in equation_lines
                and not block.removed
            ]

            lines = []
            for line in page_lines + page_equations:
                line_obj = OCRJSONLineOutput(
                    id=str(line.id),
                    block_type=str(line.block_type),
                    html="",
                    polygon=line.polygon.polygon,
                    bbox=line.polygon.bbox,
                )
                if line in page_equations:
                    line_obj.html = line.html
                else:
                    line_obj.html = line.formatted_text(document)
                    spans = (
                        [document.get_block(span_id) for span_id in line.structure]
                        if line.structure
                        else []
                    )
                    children = []
                    for span in spans:
                        if not span.structure:
                            continue

                        span_chars = [
                            document.get_block(char_id) for char_id in span.structure
                        ]
                        children.extend(
                            [
                                OCRJSONCharOutput(
                                    id=str(char.id),
                                    block_type=str(char.block_type),
                                    text=char.text,
                                    polygon=char.polygon.polygon,
                                    bbox=char.polygon.bbox,
                                )
                                for char in span_chars
                            ]
                        )
                    line_obj.children = children
                lines.append(line_obj)

            page = OCRJSONPageOutput(
                id=str(page.id),
                block_type=str(page.block_type),
                polygon=page.polygon.polygon,
                bbox=page.polygon.bbox,
                children=lines,
            )
            pages.append(page)

        return pages

    def __call__(self, document: Document) -> OCRJSONOutput:
        """
        Рендерит документ в OCR JSON формат.
        
        Аргументы:
            document: Document для рендеринга
            
        Возвращает:
            OCRJSONOutput: Объект с OCR данными
        """
        return OCRJSONOutput(children=self.extract_json(document), metadata=None)
