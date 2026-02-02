# Блок математического уравнения
# Представляет блочное математическое уравнение

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Математическое уравнение (блочное)
# Содержит математическую формулу, которая занимает отдельный блок текста
class Equation(Block):
    block_type: BlockTypes = BlockTypes.Equation  # Тип блока - уравнение
    html: str | None = None  # HTML представление уравнения (если было сгенерировано)
    block_description: str = "A block math equation."  # Описание для LLM

    # Собрать HTML представление уравнения
    def assemble_html(
        self, document, child_blocks, parent_structure=None, block_config=None
    ):
        if self.html:
            # Если HTML был сгенерирован LLM процессором
            child_ref_blocks = [
                block
                for block in child_blocks
                if block.id.block_type == BlockTypes.Reference
            ]
            html_out = super().assemble_html(
                document, child_ref_blocks, parent_structure, block_config
            )
            html_out += f"""<p block-type='{self.block_type}'>{self.html}</p>"""
            return html_out
        else:
            # Используем стандартную генерацию HTML с указанием типа блока
            template = super().assemble_html(
                document, child_blocks, parent_structure, block_config
            )
            return f"<p block-type='{self.block_type}'>{template}</p>"
