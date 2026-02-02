# Группа рисунков
# Группирует рисунок с подписями и другими связанными элементами

from marker.schema import BlockTypes
from marker.schema.groups.base import Group


# Группа рисунков
# Содержит рисунок и связанные с ним подписи
class FigureGroup(Group):
    block_type: BlockTypes = BlockTypes.FigureGroup  # Тип блока - группа рисунков
    block_description: str = "A group that contains a figure and associated captions."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление группы рисунков
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        if self.html:
            # Если HTML уже сгенерирован, возвращаем его
            return self.html

        # Иначе используем стандартную генерацию HTML для дочерних блоков
        child_html = super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
        return child_html
