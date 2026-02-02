# Блок подписи
# Представляет текст подписи к изображению или таблице

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Подпись к изображению или таблице
# Содержит описательный текст, расположенный над или под элементом
class Caption(Block):
    block_type: BlockTypes = BlockTypes.Caption  # Тип блока - подпись
    block_description: str = "A text caption that is directly above or below an image or table. Only used for text describing the image or table.  "
    replace_output_newlines: bool = True  # Заменять переносы строк в выводе
    html: str | None = None  # HTML представление подписи (если было сгенерировано LLM процессором)

    # Собрать HTML представление подписи
    # Использует готовый HTML или стандартный метод из родительского класса
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        if self.html:
            # Если HTML был сгенерирован LLM процессором, используем его
            return super().handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Иначе используем стандартную генерацию HTML
        return super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
