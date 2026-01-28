# Модуль утилитарных функций для Marker
# Содержит вспомогательные функции для работы с текстом, классами, конфигурацией и математическими тегами

import inspect
import os
from importlib import import_module
from typing import List, Annotated
import re

import numpy as np
import requests
from pydantic import BaseModel

# Локальные импорты
from marker.schema.polygon import PolygonBox
from marker.settings import settings

# Регулярные выражения для обработки тегов форматирования
# Теги для открывающих элементов (математика, курсив, жирный)
OPENING_TAG_REGEX = re.compile(r"<((?:math|i|b))(?:\s+[^>]*)?>")
# Теги для закрывающих элементов
CLOSING_TAG_REGEX = re.compile(r"</((?:math|i|b))>")
# Сопоставление тегов с типами форматирования
TAG_MAPPING = {
    'i': 'italic',           # курсив
    'b': 'bold',             # жирный
    'math': 'math',          # математическая формула
    'mark': 'highlight',     # выделение
    'sub': 'subscript',      # нижний индекс
    'sup': 'superscript',    # верхний индекс
    'small': 'small',        # мелкий текст
    'u': 'underline',        # подчеркивание
    'code': 'code'           # код
}

def strings_to_classes(items: List[str]) -> List[type]:
    """
    Преобразует список строк с полными именами классов в список объектов классов.
    
    Функция используется для динамической загрузки классов по их строковым именам,
    что необходимо при конфигурировании процессоров и других компонентов системы.
    
    Аргументы:
        items: Список строк формата "модуль.Класс"
    
    Возвращает:
        Список объектов классов
    
    Исключения:
        ImportError: Если модуль не найден
        AttributeError: Если класс не найден в модуле
    """
    classes = []
    for item in items:
        # Разделяем полное имя на модуль и класс
        module_name, class_name = item.rsplit('.', 1)
        # Импортируем модуль динамически
        module = import_module(module_name)
        # Получаем объект класса из модуля
        classes.append(getattr(module, class_name))
    return classes


def classes_to_strings(items: List[type]) -> List[str]:
    """
    Преобразует список объектов классов в список их полных имен.
    
    Обратная функция к strings_to_classes, используется для сериализации
    конфигурации и сохранения списка классов в текстовом виде.
    
    Аргументы:
        items: Список объектов классов
    
    Возвращает:
        Список строк формата "модуль.Класс"
    
    Исключения:
        ValueError: Если элемент не является классом
    """
    for item in items:
        # Проверяем, что элемент действительно является классом
        if not inspect.isclass(item):
            raise ValueError(f"Элемент {item} не является классом")

    # Формируем список полных имен классов
    return [f"{item.__module__}.{item.__name__}" for item in items]


def verify_config_keys(obj):
    """
    Проверяет, что все необходимые конфигурационные параметры объекта установлены.
    
    Функция анализирует аннотации типов объекта и проверяет, что все
    параметры с аннотацией Annotated[str, ""] имеют значения (не None).
    Это обеспечивает валидность конфигурации перед использованием объекта.
    
    Аргументы:
        obj: Объект для проверки конфигурации
    
    Исключения:
        AssertionError: Если найдены неустановленные обязательные параметры
    """
    # Получаем аннотации типов из класса объекта
    annotations = inspect.get_annotations(obj.__class__)

    # Собираем список параметров со значением None
    none_vals = ""
    for attr_name, annotation in annotations.items():
        # Проверяем, является ли аннотацией Annotated[str, ""]
        if isinstance(annotation, type(Annotated[str, ""])):
            value = getattr(obj, attr_name)
            if value is None:
                none_vals += f"{attr_name}, "

    # Если есть неустановленные параметры, выбрасываем ошибку
    assert len(none_vals) == 0, f"Для использования {obj.__class__.__name__} необходимо установить конфигурационные значения `{none_vals}`."


def assign_config(cls, config: BaseModel | dict | None):
    """
    Назначает конфигурационные значения атрибутам класса.
    
    Функция поддерживает несколько форматов конфигурации:
    1. Словарь Python (dict)
    2. Модель Pydantic (BaseModel)
    3. None (в этом случае ничего не делает)
    
    Поддерживает два способа указания атрибутов:
    - Прямое имя атрибута: "attribute_name"
    - С префиксом класса: "ClassName_attribute_name"
    
    Аргументы:
        cls: Экземпляр класса для конфигурирования
        config: Конфигурация в одном из поддерживаемых форматов
    
    Исключения:
        ValueError: Если config имеет неподдерживаемый тип
    """
    cls_name = cls.__class__.__name__
    
    # Если конфигурация не передана, ничего не делаем
    if config is None:
        return
    elif isinstance(config, BaseModel):
        # Преобразуем модель Pydantic в словарь
        dict_config = config.dict()
    elif isinstance(config, dict):
        dict_config = config
    else:
        raise ValueError("config должен быть словарем или моделью Pydantic BaseModel")

    # Сначала обрабатываем атрибуты по их прямым именам
    for k in dict_config:
        if hasattr(cls, k):
            setattr(cls, k, dict_config[k])
    
    # Затем обрабатываем атрибуты с префиксом класса
    for k in dict_config:
        # Пропускаем ключи, которые не относятся к данному классу
        if cls_name not in k:
            continue
        # Удаляем префикс класса из ключа
        # Пример: "MarkdownRenderer_remove_blocks" -> "remove_blocks"
        split_k = k.removeprefix(cls_name + "_")

        # Если у класса есть такой атрибут, устанавливаем значение
        if hasattr(cls, split_k):
            setattr(cls, split_k, dict_config[k])


def parse_range_str(range_str: str) -> List[int]:
    """
    Парсит строку с диапазонами страниц и возвращает список номеров страниц.
    
    Поддерживаемые форматы:
    - "1,3,5" -> [1, 3, 5]
    - "1-5" -> [1, 2, 3, 4, 5]
    - "1,3-5,7" -> [1, 3, 4, 5, 7]
    
    Функция автоматически удаляет дубликаты и сортирует результат.
    
    Аргументы:
        range_str: Строка с диапазонами страниц
    
    Возвращает:
        Отсортированный список уникальных номеров страниц
    
    Исключения:
        ValueError: Если строка содержит некорректные данные
    """
    # Разделяем строку по запятым
    range_lst = range_str.split(",")
    page_lst = []
    
    for i in range_lst:
        if "-" in i:
            # Диапазон страниц (например, "1-5")
            start, end = i.split("-")
            page_lst += list(range(int(start), int(end) + 1))
        else:
            # Одиночная страница
            page_lst.append(int(i))
    
    # Удаляем дубликаты и сортируем в порядке возрастания
    page_lst = sorted(list(set(page_lst)))
    return page_lst


def matrix_intersection_area(boxes1: List[List[float]], boxes2: List[List[float]]) -> np.ndarray:
    """
    Вычисляет матрицу площадей пересечений между двумя наборами прямоугольников.
    
    Каждый прямоугольник задается как [x1, y1, x2, y2], где:
    - x1, y1: координаты верхнего левого угла
    - x2, y2: координаты нижнего правого угла
    
    Аргументы:
        boxes1: Список первого набора прямоугольников
        boxes2: Список второго набора прямоугольников
    
    Возвращает:
        Матрица размера (len(boxes1), len(boxes2)) с площадями пересечений
    """
    # Обрабатываем случаи с пустыми списками
    if len(boxes1) == 0 or len(boxes2) == 0:
        return np.zeros((len(boxes1), len(boxes2)))

    # Преобразуем списки в numpy массивы для векторных вычислений
    boxes1 = np.array(boxes1)
    boxes2 = np.array(boxes2)

    # Добавляем измерения для векторных операций
    # boxes1: (N, 1, 4) и boxes2: (1, M, 4) для вычисления всех пар
    boxes1 = boxes1[:, np.newaxis, :]  # Shape: (N, 1, 4)
    boxes2 = boxes2[np.newaxis, :, :]  # Shape: (1, M, 4)

    # Вычисляем координаты пересечения для всех пар прямоугольников
    min_x = np.maximum(boxes1[..., 0], boxes2[..., 0])  # Shape: (N, M)
    min_y = np.maximum(boxes1[..., 1], boxes2[..., 1])
    max_x = np.minimum(boxes1[..., 2], boxes2[..., 2])
    max_y = np.minimum(boxes1[..., 3], boxes2[..., 3])

    # Вычисляем ширину и высоту пересечения
    width = np.maximum(0, max_x - min_x)
    height = np.maximum(0, max_y - min_y)

    # Площадь пересечения = ширина * высота
    return width * height  # Shape: (N, M)


def matrix_distance(boxes1: List[List[float]], boxes2: List[List[float]]) -> np.ndarray:
    """
    Вычисляет матрицу расстояний между центрами двух наборов прямоугольников.
    
    Используется для определения близости элементов документа при
    сортировке, группировке и определении структуры.
    
    Аргументы:
        boxes1: Список первого набора прямоугольников
        boxes2: Список второго набора прямоугольников
    
    Возвращает:
        Матрица размеров (len(boxes1), len(boxes2)) с евклидовыми расстояниями
    """
    # Обрабатываем случаи с пустыми списками
    if len(boxes2) == 0:
        return np.zeros((len(boxes1), 0))
    if len(boxes1) == 0:
        return np.zeros((0, len(boxes2)))

    # Преобразуем в numpy массивы
    boxes1 = np.array(boxes1)  # Shape: (N, 4)
    boxes2 = np.array(boxes2)  # Shape: (M, 4)

    # Вычисляем координаты центров прямоугольников
    # Центр = (верхний_левый + нижний_правый) / 2
    boxes1_centers = (boxes1[:, :2] + boxes1[:, 2:]) / 2 # Shape: (N, 2)
    boxes2_centers = (boxes2[:, :2] + boxes2[:, 2:]) / 2  # Shape: (M, 2)

    # Добавляем измерения для векторных операций
    boxes1_centers = boxes1_centers[:, np.newaxis, :]  # Shape: (N, 1, 2)
    boxes2_centers = boxes2_centers[np.newaxis, :, :]  # Shape: (1, M, 2)

    # Вычисляем евклидовы расстояния между всеми парами центров
    distances = np.linalg.norm(boxes1_centers - boxes2_centers, axis=2)  # Shape: (N, M)
    return distances


def sort_text_lines(lines: List[PolygonBox], tolerance=1.25):
    """
    Сортирует строки текста в порядке чтения.
    
    Функция использует приближенный алгоритм сортировки строк по их
    вертикальным позициям. Строки группируются по высоте, а затем
    сортируются горизонтально внутри каждой группы.
    
    Примечание: Это приближенный алгоритм и не является 100% точным.
    Должен использоваться как отправная точка для более сложной сортировки.
    
    Аргументы:
        lines: Список объектов PolygonBox с координатами строк
        tolerance: Коэффициент группировки строк по вертикали (по умолчанию 1.25)
    
    Возвращает:
        Список строк, отсортированных в порядке чтения
    """
    # Группируем строки по вертикальным позициям
    vertical_groups = {}
    for line in lines:
        # Вычисляем ключ группы как округленную координату Y
        group_key = round(line.bbox[1] / tolerance) * tolerance
        # Добавляем строку в соответствующую группу
        if group_key not in vertical_groups:
            vertical_groups[group_key] = []
        vertical_groups[group_key].append(line)

    # Сортируем каждую группу горизонтально и объединяем в один список
    sorted_lines = []
    for _, group in sorted(vertical_groups.items()):
        # Сортируем строки в группе по X координате (слева направо)
        sorted_group = sorted(group, key=lambda x: x.bbox[0])
        sorted_lines.extend(sorted_group)

    return sorted_lines


def download_font():
    """
    Загружает шрифт из удаленного репозитория, если он отсутствует.
    
    Шрифт необходим для правильного рендеринга документов с нестандартными
    символами. Функция проверяет наличие локального файла шрифта и
    загружает его при необходимости.
    
    Параметры:
        settings.FONT_PATH: Локальный путь для сохранения шрифта
        settings.ARTIFACT_URL: Базовый URL для загрузки артефактов
        settings.FONT_NAME: Имя файла шрифта
    
    Создает:
        Файл шрифта в локальной файловой системе
    """
    # Проверяем наличие шрифта локально
    if not os.path.exists(settings.FONT_PATH):
        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(settings.FONT_PATH), exist_ok=True)
        # Формируем полный URL для загрузки
        font_dl_path = f"{settings.ARTIFACT_URL}/{settings.FONT_NAME}"
        
        # Загружаем файл шрифта по частям
        with requests.get(font_dl_path, stream=True) as r, open(settings.FONT_PATH, 'wb') as f:
            # Проверяем успешность HTTP запроса
            r.raise_for_status()
            # Записываем файл по частям для экономии памяти
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def get_opening_tag_type(tag):
    """
    Определяет, является ли тег открывающим, и извлекает тип тега.
    
    Используется для обработки тегов форматирования в математических
    и текстовых элементах документа.
    
    Аргументы:
        tag (str): Строка с тегом для анализа
    
    Возвращает:
        tuple: (is_opening_tag (bool), tag_type (str или None))
    """
    # Пытаемся сопоставить тег с шаблоном открывающих тегов
    match = OPENING_TAG_REGEX.match(tag)
    
    if match:
        # Извлекаем тип тега из группы регулярного выражения
        tag_type = match.group(1)
        # Проверяем, что тип поддерживается
        if tag_type in TAG_MAPPING:
            return True, TAG_MAPPING[tag_type]
    
    # Тег не является открывающим или не поддерживается
    return False, None


def get_closing_tag_type(tag):
    """
    Определяет, является ли тег закрывающим, и извлекает тип тега.
    
    Используется совместно с get_opening_tag_type для парсинга
    тегов форматирования в документе.
    
    Аргументы:
        tag (str): Строка с тегом для анализа
    
    Возвращает:
        tuple: (is_closing_tag (bool), tag_type (str или None))
    """
    # Пытаемся сопоставить тег с шаблоном закрывающих тегов
    match = CLOSING_TAG_REGEX.match(tag)
    
    if match:
        # Извлекаем тип тега из группы регулярного выражения
        tag_type = match.group(1)
        # Проверяем, что тип поддерживается
        if tag_type in TAG_MAPPING:
            return True, TAG_MAPPING[tag_type]
    
    # Тег не является закрывающим или не поддерживается
    return False, None


# Математические символы для определения истинных математических формул
# Измененная версия unwrap_math из surya.recognition
MATH_SYMBOLS = ["^", "_", "\\", "{", "}"]
# Шаблон для поиска математических тегов
MATH_TAG_PATTERN = re.compile(r'<math\b[^>]*>.*?</math>', re.DOTALL)
# Словарь для нормализации LaTeX экранирования
LATEX_ESCAPES = {
    r'\%': '%',
    r'\$': '$',
    r'\_': '_',
    r'\&': '&',
    r'\#': '#',
    r'\‰': '‰',
}


def normalize_latex_escapes(s: str) -> str:
    """
    Нормализует LaTeX экранированные символы в строке.
    
    Преобразует специальные символы LaTeX в их нормальное представление.
    
    Аргументы:
        s (str): Строка с экранированными символами
    
    Возвращает:
        str: Строка с нормализованными символами
    """
    # Применяем все замены из словаря экранирования
    for k, v in LATEX_ESCAPES.items():
        s = s.replace(k, v)
    return s


def unwrap_math(text: str, math_symbols: List[str] = MATH_SYMBOLS) -> str:
    """
    Извлекает содержимое из математического тега, если это не истинная формула.
    
    Функция анализирует содержимое <math>...</math> блока и определяет,
    является ли он настоящей математической формулой или просто текстом
    с тегами форматирования.
    
    Логика определения:
    1. Если нет математических символов - считаем текстом
    2. Удаляем теги и проверяем оставшийся текст
    3. Если математических символов не осталось - извлекаем содержимое
    
    Аргументы:
        text (str): Текст для анализа
        math_symbols (List[str]): Список символов, определяющих математическую формулу
    
    Возвращает:
        str: Извлеченный текст или исходный текст, если это формула
    """
    # Проверяем, что текст соответствует шаблону математического тега
    if MATH_TAG_PATTERN.match(text):
        # Удаляем открывающие и закрывающие теги <math>
        inner = re.sub(r'^\s*<math\b[^>]*>|</math>\s*$', '', text, flags=re.DOTALL)

        # Удаляем одиночные ведущие/завершающие \\ и окружающие пробелы
        inner_stripped = re.sub(r'^\s*\\\\\s*|\s*\\\\\s*$', '', inner)

        # Извлекаем текст из команд \text{...}
        unwrapped = re.sub(r'\\text[a-zA-Z]*\s*\{(.*?)\}', r'\1', inner_stripped)

        # Нормализуем LaTeX экранирования
        normalized = normalize_latex_escapes(unwrapped)

        # Если математических символов не осталось → извлекаем полностью
        if not any(symb in normalized for symb in math_symbols):
            return normalized.strip()

    # В противном случае возвращаем исходный текст (это формула)
    return text