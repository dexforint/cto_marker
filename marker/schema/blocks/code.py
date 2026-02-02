# Блок программного кода
# Представляет фрагмент программного кода

import html

from marker.schema import BlockTypes
from marker.schema.blocks import Block


# Блок программного кода
# Содержит фрагмент кода, который должен быть выведен в моноширинном шрифте
class Code(Block):
    block_type: BlockTypes = BlockTypes.Code  # Тип блока - код
    code: str | None = None  # Текст программного кода
    html: str | None = None  # HTML представление кода (если было сгенерировано)
    block_description: str = "A programming code block."  # Описание для LLM

    # Собрать HTML представление блока кода
    # Экранирует специальные символы HTML и обертывает в тег <pre>
    def assemble_html(self, document, child_blocks, parent_structure, block_config):
        if self.html:
            # Если HTML уже сгенерирован, используем его
            return self.html
        code = self.code or ""  # Получаем код или пустую строку
        # Экранируем спецсимволы HTML и обертываем в тег <pre>
        return f"<pre>{html.escape(code)}</pre>"
