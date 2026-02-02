# Блок рукописного текста
# Представляет область с рукописным содержанием

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Рукописный текст
# Содержит текст, написанный от руки
class Handwriting(Block):
    block_type: BlockTypes = BlockTypes.Handwriting  # Тип блока - рукописный текст
    block_description: str = "A region that contains handwriting."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано)
    replace_output_newlines: bool = True  # Заменять переносы строк в выводе

    # Собрать HTML представление рукописного текста
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        if self.html:
            # Если HTML уже сгенерирован, используем его
            return self.html
        else:
            # Иначе используем стандартную генерацию HTML
            return super().assemble_html(
                document, child_blocks, parent_structure, block_config
            )
