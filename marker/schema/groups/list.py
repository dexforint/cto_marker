# Группа списка
# Группирует элементы списка вместе для совместного рендеринга

from marker.schema import BlockTypes
from marker.schema.groups.base import Group


# Группа элементов списка
# Содержит несколько элементов списка, которые должны рендериться вместе
class ListGroup(Group):
    block_type: BlockTypes = BlockTypes.ListGroup  # Тип блока - группа списка
    has_continuation: bool = False  # Имеет ли продолжение на следующей строке
    block_description: str = "A group of list items that should be rendered together."  # Описание для LLM
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление группы списка
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        if self.html:
            # Если HTML был сгенерирован LLM процессором
            return self.handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Собираем базовый шаблон HTML
        template = super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )

        # Формируем атрибуты элемента
        el_attr = f" block-type='{self.block_type}'"
        if self.has_continuation:
            el_attr += " class='has-continuation'"  # Добавляем класс для продолжения

        # Оборачиваем в параграф с маркированным списком
        return f"<p{el_attr}><ul>{template}</ul></p>"
