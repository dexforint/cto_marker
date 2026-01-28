"""marker.converters.extraction

Конвертер для режима «structured extraction».

`ExtractionConverter` — это специализированный конвертер, который:
- гарантирует, что выход конвертации будет в Markdown (с пагинацией),
  чтобы его можно было корректно разбить на страницы;
- затем передаёт постраничный Markdown в экстракторы (`PageExtractor` и
  `DocumentExtractor`), которые используют LLM для извлечения структурированных
  данных по заданной JSON-схеме;
- в конце объединяет структурированный результат с исходным Markdown
  через `ExtractionRenderer`.

Модуль не описывает саму схему извлечения — она задаётся конфигурацией экстракторов.
"""

# Стандартная библиотека: регулярные выражения.
import re
from typing import Annotated

# Билдеры, необходимые для построения документа.
from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.builders.structure import StructureBuilder

# Базовый PDF-конвертер, от которого наследуемся.
from marker.converters.pdf import PdfConverter

# Экстракторы для постраничного и документного уровня.
from marker.extractors.document import DocumentExtractor
from marker.extractors.page import PageExtractor

# Выбор провайдера по пути к файлу.
from marker.providers.registry import provider_from_filepath

# Рендереры, специфичные для extraction режима.
from marker.renderers.extraction import ExtractionRenderer, ExtractionOutput
from marker.renderers.markdown import MarkdownRenderer

# Логирование.
from marker.logger import get_logger

logger = get_logger()


class ExtractionConverter(PdfConverter):
    """Конвертер, который выполняет PDF->Markdown и затем запускает structured extraction.

    Атрибуты класса:
        pattern: Регулярное выражение, по которому итоговый Markdown разбивается на страницы.
        existing_markdown: Если уже есть ранее сгенерированный Markdown, можно
            передать его сюда и пропустить стадию конвертации.
    """

    # Паттерн разделителя страниц, который добавляет MarkdownRenderer в режиме paginate_output.
    pattern: str = r"{\d+\}-{48}\n\n"

    # Уже готовый Markdown (если конвертация была выполнена ранее).
    existing_markdown: Annotated[
        str, "Markdown that was already converted for extraction."
    ] = None

    def build_document(self, filepath: str):
        """Строит документ и возвращает также provider (для совместимости с пайплайном).

        Этот метод похож на `PdfConverter.build_document`, но возвращает кортеж
        `(document, provider)`, так как provider иногда нужен вызывающей стороне.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Кортеж `(document, provider)`.
        """

        # Определяем провайдера по входному файлу.
        provider_cls = provider_from_filepath(filepath)

        # Создаём билдеры через DI.
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)

        # Инстанцируем провайдера.
        provider = provider_cls(filepath, self.config)

        # Строим документ.
        document = DocumentBuilder(self.config)(
            provider, layout_builder, line_builder, ocr_builder
        )

        # Строим структуру документа (разметка блоков в логическую структуру).
        structure_builder_cls = self.resolve_dependencies(StructureBuilder)
        structure_builder_cls(document)

        # Применяем процессоры.
        for processor in self.processor_list:
            processor(document)

        return document, provider

    def __call__(self, filepath: str) -> ExtractionOutput:
        """Запускает пайплайн extraction: Markdown -> page notes -> document JSON -> merge.

        Аргументы:
            filepath: Путь к исходному файлу.

        Возвращает:
            Объект `ExtractionOutput` (структурированный результат + исходный Markdown).
        """

        # Гарантируем, что Markdown будет с пагинацией, чтобы можно было корректно разбить по страницам.
        self.config["paginate_output"] = True  # Нужно, чтобы корректно разделить вывод на страницы
        self.config["output_format"] = (
            "markdown"  # Для extraction режимов вывод должен быть именно Markdown
        )

        # Если Markdown был передан заранее — используем его.
        markdown = self.existing_markdown

        if not markdown:
            # Иначе сначала выполняем обычную конвертацию в Markdown.
            document, provider = self.build_document(filepath)
            self.page_count = len(document.pages)

            # Рендерим Markdown напрямую (не через self.renderer, т.к. здесь нужен именно MarkdownRenderer).
            renderer = self.resolve_dependencies(MarkdownRenderer)
            output = renderer(document)
            markdown = output.markdown

        # Разбиваем Markdown на страницы по маркерам пагинации.
        output_pages = re.split(self.pattern, markdown)[1:]  # Разделяем вывод на страницы

        # Для structured extraction нужен LLM-сервис.
        # Если он не был установлен в artifact_dict ранее — поднимаем дефолтный.
        if self.artifact_dict.get("llm_service") is None:
            self.artifact_dict["llm_service"] = self.resolve_dependencies(
                self.default_llm_service
            )

        # Создаём экстракторы и рендерер через DI.
        page_extractor = self.resolve_dependencies(PageExtractor)
        document_extractor = self.resolve_dependencies(DocumentExtractor)
        renderer = self.resolve_dependencies(ExtractionRenderer)

        # Inference в параллельном режиме:
        # - сначала получаем заметки по каждому чанку страниц;
        # - затем агрегируем их на уровне документа.
        notes = page_extractor(output_pages)
        document_output = document_extractor(notes)

        # Объединяем структурированный результат и исходный Markdown.
        merged = renderer(document_output, markdown)
        return merged
