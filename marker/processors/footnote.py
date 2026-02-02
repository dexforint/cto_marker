# Модуль процессора сносок
# Перемещает блоки Footnote в конец страницы и помечает номера сносок как верхний индекс

import re

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups import PageGroup


class FootnoteProcessor(BaseProcessor):
    """
    Процессор для обработки сносок (footnotes).

    Выполняет две основные задачи:
    1. Перемещает top-level блоки Footnote в конец структуры страницы (чтобы они шли после основного текста)
    2. Помечает первые span'ы в сноске как верхний индекс, если они выглядят как номер (например, "1" или "[2]")
    """
    block_types = (BlockTypes.Footnote,)

    def __call__(self, document: Document):
        """
        Применяет обработку сносок ко всем страницам документа.

        Аргументы:
            document: Документ для обработки
        """
        # Обрабатываем каждую страницу отдельно
        for page in document.pages:
            self.push_footnotes_to_bottom(page, document)
            self.assign_superscripts(page, document)

    def push_footnotes_to_bottom(self, page: PageGroup, document: Document):
        """
        Перемещает top-level сноски в конец структуры страницы.

        Аргументы:
            page: Страница, структура которой будет изменена
            document: Документ, используемый для поиска блоков на странице
        """
        # Находим все блоки сносок на странице
        footnote_blocks = page.contained_blocks(document, self.block_types)

        # Перемещаем сноски в конец структуры страницы
        for block in footnote_blocks:
            # Двигаем только те сноски, которые находятся на верхнем уровне структуры
            if block.id in page.structure:
                # Удаляем из текущего места и добавляем в конец
                page.structure.remove(block.id)
                page.add_structure(block)

    def assign_superscripts(self, page: PageGroup, document: Document):
        """
        Помечает номер сноски как верхний индекс (superscript).

        Эвристика: если первый Span внутри блока Footnote начинается с цифр/небуквенных символов,
        считаем это маркером сноски и выставляем span.has_superscript = True.

        Аргументы:
            page: Страница со сносками
            document: Документ для доступа к вложенным span-блокам
        """
        # Получаем все блоки сносок
        footnote_blocks = page.contained_blocks(document, self.block_types)

        # Для каждой сноски пытаемся найти её «номер» в первом span
        for block in footnote_blocks:
            for span in block.contained_blocks(document, (BlockTypes.Span,)):
                # Если span начинается с цифры или небуквенных символов — помечаем как верхний индекс
                if re.match(r"^[0-9\W]+", span.text):
                    span.has_superscript = True
                # Проверяем только первый span, дальше не нужно
                break
