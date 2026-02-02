# Блок верхнего колонтитула страницы
# Представляет текст вверху страницы (например, заголовок документа)

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Верхний колонтитул страницы
# Содержит текст, который появляется вверху каждой страницы
class PageHeader(Block):
    block_type: BlockTypes = BlockTypes.PageHeader  # Тип блока - верхний колонтитул
    block_description: str = (
        "Text that appears at top of a page, like a page title."
    )
    replace_output_newlines: bool = True  # Заменять переносы строк в выводе
    ignore_for_output: bool = True  # Игнорировать при выводе (по умолчанию)
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление верхнего колонтитула
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        # Если конфигурация требует сохранение колонтитула, не игнорируем его
        if block_config and block_config.get("keep_pageheader_in_output"):
            self.ignore_for_output = False

        if self.html and not self.ignore_for_output:
            # Если HTML был сгенерирован и блок не игнорируется, возвращаем его
            return self.html

        # Иначе используем стандартную генерацию HTML
        return super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
