# Блок формы
# Представляет форму с полями для ввода данных

from typing import List

from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


# Форма документа (например, налоговая декларация)
# Содержит поля и метки, обычно без строгой табличной структуры
# Наследует логику форматирования от BaseTable
class Form(BaseTable):
    block_type: BlockTypes = BlockTypes.Form  # Тип блока - форма
    block_description: str = "A form, such as a tax form, that contains fields and labels.  It most likely doesn't have a table structure."
