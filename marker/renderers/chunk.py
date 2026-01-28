"""
Модуль рендеринга документов в chunked (плоский) формат.

Предоставляет рендерер для преобразования иерархического документа в плоский
список блоков с собранным HTML. Удобно для RAG систем и чанкинга текста.

Основные возможности:
- Плоский список блоков (без вложенной иерархии)
- Собранный HTML для каждого блока
- Информация о странице для каждого блока
- Встроенные изображения
- Метаданные страниц и документа
"""

import html
from typing import List, Dict

from bs4 import BeautifulSoup
from pydantic import BaseModel

from marker.renderers.json import JSONRenderer, JSONBlockOutput
from marker.schema.document import Document


class FlatBlockOutput(BaseModel):
    """
    Модель плоского представления блока.
    
    Атрибуты:
        id: ID блока
        block_type: Тип блока
        html: Полностью собранный HTML блока (с дочерними элементами)
        page: Номер страницы
        polygon: Координаты полигона
        bbox: Ограничивающий прямоугольник
        section_hierarchy: Иерархия секций
        images: Словарь изображений в base64
    """
    id: str
    block_type: str
    html: str
    page: int
    polygon: List[List[float]]
    bbox: List[float]
    section_hierarchy: Dict[int, str] | None = None
    images: dict | None = None


class ChunkOutput(BaseModel):
    """
    Модель выходных данных chunk рендеринга.
    
    Атрибуты:
        blocks: Плоский список блоков
        page_info: Информация о страницах {page_id: {bbox, polygon}}
        metadata: Метаданные документа
    """
    blocks: List[FlatBlockOutput]
    page_info: Dict[int, dict]
    metadata: dict

def collect_images(block: JSONBlockOutput) -> dict[str, str]:
    """
    Рекурсивно собирает все изображения из блока и его дочерних элементов.
    
    Аргументы:
        block: JSONBlockOutput блок для обработки
        
    Возвращает:
        dict: Словарь всех изображений {block_id: base64_image}
    """
    # Листовой блок - возвращаем его изображения
    if not getattr(block, "children", None):
        return block.images or {}
    else:
        # Контейнерный блок - собираем изображения рекурсивно
        images = block.images or {}
        for child_block in block.children:
            images.update(collect_images(child_block))
        return images

def assemble_html_with_images(block: JSONBlockOutput, image_blocks: set[str]) -> str:
    """
    Собирает полный HTML блока, заменяя content-ref на реальный контент.
    
    Рекурсивно обрабатывает дочерние блоки и вставляет их HTML в родительский.
    Для блоков изображений добавляет <img> теги.
    
    Аргументы:
        block: JSONBlockOutput блок для обработки
        image_blocks: Множество типов блоков которые являются изображениями
        
    Возвращает:
        str: Полностью собранный HTML
    """
    # Листовой блок
    if not getattr(block, "children", None):
        # Для изображений добавляем img тег
        if block.block_type in image_blocks:
            return f"<p>{block.html}<img src='{block.id}'></p>"
        else:
            return block.html

    # Контейнерный блок - рекурсивно собираем HTML дочерних блоков
    child_html = [assemble_html_with_images(child, image_blocks) for child in block.children]
    child_ids = [child.id for child in block.children]

    # Парсим HTML блока и заменяем content-ref на реальный контент
    soup = BeautifulSoup(block.html, "html.parser")
    content_refs = soup.find_all("content-ref")
    for ref in content_refs:
        src_id = ref.attrs["src"]
        if src_id in child_ids:
            ref.replace_with(child_html[child_ids.index(src_id)])

    # Возвращаем HTML с декодированными entities
    return html.unescape(str(soup))

def json_to_chunks(
    block: JSONBlockOutput, image_blocks: set[str], page_id: int=0) -> FlatBlockOutput | List[FlatBlockOutput]:
    """
    Преобразует иерархический JSON блок в плоский формат.
    
    Для блоков Page рекурсивно обрабатывает дочерние блоки.
    Для остальных блоков создает FlatBlockOutput с собранным HTML.
    
    Аргументы:
        block: JSONBlockOutput блок для преобразования
        image_blocks: Множество типов блоков изображений
        page_id: ID текущей страницы
        
    Возвращает:
        FlatBlockOutput или список FlatBlockOutput
    """
    # Блок Page - рекурсивно обрабатываем детей
    if block.block_type == "Page":
        children = block.children
        # Извлекаем page_id из строки ID
        page_id = int(block.id.split("/")[-1])
        return [json_to_chunks(child, image_blocks, page_id=page_id) for child in children]
    else:
        # Обычный блок - создаем плоское представление
        return FlatBlockOutput(
            id=block.id,
            block_type=block.block_type,
            html=assemble_html_with_images(block, image_blocks),  # Собираем полный HTML
            page=page_id,
            polygon=block.polygon,
            bbox=block.bbox,
            section_hierarchy=block.section_hierarchy,
            images=collect_images(block),  # Собираем все изображения
        )


class ChunkRenderer(JSONRenderer):
    """
    Рендерер для преобразования документов в chunked (плоский) формат.
    
    Наследуется от JSONRenderer и преобразует иерархический JSON
    в плоский список блоков. Удобно для RAG систем и текстового чанкинга.
    """

    def __call__(self, document: Document) -> ChunkOutput:
        """
        Рендерит документ в chunked формат.
        
        Аргументы:
            document: Document для рендеринга
            
        Возвращает:
            ChunkOutput: Объект с плоским списком блоков и метаданными
        """
        # Рендерим документ в BlockOutput структуру
        document_output = document.render(self.block_config)
        # Извлекаем JSON для каждой страницы
        json_output = []
        for page_output in document_output.children:
            json_output.append(self.extract_json(document, page_output))

        # Преобразуем иерархический JSON в плоский список блоков верхнего уровня
        chunk_output = []
        for item in json_output:
            # Конвертируем блок страницы в chunks
            chunks = json_to_chunks(item, set([str(block) for block in self.image_blocks]))
            chunk_output.extend(chunks)

        # Собираем информацию о страницах (bbox и polygon)
        page_info = {
            page.page_id: {"bbox": page.polygon.bbox, "polygon": page.polygon.polygon}
            for page in document.pages
        }

        # Возвращаем результат
        return ChunkOutput(
            blocks=chunk_output,
            page_info=page_info,
            metadata=self.generate_document_metadata(document, document_output),
        )
