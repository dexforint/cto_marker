# Базовый класс для таблиц
# Предоставляет общую логику для работы с таблицами и их ячейками

from typing import List

from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput
from marker.schema.blocks.tablecell import TableCell


# Базовый класс таблицы, наследуемый от Block
# Содержит общую логику форматирования и рендеринга таблиц
class BaseTable(Block):
    block_type: BlockTypes | None = None  # Тип блока таблицы (переопределяется в наследниках)
    html: str | None = None  # HTML представление таблицы (если было сгенерировано LLM процессором)

    # Форматировать ячейки таблицы в HTML
    # Собирает ячейки по строкам и формирует таблицу
    # document: документ для получения блоков
    # child_blocks: дочерние блоки
    # block_config: конфигурация рендеринга
    # child_cells: список ячеек таблицы (опционально, если уже отфильтрован)
    @staticmethod
    def format_cells(
        document, child_blocks, block_config, child_cells: List[TableCell] | None = None
    ):
        if child_cells is None:
            # Если ячейки не переданы, фильтруем их из дочерних блоков
            child_cells: List[TableCell] = [
                document.get_block(c.id)  # Получаем блок по идентификатору
                for c in child_blocks
                if c.id.block_type == BlockTypes.TableCell  # Только ячейки таблицы
            ]

        # Получаем уникальные идентификаторы строк и сортируем их
        unique_rows = sorted(list(set([c.row_id for c in child_cells])))
        html_repr = "<table><tbody>"  # Начало HTML таблицы

        for row_id in unique_rows:
            # Получаем все ячейки для текущей строки и сортируем по столбцам
            row_cells = sorted(
                [c for c in child_cells if c.row_id == row_id], key=lambda x: x.col_id
            )
            html_repr += "<tr>"  # Начало строки таблицы
            for cell in row_cells:
                # Собираем HTML для каждой ячейки
                html_repr += cell.assemble_html(
                    document, child_blocks, None, block_config
                )
            html_repr += "</tr>"  # Конец строки таблицы

        html_repr += "</tbody></table>"  # Конец HTML таблицы
        return html_repr

    # Собрать HTML представление таблицы
    # Выбирает метод форматирования в зависимости от источника данных
    def assemble_html(
        self,
        document,
        child_blocks: List[BlockOutput],
        parent_structure=None,
        block_config: dict | None = None,
    ):
        # Фильтруем блоки, оставляя только ссылки (ячейки таблицы рендерятся отдельно)
        child_ref_blocks = [
            block
            for block in child_blocks
            if block.id.block_type == BlockTypes.Reference
        ]
        template = super().assemble_html(
            document, child_ref_blocks, parent_structure, block_config
        )

        # Определяем, какой источник данных использовать
        child_block_types = set([c.id.block_type for c in child_blocks])
        if self.html:
            # Данные были сгенерированы LLM процессором - используем готовый HTML
            return template + self.html
        elif len(child_blocks) > 0 and BlockTypes.TableCell in child_block_types:
            # Данные от Table процессора - форматируем ячейки
            return template + self.format_cells(document, child_blocks, block_config)
        else:
            # По умолчанию - просто текстовые строки и фрагменты
            return f"<p>{template}</p>"
