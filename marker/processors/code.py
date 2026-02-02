# Модуль процессора кода
# Форматирует Code-блоки, восстанавливая отступы по координатам строк

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Code
from marker.schema.document import Document


class CodeProcessor(BaseProcessor):
    """
    Процессор для форматирования блоков кода.
    
    Идея: строки кода часто распознаются как отдельные Line-блоки.
    Чтобы получить читабельный код, необходимо восстановить пробельные отступы,
    используя координаты строк (x_start) и оценку средней ширины символа.
    """
    block_types = (BlockTypes.Code, )

    def __call__(self, document: Document):
        """
        Форматирует все блоки кода в документе.
        
        Аргументы:
            document: Документ для обработки
        """
        # Проходим по страницам и находим Code-блоки
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                self.format_block(document, block)


    def format_block(self, document: Document, block: Code):
        """
        Восстанавливает текст кода для одного Code-блока.
        
        Алгоритм:
        1. Находим минимальную левую координату среди строк (это «нулевая колонка»)
        2. Оцениваем среднюю ширину символа по (суммарная ширина строк / количество символов)
        3. Для каждой строки вычисляем количество пробелов, соответствующее её сдвигу вправо
        4. Добавляем отступы и собираем итоговый code_text
        
        Аргументы:
            document: Документ, из которого берутся Line-блоки
            block: Code-блок, который нужно отформатировать
        """
        # Минимальная левая координата (приблизительная позиция «0-го столбца»)
        min_left = 9999  # will contain x- coord of column 0
        # Суммарная ширина строк (для оценки средней ширины символа)
        total_width = 0
        # Суммарное количество символов во всех строках
        total_chars = 0
        
        # Получаем все строки, входящие в кодовый блок
        contained_lines = block.contained_blocks(document, (BlockTypes.Line,))
        for line in contained_lines:
            # Обновляем минимальную левую координату
            min_left = min(line.polygon.bbox[0], min_left)
            # Накопление ширины и количества символов для оценки avg_char_width
            total_width += line.polygon.width
            total_chars += len(line.raw_text(document))

        # Средняя ширина символа (защита от деления на ноль через max(..., 1))
        avg_char_width = total_width / max(total_chars, 1)
        # Итоговый текст кода
        code_text = ""
        # Флаг: предыдущая строка закончилась символом переноса строки
        is_new_line = False
        for line in contained_lines:
            text = line.raw_text(document)
            # Если не удалось оценить ширину символа, отступы восстановить нельзя
            if avg_char_width == 0:
                prefix = ""
            else:
                # Считаем, сколько «символьных позиций» соответствует сдвигу строки относительно min_left
                total_spaces = int((line.polygon.bbox[0] - min_left) / avg_char_width)
                prefix = " " * max(0, total_spaces)

            # Добавляем отступ только если строка реально начинается «с новой строки»
            if is_new_line:
                text = prefix + text

            # Конкатенируем строки в общий текст
            code_text += text
            # Обновляем флаг конца строки
            is_new_line = text.endswith("\n")

        # Записываем текст кода в блок (rstrip убирает лишние переводы строк в конце)
        block.code = code_text.rstrip()
