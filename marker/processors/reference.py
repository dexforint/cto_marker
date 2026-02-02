# Модуль процессора ссылок/референсов
# Добавляет блоки Reference рядом с распознанными ссылками страницы (page.refs)

import numpy as np

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Reference
from marker.schema.document import Document
from marker.schema.groups.list import ListGroup
from marker.schema.groups.table import TableGroup
from marker.schema.registry import get_block_class
from marker.schema.groups.figure import FigureGroup


class ReferenceProcessor(BaseProcessor):
    """
    Процессор для добавления ссылок (Reference) в структуру документа.

    На некоторых источниках при извлечении текста формируются координаты ссылок
    (page.refs), но сами ссылки не представлены отдельными блоками.

    Этот процессор:
    - для каждой ссылки на странице находит ближайший текстовый/контентный блок
    - создаёт Reference-блок и вставляет его в начало структуры найденного блока
    """

    def __init__(self, config):
        """
        Инициализирует процессор.

        Аргументы:
            config: Конфигурация процессора
        """
        super().__init__(config)

    def __call__(self, document: Document):
        """
        Добавляет Reference-блоки ко всем страницам документа.

        Аргументы:
            document: Документ для обработки
        """
        # Получаем класс Reference из registry (чтобы корректно создавать pydantic-модель блока)
        ReferenceClass: Reference = get_block_class(BlockTypes.Reference)

        for page in document.pages:
            # Список распознанных ссылок на странице (каждая содержит ref и координату)
            refs = page.refs
            # Преобразуем стартовые координаты ссылок в numpy-массив для векторных вычислений
            ref_starts = np.array([ref.coord for ref in refs])

            blocks = []
            # Разворачиваем group-блоки (списки/таблицы/фигуры) до базовых элементов,
            # чтобы корректно найти ближайший «контентный» блок
            for block_id in page.structure:
                block = page.get_block(block_id)
                if isinstance(block, (ListGroup, FigureGroup, TableGroup)):
                    blocks.extend([page.get_block(b) for b in block.structure])
                else:
                    blocks.append(block)
            # Исключаем блоки, которые помечены как игнорируемые для вывода
            blocks = [b for b in blocks if not b.ignore_for_output]

            # Берём (x_start, y_start) каждого блока
            block_starts = np.array([block.polygon.bbox[:2] for block in blocks])

            # Если нет ссылок или нет блоков для привязки — пропускаем страницу
            if not (len(refs) and len(block_starts)):
                continue

            # Считаем евклидовы расстояния между каждым блоком и каждой ссылкой
            distances = np.linalg.norm(block_starts[:, np.newaxis, :] - ref_starts[np.newaxis, :, :], axis=2)
            for ref_idx in range(len(ref_starts)):
                # Находим индекс ближайшего блока к текущей ссылке
                block_idx = np.argmin(distances[:, ref_idx])
                block = blocks[block_idx]

                # Создаём Reference-блок и прикрепляем его к найденному блоку
                ref_block = page.add_full_block(ReferenceClass(
                    ref=refs[ref_idx].ref,
                    polygon=block.polygon,
                    page_id=page.page_id
                ))
                # Гарантируем, что у целевого блока есть структура
                if block.structure is None:
                    block.structure = []
                # Вставляем ссылку в начало структуры блока
                block.structure.insert(0, ref_block.id)
