# Реестр классов блоков
# Управляет регистрацией и получением классов блоков по их типам
# Позволяет динамически создавать блоки по идентификатору типа

from typing import Dict, Type
from importlib import import_module

from marker.schema import BlockTypes
from marker.schema.blocks import (
    Block,
    Caption,
    Code,
    Equation,
    Figure,
    Footnote,
    Form,
    Handwriting,
    InlineMath,
    ListItem,
    PageFooter,
    PageHeader,
    Picture,
    SectionHeader,
    Table,
    TableOfContents,
    Text,
    ComplexRegion,
    TableCell,
    Reference,
)
from marker.schema.document import Document
from marker.schema.groups import (
    FigureGroup,
    ListGroup,
    PageGroup,
    PictureGroup,
    TableGroup,
)
from marker.schema.text import Line, Span
from marker.schema.text.char import Char

# Реестр сопоставления типов блоков с путями к их классам
# Ключ: тип блока (BlockTypes), значение: путь к классу (module.ClassName)
BLOCK_REGISTRY: Dict[BlockTypes, str] = {}


# Зарегистрировать класс блока для заданного типа
# Сохраняет полное имя класса в реестре для последующего получения
def register_block_class(block_type: BlockTypes, block_cls: Type[Block]):
    BLOCK_REGISTRY[block_type] = f"{block_cls.__module__}.{block_cls.__name__}"


# Получить класс блока по его типу
# Динамически импортирует модуль и возвращает класс
def get_block_class(block_type: BlockTypes) -> Type[Block]:
    class_path = BLOCK_REGISTRY[block_type]  # Получаем путь к классу
    module_name, class_name = class_path.rsplit(".", 1)  # Разделяем на модуль и имя класса
    module = import_module(module_name)  # Импортируем модуль
    return getattr(module, class_name)  # Получаем класс из модуля


# Регистрация всех типов блоков
# Создаем сопоставления между перечислением BlockTypes и соответствующими классами

# Текстовые примитивы
register_block_class(BlockTypes.Line, Line)  # Строка текста
register_block_class(BlockTypes.Span, Span)  # Фрагмент текста с форматированием
register_block_class(BlockTypes.Char, Char)  # Отдельный символ

# Группы блоков
register_block_class(BlockTypes.FigureGroup, FigureGroup)  # Группа рисунков
register_block_class(BlockTypes.TableGroup, TableGroup)  # Группа таблиц
register_block_class(BlockTypes.ListGroup, ListGroup)  # Группа списка
register_block_class(BlockTypes.PictureGroup, PictureGroup)  # Группа картинок
register_block_class(BlockTypes.Page, PageGroup)  # Страница документа

# Блоки контента
register_block_class(BlockTypes.Caption, Caption)  # Подпись к элементу
register_block_class(BlockTypes.Code, Code)  # Блок кода
register_block_class(BlockTypes.Figure, Figure)  # Рисунок/диаграмма
register_block_class(BlockTypes.Footnote, Footnote)  # Сноска
register_block_class(BlockTypes.Form, Form)  # Форма ввода данных
register_block_class(BlockTypes.Equation, Equation)  # Математическое уравнение
register_block_class(BlockTypes.Handwriting, Handwriting)  # Рукописный текст
register_block_class(BlockTypes.TextInlineMath, InlineMath)  # Inline математика
register_block_class(BlockTypes.ListItem, ListItem)  # Элемент списка
register_block_class(BlockTypes.PageFooter, PageFooter)  # Нижний колонтитул
register_block_class(BlockTypes.PageHeader, PageHeader)  # Верхний колонтитул
register_block_class(BlockTypes.Picture, Picture)  # Изображение
register_block_class(BlockTypes.SectionHeader, SectionHeader)  # Заголовок раздела
register_block_class(BlockTypes.Table, Table)  # Таблица
register_block_class(BlockTypes.Text, Text)  # Текстовый параграф
register_block_class(BlockTypes.TableOfContents, TableOfContents)  # Оглавление
register_block_class(BlockTypes.ComplexRegion, ComplexRegion)  # Сложный регион (mixed content)
register_block_class(BlockTypes.TableCell, TableCell)  # Ячейка таблицы
register_block_class(BlockTypes.Reference, Reference)  # Библиографическая ссылка

# Документ целиком
register_block_class(BlockTypes.Document, Document)  # Полный документ

# Проверки целостности реестра
# Убедимся, что все типы зарегистрированы и соответствия корректны

# Проверяем, что количество зарегистрированных типов равно общему количеству типов
assert len(BLOCK_REGISTRY) == len(BlockTypes)

# Проверяем, что каждый зарегистрированный класс имеет правильный тип в поле block_type
assert all(
    [
        get_block_class(k).model_fields["block_type"].default == k
        for k, _ in BLOCK_REGISTRY.items()
    ]
)
