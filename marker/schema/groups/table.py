# Группа таблиц
# Группирует таблицу с подписями и другими связанными элементами

from typing import List

from marker.schema import BlockTypes
from marker.schema.blocks import BlockOutput
from marker.schema.groups.base import Group


# Группа таблиц
# Содержит таблицу и связанные с ней подписи
class TableGroup(Group):
    block_type: BlockTypes = BlockTypes.TableGroup  # Тип блока - группа таблиц
    block_description: str = "A table along with associated captions."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление группы таблиц
    def assemble_html(
        self,
        document,
        child_blocks: List[BlockOutput],
        parent_structure=None,
        block_config: dict | None = None,
    ):
        if self.html:
            # Если HTML был сгенерирован LLM процессором
            return self.handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Иначе используем стандартную генерацию HTML
        return super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
