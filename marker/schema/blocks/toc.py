# Блок оглавления
# Представляет таблицу содержания документа

from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


# Оглавление документа
# Содержит структуру оглавления с ссылками на разделы
# Наследует логику форматирования от BaseTable
class TableOfContents(BaseTable):
    block_type: str = BlockTypes.TableOfContents  # Тип блока - оглавление
    block_description: str = "A table of contents."  # Описание для LLM
