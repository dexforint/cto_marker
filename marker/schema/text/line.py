# Модель строки текста
# Представляет строку текста, состоящую из фрагментов (spans)

import html
import re
from typing import Literal, List

import regex

from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput

# Символы дефиса
HYPHENS = r"-—¬"


# Удалить HTML теги из текста
# Убирает все теги вида <...> из строки
def remove_tags(text):
    return re.sub(r"<[^>]+>", "", text)


# Заменить последнее вхождение подстроки
# Заменяет только последнее совпадение old на new
def replace_last(string, old, new):
    matches = list(re.finditer(old, string))
    if not matches:
        return string  # Нет совпадений
    last_match = matches[-1]  # Берем последнее совпадение
    return string[: last_match.start()] + new + string[last_match.end():]


# Убрать дефис в конце строки если следующая строка начинается с маленькой буквы
# Обработка переноса слов между строками
def strip_trailing_hyphens(line_text, next_line_text, line_html) -> str:
    lowercase_letters = r"\p{Ll}"  # Паттерн для строчных букв

    # Проверяем, что строка заканчивается дефисом
    hyphen_regex = regex.compile(rf".*[{HYPHENS}]\s?$", regex.DOTALL)
    # Проверяем, что следующая строка начинается со строчной буквы
    next_line_starts_lowercase = regex.match(
        rf"^\s?[{lowercase_letters}]", next_line_text
    )

    # Если оба условия выполнены, убираем дефис
    if hyphen_regex.match(line_text) and next_line_starts_lowercase:
        line_html = replace_last(line_html, rf"[{HYPHENS}]", "")

    return line_html


# Строка текста
# Содержит последовательность фрагментов текста (spans)
class Line(Block):
    block_type: BlockTypes = BlockTypes.Line  # Тип блока - строка
    block_description: str = "A line of text."
    # Форматирование на уровне строки (иногда нужно для математики)
    formats: List[Literal["math"]] | None = (
        None
    )

    # Получить текст для OCR
    # Форматирует текст с учетом italic/bold, но без sup/sub и math (могут быть ненадежны)
    def ocr_input_text(self, document):
        text = ""
        for block in self.contained_blocks(document, (BlockTypes.Span,)):
            # Мы не включаем надстрочные/подстрочные и математику на этом этапе
            block_text = block.text
            if block.italic:
                text += f"<i>{block_text}</i>"
            elif block.bold:
                text += f"<b>{block_text}</b>"
            else:
                text += block_text

        return text.strip()

    # Получить отформатированный текст
    # Возвращает HTML с форматированием (italic, bold, math, sup, url)
    def formatted_text(self, document, skip_urls=False):
        text = ""
        for block in self.contained_blocks(document, (BlockTypes.Span,)):
            block_text = html.escape(block.text)  # Экранируем спецсимволы HTML

            # Обработка надстрочных символов
            if block.has_superscript:
                # Пытаемся отделить цифры/знаки от текста
                block_text = re.sub(r"^([0-9\W]+)(.*)", r"<sup>\1</sup>\2", block_text)
                # Если не сработало, оборачиваем весь текст
                if "<sup>" not in block_text:
                    block_text = f"<sup>{block_text}</sup>"

            # Обработка URL
            if block.url and not skip_urls:
                block_text = f"<a href='{block.url}'>{block_text}</a>"

            # Обработка форматирования
            if block.italic:
                text += f"<i>{block_text}</i>"
            elif block.bold:
                text += f"<b>{block_text}</b>"
            elif block.math:
                text += f"<math display='inline'>{block_text}</math>"
            else:
                text += block_text

        return text

    # Собрать HTML представление строки
    # Объединяет HTML фрагментов и обрабатывает дефисы
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        template = ""
        for c in child_blocks:
            template += c.html  # Объединяем HTML дочерних блоков

        # Получаем чистый текст (без тегов)
        raw_text = remove_tags(template).strip()
        structure_idx = parent_structure.index(self.id)

        # Если есть следующая строка, обрабатываем дефисы
        if structure_idx < len(parent_structure) - 1:
            next_block_id = parent_structure[structure_idx + 1]
            next_line = document.get_block(next_block_id)
            next_line_raw_text = next_line.raw_text(document)
            template = strip_trailing_hyphens(raw_text, next_line_raw_text, template)
        else:
            # Убираем завершающие пробелы с последней строки
            template = template.strip(" ")

        return template

    # Рендерить строку
    # Рендерит все дочерние фрагменты и собирает результат в BlockOutput
    def render(
        self, document, parent_structure, section_hierarchy=None, block_config=None
    ):
        child_content = []
        if self.structure is not None and len(self.structure) > 0:
            # Рендерим все фрагменты строки
            for block_id in self.structure:
                block = document.get_block(block_id)
                child_content.append(
                    block.render(
                        document, parent_structure, section_hierarchy, block_config
                    )
                )

        return BlockOutput(
            html=self.assemble_html(
                document, child_content, parent_structure, block_config
            ),
            polygon=self.polygon,
            id=self.id,
            children=[],
            section_hierarchy=section_hierarchy,
        )

    # Слить строку с другой строкой
    # Объединяет полигоны, структуры и форматирование
    def merge(self, other: "Line"):
        # Объединяем полигоны
        self.polygon = self.polygon.merge([other.polygon])

        # Обрабатываем слияние структур с None
        if self.structure is None:
            self.structure = other.structure
        elif other.structure is not None:
            self.structure = self.structure + other.structure

        # Объединяем форматы с None
        if self.formats is None:
            self.formats = other.formats
        elif other.formats is not None:
            # Убираем дубликаты форматов
            self.formats = list(set(self.formats + other.formats))
