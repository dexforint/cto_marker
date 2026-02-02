# Блок текста
# Представляет обычный текстовый параграф

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Текстовый блок
# Содержит абзац или строку обычного текста
class Text(Block):
    block_type: BlockTypes = BlockTypes.Text  # Тип блока - текст
    has_continuation: bool = False  # Имеет ли продолжение на следующей строке
    blockquote: bool = False  # Является ли блок цитатой
    blockquote_level: int = 0  # Уровень вложенности цитаты
    html: str | None = None  # HTML представление (если было сгенерировано)
    block_description: str = "A paragraph or line of text."  # Описание для LLM

    # Собрать HTML представление текста
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        # Если блок нужно проигнорировать в выводе
        if self.ignore_for_output:
            return ""

        # Это происходит когда использовался LLM процессор
        if self.html:
            return super().handle_html_output(
                document, child_blocks, parent_structure, block_config
            )

        # Собираем базовый шаблон HTML
        template = super().assemble_html(
            document, child_blocks, parent_structure, block_config
        )
        template = template.replace("\n", " ")  # Заменяем переносы строк на пробелы

        # Формируем атрибуты элемента
        el_attr = f" block-type='{self.block_type}'"
        if self.has_continuation:
            el_attr += " class='has-continuation'"  # Добавляем класс для продолжения

        if self.blockquote:
            # Добавляем отступы для уровней цитаты
            blockquote_prefix = "<blockquote>" * self.blockquote_level
            blockquote_suffix = "</blockquote>" * self.blockquote_level
            return f"{blockquote_prefix}<p{el_attr}>{template}</p>{blockquote_suffix}"
        else:
            return f"<p{el_attr}>{template}</p>"
