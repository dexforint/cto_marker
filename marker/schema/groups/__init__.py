# Модуль групп блоков
# Экспортирует все типы групп - контейнеров для объединения блоков

from marker.schema.blocks.base import Block  # Базовый класс блока (для совместимости)
from marker.schema.groups.figure import FigureGroup  # Группа рисунков
from marker.schema.groups.table import TableGroup  # Группа таблиц
from marker.schema.groups.list import ListGroup  # Группа списка
from marker.schema.groups.picture import PictureGroup  # Группа картинок
from marker.schema.groups.page import PageGroup  # Группа страницы (страница документа)
