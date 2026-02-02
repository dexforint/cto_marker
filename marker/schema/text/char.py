# Отдельный символ
# Представляет один символ внутри фрагмента текста (span)

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Символ
# Минимальная текстовая единица внутри span
class Char(Block):
    block_type: BlockTypes = BlockTypes.Char  # Тип блока - символ
    block_description: str = "A single character inside a span."

    text: str  # Сам символ
    idx: int  # Индекс символа в span
