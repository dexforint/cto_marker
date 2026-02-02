# Блок ссылки
# Представляет ссылку на другой блок в документе

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Ссылка на блок
# Используется для создания ссылок из одного блока на другой
class Reference(Block):
    block_type: BlockTypes = BlockTypes.Reference  # Тип блока - ссылка
    ref: str  # Идентификатор ссылки (anchor)
    block_description: str = "A reference to this block from another block."

    # Собрать HTML представление ссылки
    # Оборачивает контент в span с атрибутом id для создания якоря
    def assemble_html(
        self, document, child_blocks, parent_structure=None, block_config=None
    ):
        template = super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
        return f"<span id='{self.ref}'>{template}</span>"
