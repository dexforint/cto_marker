# Модуль для распознавания текста (OCR)
# Содержит OcrBuilder - builder для выполнения OCR и интеграции результатов в документ

import copy
from typing import Annotated, List

from ftfy import fix_text
from PIL import Image
from surya.common.surya.schema import TaskNames
from surya.recognition import RecognitionPredictor, OCRResult, TextChar

# Локальные импорты
from marker.builders import BaseBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.schema.blocks.base import Block
from marker.schema.document import Document
from marker.schema.groups import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text.char import Char
from marker.schema.text.line import Line
from marker.schema.text.span import Span
from marker.settings import settings
from marker.schema.polygon import PolygonBox
from marker.util import get_opening_tag_type, get_closing_tag_type


class OcrBuilder(BaseBuilder):
    """
    Builder для выполнения OCR (Optical Character Recognition) на страницах PDF.
    
    Использует модели машинного обучения для распознавания текста из изображений
    и интеграции распознанного текста в структуру документа. Поддерживает
    различные форматы текста и теги форматирования.
    
    Основные возможности:
    - Распознавание текста из изображений страниц
    - Поддержка различных языков и шрифтов
    - Обработка тегов форматирования (математика, курсив, жирный)
    - Интеграция результатов в иерархию Char -> Span -> Line
    - Исправление текста и нормализация кодировки
    """