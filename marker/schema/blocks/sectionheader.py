# Блок заголовка раздела
# Представляет заголовок раздела документа (H1, H2, H3 и т.д.)

from typing import Optional

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Заголовок раздела документа
# Содержит заголовок уровня (например, H1, H2, H3)
class SectionHeader(Block):
    block_type: BlockTypes = BlockTypes.SectionHeader  # Тип блока - заголовок раздела
    heading_level: Optional[int] = None  # Уровень заголовка (1 для H1, 2 для H2 и т.д.)
    block_description: str = "The header of a section of text or other blocks."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление заголовка раздела
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        # Если блок нужно проигнорировать в выводе
        if self.ignore_for_output:
            return ""

        if self.html:
            # Если HTML был сгенерирован LLM процессором
            return super().handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Собираем базовый шаблон HTML
        template = super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
        template = template.replace("\n", " ")  # Заменяем переносы строк на пробелы
        # Определяем тег заголовка (h1, h2, h3 и т.д.)
        tag = f"h{self.heading_level}" if self.heading_level else "h2"
        return f"<{tag}>{template}</{tag}>"
