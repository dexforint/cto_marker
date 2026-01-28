"""
Модуль рендеринга документов в Markdown формат.

Предоставляет рендерер для преобразования документов в Markdown с поддержкой
математических формул, таблиц, пагинации и изображений. Использует кастомный
Markdownify конвертер для точного контроля над форматированием.

Основные возможности:
- Преобразование HTML в Markdown
- Поддержка математических формул (inline и block)
- Умная обработка таблиц (Markdown или HTML режим)
- Пагинация с маркерами страниц
- Обработка переносов слов (hyphenation)
- Извлечение изображений
- Настраиваемые delimiters для математики
"""

import re
from collections import defaultdict
from typing import Annotated, Tuple

import regex
import six
from bs4 import NavigableString
from markdownify import MarkdownConverter, re_whitespace
from marker.logger import get_logger
from pydantic import BaseModel

from marker.renderers.html import HTMLRenderer
from marker.schema import BlockTypes
from marker.schema.document import Document

logger = get_logger()


def escape_dollars(text):
    """Экранирует символы доллара для Markdown."""
    return text.replace("$", r"\$")


def cleanup_text(full_text):
    """
    Очищает текст от избыточных переводов строк.
    
    Аргументы:
        full_text: Текст для очистки
        
    Возвращает:
        str: Очищенный текст
    """
    # Заменяем 3+ переводов строк на два
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    # Заменяем 3+ комбинаций \n\s на два перевода строки
    full_text = re.sub(r"(\n\s){3,}", "\n\n", full_text)
    return full_text.strip()


def get_formatted_table_text(element):
    """
    Форматирует текст ячейки таблицы для Markdown.
    
    Обрабатывает NavigableString, br теги, math теги и другой контент,
    экранируя доллары и добавляя пробелы.
    
    Аргументы:
        element: BeautifulSoup элемент ячейки таблицы
        
    Возвращает:
        str: Отформатированный текст ячейки
    """
    text = []
    # Обрабатываем содержимое ячейки
    for content in element.contents:
        if content is None:
            continue

        if isinstance(content, NavigableString):
            stripped = content.strip()
            if stripped:
                text.append(escape_dollars(stripped))
        elif content.name == "br":
            text.append("<br>")
        elif content.name == "math":
            text.append("$" + content.text + "$")
        else:
            content_str = escape_dollars(str(content))
            text.append(content_str)

    full_text = ""
    for i, t in enumerate(text):
        if t == "<br>":
            full_text += t
        elif i > 0 and text[i - 1] != "<br>":
            full_text += " " + t
        else:
            full_text += t
    return full_text


class Markdownify(MarkdownConverter):
    """
    Кастомный конвертер HTML в Markdown.
    
    Расширяет markdownify.MarkdownConverter для поддержки:
    - Математических формул с кастомными delimiters
    - Умной обработки таблиц (Markdown или HTML)
    - Пагинации с маркерами страниц
    - Обработки переносов слов (hyphenation)
    """
    def __init__(
        self,
        paginate_output,
        page_separator,
        inline_math_delimiters,
        block_math_delimiters,
        html_tables_in_markdown,
        **kwargs,
    ):
        """
        Инициализирует конвертер.
        
        Аргументы:
            paginate_output: Добавлять ли маркеры пагинации
            page_separator: Разделитель страниц (например, "---...")
            inline_math_delimiters: Tuple delimiters для inline math (например, ("$", "$"))
            block_math_delimiters: Tuple delimiters для block math (например, ("$", "$"))
            html_tables_in_markdown: Возвращать ли таблицы как HTML вместо Markdown
            **kwargs: Аргументы для MarkdownConverter
        """
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator
        self.inline_math_delimiters = inline_math_delimiters
        self.block_math_delimiters = block_math_delimiters
        self.html_tables_in_markdown = html_tables_in_markdown

    def convert_div(self, el, text, parent_tags):
        is_page = el.has_attr("class") and el["class"][0] == "page"
        if self.paginate_output and is_page:
            page_id = el["data-page-id"]
            pagination_item = (
                "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            )
            return pagination_item + text
        else:
            return text

    def convert_p(self, el, text, parent_tags):
        hyphens = r"-—¬"
        has_continuation = el.has_attr("class") and "has-continuation" in el["class"]
        if has_continuation:
            block_type = BlockTypes[el["block-type"]]
            if block_type in [BlockTypes.TextInlineMath, BlockTypes.Text]:
                if regex.compile(
                    rf".*[\p{{Ll}}|\d][{hyphens}]\s?$", regex.DOTALL
                ).match(text):  # handle hypenation across pages
                    return regex.split(rf"[{hyphens}]\s?$", text)[0]
                return f"{text} "
            if block_type == BlockTypes.ListGroup:
                return f"{text}"
        return f"{text}\n\n" if text else ""  # default convert_p behavior

    def convert_math(self, el, text, parent_tags):
        block = el.has_attr("display") and el["display"] == "block"
        if block:
            return (
                "\n"
                + self.block_math_delimiters[0]
                + text.strip()
                + self.block_math_delimiters[1]
                + "\n"
            )
        else:
            return (
                " "
                + self.inline_math_delimiters[0]
                + text.strip()
                + self.inline_math_delimiters[1]
                + " "
            )

    def convert_table(self, el, text, parent_tags):
        if self.html_tables_in_markdown:
            return "\n\n" + str(el) + "\n\n"

        total_rows = len(el.find_all("tr"))
        colspans = []
        rowspan_cols = defaultdict(int)
        for i, row in enumerate(el.find_all("tr")):
            row_cols = rowspan_cols[i]
            for cell in row.find_all(["td", "th"]):
                colspan = int(cell.get("colspan", 1))
                row_cols += colspan
                for r in range(int(cell.get("rowspan", 1)) - 1):
                    rowspan_cols[i + r] += (
                        colspan  # Add the colspan to the next rows, so they get the correct number of columns
                    )
            colspans.append(row_cols)
        total_cols = max(colspans) if colspans else 0

        grid = [[None for _ in range(total_cols)] for _ in range(total_rows)]

        for row_idx, tr in enumerate(el.find_all("tr")):
            col_idx = 0
            for cell in tr.find_all(["td", "th"]):
                # Skip filled positions
                while col_idx < total_cols and grid[row_idx][col_idx] is not None:
                    col_idx += 1

                # Fill in grid
                value = (
                    get_formatted_table_text(cell)
                    .replace("\n", " ")
                    .replace("|", " ")
                    .strip()
                )
                rowspan = int(cell.get("rowspan", 1))
                colspan = int(cell.get("colspan", 1))

                if col_idx >= total_cols:
                    # Skip this cell if we're out of bounds
                    continue

                for r in range(rowspan):
                    for c in range(colspan):
                        try:
                            if r == 0 and c == 0:
                                grid[row_idx][col_idx] = value
                            else:
                                grid[row_idx + r][col_idx + c] = (
                                    ""  # Empty cell due to rowspan/colspan
                                )
                        except IndexError:
                            # Sometimes the colspan/rowspan predictions can overflow
                            logger.info(
                                f"Overflow in columns: {col_idx + c} >= {total_cols} or rows: {row_idx + r} >= {total_rows}"
                            )
                            continue

                col_idx += colspan

        markdown_lines = []
        col_widths = [0] * total_cols
        for row in grid:
            for col_idx, cell in enumerate(row):
                if cell is not None:
                    col_widths[col_idx] = max(col_widths[col_idx], len(str(cell)))

        def add_header_line():
            markdown_lines.append(
                "|" + "|".join("-" * (width + 2) for width in col_widths) + "|"
            )

        # Generate markdown rows
        added_header = False
        for i, row in enumerate(grid):
            is_empty_line = all(not cell for cell in row)
            if is_empty_line and not added_header:
                # Skip leading blank lines
                continue

            line = []
            for col_idx, cell in enumerate(row):
                if cell is None:
                    cell = ""
                padding = col_widths[col_idx] - len(str(cell))
                line.append(f" {cell}{' ' * padding} ")
            markdown_lines.append("|" + "|".join(line) + "|")

            if not added_header:
                # Skip empty lines when adding the header row
                add_header_line()
                added_header = True

        # Handle one row tables
        if total_rows == 1:
            add_header_line()

        table_md = "\n".join(markdown_lines)
        return "\n\n" + table_md + "\n\n"

    def convert_a(self, el, text, parent_tags):
        text = self.escape(text)
        # Escape brackets and parentheses in text
        text = re.sub(r"([\[\]()])", r"\\\1", text)
        return super().convert_a(el, text, parent_tags)

    def convert_span(self, el, text, parent_tags):
        if el.get("id"):
            return f'<span id="{el["id"]}">{text}</span>'
        else:
            return text

    def escape(self, text, parent_tags=None):
        text = super().escape(text, parent_tags)
        if self.options["escape_dollars"]:
            text = text.replace("$", r"\$")
        return text

    def process_text(self, el, parent_tags=None):
        text = six.text_type(el) or ""

        # normalize whitespace if we're not inside a preformatted element
        if not el.find_parent("pre"):
            text = re_whitespace.sub(" ", text)

        # escape special characters if we're not inside a preformatted or code element
        if not el.find_parent(["pre", "code", "kbd", "samp", "math"]):
            text = self.escape(text)

        # remove trailing whitespaces if any of the following condition is true:
        # - current text node is the last node in li
        # - current text node is followed by an embedded list
        if el.parent.name == "li" and (
            not el.next_sibling or el.next_sibling.name in ["ul", "ol"]
        ):
            text = text.rstrip()

        return text


class MarkdownOutput(BaseModel):
    """
    Модель выходных данных Markdown рендеринга.
    
    Атрибуты:
        markdown: Markdown текст документа
        images: Словарь изображений {block_id: base64_image}
        metadata: Метаданные документа
    """
    markdown: str
    images: dict
    metadata: dict


class MarkdownRenderer(HTMLRenderer):
    """
    Рендерер для преобразования документов в Markdown формат.
    
    Сначала преобразует документ в HTML (наследует HTMLRenderer),
    затем конвертирует HTML в Markdown с помощью кастомного Markdownify.
    
    Атрибуты:
        page_separator: Разделитель между страницами (по умолчанию 48 дефисов)
        inline_math_delimiters: Delimiters для inline математики (по умолчанию "$")
        block_math_delimiters: Delimiters для block математики (по умолчанию "$")
        html_tables_in_markdown: Возвращать ли таблицы как HTML вместо Markdown
    """
    page_separator: Annotated[
        str, "The separator to use between pages.", "Default is '-' * 48."
    ] = "-" * 48
    inline_math_delimiters: Annotated[
        Tuple[str], "The delimiters to use for inline math."
    ] = ("$", "$")
    block_math_delimiters: Annotated[
        Tuple[str], "The delimiters to use for block math."
    ] = ("$", "$")
    html_tables_in_markdown: Annotated[
        bool, "Return tables formatted as HTML, instead of in markdown"
    ] = False

    @property
    def md_cls(self):
        """
        Создает экземпляр Markdownify конвертера с настройками.
        
        Возвращает:
            Markdownify: Настроенный конвертер HTML в Markdown
        """
        return Markdownify(
            self.paginate_output,
            self.page_separator,
            heading_style="ATX",  # Стиль заголовков с #
            bullets="-",  # Символ для списков
            escape_misc=False,
            escape_underscores=True,  # Экранировать _
            escape_asterisks=True,  # Экранировать *
            escape_dollars=True,  # Экранировать $
            sub_symbol="<sub>",  # Сохранять <sub> как HTML
            sup_symbol="<sup>",  # Сохранять <sup> как HTML
            inline_math_delimiters=self.inline_math_delimiters,
            block_math_delimiters=self.block_math_delimiters,
            html_tables_in_markdown=self.html_tables_in_markdown
        )

    def __call__(self, document: Document) -> MarkdownOutput:
        """
        Рендерит документ в Markdown формат.
        
        Аргументы:
            document: Document для рендеринга
            
        Возвращает:
            MarkdownOutput: Объект с Markdown, изображениями и метаданными
        """
        # Рендерим документ в BlockOutput структуру
        document_output = document.render(self.block_config)
        # Извлекаем HTML и изображения (через HTMLRenderer)
        full_html, images = self.extract_html(document, document_output)
        # Конвертируем HTML в Markdown
        markdown = self.md_cls.convert(full_html)
        # Очищаем избыточные переводы строк
        markdown = cleanup_text(markdown)

        # Гарантируем правильные пробелы для маркеров пагинации
        if self.paginate_output:
            # Добавляем начальные переводы строк если их нет
            if not markdown.startswith("\n\n"):
                markdown = "\n\n" + markdown
            # Добавляем конечные переводы строк если markdown заканчивается разделителем
            if markdown.endswith(self.page_separator):
                markdown += "\n\n"

        # Возвращаем результат
        return MarkdownOutput(
            markdown=markdown,
            images=images,
            metadata=self.generate_document_metadata(document, document_output),
        )
