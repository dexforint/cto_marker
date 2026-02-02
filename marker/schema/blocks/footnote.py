# Блок сноски
# Представляет дополнительную информацию внизу страницы

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Сноска документа
# Содержит пояснение к термину или концепцию в документе
class Footnote(Block):
    block_type: BlockTypes = BlockTypes.Footnote  # Тип блока - сноска
    block_description: str = (
        "A footnote that explains a term or concept in the document."
    )
    replace_output_newlines: bool = True  # Заменять переносы строк в выводе
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление сноски
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        if self.html:
            # Если HTML был сгенерирован LLM процессором, используем его
            return super().handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Иначе используем стандартную генерацию HTML
        return super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
