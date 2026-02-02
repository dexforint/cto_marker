# Блок таблицы
# Представляет табличные данные

from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


# Таблица данных
# Содержит данные в табличном формате, например, таблица результатов
# Наследует логику форматирования от BaseTable
class Table(BaseTable):
    block_type: BlockTypes = BlockTypes.Table  # Тип блока - таблица
    block_description: str = "A table of data, like a results table.  It will be in a tabular format."
