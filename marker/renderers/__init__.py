"""
Модуль базовых рендереров для преобразования документов в различные форматы.

Этот модуль предоставляет базовый класс BaseRenderer, который служит основой
для всех рендереров вывода (Markdown, HTML, JSON и др.). Рендереры преобразуют
внутреннее представление документа (Document с иерархией блоков) в финальные
форматы для пользователя.

Основные возможности:
- Извлечение и обработка изображений из документа
- Управление метаданными страниц и блоков
- Слияние последовательных HTML тегов для чистого вывода
- Гибкая конфигурация через Pydantic модели
- Поддержка различных режимов извлечения изображений (lowres/highres)
"""

import base64
import io
import re
from collections import Counter
from typing import Annotated, Optional, Tuple, Literal

from bs4 import BeautifulSoup
from pydantic import BaseModel

from marker.schema import BlockTypes
from marker.schema.blocks.base import BlockId, BlockOutput
from marker.schema.document import Document
from marker.settings import settings
from marker.util import assign_config


class BaseRenderer:
    """
    Базовый класс для всех рендереров.
    
    Предоставляет общую функциональность для преобразования внутреннего
    представления документа в различные выходные форматы. Все конкретные
    рендереры (Markdown, HTML, JSON и т.д.) наследуются от этого класса.
    
    Атрибуты:
        image_blocks: Типы блоков, которые считаются изображениями (Picture, Figure)
        extract_images: Извлекать ли изображения из документа
        image_extraction_mode: Режим извлечения изображений ("lowres" или "highres")
        keep_pageheader_in_output: Сохранять ли заголовки страниц в выводе
        keep_pagefooter_in_output: Сохранять ли подвалы страниц в выводе
        add_block_ids: Добавлять ли ID блоков в выходной HTML
    """
    image_blocks: Annotated[
        Tuple[BlockTypes, ...], "The block types to consider as images."
    ] = (BlockTypes.Picture, BlockTypes.Figure)
    extract_images: Annotated[bool, "Extract images from the document."] = True
    image_extraction_mode: Annotated[
        Literal["lowres", "highres"],
        "The mode to use for extracting images.",
    ] = "highres"
    keep_pageheader_in_output: Annotated[
        bool, "Keep the page header in the output HTML."
    ] = False
    keep_pagefooter_in_output: Annotated[
        bool, "Keep the page footer in the output HTML."
    ] = False
    add_block_ids: Annotated[bool, "Whether to add block IDs to the output HTML."] = (
        False
    )

    def __init__(self, config: Optional[BaseModel | dict] = None):
        """
        Инициализирует рендерер с заданной конфигурацией.
        
        Аргументы:
            config: Конфигурация в виде Pydantic модели или словаря
        """
        # Применяем конфигурацию к атрибутам класса
        assign_config(self, config)

        # Создаем конфигурацию блоков для передачи в document.render()
        self.block_config = {
            "keep_pageheader_in_output": self.keep_pageheader_in_output,
            "keep_pagefooter_in_output": self.keep_pagefooter_in_output,
            "add_block_ids": self.add_block_ids,
        }

    def __call__(self, document):
        """
        Рендерит документ в целевой формат.
        
        Этот метод должен быть переопределен в дочерних классах.
        
        Аргументы:
            document: Document для рендеринга
            
        Raises:
            NotImplementedError: Если метод не переопределен в дочернем классе
        """
        # Children are in reading order
        raise NotImplementedError

    def extract_image(self, document: Document, image_id, to_base64=False):
        """
        Извлекает изображение из документа по ID блока.
        
        Аргументы:
            document: Документ для извлечения изображения
            image_id: ID блока изображения
            to_base64: Конвертировать ли изображение в base64 строку
            
        Возвращает:
            PIL.Image или str: PIL изображение или base64 строка
        """
        # Получаем блок изображения
        image_block = document.get_block(image_id)
        # Извлекаем изображение в выбранном режиме качества
        cropped = image_block.get_image(
            document, highres=self.image_extraction_mode == "highres"
        )

        # Если нужен base64, конвертируем
        if to_base64:
            image_buffer = io.BytesIO()
            # Конвертируем RGBA в RGB если необходимо
            if not cropped.mode == "RGB":
                cropped = cropped.convert("RGB")

            # Сохраняем в буфер в заданном формате
            cropped.save(image_buffer, format=settings.OUTPUT_IMAGE_FORMAT)
            # Кодируем в base64
            cropped = base64.b64encode(image_buffer.getvalue()).decode(
                settings.OUTPUT_ENCODING
            )
        return cropped

    @staticmethod
    def merge_consecutive_math(html, tag="math"):
        """
        Сливает последовательные математические теги.
        
        Убирает дефисы между последовательными math тегами для правильного
        отображения разбитых формул.
        
        Аргументы:
            html: HTML строка для обработки
            tag: Имя тега для слияния (по умолчанию "math")
            
        Возвращает:
            str: Обработанный HTML
        """
        if not html:
            return html
        # Удаляем дефис между последовательными math тегами
        pattern = rf"-</{tag}>(\s*)<{tag}>"
        html = re.sub(pattern, " ", html)

        # То же для inline math тегов
        pattern = rf'-</{tag}>(\s*)<{tag} display="inline">'
        html = re.sub(pattern, " ", html)
        return html

    @staticmethod
    def merge_consecutive_tags(html, tag):
        """
        Сливает последовательные теги одного типа.
        
        Объединяет соседние теги (например, <b></b><b> -> <b>)
        для более чистого HTML вывода.
        
        Аргументы:
            html: HTML строка для обработки
            tag: Имя тега для слияния
            
        Возвращает:
            str: Обработанный HTML
        """
        if not html:
            return html

        def replace_whitespace(match):
            # Заменяем пробелы между тегами: оставляем один пробел или удаляем
            whitespace = match.group(1)
            if len(whitespace) == 0:
                return ""
            else:
                return " "

        pattern = rf"</{tag}>(\s*)<{tag}>"

        # Повторяем пока есть что сливать
        while True:
            new_merged = re.sub(pattern, replace_whitespace, html)
            if new_merged == html:
                break
            html = new_merged

        return html

    def generate_page_stats(self, document: Document, document_output):
        """
        Генерирует статистику по страницам документа.
        
        Собирает информацию о количестве блоков каждого типа на каждой странице
        и агрегированные метаданные блоков.
        
        Аргументы:
            document: Документ для анализа
            document_output: Вывод рендеринга документа
            
        Возвращает:
            list: Список словарей со статистикой по каждой странице
        """
        page_stats = []
        for page in document.pages:
            # Подсчитываем количество блоков каждого типа
            block_counts = Counter(
                [str(block.block_type) for block in page.children]
            ).most_common()
            # Получаем агрегированные метаданные блоков
            block_metadata = page.aggregate_block_metadata()
            page_stats.append(
                {
                    "page_id": page.page_id,
                    "text_extraction_method": page.text_extraction_method,
                    "block_counts": block_counts,
                    "block_metadata": block_metadata.model_dump(),
                }
            )
        return page_stats

    def generate_document_metadata(self, document: Document, document_output):
        """
        Генерирует метаданные документа для включения в вывод.
        
        Аргументы:
            document: Документ для анализа
            document_output: Вывод рендеринга документа
            
        Возвращает:
            dict: Метаданные документа (содержание, статистика страниц и т.д.)
        """
        metadata = {
            "table_of_contents": document.table_of_contents,
            "page_stats": self.generate_page_stats(document, document_output),
        }
        # Добавляем путь к debug данным если есть
        if document.debug_data_path is not None:
            metadata["debug_data_path"] = document.debug_data_path

        return metadata

    def extract_block_html(self, document: Document, block_output: BlockOutput):
        """
        Извлекает HTML из блока и его дочерних элементов.
        
        Рекурсивно обрабатывает content-ref теги, заменяя их на реальный контент
        или извлекая изображения в base64.
        
        Аргументы:
            document: Документ для извлечения данных
            block_output: Выходные данные блока для обработки
            
        Возвращает:
            tuple: (HTML строка, словарь изображений {block_id: base64_image})
        """
        # Парсим HTML блока
        soup = BeautifulSoup(block_output.html, "html.parser")

        # Находим все content-ref теги (ссылки на дочерние блоки)
        content_refs = soup.find_all("content-ref")
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get("src")
            sub_images = {}
            # Ищем соответствующий дочерний блок
            for item in block_output.children:
                if item.id == src:
                    # Рекурсивно извлекаем HTML дочернего блока
                    content, sub_images_ = self.extract_block_html(document, item)
                    sub_images.update(sub_images_)
                    ref_block_id: BlockId = item.id
                    break

            # Если это блок изображения, извлекаем изображение
            if ref_block_id.block_type in self.image_blocks and self.extract_images:
                images[ref_block_id] = self.extract_image(
                    document, ref_block_id, to_base64=True
                )
            else:
                # Иначе заменяем content-ref на реальный контент
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(content, "html.parser"))

        # Если сам блок является изображением, извлекаем его
        if block_output.id.block_type in self.image_blocks and self.extract_images:
            images[block_output.id] = self.extract_image(
                document, block_output.id, to_base64=True
            )

        return str(soup), images
