# Блок нижнего колонтитула страницы
# Представляет текст внизу страницы (например, номер страницы)

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Нижний колонтитул страницы
# Содержит текст, который появляется внизу каждой страницы
class PageFooter(Block):
    block_type: str = BlockTypes.PageFooter  # Тип блока - нижний колонтитул
    block_description: str = (
        "Text that appears at bottom of a page, like a page number."
    )
    replace_output_newlines: bool = True  # Заменять переносы строк в выводе
    ignore_for_output: bool = True  # Игнорировать при выводе (по умолчанию)
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление нижнего колонтитула
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        # Если конфигурация требует сохранение колонтитула, не игнорируем его
        if block_config and block_config.get("keep_pagefooter_in_output"):
            self.ignore_for_output = False

        if self.html and not self.ignore_for_output:
            # Если HTML был сгенерирован и блок не игнорируется, возвращаем его
            return self.html

        # Иначе используем стандартную генерацию HTML
        return super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
