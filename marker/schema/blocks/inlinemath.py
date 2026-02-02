# Блок текста с inline математическими формулами
# Представляет текст, содержащий математику внутри параграфа

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Текст с inline математическими формулами
# Используется для текста, содержащего математические выражения внутри строки
# Не используется для курсива или ссылок - только для математики
class InlineMath(Block):
    block_type: BlockTypes = BlockTypes.TextInlineMath  # Тип блока - текст с inline математикой
    has_continuation: bool = False  # Имеет ли продолжение на следующей строке
    blockquote: bool = False  # Является ли блок цитатой
    blockquote_level: int = 0  # Уровень вложенности цитаты
    block_description: str = "A text block that contains inline math.  This is not used for italic text or references - only for text that contains math."
    html: str | None = None  # HTML представление (если было сгенерировано)

    # Собрать HTML представление текста с inline математикой
    def assemble_html(
        self, document, child_blocks, parent_structure, block_config=None
    ):
        # Если блок нужно проигнорировать в выводе
        if self.ignore_for_output:
            return ""

        if self.html:
            # Если HTML был сгенерирован LLM процессором
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
