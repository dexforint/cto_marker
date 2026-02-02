# Группа картинок
# Группирует изображение с подписями и другими связанными элементами

from marker.schema import BlockTypes
from marker.schema.groups.base import Group


# Группа картинок
# Содержит изображение и связанные с ним подписи
class PictureGroup(Group):
    block_type: BlockTypes = BlockTypes.PictureGroup  # Тип блока - группа картинок
    block_description: str = "A picture along with associated captions."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление группы картинок
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
