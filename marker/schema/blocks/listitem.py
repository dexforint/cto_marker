# Блок элемента списка
# Представляет отдельный пункт маркированного или нумерованного списка

import re

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Заменить символы маркеров в тексте на дефис
# Удаляет символы маркеров (•, ●, ○, и т.д.) из начала текста
def replace_bullets(child_blocks):
    # Заменяем символы маркеров на -
    first_block = None
    while len(child_blocks) > 0:
        first_block = child_blocks[0]
        child_blocks = first_block.children

    # Если нашли строку текста, удаляем символ маркера
    if first_block is not None and first_block.id.block_type == BlockTypes.Line:
        # Паттерн для разных типов маркеров
        bullet_pattern = r"(^|[\n ]|<[^>]*>)[•●○ഠ ം◦■▪▫–—-]( )"
        first_block.html = re.sub(bullet_pattern, r"\1\2", first_block.html)


# Элемент списка
# Представляет отдельный пункт маркированного или нумерованного списка
class ListItem(Block):
    block_type: BlockTypes = BlockTypes.ListItem  # Тип блока - элемент списка
    list_indent_level: int = 0  # Уровень вложенности списка
    block_description: str = "A list item that is part of a list.  This block is used to represent a single item in a list."
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление элемента списка
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        # Собираем базовый шаблон HTML
        template = super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
        template = template.replace("\n", " ")  # Заменяем переносы строк на пробелы
        # Удаляем первый символ маркера
        replace_bullets(child_blocks)

        if self.html:
            # Если HTML был сгенерирован LLM процессором
            template = (
                super()
                .handle_html_output(
                    document, child_blocks, parent_structure, block_config
                )
                .strip()
            )
            template = template.replace("<li>", "").replace("</li>", "")  # Удаляем лишние теги li

        # Формируем атрибуты элемента списка
        el_attr = f" block-type='{self.block_type}'"
        if self.list_indent_level:
            # Если есть вложенность, оборачиваем в ul с классом уровня
            return f"<ul><li{el_attr} class='list-indent-{self.list_indent_level}'>{template}</li></ul>"
        return f"<li{el_attr}>{template}</li>"
