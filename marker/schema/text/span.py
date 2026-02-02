# Модель фрагмента текста (span)
# Представляет фрагмент текста с определенным форматированием внутри строки

import html
import re
from typing import List, Literal, Optional

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.util import unwrap_math


# Очистить текст от лишних символов
# Убирает множественные переносы строк и неразрывные пробелы
def cleanup_text(full_text):
    full_text = re.sub(r"(\n\s){3,}", "\n\n", full_text)  # Заменяем 3+ перенос на 2
    full_text = full_text.replace("\xa0", " ")  # Заменяем неразрывные пробелы
    return full_text


# Фрагмент текста (span)
# Минимальная единица текста с единым форматированием
class Span(Block):
    block_type: BlockTypes = BlockTypes.Span  # Тип блока - фрагмент
    block_description: str = "A span of text inside a line."

    # Текст и свойства шрифта
    text: str  # Текст фрагмента
    font: str  # Имя шрифта
    font_weight: float  # Толщина шрифта
    font_size: float  # Размер шрифта
    minimum_position: int  # Минимальная позиция в строке
    maximum_position: int  # Максимальная позиция в строке

    # Список форматов, примененных к фрагменту
    formats: List[
        Literal[
            "plain",
            "math",
            "chemical",
            "bold",
            "italic",
            "highlight",
            "subscript",
            "superscript",
            "small",
            "code",
            "underline",
        ]
    ]

    # Флаги для упрощенного доступа к форматам
    has_superscript: bool = False
    has_subscript: bool = False
    url: Optional[str] = None  # URL если фрагмент является ссылкой
    html: Optional[str] = None  # HTML представление (если было сгенерировано)

    # Свойства для проверки форматов
    @property
    def bold(self):
        return "bold" in self.formats

    @property
    def italic(self):
        return "italic" in self.formats

    @property
    def math(self):
        return "math" in self.formats

    @property
    def highlight(self):
        return "highlight" in self.formats

    @property
    def superscript(self):
        return "superscript" in self.formats

    @property
    def subscript(self):
        return "subscript" in self.formats

    @property
    def small(self):
        return "small" in self.formats

    @property
    def code(self):
        return "code" in self.formats

    @property
    def underline(self):
        return "underline" in self.formats

    # Собрать HTML представление фрагмента
    # Применяет форматирование и экранирование текста
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        if self.ignore_for_output:
            return ""  # Фрагмент нужно игнорировать

        if self.html:
            return self.html  # Используем готовый HTML

        text = self.text

        # Убираем завершающие переносы строк
        replaced_newline = False
        while len(text) > 0 and text[-1] in ["\n", "\r"]:
            text = text[:-1]
            replaced_newline = True

        # Убираем начальные переносы строк
        while len(text) > 0 and text[0] in ["\n", "\r"]:
            text = text[1:]

        # Добавляем пробел если был перенос строки, но нет дефиса
        if replaced_newline and not text.endswith("-"):
            text += " "

        # Убираем дефис в середине фрагмента (перенос строки)
        text = text.replace("-\n", "")

        # Экранируем спецсимволы HTML
        text = html.escape(text)
        text = cleanup_text(text)

        # Обработка надстрочных символов
        if self.has_superscript:
            # Пытаемся отделить цифры/знаки от текста
            text = re.sub(r"^([0-9\W]+)(.*)", r"<sup>\1</sup>\2", text)
            # Если не сработало, оборачиваем весь текст
            if "<sup>" not in text:
                text = f"<sup>{text}</sup>"

        # Обработка URL (превращаем в ссылку)
        if self.url:
            text = f"<a href='{self.url}'>{text}</a>"

        # Применяем форматирование (поддерживается только один формат)
        # TODO: Поддержка множественных форматов
        if self.italic:
            text = f"<i>{text}</i>"
        elif self.bold:
            text = f"<b>{text}</b>"
        elif self.math:
            # Определяем режим отображения математики (блочный или inline)
            block_envs = ["split", "align", "gather", "multline"]
            if any(f"\\begin{{{env}}}" in text for env in block_envs):
                display_mode = "block"
            else:
                display_mode = "inline"
            text = f"<math display='{display_mode}'>{text}</math>"
        elif self.highlight:
            text = f"<mark>{text}</mark>"
        elif self.subscript:
            text = f"<sub>{text}</sub>"
        elif self.superscript:
            text = f"<sup>{text}</sup>"
        elif self.underline:
            text = f"<u>{text}</u>"
        elif self.small:
            text = f"<small>{text}</small>"
        elif self.code:
            text = f"<code>{text}</code>"

        # Разворачиваем математические выражения
        text = unwrap_math(text)
        return text
