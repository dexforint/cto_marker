# Модуль для создания линий и текстовых блоков
# Содержит LineBuilder - builder для детекции и создания текстовых строк

from copy import deepcopy
from typing import Annotated, List, Tuple

import numpy as np
from PIL import Image
import cv2

# Импорты из Surya для детекции и OCR ошибок
from surya.detection import DetectionPredictor
from surya.ocr_error import OCRErrorPredictor

# Локальные импорты
from marker.builders import BaseBuilder
from marker.providers import ProviderOutput, ProviderPageLines
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.settings import settings
from marker.util import matrix_intersection_area, sort_text_lines
from marker.utils.image import is_blank_image


class LineBuilder(BaseBuilder):
    """
    Builder для детекции текстовых строк и их объединения с исходными данными.
    
    Отвечает за обнаружение и создание текстовых строк на основе результатов
    детекции и существующих данных провайдера. Выполняет объединение найденных
    строк с исходными элементами PDF и их дальнейшую обработку.
    
    Основные возможности:
    - Детекция текстовых строк с помощью ML моделей
    - Объединение результатов детекции с исходными данными
    - Создание структурированных объектов Line
    - Обработка пустых страниц и фильтрация результатов
    - Интеграция с системой оценки качества OCR
    """