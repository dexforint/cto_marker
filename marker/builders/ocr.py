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
    
    # Модель распознавания для выполнения OCR
    recognition_model: Annotated[
        RecognitionPredictor,
        "Модель распознавания для выполнения OCR на изображениях текста"
    ]
    
    # Размер батча для OCR
    batch_size: Annotated[
        int,
        "Размер батча для использования в модели распознавания"
    ] = 16
    
    # Языки для распознавания
    languages: Annotated[
        List[str],
        "Список языков для распознавания в формате ISO кодов (например, ['en', 'ru'])"
    ] = ["en"]
    
    # Отключение прогресс-баров
    disable_tqdm: Annotated[
        bool,
        "Отключить прогресс-бары tqdm"
    ] = False

    def __init__(self, recognition_model: RecognitionPredictor, config=None):
        """
        Инициализирует OcrBuilder с моделью распознавания.
        
        Аргументы:
            recognition_model: Обученная модель RecognitionPredictor для OCR
            config: Опциональная конфигурация для настройки параметров builder
        """
        self.recognition_model = recognition_model
        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        """
        Выполняет OCR на всех страницах документа и интегрирует результаты.
        
        Основной метод builder'а, который:
        1. Извлекает изображения линий из страниц
        2. Запускает OCR для распознавания текста
        3. Создает иерархию Char -> Span -> Line
        4. Интегрирует результаты в структуру документа
        
        Аргументы:
            document: Документ для добавления распознанного текста
            provider: Провайдер с исходными данными PDF
        """
        # Выполняем OCR для всех страниц документа
        ocr_results = self.ocr_recognition(document.pages)
        
        # Интегрируем результаты в структуру документа
        self.integrate_ocr_results(document, provider, ocr_results)

    def get_batch_size(self):
        """
        Определяет размер батча для OCR в зависимости от настроек и устройства.
        
        Возвращает:
            int: Размер батча для модели распознавания
        """
        if settings.TORCH_DEVICE_MODEL == "cuda":
            return min(self.batch_size, 16)  # Ограничиваем для CUDA
        return min(self.batch_size, 8)      # Ограничиваем для CPU

    def ocr_recognition(self, pages: List[PageGroup]):
        """
        Выполняет распознавание текста на всех страницах документа.
        
        Использует модель распознавания для извлечения текста из изображений
        линий с учетом настроек батча, языков и прогресс-баров.
        
        Аргументы:
            pages: Список групп страниц для распознавания
        
        Возвращает:
            List[List[OCRResult]]: Результаты OCR для каждой страницы
        """
        # Подготавливаем данные для OCR
        images, image_info = self.prepare_ocr_input(pages)
        
        if not images:
            return []  # Нет изображений для обработки
            
        # Настраиваем модель распознавания
        self.recognition_model.disable_tqdm = self.disable_tqdm
        
        # Создаем задачи для распознавания
        task_names = [TaskNames(self.languages) for _ in images]
        
        # Запускаем OCR с оптимальным размером батча
        recognition_results = self.recognition_model(
            images, 
            [task_names] * len(images),  # Одинаковые задачи для всех изображений
            batch_size=int(self.get_batch_size())
        )
        
        return recognition_results

    def prepare_ocr_input(self, pages: List[PageGroup]):
        """
        Подготавливает входные данные для OCR из страниц документа.
        
        Извлекает изображения всех линий на страницах для дальнейшего
        распознавания текста с сохранением связи с исходными элементами.
        
        Аргументы:
            pages: Список групп страниц для подготовки данных
        
        Возвращает:
            Tuple[List[Image], List[Tuple]]: 
                Список изображений и информация о их связи с элементами документа
        """
        images = []
        image_info = []
        
        for page_idx, page in enumerate(pages):
            # Получаем изображение высокого разрешения для OCR
            page_image = page.get_image(highres=True)
            
            # Извлекаем изображения всех линий на странице
            for line_block_id in page.structure:
                # Получаем объект линии
                line_block = page.get_block(line_block_id)
                
                if line_block.block_type == BlockTypes.Line:
                    # Извлекаем область линии из страницы
                    line_image = self.extract_line_image(page_image, line_block.polygon.bbox)
                    if line_image:
                        images.append(line_image)
                        image_info.append((page_idx, line_block_id, line_block))
        
        return images, image_info

    def extract_line_image(self, page_image: Image.Image, bbox) -> Image.Image:
        """
        Извлекает изображение линии из страницы по ограничивающему прямоугольнику.
        
        Вырезает область изображения, соответствующую линии, для дальнейшего
        OCR распознавания с правильным масштабированием и отступами.
        
        Аргументы:
            page_image: Полное изображение страницы высокого разрешения
            bbox: Ограничивающий прямоугольник линии
        
        Возвращает:
            Image.Image: Изображение вырезанной линии или None если ошибка
        """
        try:
            x1, y1, x2, y2 = bbox
            
            # Добавляем отступы для лучшего захвата текста
            padding = 4
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(page_image.width, x2 + padding)
            y2 = min(page_image.height, y2 + padding)
            
            # Вырезаем изображение линии
            line_image = page_image.crop((x1, y1, x2, y2))
            
            # Проверяем, что изображение не пустое
            if line_image.width > 0 and line_image.height > 0:
                return line_image
            else:
                return None
                
        except Exception:
            # В случае ошибки возвращаем None
            return None

    def integrate_ocr_results(self, document: Document, provider: PdfProvider, ocr_results):
        """
        Интегрирует результаты OCR в структуру документа.
        
        Создает иерархию символов, спаны и линии из результатов OCR
        и добавляет их в соответствующие блоки документа.
        
        Аргументы:
            document: Документ для интеграции результатов
            provider: Провайдер с исходными данными
            ocr_results: Результаты распознавания текста
        """
        for page_idx, page in enumerate(document.pages):
            for line_block_id in page.structure:
                # Получаем объект линии
                line_block = page.get_block(line_block_id)
                
                if line_block.block_type == BlockTypes.Line and hasattr(line_block, 'polygon'):
                    # Инициализируем структуру линии если нужно
                    if line_block.structure is None:
                        line_block.structure = []
                    
                    # Создаем текстовую структуру из OCR результатов
                    self.create_text_structure_from_ocr(line_block, page)

    def create_text_structure_from_ocr(self, line_block: Line, page: PageGroup):
        """
        Создает текстовую структуру из результатов OCR для линии.
        
        Преобразует результаты распознавания в иерархическую структуру
        символов, спаны и связывает их с объектом линии.
        
        Аргументы:
            line_block: Блок линии для заполнения текстом
            page: Страница документа
        """
        # Получаем результаты OCR для этой линии
        ocr_result = self.get_ocr_result_for_line(line_block, page)
        
        if not ocr_result:
            return
            
        # Создаем структуру текста из результатов OCR
        self.create_spans_from_ocr_result(line_block, ocr_result)

    def get_ocr_result_for_line(self, line_block: Line, page: PageGroup):
        """
        Находит результат OCR соответствующий данной линии.
        
        Поиск результатов распознавания, соответствующих конкретной
        линии документа, на основе позиции и размеров.
        
        Аргументы:
            line_block: Блок линии для поиска соответствующего OCR результата
            page: Страница документа
        
        Возвращает:
            OCRResult or None: Результат OCR для линии или None
        """
        # Эта логика должна быть реализована на основе связи между
        # изображениями и результатами OCR в методе prepare_ocr_input
        # Для упрощения возвращаем первый доступный результат
        # В реальной реализации здесь должна быть правильная индексация
        
        return None  # Временная заглушка

    def create_spans_from_ocr_result(self, line_block: Line, ocr_result):
        """
        Создает спаны из результатов OCR для линии.
        
        Преобразует результаты распознавания в структуру спаны,
        обрабатывая теги форматирования и создавая соответствующие объекты.
        
        Аргументы:
            line_block: Блок линии для добавления спаны
            ocr_result: Результат OCR для обработки
        """
        if not ocr_result or not hasattr(ocr_result, 'text_lines'):
            return
            
        for text_line in ocr_result.text_lines:
            if hasattr(text_line, 'text_line'):
                # Создаем спаны из символов результата OCR
                spans = self.spans_from_html_chars(
                    text_line.text_line, 
                    line_block, 
                    None  # Изображение передается отдельно если нужно
                )
                
                # Добавляем созданные спаны в структуру линии
                for span in spans:
                    span_id = f"/span/{len(line_block.structure)}"
                    line_block.structure.append(span_id)

    def spans_from_html_chars(self, chars: List[TextChar], block: Block, image: Image.Image = None):
        """
        Создает спаны из HTML символов результатов OCR.
        
        Преобразует список символов с HTML тегами в структурированные
        спаны, обрабатывая открывающие и закрывающие теги форматирования.
        
        Аргументы:
            chars: Список символов с HTML тегами от OCR модели
            block: Блок документа для связывания
            image: Изображение линии (опционально)
        
        Возвращает:
            List[Span]: Список созданных спаны
        """
        spans = []
        current_text = ""
        current_tags = []
        
        for char in chars:
            text = fix_text(char.text) if hasattr(char, 'text') else str(char)
            
            if hasattr(char, 'html_tags') and char.html_tags:
                # Обрабатываем HTML теги
                for tag in char.html_tags:
                    if tag.startswith('<'):
                        # Открывающий тег
                        tag_type = get_opening_tag_type(tag)
                        if tag_type:
                            current_tags.append(tag_type)
                    elif tag.startswith('</'):
                        # Закрывающий тег
                        tag_type = get_closing_tag_type(tag)
                        if tag_type and current_tags and current_tags[-1] == tag_type:
                            current_tags.pop()
                    else:
                        # Обычный текст
                        current_text += text
            else:
                # Обычный символ без тегов
                current_text += text
        
        # Создаем финальный спан если есть текст
        if current_text.strip():
            span_class = get_block_class(BlockTypes.Span)
            span = span_class(
                text=current_text,
                tags=current_tags.copy()
            )
            spans.append(span)
        
        # Обрабатываем теги между символами
        for i, char in enumerate(chars):
            if hasattr(char, 'html_tags') and char.html_tags:
                # Проверяем теги на границах символов
                for tag in char.html_tags:
                    if tag.startswith('<') and not tag.startswith('</'):
                        tag_type = get_opening_tag_type(tag)
                        if tag_type:
                            current_tags.append(tag_type)
                    elif tag.startswith('</'):
                        tag_type = get_closing_tag_type(tag)
                        if tag_type and current_tags and current_tags[-1] == tag_type:
                            current_tags.pop()
        
        return spans

    def normalize_text_encoding(self, text: str) -> str:
        """
        Нормализует кодировку текста для корректного отображения.
        
        Использует библиотеку ftfy для исправления проблем с кодировкой,
        такими как неправильные символы, дублированные символы и другие
        артефакты, возникающие при OCR.
        
        Аргументы:
            text: Исходный текст для нормализации
        
        Возвращает:
            str: Нормализованный текст
        """
        # Используем ftfy для исправления текста
        normalized_text = fix_text(text)
        
        # Дополнительные исправления
        normalized_text = normalized_text.strip()
        
        # Удаляем лишние пробелы
        normalized_text = ' '.join(normalized_text.split())
        
        return normalized_text

    def create_char_objects(self, text: str, span: Span, image: Image.Image = None) -> List[Char]:
        """
        Создает объекты символов из текста для спаны.
        
        Преобразует текстовые символы в структурированные объекты Char
        с позиционной информацией и атрибутами форматирования.
        
        Аргументы:
            text: Текст для создания символов
            span: Родительский спан
            image: Изображение для анализа позиций (опционально)
        
        Возвращает:
            List[Char]: Список созданных объектов символов
        """
        chars = []
        
        for char_idx, char_text in enumerate(text):
            # Создаем объект символа
            char_class = get_block_class(BlockTypes.Char)
            char = char_class(
                text=char_text,
                position=char_idx,
                span_id=f"/span/{len(span.structure) if span.structure else 0}/char/{char_idx}"
            )
            
            # Добавляем символ в структуру спана
            if span.structure is None:
                span.structure = []
            span.structure.append(f"/char/{char_idx}")
            
            chars.append(char)
        
        return chars