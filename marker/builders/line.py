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
    
    # Модель детекции для обнаружения текстовых строк
    detection_model: Annotated[
        DetectionPredictor,
        "Модель детекции для обнаружения текстовых строк в изображениях"
    ]
    
    # Модель для оценки качества OCR результатов
    ocr_error_model: Annotated[
        OCRErrorPredictor,
        "Модель для определения качества OCR результатов и обнаружения ошибок"
    ]
    
    # Размер батча для детекции
    batch_size: Annotated[
        int,
        "Размер батча для использования в модели детекции"
    ] = 16
    
    # Порог для определения плохого OCR
    bad_ocr_threshold: Annotated[
        float,
        "Порог для определения плохого OCR. Если confidence меньше этого значения, считается плохим OCR"
    ] = 0.7
    
    # Отключение прогресс-баров
    disable_tqdm: Annotated[
        bool,
        "Отключить прогресс-бары tqdm"
    ] = False

    def __init__(self, detection_model: DetectionPredictor, ocr_error_model: OCRErrorPredictor, config=None):
        """
        Инициализирует LineBuilder с моделями детекции и OCR error detection.
        
        Аргументы:
            detection_model: Модель для детекции текстовых строк
            ocr_error_model: Модель для оценки качества OCR результатов
            config: Опциональная конфигурация для настройки параметров builder
        """
        self.detection_model = detection_model
        self.ocr_error_model = ocr_error_model
        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        """
        Выполняет детекцию линий и их интеграцию в документ.
        
        Основной метод builder'а, который:
        1. Запускает детекцию текстовых строк на страницах
        2. Объединяет найденные строки с исходными данными PDF
        3. Создает структурированные объекты Line
        4. Добавляет их в документ
        
        Аргументы:
            document: Документ для добавления обнаруженных линий
            provider: Провайдер с исходными данными PDF
        """
        # Получаем результаты детекции строк
        detection_results = self.detection_lines(document.pages, provider)
        
        # Создаем линии из результатов детекции и объединяем с исходными данными
        self.create_lines_from_detection(document, provider, detection_results)

    def get_batch_size(self):
        """
        Определяет размер батча для детекции в зависимости от настроек и устройства.
        
        Возвращает:
            int: Размер батча для модели детекции
        """
        if settings.TORCH_DEVICE_MODEL == "cuda":
            return min(self.batch_size, 12)  # Ограничиваем для CUDA
        return min(self.batch_size, 6)      # Ограничиваем для CPU

    def detection_lines(self, pages: List[PageGroup], provider: PdfProvider):
        """
        Выполняет детекцию текстовых строк на всех страницах.
        
        Использует модель детекции для обнаружения границ текстовых строк
        на изображениях страниц с учетом настроек батча и прогресс-баров.
        
        Аргументы:
            pages: Список групп страниц для обработки
            provider: Провайдер с исходными данными
        
        Возвращает:
            List[DetectionResult]: Результаты детекции для каждой страницы
        """
        # Настраиваем модель детекции
        self.detection_model.disable_tqdm = self.disable_tqdm
        
        # Получаем изображения низкого разрешения для детекции
        images = [p.get_image(highres=False) for p in pages]
        
        # Запускаем детекцию с оптимальным размером батча
        detection_results = self.detection_model(
            images, 
            batch_size=int(self.get_batch_size())
        )
        
        return detection_results

    def create_lines_from_detection(self, document: Document, provider: PdfProvider, detection_results):
        """
        Создает структурированные объекты Line из результатов детекции.
        
        Объединяет найденные в детекции строки с исходными элементами PDF,
        создает структурированные объекты Line и добавляет их в документ.
        
        Аргументы:
            document: Документ для добавления созданных линий
            provider: Провайдер с исходными данными
            detection_results: Результаты детекции строк
        """
        for page, page_detection in zip(document.pages, detection_results):
            if not page_detection.text_lines:
                continue  # Пропускаем страницы без обнаруженных строк
                
            # Сортируем строки по вертикальной позиции для правильного порядка
            sorted_lines = sort_text_lines(page_detection.text_lines)
            
            # Создаем Line объекты для каждой обнаруженной строки
            for line_bbox in sorted_lines:
                # Проверяем, что изображение не пустое
                line_image = self.extract_line_image(page.get_image(highres=False), line_bbox.bbox)
                if is_blank_image(line_image):
                    continue
                    
                # Создаем объект Line
                LineClass = get_block_class(BlockTypes.Line)
                line_polygon = PolygonBox.from_bbox(line_bbox.bbox)
                line = LineClass(polygon=line_polygon)
                
                # Обновляем размер линии под размер страницы
                page_size = page.polygon.size
                layout_page_size = PolygonBox.from_bbox(page_detection.image_bbox).size
                line.polygon = line.polygon.rescale(layout_page_size, page_size)
                
                # Находим пересечения с исходными элементами PDF
                self.match_lines_with_provider_elements(line, page, provider)
                
                # Добавляем строку в структуру страницы
                page.add_structure(line)

    def extract_line_image(self, page_image: Image.Image, bbox: Tuple[int, int, int, int]) -> Image.Image:
        """
        Извлекает изображение линии из страницы по ограничивающему прямоугольнику.
        
        Вырезает область изображения, соответствующую найденной строке,
        для дальнейшей обработки (например, определения качества OCR).
        
        Аргументы:
            page_image: Полное изображение страницы
            bbox: Ограничивающий прямоугольник строки (x1, y1, x2, y2)
        
        Возвращает:
            Image.Image: Изображение вырезанной линии
        """
        x1, y1, x2, y2 = bbox
        # Добавляем небольшие отступы для лучшего захвата текста
        padding = 2
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(page_image.width, x2 + padding)
        y2 = min(page_image.height, y2 + padding)
        
        return page_image.crop((x1, y1, x2, y2))

    def match_lines_with_provider_elements(self, line: Line, page: PageGroup, provider: PdfProvider):
        """
        Сопоставляет обнаруженные линии с исходными элементами PDF.
        
        Находит пересечения между обнаруженными линиями и текстовыми
        элементами в исходном PDF, чтобы связать их и сохранить
        оригинальные атрибуты (шрифт, размер, стиль).
        
        Аргументы:
            line: Создаваемая линия для связывания
            page: Страница документа
            provider: Провайдер с исходными данными PDF
        """
        # Получаем элементы страницы из провайдера
        page_lines = provider.page_lines
        
        # Инициализируем структуру для хранения ссылок
        if line.structure is None:
            line.structure = []
            
        # Ищем пересечения с исходными элементами
        for provider_line_idx, provider_line in enumerate(page_lines):
            if matrix_intersection_area(line.polygon.bbox, provider_line.polygon.bbox) > 0:
                # Найдено пересечение, добавляем ссылку на исходный элемент
                provider_line_id = f"/page/{page.page_id}/Line/{provider_line_idx}"
                line.structure.append(provider_line_id)
                
                # Если есть текст в исходном элементе, копируем его
                if hasattr(provider_line, 'text') and provider_line.text:
                    line.text = provider_line.text

    def ocr_error_detection(self, pages: List[PageGroup], page_lines: List[ProviderPageLines]):
        """
        Выполняет обнаружение ошибок OCR с помощью модели машинного обучения.
        
        Использует специальную модель для оценки качества распознанного текста
        и определения строк с потенциальными ошибками OCR. Это позволяет
        в дальнейшем повторно обработать проблемные области.
        
        Аргументы:
            pages: Список групп страниц для анализа
            page_lines: Список исходных текстовых элементов от провайдера
        
        Возвращает:
            OCRErrorResults: Результаты анализа качества OCR с метками и confidence scores
        """
        # Подготавливаем изображения для анализа
        images = []
        line_image_map = []
        
        for page, provider_lines in zip(pages, page_lines):
            page_image = page.get_image(highres=False)
            
            for provider_line in provider_lines:
                # Извлекаем изображение строки
                line_image = self.extract_line_image(page_image, provider_line.polygon.bbox)
                images.append(line_image)
                line_image_map.append((page, provider_line))
        
        if not images:
            return []  # Нет данных для анализа
            
        # Запускаем модель определения ошибок OCR
        self.ocr_error_model.disable_tqdm = self.disable_tqdm
        error_results = self.ocr_error_model(images, batch_size=int(self.get_batch_size()))
        
        return error_results

    def filter_bad_ocr_lines(self, pages: List[PageGroup], page_lines: List[ProviderPageLines]):
        """
        Фильтрует строки с плохим качеством OCR на основе результатов анализа.
        
        Использует результаты ocr_error_detection для удаления или повторной
        обработки строк с низким качеством распознавания. Это улучшает
        общее качество итогового документа.
        
        Аргументы:
            pages: Список групп страниц для фильтрации
            page_lines: Список исходных текстовых элементов
        
        Возвращает:
            Tuple[List[List[ProviderPageLines]], List[List[str]]]: 
                Отфильтрованные строки и метки качества для каждой страницы
        """
        # Получаем результаты анализа ошибок
        error_results = self.ocr_error_detection(pages, page_lines)
        
        filtered_lines = []
        quality_labels = []
        
        for page_idx, (page, page_provider_lines) in enumerate(zip(pages, page_lines)):
            page_filtered = []
            page_labels = []
            
            for line_idx, provider_line in enumerate(page_provider_lines):
                # Определяем индекс в общих результатах
                result_idx = sum(len(p.lines) for p in page_lines[:page_idx]) + line_idx
                
                if result_idx < len(error_results):
                    # Получаем confidence для этой строки
                    confidence = error_results[result_idx].confidence
                    label = "good" if confidence >= self.bad_ocr_threshold else "bad"
                    
                    # Добавляем только хорошие строки
                    if label == "good":
                        page_filtered.append(provider_line)
                    
                    page_labels.append(label)
                else:
                    # Если нет результата, считаем строкой хорошего качества
                    page_filtered.append(provider_line)
                    page_labels.append("unknown")
            
            filtered_lines.append(page_filtered)
            quality_labels.append(page_labels)
        
        return filtered_lines, quality_labels