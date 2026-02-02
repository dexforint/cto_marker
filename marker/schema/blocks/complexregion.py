# Сложный регион (mixed content)
# Представляет область документа с разными типами блоков и изображениями

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Сложный регион с разнородным контентом
# Используется когда трудно классифицировать область как один тип блока
# Может содержать смесь текста, изображений и других элементов
class ComplexRegion(Block):
    block_type: BlockTypes = BlockTypes.ComplexRegion  # Тип блока - сложный регион
    html: str | None = None  # HTML представление региона (если было сгенерировано LLM процессором)
    block_description: str = "A complex region that can consist of multiple different types of blocks mixed with images. This block is chosen when it is difficult to categorize the region as a single block type."

    # Собрать HTML представление сложного региона
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        if self.html:
            # Если HTML был сгенерирован LLM процессором
            # Фильтруем только ссылки для избежания дублирования
            child_ref_blocks = [
                block
                for block in child_blocks
                if block.id.block_type == BlockTypes.Reference
            ]
            # Собираем базовый шаблон и добавляем готовый HTML
            html = super().assemble_html(
                document, child_ref_blocks, parent_structure, block_config
            )
            return html + self.html
        else:
            # Используем стандартную генерацию HTML
            template = super().assemble_html(
                document, child_blocks, parent_structure, block_config
            )
            return f"<p>{template}</p>"  # Обертываем в параграф
