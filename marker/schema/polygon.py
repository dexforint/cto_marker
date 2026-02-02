# Модуль полигонов и ограничивающих рамок
# Определяет модели для работы с координатами блоков на странице
# Поддерживает операции с полигонами: вычисление размеров, расстояний, пересечений

from __future__ import annotations
import copy
from typing import List

import numpy as np
from pydantic import BaseModel, field_validator, computed_field


# Модель полигона (ограничивающей рамки блока)
# Хранит координаты 4 углов блока в порядке по часовой стрелке: верхний левый, верхний правый, нижний правый, нижний левый
class PolygonBox(BaseModel):
    polygon: List[List[float]]  # Координаты углов в формате [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

    # Валидатор для проверки корректности полигона
    # Убедимся, что полигон имеет 4 угла с 2 координатами каждый и углы упорядочены правильно
    @field_validator('polygon')
    @classmethod
    def check_elements(cls, v: List[List[float]]) -> List[List[float]]:
        if len(v) != 4:
            raise ValueError('corner must have 4 elements')

        for corner in v:
            if len(corner) != 2:
                raise ValueError('corner must have 2 elements')

        # Находим минимальные координаты для проверки порядка
        min_x = min([corner[0] for corner in v])
        min_y = min([corner[1] for corner in v])

        # Проверяем, что углы расположены по часовой стрелке от верхнего левого
        corner_error = f" .Corners are {v}"
        assert v[2][1] >= min_y, f'bottom right corner should have a greater y value than top right corner' + corner_error
        assert v[3][1] >= min_y, 'bottom left corner should have a greater y value than top left corner' + corner_error
        assert v[1][0] >= min_x, 'top right corner should have a greater x value than top left corner' + corner_error
        assert v[2][0] >= min_x, 'bottom right corner should have a greater x value than bottom left corner' + corner_error
        return v

    # Высота полигона (разница между нижней и верхней границей)
    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    # Ширина полигона (разница между правой и левой границей)
    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    # Площадь полигона (произведение ширины на высоту)
    @property
    def area(self):
        return self.width * self.height

    # Центр полигона (средняя точка между углами ограничивающего прямоугольника)
    @property
    def center(self):
        return [(self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2]

    # Размер полигона в формате [ширина, высота]
    @property
    def size(self):
        return [self.width, self.height]

    # Начальная координата X (левая граница)
    @property
    def x_start(self):
        return self.bbox[0]

    # Начальная координата Y (верхняя граница)
    @property
    def y_start(self):
        return self.bbox[1]

    # Конечная координата X (правая граница)
    @property
    def x_end(self):
        return self.bbox[2]

    # Конечная координата Y (нижняя граница)
    @property
    def y_end(self):
        return self.bbox[3]

    # Ограничивающий прямоугольник (bbox) - минимальный прямоугольник, содержащий полигон
    # Вычисляется как [min_x, min_y, max_x, max_y]
    @computed_field
    @property
    def bbox(self) -> List[float]:
        min_x = min([corner[0] for corner in self.polygon])  # Минимальная X
        min_y = min([corner[1] for corner in self.polygon])  # Минимальная Y
        max_x = max([corner[0] for corner in self.polygon])  # Максимальная X
        max_y = max([corner[1] for corner in self.polygon])  # Максимальная Y
        return [min_x, min_y, max_x, max_y]

    # Расширить полигон на заданные отступы
    # x_margin, y_margin: отступы в долях от ширины/высоты полигона
    def expand(self, x_margin: float, y_margin: float) -> PolygonBox:
        new_polygon = []
        x_margin = x_margin * self.width  # Преобразуем долю в пиксели
        y_margin = y_margin * self.height
        for idx, poly in enumerate(self.polygon):
            if idx == 0:
                new_polygon.append([poly[0] - x_margin, poly[1] - y_margin])  # Верхний левый - влево и вверх
            elif idx == 1:
                new_polygon.append([poly[0] + x_margin, poly[1] - y_margin])  # Верхний правый - вправо и вверх
            elif idx == 2:
                new_polygon.append([poly[0] + x_margin, poly[1] + y_margin])  # Нижний правый - вправо и вниз
            elif idx == 3:
                new_polygon.append([poly[0] - x_margin, poly[1] + y_margin])  # Нижний левый - влево и вниз
        return PolygonBox(polygon=new_polygon)

    # Расширить полигон вниз по оси Y (только нижние углы)
    def expand_y2(self, y_margin: float) -> PolygonBox:
        new_polygon = []
        y_margin = y_margin * self.height
        for idx, poly in enumerate(self.polygon):
            if idx == 2:
                new_polygon.append([poly[0], poly[1] + y_margin])  # Нижний правый - вниз
            elif idx == 3:
                new_polygon.append([poly[0], poly[1] + y_margin])  # Нижний левый - вниз
            else:
                new_polygon.append(poly)  # Верхние углы не меняем
        return PolygonBox(polygon=new_polygon)

    # Расширить полигон вверх по оси Y (только верхние углы)
    def expand_y1(self, y_margin: float) -> PolygonBox:
        new_polygon = []
        y_margin = y_margin * self.height
        for idx, poly in enumerate(self.polygon):
            if idx == 0:
                new_polygon.append([poly[0], poly[1] - y_margin])  # Верхний левый - вверх
            elif idx == 1:
                new_polygon.append([poly[0], poly[1] - y_margin])  # Верхний правый - вверх
            else:
                new_polygon.append(poly)  # Нижние углы не меняем
        return PolygonBox(polygon=new_polygon)

    # Вычислить минимальное расстояние до другого полигона
    # Если полигоны пересекаются, возвращает 0
    def minimum_gap(self, other: PolygonBox):
        if self.intersection_pct(other) > 0:
            return 0  # Полигоны пересекаются

        # Вспомогательная функция для вычисления евклидова расстояния
        def dist(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

        # Определяем относительное положение полигонов
        left = other.bbox[2] < self.bbox[0]  # Другой полигон слева
        right = self.bbox[2] < other.bbox[0]  # Другой полигон справа
        bottom = other.bbox[3] < self.bbox[1]  # Другой полигон снизу
        top = self.bbox[3] < other.bbox[1]  # Другой полигон сверху

        # Вычисляем расстояние по диагонали для угловых случаев
        if top and left:
            return dist((self.bbox[0], self.bbox[3]), (other.bbox[2], other.bbox[1]))  # Верхний левый угол
        elif left and bottom:
            return dist((self.bbox[0], self.bbox[1]), (other.bbox[2], other.bbox[3]))  # Нижний левый угол
        elif bottom and right:
            return dist((self.bbox[2], self.bbox[1]), (other.bbox[0], other.bbox[3]))  # Нижний правый угол
        elif right and top:
            return dist((self.bbox[2], self.bbox[3]), (other.bbox[0], other.bbox[1]))  # Верхний правый угол
        elif left:
            return self.bbox[0] - other.bbox[2]  # Пространство слева
        elif right:
            return other.bbox[0] - self.bbox[2]  # Пространство справа
        elif bottom:
            return self.bbox[1] - other.bbox[3]  # Пространство снизу
        elif top:
            return other.bbox[1] - self.bbox[3]  # Пространство сверху
        else:
            return 0  # Полигоны наложены

    # Вычислить расстояние между центрами полигонов
    # x_weight, y_weight: веса для координат X и Y (по умолчанию равны)
    # absolute: если True, использует манхэттенское расстояние, иначе евклидово
    def center_distance(self, other: PolygonBox, x_weight: float = 1, y_weight: float = 1, absolute=False):
        if not absolute:
            # Евклидово расстояние с весами
            return ((self.center[0] - other.center[0]) ** 2 * x_weight + (self.center[1] - other.center[1]) ** 2 * y_weight) ** 0.5
        else:
            # Манхэттенское расстояние с весами
            return abs(self.center[0] - other.center[0]) * x_weight + abs(self.center[1] - other.center[1]) * y_weight

    # Вычислить расстояние между верхними левыми углами полигонов
    def tl_distance(self, other: PolygonBox):
        return ((self.bbox[0] - other.bbox[0]) ** 2 + (self.bbox[1] - other.bbox[1]) ** 2) ** 0.5

    # Пересчитать координаты полигона при изменении размера страницы
    # old_size: старый размер страницы (ширина, высота)
    # new_size: новый размер страницы (ширина, высота)
    def rescale(self, old_size, new_size):
        # Координаты точки в формате (x, y)
        page_width, page_height = old_size
        img_width, img_height = new_size

        # Вычисляем коэффициенты масштабирования
        width_scaler = img_width / page_width
        height_scaler = img_height / page_height

        # Применяем масштабирование ко всем углам полигона
        new_corners = copy.deepcopy(self.polygon)
        for corner in new_corners:
            corner[0] = corner[0] * width_scaler  # Масштабируем X
            corner[1] = corner[1] * height_scaler  # Масштабируем Y
        return PolygonBox(polygon=new_corners)

    # Подогнать полигон к границам (обрезать, если выходит за пределы)
    # bounds: границы в формате [min_x, min_y, max_x, max_y]
    def fit_to_bounds(self, bounds):
        new_corners = copy.deepcopy(self.polygon)
        for corner in new_corners:
            # Ограничиваем X между min_x и max_x
            corner[0] = max(min(corner[0], bounds[2]), bounds[0])
            # Ограничиваем Y между min_y и max_y
            corner[1] = max(min(corner[1], bounds[3]), bounds[1])
        return PolygonBox(polygon=new_corners)

    # Вычислить горизонтальное перекрытие с другим полигоном
    def overlap_x(self, other: PolygonBox):
        return max(0, min(self.bbox[2], other.bbox[2]) - max(self.bbox[0], other.bbox[0]))

    # Вычислить вертикальное перекрытие с другим полигоном
    def overlap_y(self, other: PolygonBox):
        return max(0, min(self.bbox[3], other.bbox[3]) - max(self.bbox[1], other.bbox[1]))

    # Вычислить площадь пересечения с другим полигоном
    def intersection_area(self, other: PolygonBox):
        return self.overlap_x(other) * self.overlap_y(other)

    # Вычислить процент перекрытия с другим полигоном относительно текущего
    def intersection_pct(self, other: PolygonBox):
        if self.area == 0:
            return 0  # Избегаем деления на ноль

        intersection = self.intersection_area(other)
        return intersection / self.area

    # Объединить текущий полигон с другими в один
    # Создает минимальный полигон, содержащий все исходные полигоны
    def merge(self, others: List[PolygonBox]) -> PolygonBox:
        corners = []
        for i in range(len(self.polygon)):
            # Собираем координаты для каждого угла из всех полигонов
            x_coords = [self.polygon[i][0]] + [other.polygon[i][0] for other in others]
            y_coords = [self.polygon[i][1]] + [other.polygon[i][1] for other in others]
            min_x = min(x_coords)
            min_y = min(y_coords)
            max_x = max(x_coords)
            max_y = max(y_coords)

            # Формируем новый угол, используя экстремальные значения
            if i == 0:
                corners.append([min_x, min_y])  # Верхний левый - минимум по обеим координатам
            elif i == 1:
                corners.append([max_x, min_y])  # Верхний правый - максимум X, минимум Y
            elif i == 2:
                corners.append([max_x, max_y])  # Нижний правый - максимум по обеим координатам
            elif i == 3:
                corners.append([min_x, max_y])  # Нижний левый - минимум X, максимум Y
        return PolygonBox(polygon=corners)

    # Создать полигон из ограничивающего прямоугольника (bbox)
    # bbox: прямоугольник в формате [min_x, min_y, max_x, max_y]
    # ensure_nonzero_area: если True, гарантирует ненулевую площадь (минимум 1x1 пиксель)
    @classmethod
    def from_bbox(cls, bbox: List[float], ensure_nonzero_area=False):
        if ensure_nonzero_area:
            bbox = list(bbox)
            bbox[2] = max(bbox[2], bbox[0] + 1)  # Минимальная ширина 1 пиксель
            bbox[3] = max(bbox[3], bbox[1] + 1)  # Минимальная высота 1 пиксель
        # Создаем полигон из 4 углов прямоугольника
        return cls(polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]])
