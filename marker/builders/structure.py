# Модуль строителя структуры документа
# Отвечает за группировку блоков на основе их структурных взаимосвязей и иерархии

from typing import Annotated

from marker.builders import BaseBuilder
from marker.schema import BlockTypes
from marker.schema.blocks import Text
from marker.schema.document import Document
from marker.schema.groups import ListGroup
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class


class StructureBuilder(BaseBuilder):
    """
    Строитель структуры документа для группировки блоков.
    
    Выполняет структурный анализ блоков и определяет их иерархию:
    1. Группирует таблицы/картинки с их подписями (captions)
    2. Объединяет последовательные элементы списков в группы
    3. Конвертирует несгруппированные элементы списков обратно в текст
    
    Атрибуты:
        gap_threshold: Минимальный разрыв между блоками для группировки (доля от высоты страницы)
        list_gap_threshold: Минимальный разрыв между элементами списка (доля от высоты страницы)
    """
    gap_threshold: Annotated[
        float,
        "The minimum gap between blocks to consider them part of the same group.",
    ] = 0.05
    list_gap_threshold: Annotated[
        float,
        "The minimum gap between list items to consider them part of the same group.",
    ] = 0.1

    def __init__(self, config=None):
        """
        Инициализирует строитель структуры.
        
        Аргументы:
            config: Опциональная конфигурация с порогами разрывов
        """
        super().__init__(config)

    def __call__(self, document: Document):
        """
        Применяет структурный анализ ко всем страницам документа.
        
        Последовательно выполняет:
        1. Группировку блоков с подписями (captions)
        2. Группировку элементов списков
        3. Преобразование несгруппированных элементов списков в текст
        
        Аргументы:
            document: Документ для обработки структуры
        """
        # Обрабатываем каждую страницу документа
        for page in document.pages:
            # Группируем таблицы, картинки и фигуры с их подписями
            self.group_caption_blocks(page)
            # Объединяем последовательные элементы списков в группы
            self.group_lists(page)
            # Преобразуем несгруппированные элементы списков в обычный текст
            self.unmark_lists(page)

    def group_caption_blocks(self, page: PageGroup):
        """
        Группирует блоки таблиц/фигур/изображений с подписью или сноской рядом.
        
        Логика:
        - Находим блоки Table/Figure/Picture в структуре страницы
        - Проверяем соседние блоки (предыдущий/следующий) на тип Caption/Footnote
        - Если подпись достаточно близко (по вертикальному разрыву), объединяем их в Group-блок
        - В структуре страницы заменяем исходный блок на новый Group-блок и удаляем объединённые элементы
        
        Аргументы:
            page: Страница (PageGroup) с блоками и структурным порядком
        """
        # Переводим относительный порог (доля высоты страницы) в пиксели
        gap_threshold_px = self.gap_threshold * page.polygon.height
        # Работаем по «снимку» структуры, чтобы безопасно менять page.structure внутри цикла
        static_page_structure = page.structure.copy()
        # Список id блоков, которые нужно удалить из структуры (потому что они станут частью группы)
        remove_ids = list()

        # Проходим по блокам в текущем порядке чтения страницы
        for i, block_id in enumerate(static_page_structure):
            # Достаём блок по id из страницы
            block = page.get_block(block_id)
            # Группируем подписи только для таблиц, фигур и картинок
            if block.block_type not in [BlockTypes.Table, BlockTypes.Figure, BlockTypes.Picture]:
                continue

            # Если блок уже включён в ранее созданную группу, пропускаем
            if block.id in remove_ids:
                continue

            # Структура будущего group-блока: начинаем с основного объекта (таблица/фигура/картинка)
            block_structure = [block_id]
            # Список полигонов, которые будут объединены для вычисления общего bounding polygon
            selected_polygons = [block.polygon]
            # Типы блоков, которые считаем подписью/сноской к объекту
            caption_types = [BlockTypes.Caption, BlockTypes.Footnote]

            # Берём соседние блоки в порядке чтения
            prev_block = page.get_prev_block(block)
            next_block = page.get_next_block(block)

            # Если подпись/сноска находится перед объектом и достаточно близко — включаем её в группу
            if prev_block and \
                prev_block.block_type in caption_types and \
                prev_block.polygon.minimum_gap(block.polygon) < gap_threshold_px and \
                    prev_block.id not in remove_ids:
                block_structure.insert(0, prev_block.id)
                selected_polygons.append(prev_block.polygon)

            # Если подпись/сноска находится после объекта и достаточно близко — включаем её в группу
            if next_block and \
                    next_block.block_type in caption_types and \
                    next_block.polygon.minimum_gap(block.polygon) < gap_threshold_px:
                block_structure.append(next_block.id)
                selected_polygons.append(next_block.polygon)

            # Создаём группу только если помимо основного блока нашлась ещё подпись/сноска
            if len(block_structure) > 1:
                # Подбираем класс Group-блока по имени типа: например, Table -> TableGroup
                new_block_cls = get_block_class(BlockTypes[block.block_type.name + "Group"])
                # Объединяем полигоны всех элементов группы, чтобы новый блок покрывал их целиком
                new_polygon = block.polygon.merge(selected_polygons)
                # Добавляем на страницу новый «групповой» блок
                group_block = page.add_block(new_block_cls, new_polygon)
                # Сохраняем структуру группы как список id исходных блоков
                group_block.structure = block_structure

                # Обновляем структуру страницы: заменяем исходный блок на новый group-блок
                page.update_structure_item(block_id, group_block.id)
                # Отмечаем исходные блоки группы как подлежащие удалению из структуры страницы
                remove_ids.extend(block_structure)
        # Удаляем все элементы, которые «переехали» внутрь group-блоков
        page.remove_structure_items(remove_ids)

    def group_lists(self, page: PageGroup):
        """
        Группирует последовательные элементы списков (ListItem) в ListGroup.
        
        Логика:
        - Ищем блоки типа ListItem в структуре страницы
        - Проверяем последующие блоки: если они тоже ListItem и расположены достаточно близко,
          добавляем их к текущей группе
        - Если найдено 2+ элемента — создаём ListGroup-блок и заменяем им эти элементы в структуре
        
        Аргументы:
            page: Страница с блоками списков
        """
        # Переводим относительный порог (доля высоты страницы) в пиксели
        gap_threshold_px = self.list_gap_threshold * page.polygon.height
        # Работаем со «снимком» структуры для безопасности
        static_page_structure = page.structure.copy()
        # Список id блоков, которые будут убраны из структуры (т.к. станут частью группы списка)
        remove_ids = list()
        
        # Проходим по каждому блоку на странице
        for i, block_id in enumerate(static_page_structure):
            # Достаём блок
            block = page.get_block(block_id)
            # Интересуют только элементы списка
            if block.block_type not in [BlockTypes.ListItem]:
                continue

            # Если блок уже в списке на удаление (вошёл в ранее созданную группу), пропускаем
            if block.id in remove_ids:
                continue

            # Стартуем новую группу элементов списка
            block_structure = [block_id]
            # Список полигонов будущей группы (для вычисления общего bounding box)
            selected_polygons = [block.polygon]

            # Проверяем последующие блоки на странице
            for j, next_block_id in enumerate(page.structure[i + 1:]):
                next_block = page.get_block(next_block_id)
                # Если следующий блок — тоже ListItem и достаточно близок к предыдущему элементу группы
                if all([
                    next_block.block_type == BlockTypes.ListItem,
                    next_block.polygon.minimum_gap(selected_polygons[-1]) < gap_threshold_px
                ]):
                    # Добавляем его в группу
                    block_structure.append(next_block_id)
                    selected_polygons.append(next_block.polygon)
                else:
                    # Как только встретили не-ListItem или слишком далёкий блок — прерываем группу
                    break

            # Создаём ListGroup только если в группе 2+ элемента
            if len(block_structure) > 1:
                # Объединяем полигоны всех элементов списка в один общий
                new_polygon = block.polygon.merge(selected_polygons)
                # Создаём новый блок типа ListGroup
                group_block = page.add_block(ListGroup, new_polygon)
                # Сохраняем структуру группы как список id исходных ListItem-блоков
                group_block.structure = block_structure

                # Обновляем структуру страницы: заменяем первый элемент на group-блок
                page.update_structure_item(block_id, group_block.id)
                # Помечаем все элементы группы как подлежащие удалению из структуры страницы
                remove_ids.extend(block_structure)

        # Удаляем все элементы, которые вошли в group-блоки
        page.remove_structure_items(remove_ids)

    def unmark_lists(self, page: PageGroup):
        """
        Преобразует несгруппированные ListItem-блоки обратно в обычный Text.
        
        Если после group_lists() на странице остались одиночные ListItem-блоки
        (не объединённые ни с чем), значит, они, вероятно, не являются частью
        настоящего списка. Преобразуем их в обычный текстовый блок.
        
        Аргументы:
            page: Страница для обработки
        """
        # Проходим по структуре страницы
        for block_id in page.structure:
            block = page.get_block(block_id)
            # Если находим одиночный ListItem (не вошедший в группу)
            if block.block_type == BlockTypes.ListItem:
                # Создаём новый текстовый блок с теми же координатами и структурой
                generated_block = Text(
                    polygon=block.polygon,
                    page_id=block.page_id,
                    structure=block.structure,
                )
                # Заменяем ListItem на Text
                page.replace_block(block, generated_block)
