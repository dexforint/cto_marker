# Модуль процессора игнорируемого текста
# Находит повторяющиеся текстовые элементы (например, колонтитулы/номера страниц)
# и помечает соответствующие блоки как ignore_for_output

import re
from collections import Counter
from itertools import groupby
from typing import Annotated, List

from rapidfuzz import fuzz

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document


class IgnoreTextProcessor(BaseProcessor):
    """
    Процессор для выявления и игнорирования повторяющихся текстовых блоков.

    Часто в PDF встречаются элементы, которые повторяются на многих страницах:
    - верхние и нижние колонтитулы
    - номера страниц
    - одинаковые заголовки/подписи

    Эти элементы обычно не должны попадать в итоговый вывод, поэтому процессор
    помечает соответствующие блоки флагом ignore_for_output = True.
    """
    block_types = (
        BlockTypes.Text, BlockTypes.SectionHeader,
        BlockTypes.TextInlineMath
    )
    common_element_threshold: Annotated[
        float,
        "The minimum ratio of pages a text block must appear on to be considered a common element.",
        "Blocks that meet or exceed this threshold are marked as common elements.",
    ] = 0.2
    common_element_min_blocks: Annotated[
        int,
        "The minimum number of occurrences of a text block within a document to consider it a common element.",
        "This ensures that rare blocks are not mistakenly flagged.",
    ] = 3
    max_streak: Annotated[
        int,
        "The maximum number of consecutive occurrences of a text block allowed before it is classified as a common element.",
        "Helps to identify patterns like repeated headers or footers.",
    ] = 3
    text_match_threshold: Annotated[
        int,
        "The minimum fuzzy match score (0-100) required to classify a text block as similar to a common element.",
        "Higher values enforce stricter matching.",
    ] = 90

    def __call__(self, document: Document):
        """
        Выполняет поиск повторяющихся текстовых блоков в документе и помечает их для игнорирования.

        Алгоритм работает с первыми и последними блоками на каждой странице,
        так как именно там чаще всего располагаются колонтитулы и номера страниц.

        Аргументы:
            document: Документ для обработки
        """
        # Собираем первые и последние текстовые блоки на каждой странице
        first_blocks = []
        last_blocks = []
        for page in document.pages:
            initial_block = None
            last_block = None
            # Проходим по всем текстовым блокам на странице
            for block in page.contained_blocks(document, self.block_types):
                if block.structure is not None:
                    # Запоминаем первый блок, встреченный на странице
                    if initial_block is None:
                        initial_block = block

                    # Обновляем последний блок (в конце цикла будет реально последний)
                    last_block = block

            if initial_block is not None:
                first_blocks.append(initial_block)
            if last_block is not None:
                last_blocks.append(last_block)

        # Фильтруем повторяющиеся элементы среди первых блоков (верхние колонтитулы)
        self.filter_common_elements(document, first_blocks)
        # Фильтруем повторяющиеся элементы среди последних блоков (нижние колонтитулы)
        self.filter_common_elements(document, last_blocks)

    @staticmethod
    def clean_text(text):
        """
        Очищает текст от переносов строк и номеров страниц для корректного сравнения.

        Удаляет цифры в начале и в конце строки, чтобы текст типа "1 Заголовок"
        и "2 Заголовок" сравнивались как одинаковые (отличаются только номером страницы).

        Аргументы:
            text: Текст для очистки

        Возвращает:
            Очищенный текст
        """
        # Убираем переносы строк и лишние пробелы
        text = text.replace("\n", "").strip()
        # Удаляем цифры в начале строки
        text = re.sub(r"^\d+\s*", "", text)
        # Удаляем цифры в конце строки
        text = re.sub(r"\s*\d+$", "", text)
        return text

    def filter_common_elements(self, document, blocks: List[Block]):
        """
        Помечает повторяющиеся блоки для игнорирования.

        Эвристики:
        - Если блок встречается на >20% страниц (или в длинной последовательности) — считается общим
        - Используется нечёткое сравнение (fuzzy matching) для учёта мелких отличий
        - Общие блоки помечаются как ignore_for_output = True

        Аргументы:
            document: Документ (используется для извлечения текста блоков)
            blocks: Список блоков для анализа (например, первые блоки всех страниц)
        """
        # Не можем провести статистический анализ на малом количестве блоков
        if len(blocks) < self.common_element_min_blocks:
            return

        # Очищаем текст каждого блока (удаляем номера страниц, переносы строк и т.д.)
        text = [self.clean_text(b.raw_text(document)) for b in blocks]

        # Считаем максимальную длину последовательности (streak) каждого уникального текста
        # Это помогает находить подряд идущие одинаковые блоки (например, колонтитул на каждой странице)
        streaks = {}
        for key, group in groupby(text):
            streaks[key] = max(streaks.get(key, 0), len(list(group)))

        # Считаем сколько раз каждый текст встречается в общем
        counter = Counter(text)
        # Определяем общие (часто встречающиеся) элементы по критериям:
        # 1. встречаются на >= 20% страниц OR длинная серия подряд (>= max_streak)
        # 2. встречаются больше чем common_element_min_blocks раз
        common = [
            k for k, v in counter.items()
            if (v >= len(blocks) * self.common_element_threshold or streaks[k] >= self.max_streak)
            and v > self.common_element_min_blocks
        ]
        # Если общих элементов нет — нечего помечать
        if len(common) == 0:
            return

        # Помечаем блоки, которые похожи на общие элементы
        for t, b in zip(text, blocks):
            # Проверяем нечёткое совпадение (fuzzy match) с каждым общим элементом
            if any(fuzz.ratio(t, common_element) > self.text_match_threshold for common_element in common):
                b.ignore_for_output = True
