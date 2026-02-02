# Модель страницы документа
# Содержит все блоки, изображения и методы для работы с содержимым страницы

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

from PIL import Image, ImageDraw

from pdftext.schema import Reference
from pydantic import computed_field

from marker.providers import ProviderOutput
from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockId, Text
from marker.schema.blocks.base import BlockMetadata
from marker.schema.groups.base import Group
from marker.schema.polygon import PolygonBox
from marker.util import matrix_intersection_area, sort_text_lines

# Тип для отображения строк к результатам провайдера
# Список кортежей (индекс строки, ProviderOutput)
LINE_MAPPING_TYPE = List[Tuple[int, ProviderOutput]]


# Группа страницы - корневой контейнер для одной страницы документа
# Содержит изображения, блоки и структуру страницы
class PageGroup(Group):
    block_type: BlockTypes = BlockTypes.Page  # Тип блока - страница
    # Изображения страницы (lowres для предпросмотра, highres для детальной обработки)
    lowres_image: Image.Image | None | bytes = None  # Низкое разрешение (байты при сериализации)
    highres_image: Image.Image | None | bytes = None  # Высокое разрешение (байты при сериализации)
    children: List[Union[Any, Block]] | None = None  # Дочерние блоки страницы
    layout_sliced: bool = (
        False  # Было ли изображение разбито layout моделью (порядок может быть неверным)
    )
    excluded_block_types: Sequence[BlockTypes] = (
        BlockTypes.Line,
        BlockTypes.Span,
    )
    maximum_assignment_distance: float = 20  # Максимальное расстояние для присваивания строк блокам (в пикселях)
    block_description: str = "A single page in the document."
    refs: List[Reference] | None = None  # Ссылки на странице
    ocr_errors_detected: bool = False  # Были ли обнаружены ошибки OCR

    # Увеличить идентификатор блока
    # Используется для назначения уникальных ID новым блокам
    def incr_block_id(self):
        if self.block_id is None:
            self.block_id = 0  # Первый ID
        else:
            self.block_id += 1  # Следующий ID

    # Добавить дочерний блок на страницу
    def add_child(self, block: Block):
        if self.children is None:
            self.children = [block]  # Создаем список
        else:
            self.children.append(block)  # Добавляем в существующий список

    # Получить изображение страницы
    # highres: использовать ли высокое разрешение
    # remove_blocks: типы блоков, которые нужно закрасить белым на изображении
    def get_image(
        self,
        *args,
        highres: bool = False,
        remove_blocks: Sequence[BlockTypes] | None = None,
        **kwargs,
    ):
        image = self.highres_image if highres else self.lowres_image  # Выбираем нужное изображение

        # Проверяем, что изображение в RGB, конвертируем если нужно
        if isinstance(image, Image.Image) and image.mode != "RGB":
            image = image.convert("RGB")

        # Избегаем двойного OCR для определенных элементов
        # Закрашиваем блоки указанных типов белым цветом
        if remove_blocks:
            image = image.copy()  # Копируем изображение
            draw = ImageDraw.Draw(image)
            # Находим блоки указанных типов
            bad_blocks = [
                block
                for block in self.current_children
                if block.block_type in remove_blocks
            ]
            for bad_block in bad_blocks:
                # Масштабируем полигон блока к размеру изображения
                poly = bad_block.polygon.rescale(self.polygon.size, image.size).polygon
                poly = [(int(p[0]), int(p[1])) for p in poly]  # Преобразуем в целые числа
                draw.polygon(poly, fill="white")  # Закрашиваем белым

        return image

    # Текущие дочерние блоки (не удаленные)
    # Компьютед свойство для фильтрации удаленных блоков
    @computed_field
    @property
    def current_children(self) -> List[Block]:
        return [child for child in self.children if not child.removed]

    # Получить следующий блок после указанного
    # block: текущий блок (None для получения первого блока)
    # ignored_block_types: типы блоков, которые нужно пропустить
    def get_next_block(
        self,
        block: Optional[Block] = None,
        ignored_block_types: Optional[List[BlockTypes]] = None,
    ):
        if ignored_block_types is None:
            ignored_block_types = []  # По умолчанию не игнорируем типы

        structure_idx = 0
        if block is not None:
            # Находим индекс следующего блока в структуре
            structure_idx = self.structure.index(block.id) + 1

        # Итерируемся по блокам после указанного блока
        for next_block_id in self.structure[structure_idx:]:
            if next_block_id.block_type not in ignored_block_types:
                return self.get_block(next_block_id)  # Возвращаем первый подходящий блок

        return None  # Подходящий блок не найден

    # Получить предыдущий блок перед указанным
    def get_prev_block(self, block: Block):
        block_idx = self.structure.index(block.id)  # Находим индекс блока в структуре
        if block_idx > 0:
            return self.get_block(self.structure[block_idx - 1])  # Возвращаем предыдущий блок
        return None  # Это первый блок

    # Добавить блок заданного класса с полигоном
    # Создает новый блок с уникальным ID и добавляет его на страницу
    def add_block(self, block_cls: type[Block], polygon: PolygonBox) -> Block:
        self.incr_block_id()  # Увеличиваем ID
        # Создаем блок с текущим ID и ID страницы
        block = block_cls(
            polygon=polygon,
            block_id=self.block_id,
            page_id=self.page_id,
        )
        self.add_child(block)  # Добавляем как дочерний
        return block

    # Добавить полностью сформированный блок на страницу
    # Присваивает ID и добавляет блок в структуру страницы
    def add_full_block(self, block: Block) -> Block:
        self.incr_block_id()  # Увеличиваем ID
        block.block_id = self.block_id  # Присваиваем ID блоку
        self.add_child(block)  # Добавляем как дочерний
        return block

    # Получить блок по его идентификатору
    def get_block(self, block_id: BlockId) -> Block | None:
        block: Block = self.children[block_id.block_id]  # Получаем по индексу
        assert block.block_id == block_id.block_id  # Проверяем совпадение
        return block

    # Собрать HTML представление страницы
    # Создает шаблон с ссылками на все дочерние блоки
    def assemble_html(
        self, document, child_blocks, parent_structure=None, block_config=None
    ):
        template = ""
        for c in child_blocks:
            template += f"<content-ref src='{c.id}'></content-ref>"  # Ссылка на блок
        return template

    # Вычислить пересечения строк с блоками
    # Находит блок с максимальным пересечением для каждой строки
    def compute_line_block_intersections(
        self, blocks: List[Block], provider_outputs: List[ProviderOutput]
    ):
        max_intersections = {}

        # Получаем ограничивающие рамки блоков и строк
        block_bboxes = [block.polygon.bbox for block in blocks]
        line_bboxes = [
            provider_output.line.polygon.bbox for provider_output in provider_outputs
        ]

        # Вычисляем матрицу пересечений между строками и блоками
        intersection_matrix = matrix_intersection_area(line_bboxes, block_bboxes)

        # Для каждой строки находим блок с максимальным пересечением
        for line_idx, line in enumerate(provider_outputs):
            intersection_line = intersection_matrix[line_idx]
            if intersection_line.sum() == 0:
                continue  # Нет пересечений

            # Находим блок с максимальным пересечением
            max_intersection = intersection_line.argmax()
            max_intersections[line_idx] = (
                intersection_matrix[line_idx, max_intersection],
                blocks[max_intersection].id,
            )
        return max_intersections

    # Вычислить максимальный процент пересечения блоков структуры
    # Показывает, насколько сильно блоки перекрываются друг с другом
    def compute_max_structure_block_intersection_pct(self):
        structure_blocks = [self.get_block(block_id) for block_id in self.structure]
        strucure_block_bboxes = [b.polygon.bbox for b in structure_blocks]

        # Вычисляем матрицу пересечений между блоками структуры
        intersection_matrix = matrix_intersection_area(strucure_block_bboxes, strucure_block_bboxes)
        np.fill_diagonal(intersection_matrix, 0)  # Игнорируем самопересечения

        # Находим максимальный процент пересечения
        max_intersection_pct = 0
        for block_idx, block in enumerate(structure_blocks):
            if block.polygon.area == 0:
                continue
            max_intersection_pct = max(max_intersection_pct, np.max(intersection_matrix[block_idx]) / block.polygon.area)

        return max_intersection_pct

    # Заменить блок на новый
    # Создает новый блок, обновляет структуру и помечает старый блок как удаленный
    def replace_block(self, block: Block, new_block: Block):
        # Обрабатывает увеличение ID
        self.add_full_block(new_block)

        # Заменяем ID блока в структуре
        super().replace_block(block, new_block)

        # Заменяем блок в структуре всех дочерних элементов
        for child in self.children:
            child.replace_block(block, new_block)

        # Помечаем старый блок как удаленный
        block.removed = True

    # Идентифицировать отсутствующие блоки
    # Находит строки, которые не были присвоены ни одному блоку, и группирует их
    def identify_missing_blocks(
        self,
        provider_line_idxs: List[int],
        provider_outputs: List[ProviderOutput],
        assigned_line_idxs: set[int],
    ):
        new_blocks = []
        new_block = None
        for line_idx in provider_line_idxs:
            if line_idx in assigned_line_idxs:
                continue  # Строка уже присвоена

            # Если неприсвоенная строка - новая строка с минимальной площадью, пропускаем её
            if (
                provider_outputs[line_idx].line.polygon.area <= 1
                and provider_outputs[line_idx].raw_text == "\n"
            ):
                continue

            # Группируем последовательные строки, находящиеся близко друг к другу
            if new_block is None:
                new_block = [(line_idx, provider_outputs[line_idx])]
            elif all(
                [
                    new_block[-1][0] + 1 == line_idx,  # Следующий индекс
                    provider_outputs[line_idx].line.polygon.center_distance(
                        new_block[-1][1].line.polygon
                    )
                    < self.maximum_assignment_distance,  # Близко к предыдущей строке
                ]
            ):
                new_block.append((line_idx, provider_outputs[line_idx]))
            else:
                new_blocks.append(new_block)  # Завершаем текущий блок
                new_block = [(line_idx, provider_outputs[line_idx])]  # Начинаем новый блок
            assigned_line_idxs.add(line_idx)  # Помечаем как присвоенную
        if new_block:
            new_blocks.append(new_block)  # Добавляем последний блок

        return new_blocks

    # Создать отсутствующие блоки
    # Создает блоки Text для групп неприсвоенных строк и добавляет их в структуру
    def create_missing_blocks(
        self,
        new_blocks: List[LINE_MAPPING_TYPE],
        block_lines: Dict[BlockId, LINE_MAPPING_TYPE],
    ):
        for new_block in new_blocks:
            # Создаем текстовый блок для группы строк
            block = self.add_block(Text, new_block[0][1].line.polygon)
            block.source = "heuristics"  # Помечаем как созданный эвристикой
            block_lines[block.id] = new_block

            # Находим ближайший существующий блок для вставки
            min_dist_idx = None
            min_dist = None
            for existing_block_id in self.structure:
                existing_block = self.get_block(existing_block_id)
                if existing_block.block_type in self.excluded_block_types:
                    continue
                # Мы хотим присваивать к блокам, более близким по Y чем по X
                dist = block.polygon.center_distance(
                    existing_block.polygon, x_weight=5, absolute=True
                )
                if dist > 0 and min_dist_idx is None or dist < min_dist:
                    min_dist = dist
                    min_dist_idx = existing_block.id

            # Вставляем блок в структуру
            if min_dist_idx is not None:
                existing_idx = self.structure.index(min_dist_idx)
                self.structure.insert(existing_idx + 1, block.id)  # После ближайшего блока
            else:
                self.structure.append(block.id)  # В конец структуры

    # Добавить начальные блоки на страницу
    # Добавляет строки и их фрагменты (spans) в соответствующие блоки
    def add_initial_blocks(
        self,
        block_lines: Dict[BlockId, LINE_MAPPING_TYPE],
        text_extraction_method: str,
        keep_chars: bool = False,
    ):
        # Добавляем строки в соответствующие блоки в правильном порядке
        for block_id, lines in block_lines.items():
            # Проверяем метод извлечения текста
            line_extraction_methods = set(
                [line[1].line.text_extraction_method for line in lines]
            )
            if len(line_extraction_methods) == 1:
                # Один метод - сортируем по индексу
                lines = sorted(lines, key=lambda x: x[0])
                lines = [line for _, line in lines]
            else:
                # Разные методы - сортируем по полигонам
                lines = [line for _, line in lines]
                line_polygons = [line.line.polygon for line in lines]
                sorted_line_polygons = sort_text_lines(line_polygons)
                argsort = [line_polygons.index(p) for p in sorted_line_polygons]
                lines = [lines[i] for i in argsort]

            # Добавляем строки в блок
            block = self.get_block(block_id)
            for provider_output in lines:
                line = provider_output.line
                spans = provider_output.spans
                self.add_full_block(line)  # Добавляем строку
                block.add_structure(line)  # Добавляем в структуру блока
                block.polygon = block.polygon.merge([line.polygon])  # Обновляем полигон блока
                block.text_extraction_method = text_extraction_method

                # Добавляем фрагменты (spans) строки
                for span_idx, span in enumerate(spans):
                    self.add_full_block(span)  # Добавляем фрагмент
                    line.add_structure(span)  # Добавляем в структуру строки

                    if not keep_chars:
                        continue

                    # У провайдера нет символов
                    if len(provider_output.chars) == 0:
                        continue

                    # Добавляем символы, связанные с фрагментом
                    for char in provider_output.chars[span_idx]:
                        char.page_id = self.page_id
                        self.add_full_block(char)  # Добавляем символ
                        span.add_structure(char)  # Добавляем в структуру фрагмента

    # Слить блоки с выходными данными провайдера
    # Основной метод для слияния блоков структуры с результатами OCR
    def merge_blocks(
        self,
        provider_outputs: List[ProviderOutput],
        text_extraction_method: str,
        keep_chars: bool = False,
    ):
        provider_line_idxs = list(range(len(provider_outputs)))
        valid_blocks = [
            block
            for block in self.current_children  # Убеждаемся, что смотрим только на неудаленные дочерние блоки
            if block.block_type not in self.excluded_block_types
        ]

        # Вычисляем пересечения строк с блоками
        max_intersections = self.compute_line_block_intersections(
            valid_blocks, provider_outputs
        )

        # Пытаемся присвоить строки по пересечениям
        assigned_line_idxs = set()
        block_lines = defaultdict(list)
        for line_idx, provider_output in enumerate(provider_outputs):
            if line_idx in max_intersections:
                block_id = max_intersections[line_idx][1]
                block_lines[block_id].append((line_idx, provider_output))
                assigned_line_idxs.add(line_idx)

        # Если нет пересечения, присваиваем по расстоянию
        for line_idx in set(provider_line_idxs).difference(assigned_line_idxs):
            min_dist = None
            min_dist_idx = None
            provider_output: ProviderOutput = provider_outputs[line_idx]
            line = provider_output.line
            for block in valid_blocks:
                # Мы хотим присваивать к блокам, более близким по Y чем по X
                dist = line.polygon.center_distance(block.polygon, x_weight=5)
                if min_dist_idx is None or dist < min_dist:
                    min_dist = dist
                    min_dist_idx = block.id

            # Присваиваем, если расстояние допустимо
            if min_dist_idx is not None and dist < self.maximum_assignment_distance:
                block_lines[min_dist_idx].append((line_idx, provider_output))
                assigned_line_idxs.add(line_idx)

        # Создает новые блоки для строк, которые находятся слишком далеко
        new_blocks = self.identify_missing_blocks(
            provider_line_idxs, provider_outputs, assigned_line_idxs
        )
        self.create_missing_blocks(new_blocks, block_lines)

        # Добавляем блоки на страницу
        self.add_initial_blocks(block_lines, text_extraction_method, keep_chars)

    # Агрегировать метаданные блоков
    # Сливает метаданные всех дочерних блоков в метаданные страницы
    def aggregate_block_metadata(self) -> BlockMetadata:
        if self.metadata is None:
            self.metadata = BlockMetadata()  # Создаем если нет

        # Сливаем метаданные из всех дочерних блоков
        for block in self.current_children:
            if block.metadata is not None:
                self.metadata = self.metadata.merge(block.metadata)
        return self.metadata
