"""marker.converters.pdf

PDF-конвертер Marker.

Этот модуль содержит основной конвертер `PdfConverter`, который отвечает за полный
пайплайн преобразования PDF (и других поддерживаемых провайдерами источников) в
выходные форматы (Markdown/JSON/HTML/Chunks и т. п.).

На высоком уровне конвертер делает следующее:
1) определяет подходящий Provider по пути к файлу;
2) создаёт Builder'ы (layout/line/ocr/structure) и строит объект `Document`;
3) прогоняет документ через последовательность Processor'ов;
4) рендерит итог через выбранный Renderer.

Модуль также содержит вспомогательный контекст-менеджер, позволяющий принимать
как путь к файлу (str), так и BytesIO (например, при работе через API),
временно сохраняя поток в файл.

Важно: комментарии и docstring'и в этом файле описывают логику, но не меняют
поведение конвертера.
"""

# Стандартная библиотека: работа с окружением и временными файлами.
import os

# Локальный импорт: тип документа, который строится и обрабатывается в пайплайне.
from marker.schema.document import Document

# Отключаем предупреждение HuggingFace tokenizers про параллелизм.
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # отключает предупреждение tokenizers

# Стандартная библиотека: структуры данных, типизация, контекст-менеджеры.
from collections import defaultdict
from typing import Annotated, Any, Dict, List, Optional, Type, Tuple, Union
import io
from contextlib import contextmanager
import tempfile

# Компоненты пайплайна Marker.
from marker.processors import BaseProcessor
from marker.services import BaseService
from marker.processors.llm.llm_table_merge import LLMTableMergeProcessor
from marker.providers.registry import provider_from_filepath
from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.builders.structure import StructureBuilder
from marker.converters import BaseConverter

# Набор процессоров, используемых по умолчанию для PDF.
from marker.processors.blockquote import BlockquoteProcessor
from marker.processors.code import CodeProcessor
from marker.processors.debug import DebugProcessor
from marker.processors.document_toc import DocumentTOCProcessor
from marker.processors.equation import EquationProcessor
from marker.processors.footnote import FootnoteProcessor
from marker.processors.ignoretext import IgnoreTextProcessor
from marker.processors.line_numbers import LineNumbersProcessor
from marker.processors.list import ListProcessor
from marker.processors.llm.llm_complex import LLMComplexRegionProcessor
from marker.processors.llm.llm_form import LLMFormProcessor
from marker.processors.llm.llm_image_description import LLMImageDescriptionProcessor
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.page_header import PageHeaderProcessor
from marker.processors.reference import ReferenceProcessor
from marker.processors.sectionheader import SectionHeaderProcessor
from marker.processors.table import TableProcessor
from marker.processors.text import TextProcessor
from marker.processors.block_relabel import BlockRelabelProcessor
from marker.processors.blank_page import BlankPageProcessor
from marker.processors.llm.llm_equation import LLMEquationProcessor
from marker.renderers.markdown import MarkdownRenderer

# Регистрация типов блоков (позволяет переопределять реализацию блоков по enum).
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.registry import register_block_class

# Вспомогательная утилита: import-path -> class.
from marker.util import strings_to_classes

# Дополнительные процессоры и сервис по умолчанию для LLM.
from marker.processors.llm.llm_handwriting import LLMHandwritingProcessor
from marker.processors.order import OrderProcessor
from marker.services.gemini import GoogleGeminiService
from marker.processors.line_merge import LineMergeProcessor
from marker.processors.llm.llm_mathblock import LLMMathBlockProcessor
from marker.processors.llm.llm_page_correction import LLMPageCorrectionProcessor
from marker.processors.llm.llm_sectionheader import LLMSectionHeaderProcessor


class PdfConverter(BaseConverter):
    """Конвертер для обработки PDF-документов.

    Конвертер строит `Document` из входного файла и прогоняет его через цепочку
    процессоров, после чего вызывает рендерер.

    Особенности:
    - поддерживает переопределение классов блоков через `override_map`;
    - умеет принимать список процессоров как import-path'ы (строки);
    - может включать LLM-обработку (use_llm) и автоматически поднимать сервис LLM.

    Атрибуты класса (конфигурируемые):
        override_map: Карта переопределения классов блоков по типам BlockTypes.
        use_llm: Флаг включения LLM-улучшений качества.
        default_processors: Последовательность процессоров по умолчанию.
        default_llm_service: Сервис LLM по умолчанию (Gemini).
    """

    # Карта переопределения классов блоков:
    # например, можно подменить реализацию блока таблицы.
    override_map: Annotated[
        Dict[BlockTypes, Type[Block]],
        "A mapping to override the default block classes for specific block types.",
        "The keys are `BlockTypes` enum values, representing the types of blocks,",
        "and the values are corresponding `Block` class implementations to use",
        "instead of the defaults.",
    ] = defaultdict()

    # Флаг включения более качественной (но более дорогой) обработки через LLM.
    use_llm: Annotated[
        bool,
        "Enable higher quality processing with LLMs.",
    ] = False

    # Процессоры, которые применяются к документу по умолчанию (в заданном порядке).
    default_processors: Tuple[BaseProcessor, ...] = (
        OrderProcessor,
        BlockRelabelProcessor,
        LineMergeProcessor,
        BlockquoteProcessor,
        CodeProcessor,
        DocumentTOCProcessor,
        EquationProcessor,
        FootnoteProcessor,
        IgnoreTextProcessor,
        LineNumbersProcessor,
        ListProcessor,
        PageHeaderProcessor,
        SectionHeaderProcessor,
        TableProcessor,
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        TextProcessor,
        LLMComplexRegionProcessor,
        LLMImageDescriptionProcessor,
        LLMEquationProcessor,
        LLMHandwritingProcessor,
        LLMMathBlockProcessor,
        LLMSectionHeaderProcessor,
        LLMPageCorrectionProcessor,
        ReferenceProcessor,
        BlankPageProcessor,
        DebugProcessor,
    )

    # Сервис LLM по умолчанию (используется, если LLM включён, а сервис явно не задан).
    default_llm_service: BaseService = GoogleGeminiService

    def __init__(
        self,
        artifact_dict: Dict[str, Any],
        processor_list: Optional[List[str]] = None,
        renderer: str | None = None,
        llm_service: str | None = None,
        config=None,
    ):
        """Инициализирует PDF-конвертер и настраивает зависимости пайплайна.

        Аргументы:
            artifact_dict: Словарь артефактов/зависимостей (например, модели, сервисы),
                которые могут понадобиться процессорам/рендерам.
            processor_list: Необязательный список import-path'ов процессоров.
                Если не задан, используется `default_processors`.
            renderer: Import-path рендерера. Если не задан, используется MarkdownRenderer.
            llm_service: Import-path сервиса LLM. Если не задан, сервис может быть
                поднят автоматически при `config["use_llm"] == True`.
            config: Конфигурация конвертера.

        Возвращает:
            None
        """

        # Инициализируем базовый конвертер (применяем config, подготавливаем окружение).
        super().__init__(config)

        # Гарантируем, что config — словарь, чтобы в дальнейшем можно было делать `.get()`.
        if config is None:
            config = {}

        # Применяем переопределения классов блоков (если указаны).
        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        # Подготовка списка процессоров:
        # - если пользователь передал строки, превращаем их в классы;
        # - иначе используем дефолтную цепочку.
        if processor_list is not None:
            processor_list = strings_to_classes(processor_list)
        else:
            processor_list = self.default_processors

        # Подготовка рендера:
        # - если указан import-path, превращаем его в класс;
        # - иначе используем Markdown.
        if renderer:
            renderer = strings_to_classes([renderer])[0]
        else:
            renderer = MarkdownRenderer

        # Сохраняем артефакты до инициализации процессоров, чтобы DI мог их использовать.
        self.artifact_dict = artifact_dict

        # Разрешаем сервис LLM:
        # - если передан явно, создаём его;
        # - иначе, если в config включён use_llm, создаём дефолтный.
        if llm_service:
            llm_service_cls = strings_to_classes([llm_service])[0]
            llm_service = self.resolve_dependencies(llm_service_cls)
        elif config.get("use_llm", False):
            llm_service = self.resolve_dependencies(self.default_llm_service)

        # Пробрасываем LLM-сервис в artifact_dict, чтобы его могли получить процессоры.
        self.artifact_dict["llm_service"] = llm_service
        self.llm_service = llm_service

        # Сохраняем выбранный рендерер (класс).
        self.renderer = renderer

        # Инстанцируем процессоры и при необходимости группируем LLM-процессоры.
        processor_list = self.initialize_processors(processor_list)
        self.processor_list = processor_list

        # Класс билдера layout можно переопределять (например, в других режимах).
        self.layout_builder_class = LayoutBuilder

        # Счётчик страниц — полезен для статистики/отчётов.
        self.page_count = None  # Отслеживаем, сколько страниц было сконвертировано

    @contextmanager
    def filepath_to_str(self, file_input: Union[str, io.BytesIO]):
        """Нормализует вход: возвращает путь к файлу даже если вход был BytesIO.

        Если пользователь передаёт путь (str) — просто отдаём его.
        Если пользователь передаёт BytesIO — сохраняем содержимое во временный файл
        с расширением .pdf и отдаём путь к этому файлу, а затем гарантированно
        удаляем временный файл.

        Аргументы:
            file_input: Путь к файлу PDF или BytesIO с содержимым PDF.

        Yields:
            Путь к файлу PDF на диске.

        Raises:
            TypeError: если передан неподдерживаемый тип.
        """

        # Ссылка на временный файл, чтобы удалить его в finally.
        temp_file = None

        try:
            # Если это строка — это уже путь.
            if isinstance(file_input, str):
                yield file_input
            else:
                # Иначе ожидаем BytesIO и сохраняем его во временный файл.
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as temp_file:
                    if isinstance(file_input, io.BytesIO):
                        # Сдвигаем указатель в начало потока и пишем все байты.
                        file_input.seek(0)
                        temp_file.write(file_input.getvalue())
                    else:
                        # Неожиданный тип — явно сообщаем об ошибке.
                        raise TypeError(
                            f"Expected str or BytesIO, got {type(file_input)}"
                        )

                # Возвращаем путь к созданному временно файлу.
                yield temp_file.name
        finally:
            # Гарантируем очистку временного файла (если он был создан).
            if temp_file is not None and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    def build_document(self, filepath: str) -> Document:
        """Строит объект `Document` из входного файла.

        Этапы:
        - выбираем Provider по `filepath`;
        - создаём билдеры layout/line/ocr;
        - строим `Document` через `DocumentBuilder`;
        - создаём структуру документа через `StructureBuilder`;
        - применяем процессоры к документу.

        Аргументы:
            filepath: Путь к файлу, который нужно конвертировать.

        Возвращает:
            Заполненный объект `Document`.
        """

        # Определяем провайдера (PDF/изображение/другие форматы) по расширению/содержимому.
        provider_cls = provider_from_filepath(filepath)

        # Создаём билдеры с учётом зависимости и конфигурации.
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)

        # Инстанцируем провайдера для чтения/декодирования исходного файла.
        provider = provider_cls(filepath, self.config)

        # Строим «сырой» документ: страницы + layout/линии/базовый OCR.
        document = DocumentBuilder(self.config)(
            provider, layout_builder, line_builder, ocr_builder
        )

        # Структурный билдер (группировка блоков, дерево разделов и т. п.).
        structure_builder_cls = self.resolve_dependencies(StructureBuilder)
        structure_builder_cls(document)

        # Последовательно применяем процессоры (каждый модифицирует документ in-place).
        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str | io.BytesIO):
        """Выполняет конвертацию и возвращает результат рендера.

        Аргументы:
            filepath: Путь к файлу (str) либо BytesIO.

        Возвращает:
            Результат работы рендерера (например, объект с markdown/json/html).
        """

        # Приводим вход к пути на диске (важно для большинства провайдеров/билдеров).
        with self.filepath_to_str(filepath) as temp_path:
            # Строим документ и запоминаем количество страниц.
            document = self.build_document(temp_path)
            self.page_count = len(document.pages)

            # Инстанцируем рендерер и генерируем финальный вывод.
            renderer = self.resolve_dependencies(self.renderer)
            rendered = renderer(document)

        return rendered
