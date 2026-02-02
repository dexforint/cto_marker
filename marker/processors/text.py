# Модуль процессора текста
# Отвечает за выявление переносов текста между колонками и страницами
# и помечает текстовые блоки флагом продолжения (has_continuation)

import math
from typing import Annotated, List

import regex

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.text.line import Line


class TextProcessor(BaseProcessor):
    """
    Процессор для анализа непрерывности текста между блоками.
    
    Основная задача — определить ситуации, когда следующий текстовый блок
    является продолжением предыдущего, но разрыв вызван:
    - переходом на следующую колонку
    - переходом на следующую страницу
    
    Если процессор решает, что следующий блок — продолжение, он устанавливает
    у текущего блока флаг has_continuation = True.
    """

    # Типы блоков, для которых применяется логика поиска продолжения текста
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)
    # Типы блоков, которые не должны влиять на поиск следующего текста (например, колонтитулы)
    ignored_block_types = (BlockTypes.PageHeader, BlockTypes.PageFooter)
    column_gap_ratio: Annotated[
        float,
        "The minimum ratio of the page width to the column gap to consider a column break.",
    ] = 0.02

    def __init__(self, config):
        """
        Инициализирует процессор текста.

        Аргументы:
            config: Конфигурация процессора (например, column_gap_ratio)
        """
        super().__init__(config)

    def __call__(self, document: Document):
        """
        Анализирует текстовые блоки документа и помечает те, у которых есть продолжение.

        Проходит по страницам и по текстовым блокам. Для каждого блока проверяет,
        является ли следующий текстовый блок продолжением (через эвристики колонок/страниц).

        Аргументы:
            document: Документ для обработки
        """
        # Проходим по всем страницам документа
        for page in document.pages:
            # Находим все текстовые блоки на странице
            for block in page.contained_blocks(document, self.block_types):
                # Пропускаем блоки без внутренней структуры (без линий)
                if block.structure is None:
                    continue

                # Пропускаем одиночные строки (нет смысла искать продолжение)
                if not len(block.structure) >= 2:
                    continue

                # Получаем следующий текстовый блок (пропуская игнорируемые типы, например, колонтитулы)
                next_block = document.get_next_block(block, self.ignored_block_types)
                # Если достигнут конец документа, продолжение невозможно
                if next_block is None:
                    continue
                # Если следующий блок не текстовый, продолжение невозможно
                if next_block.block_type not in self.block_types:
                    continue
                # Пропускаем следующий блок, если у него нет структуры
                if next_block.structure is None:
                    continue
                # Пропускаем блоки, помеченные как игнорируемые при выводе
                if next_block.ignore_for_output:
                    continue

                # Вычисляем минимальный разрыв между колонками в пикселях
                column_gap = block.polygon.width * self.column_gap_ratio

                # Флаги для определения типа разрыва и характеристик блоков
                column_break, page_break = False, False
                next_block_starts_indented = True
                next_block_in_first_quadrant = False
                last_line_is_full_width = False
                last_line_is_hyphentated = False

                # Проверяем, на одной ли странице находятся блоки
                if next_block.page_id == block.page_id:
                    # Проверяем разрыв колонки: следующий блок начинается на той же высоте или выше,
                    # но справа от текущего блока с учётом разрыва колонки
                    column_break = math.floor(next_block.polygon.y_start) <= math.ceil(
                        block.polygon.y_start
                    ) and next_block.polygon.x_start > (
                        block.polygon.x_end + column_gap
                    )
                else:
                    # Блоки на разных страницах — это разрыв страницы
                    page_break = True
                    next_page = document.get_page(next_block.page_id)
                    # Проверяем, начинается ли следующий блок в первой четверти страницы
                    # (типичное положение начала новой страницы при продолжении текста)
                    next_block_in_first_quadrant = (
                        next_block.polygon.x_start < next_page.polygon.width // 2
                    ) and (next_block.polygon.y_start < next_page.polygon.height // 2)

                # Если нет ни разрыва колонки, ни разрыва страницы, продолжать не имеет смысла
                if not (column_break or page_break):
                    continue

                # Получаем строки следующего блока
                new_block_lines = next_block.structure_blocks(document)

                # Проверяем, начинается ли следующий блок с отступа (абзац)
                if len(new_block_lines):
                    # Находим минимальную левую координату среди всех строк следующего блока
                    min_x = math.ceil(
                        min([line.polygon.x_start for line in new_block_lines])
                    )
                    # Если первая строка начинается правее минимума — это отступ (новый абзац)
                    next_block_starts_indented = (
                        new_block_lines[0].polygon.x_start > min_x
                    )

                # Получаем непустые строки текущего блока (ширина > 1)
                lines: List[Line] = [
                    line
                    for line in block.structure_blocks(document)
                    if line.polygon.width > 1
                ]
                if len(lines):
                    # Находим максимальную правую координату среди всех строк
                    max_x = math.floor(max([line.polygon.x_end for line in lines]))
                    # Проверяем, заканчивается ли последняя строка на полную ширину
                    last_line_is_full_width = lines[-1].polygon.x_end >= max_x

                    # Проверяем, заканчивается ли последняя строка дефисом (перенос слова)
                    # Регулярка ищет строчную букву или цифру, за которой идёт дефис в конце строки
                    last_line_is_hyphentated = regex.compile(
                        r".*[\p{Ll}|\d][-—¬]\s?$", regex.DOTALL
                    ).match(lines[-1].raw_text(document).strip())

                # Условия для установки флага продолжения:
                # 1. Последняя строка на полную ширину ИЛИ заканчивается дефисом (перенос)
                # 2. Следующий блок НЕ начинается с отступа (не новый абзац)
                # 3. Есть разрыв колонки ИЛИ (разрыв страницы + следующий блок в первой четверти)
                if (
                    (last_line_is_full_width or last_line_is_hyphentated)
                    and not next_block_starts_indented
                    and ((next_block_in_first_quadrant and page_break) or column_break)
                ):
                    # Помечаем текущий блок как имеющий продолжение
                    block.has_continuation = True
