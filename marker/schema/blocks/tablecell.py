# Блок ячейки таблицы
# Представляет отдельную ячейку в таблице

from typing import List

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Ячейка таблицы
# Содержит данные одной ячейки таблицы с информацией о её положении
class TableCell(Block):
    block_type: BlockTypes = BlockTypes.TableCell  # Тип блока - ячейка таблицы
    rowspan: int  # Количество строк, которые занимает ячейка
    colspan: int  # Количество столбцов, которые занимает ячейка
    row_id: int  # Идентификатор строки таблицы
    col_id: int  # Идентификатор столбца таблицы
    is_header: bool  # Является ли ячейка заголовком (th вместо td)
    text_lines: List[str] | None = None  # Список строк текста в ячейке
    block_description: str = "A cell in a table."

    # Свойство для получения полного текста ячейки
    @property
    def text(self):
        return "\n".join(self.text_lines)  # Объединяем строки в один текст

    # Собрать HTML представление ячейки таблицы
    def assemble_html(
        self, document, child_blocks, parent_structure=None, block_config=None
    ):
        add_cell_id = block_config and block_config.get("add_block_ids", False)

        # Определяем тег: th для заголовка, td для обычной ячейки
        tag_cls = "th" if self.is_header else "td"
        tag = f"<{tag_cls}"

        # Добавляем атрибуты rowspan и colspan если нужно
        if self.rowspan > 1:
            tag += f" rowspan={self.rowspan}"
        if self.colspan > 1:
            tag += f" colspan={self.colspan}"

        # Добавляем идентификатор блока если требуется в конфигурации
        if add_cell_id:
            tag += f' data-block-id="{self.id}"'

        # Формируем текст ячейки (объединяем строки через <br>)
        if self.text_lines is None:
            self.text_lines = []
        text = "<br>".join(self.text_lines)

        return f"{tag}>{text}</{tag_cls}>"
