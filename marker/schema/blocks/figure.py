# Блок рисунка/диаграммы
# Представляет изображение с данными (график, диаграмма и т.д.)

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Рисунок или диаграмма с данными
# Содержит изображение, представляющее визуализацию данных
class Figure(Block):
    block_type: BlockTypes = BlockTypes.Figure  # Тип блока - рисунок
    description: str | None = None  # Описание рисунка
    html: str | None = None  # HTML представление (если было сгенерировано LLM процессором)
    block_description: str = "A chart or other image that contains data."  # Описание для LLM

    # Собрать HTML представление рисунка
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
            html += f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
        return html
