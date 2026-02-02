# Блок изображения
# Представляет картинку или фотографию

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Изображение/картинка
# Содержит изображение или фотографию
class Picture(Block):
    block_type: BlockTypes = BlockTypes.Picture  # Тип блока - изображение
    description: str | None = None  # Описание изображения
    block_description: str = "An image block that represents a picture."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано LLM процессором)

    # Собрать HTML представление изображения
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        if self.html:
            # Если HTML был сгенерирован LLM процессором, используем его
            return super().handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Фильтруем только ссылки для избежания дублирования
        child_ref_blocks = [
            block
            for block in child_blocks
            if block.id.block_type == BlockTypes.Reference
        ]
        html = super().assemble_html(
            document, child_ref_blocks, parent_structure, block_config
        )

        # Добавляем описание изображения если доступно
        if self.description:
            return (
                html
                + f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
            )
        return html
