"""marker.converters.table

Конвертер таблиц.

`TableConverter` — специализированный вариант `PdfConverter`, ориентированный на
извлечение и улучшение табличных структур (таблицы, формы, оглавления).

Отличия от базового PDF-конвертера:
- использует сокращённый набор процессоров, сфокусированный на таблицах;
- отключает OCR на этапе построения документа (для ускорения и экономии);
- после построения документа фильтрует структуру страниц, оставляя только
  интересующие типы блоков (`converter_block_types`).

Это полезно для сценариев, где пользователь хочет получить максимально чистые
таблицы без полного «литературного» восстановления документа.
"""

# Типизация.
from typing import Tuple, List

# Билдеры документа.
from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder

# Базовый конвертер PDF, от которого наследуемся.
from marker.converters.pdf import PdfConverter

# Процессоры, необходимые для табличного режима.
from marker.processors import BaseProcessor
from marker.processors.llm.llm_complex import LLMComplexRegionProcessor
from marker.processors.llm.llm_form import LLMFormProcessor
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.llm.llm_table_merge import LLMTableMergeProcessor
from marker.processors.table import TableProcessor

# Выбор провайдера по пути к файлу.
from marker.providers.registry import provider_from_filepath

# Типы блоков (для фильтрации структуры).
from marker.schema import BlockTypes


class TableConverter(PdfConverter):
    """Специализированный конвертер для извлечения таблиц и форм из документа.

    Атрибуты класса:
        default_processors: Набор процессоров, ориентированных на таблицы.
        converter_block_types: Типы блоков, которые мы оставляем в структуре страниц.
    """

    # В табличном режиме нам нужен более узкий набор процессоров.
    default_processors: Tuple[BaseProcessor, ...] = (
        TableProcessor,
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        LLMComplexRegionProcessor,
    )

    # Список типов блоков, которые мы хотим сохранять при фильтрации структуры.
    converter_block_types: List[BlockTypes] = (
        BlockTypes.Table,
        BlockTypes.Form,
        BlockTypes.TableOfContents,
    )

    def build_document(self, filepath: str):
        """Строит документ и оставляет в структуре только табличные блоки.

        По сравнению с `PdfConverter.build_document`:
        - OCR принудительно отключается;
        - структура каждой страницы фильтруется по `converter_block_types`.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Объект `Document` с отфильтрованной структурой.
        """

        # Определяем провайдера по входному файлу.
        provider_cls = provider_from_filepath(filepath)

        # Создаём билдеры (layout/line/ocr) через DI.
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)

        # Создаём билдер документа и отключаем OCR для ускорения.
        document_builder = DocumentBuilder(self.config)
        document_builder.disable_ocr = True

        # Инстанцируем провайдера и строим документ.
        provider = provider_cls(filepath, self.config)
        document = document_builder(provider, layout_builder, line_builder, ocr_builder)

        # Фильтруем структуру страниц, оставляя только нужные типы блоков.
        for page in document.pages:
            page.structure = [
                p for p in page.structure if p.block_type in self.converter_block_types
            ]

        # Запускаем процессоры (как и в базовом конвертере).
        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        """Выполняет табличную конвертацию и рендерит результат.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Результат выбранного рендера.
        """

        # Строим документ и запоминаем количество страниц.
        document = self.build_document(filepath)
        self.page_count = len(document.pages)

        # Рендерим документ выбранным рендерером.
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)
