"""marker.converters.ocr

Конвертер для режима OCR-only.

`OCRConverter` — специализированный вариант `PdfConverter`, который:
- принудительно включает OCR (`force_ocr=True`), чтобы текст извлекался даже там,
  где PDF содержит только изображения;
- использует упрощённый набор процессоров (в текущей реализации — EquationProcessor);
- рендерит результат в JSON-формате через `OCRJSONRenderer`.

Этот режим удобен для задач, где требуется получить именно результат OCR
(например, для дальнейшего анализа внешними системами), а не полноценный Markdown.
"""

# Типизация.
from typing import Tuple

# Билдеры документа.
from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder

# Базовый PDF-конвертер.
from marker.converters.pdf import PdfConverter

# Процессоры.
from marker.processors import BaseProcessor
from marker.processors.equation import EquationProcessor

# Выбор провайдера по пути к файлу.
from marker.providers.registry import provider_from_filepath

# Рендерер OCR-режима.
from marker.renderers.ocr_json import OCRJSONRenderer


class OCRConverter(PdfConverter):
    """Конвертер, который выполняет принудительный OCR и возвращает OCR-JSON.

    Атрибуты класса:
        default_processors: Минимальная цепочка процессоров для OCR-only режима.
    """

    # Для OCR-only режима используем минимальный набор процессоров.
    default_processors: Tuple[BaseProcessor, ...] = (EquationProcessor,)

    def __init__(self, *args, **kwargs):
        """Инициализирует OCR-конвертер и переопределяет ключевые параметры конфигурации.

        Аргументы:
            *args: Позиционные аргументы, которые пробрасываются в PdfConverter.
            **kwargs: Именованные аргументы, которые пробрасываются в PdfConverter.

        Возвращает:
            None
        """

        # Инициализация базового PDF-конвертера (процессоры/рендерер/артефакты).
        super().__init__(*args, **kwargs)

        # Если config не задан, приводим к словарю для дальнейших операций.
        if not self.config:
            self.config = {}

        # В OCR-only режиме принудительно включаем OCR.
        self.config["force_ocr"] = True

        # Рендерер фиксируем на OCRJSON.
        self.renderer = OCRJSONRenderer

    def build_document(self, filepath: str):
        """Строит документ для OCR-only режима.

        Отличие от базового `PdfConverter.build_document` минимально: документ
        строится обычным образом, но OCR включён принудительно через config.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Объект `Document`.
        """

        # Определяем провайдера по входному файлу.
        provider_cls = provider_from_filepath(filepath)

        # Создаём билдеры через DI.
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)

        # Инстанцируем DocumentBuilder с текущей конфигурацией.
        document_builder = DocumentBuilder(self.config)

        # Создаём провайдера и строим документ.
        provider = provider_cls(filepath, self.config)
        document = document_builder(provider, layout_builder, line_builder, ocr_builder)

        # Применяем процессоры.
        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        """Выполняет OCR-only конвертацию и возвращает результат рендера.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Результат `OCRJSONRenderer`.
        """

        # Строим документ и сохраняем количество страниц.
        document = self.build_document(filepath)
        self.page_count = len(document.pages)

        # Инстанцируем рендерер и возвращаем результат.
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)
