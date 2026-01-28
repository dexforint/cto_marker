"""
Общие функции и утилиты для скриптов Marker.

Модуль содержит вспомогательные функции, используемые различными
скриптами и CLI утилитами для обработки PDF, изображений и других
документов. Включает функции для работы с PDF, изображениями,
парсинга аргументов командной строки и обработки схем данных.

Автор: Marker Team
"""

import ast
import base64
import io
import re
import sys
from typing import Optional

from PIL import Image
import click
import pypdfium2
import streamlit as st
from pydantic import BaseModel
from streamlit.runtime.uploaded_file_manager import UploadedFile

from marker.config.parser import ConfigParser
from marker.config.printer import CustomClickPrinter
from marker.models import create_model_dict
from marker.settings import settings


@st.cache_data()
def parse_args():
    """
    Извлекает общие CLI опции из конфигурации.
    
    Используется для получения общих параметров командной строки,
    определенных в ConfigParser. Возвращает словарь с параметрами
    или словарь с ошибкой в случае неудачи.
    
    Returns:
        dict: Словарь с параметрами командной строки или {"error": str(e)}
    """
    # Декоратор для общих опций CLI
    @ConfigParser.common_options
    def options_func():
        pass

    def extract_click_params(decorated_function):
        """
        Извлекает параметры Click из декорированной функции.
        
        Args:
            decorated_function: Функция с декораторами Click
            
        Returns:
            list: Список параметров Click
        """
        if hasattr(decorated_function, "__click_params__"):
            return decorated_function.__click_params__
        return []

    # Создаем командную строку с помощью CustomClickPrinter
    cmd = CustomClickPrinter("Marker app.")
    extracted_params = extract_click_params(options_func)
    cmd.params.extend(extracted_params)
    ctx = click.Context(cmd)
    try:
        # Парсим аргументы командной строки
        cmd_args = sys.argv[1:]
        cmd.parse_args(ctx, cmd_args)
        return ctx.params
    except click.exceptions.ClickException as e:
        # Возвращаем ошибку в случае неудачного парсинга
        return {"error": str(e)}


@st.cache_resource()
def load_models():
    """
    Загружает и кэширует модели для обработки документов.
    
    Использует Streamlit cache для сохранения загруженных моделей
    между вызовами, что повышает производительность приложения.
    
    Returns:
        dict: Словарь загруженных моделей
    """
    return create_model_dict()


def open_pdf(pdf_file):
    """
    Открывает PDF файл и создает объект PdfDocument.
    
    Использует библиотеку pypdfium2 для открытия PDF файла из байтового потока.
    
    Args:
        pdf_file: Файл PDF (UploadedFile из Streamlit)
        
    Returns:
        pypdfium2.PdfDocument: Объект PDF документа для дальнейшей обработки
    """
    # Создаем байтовый поток из файла
    stream = io.BytesIO(pdf_file.getvalue())
    return pypdfium2.PdfDocument(stream)


def img_to_html(img, img_alt):
    """
    Конвертирует изображение PIL в HTML тег img с base64 кодированием.
    
    Функция сохраняет изображение в памяти, кодирует его в base64
    и создает HTML тег img с соответствующими атрибутами.
    
    Args:
        img (Image.Image): Изображение PIL для конвертации
        img_alt (str): Альтернативный текст для изображения
        
    Returns:
        str: HTML строка с изображением в формате base64
    """
    # Сохраняем изображение в байтовый поток
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=settings.OUTPUT_IMAGE_FORMAT)
    img_bytes = img_bytes.getvalue()
    
    # Кодируем изображение в base64
    encoded = base64.b64encode(img_bytes).decode()
    
    # Создаем HTML тег img с настройками из конфигурации
    img_html = f'<img src="data:image/{settings.OUTPUT_IMAGE_FORMAT.lower()};base64,{encoded}" alt="{img_alt}" style="max-width: 100%;">'
    return img_html


@st.cache_data()
def get_page_image(pdf_file, page_num, dpi=96):
    """
    Получает изображение страницы PDF или другого документа.
    
    Функция кэшируется Streamlit для повышения производительности.
    
    Args:
        pdf_file: Файл документа (PDF или изображение)
        page_num (int): Номер страницы (начиная с 0)
        dpi (int): Разрешение рендеринга в точках на дюйм (по умолчанию 96)
        
    Returns:
        Image.Image: Изображение PIL в формате RGB
    """
    if "pdf" in pdf_file.type:
        # Обрабатываем PDF файл
        doc = open_pdf(pdf_file)
        page = doc[page_num]
        # Рендерим страницу с заданным разрешением и конвертируем в PIL
        png_image = (
            page.render(
                scale=dpi / 72,  # Масштабируем для нужного DPI (72 - базовое разрешение PDF)
            )
            .to_pil()
            .convert("RGB")
        )
    else:
        # Обрабатываем изображение
        png_image = Image.open(pdf_file).convert("RGB")
    return png_image


@st.cache_data()
def page_count(pdf_file: UploadedFile):
    """
    Определяет количество страниц в документе.
    
    Функция кэшируется Streamlit для оптимизации производительности.
    
    Args:
        pdf_file (UploadedFile): Файл для анализа
        
    Returns:
        int: Количество страниц в документе (1 для не-PDF файлов)
    """
    if "pdf" in pdf_file.type:
        # Для PDF файлов возвращаем количество страниц минус 1 (индексация с 0)
        doc = open_pdf(pdf_file)
        return len(doc) - 1
    else:
        # Для других файлов возвращаем 1 страницу
        return 1


def pillow_image_to_base64_string(img: Image) -> str:
    """
    Конвертирует изображение PIL в base64 строку формата JPEG.
    
    Функция используется для подготовки изображений к отправке
    или сохранения в базе данных.
    
    Args:
        img (Image.Image): Исходное изображение PIL
        
    Returns:
        str: Base64 строка изображения в формате JPEG
    """
    # Создаем буфер для сохранения изображения
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def extract_root_pydantic_class(schema_code: str) -> Optional[str]:
    """
    Извлекает корневой класс Pydantic из кода схемы данных.
    
    Функция анализирует AST дерево кода схемы и определяет основной
    корневой класс, который наследуется от BaseModel. Использует
    эвристики для определения "корневого" класса среди множества классов.
    
    Args:
        schema_code (str): Код Python с определениями Pydantic моделей
        
    Returns:
        Optional[str]: Имя корневого класса или None, если не удалось определить
    """
    try:
        # Парсим код в AST дерево
        tree = ast.parse(schema_code)

        # Находим все классы, наследующиеся от BaseModel
        class_names = set()
        class_info = {}  # Информация о каждом классе

        # Проходим по всем узлам AST
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Проверяем, наследуется ли класс от BaseModel
                is_pydantic = False
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseModel":
                        is_pydantic = True
                        break

                if is_pydantic:
                    # Добавляем класс в набор
                    class_names.add(node.name)
                    class_info[node.name] = {
                        "references": set(),  # Классы, на которые ссылается данный класс
                        "fields": [],  # Имена полей в данном классе
                    }

                    # Извлекаем информацию о полях
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(
                            item.target, ast.Name
                        ):
                            field_name = item.target.id
                            class_info[node.name]["fields"].append(field_name)

                            # Проверяем, ссылается ли это поле на другой класс
                            annotation_str = ast.unparse(item.annotation)

                            # Ищем паттерны ссылок на другие классы
                            for other_class in class_names:
                                pattern = rf"(?:List|Dict|Set|Tuple|Optional|Union)?\[.*{other_class}.*\]|{other_class}"
                                if re.search(pattern, annotation_str):
                                    class_info[node.name]["references"].add(other_class)

        # Если найден только один класс, возвращаем его
        if len(class_names) == 1:
            return list(class_names)[0]

        # Находим все классы, на которые ссылаются
        referenced_classes = set()
        for class_name, info in class_info.items():
            referenced_classes.update(info["references"])

        # Находим классы, которые ссылаются на другие, но на которые не ссылаются сами
        root_candidates = set()
        for class_name, info in class_info.items():
            if info["references"] and class_name not in referenced_classes:
                root_candidates.add(class_name)

        # Если найден ровно один кандидат на корневой класс, возвращаем его
        if len(root_candidates) == 1:
            return list(root_candidates)[0]

        return None
    except Exception as e:
        # Логируем ошибку и возвращаем None
        print(f"Error parsing schema: {e}")
        return None


def get_root_class(schema_code: str) -> Optional[BaseModel]:
    """
    Получает объект корневого класса из кода схемы.
    
    Функция сначала находит имя корневого класса, затем добавляет
    необходимые импорты и выполняет код для получения объекта класса.
    
    Args:
        schema_code (str): Код Python с определениями Pydantic моделей
        
    Returns:
        Optional[BaseModel]: Объект корневого класса или None, если не удалось получить
    """
    # Находим имя корневого класса
    root_class_name = extract_root_pydantic_class(schema_code)

    if not root_class_name:
        return None

    # Добавляем необходимые импорты, если они отсутствуют
    if "from pydantic" not in schema_code:
        schema_code = "from pydantic import BaseModel\n" + schema_code
    if "from typing" not in schema_code:
        schema_code = (
            "from typing import List, Dict, Optional, Set, Tuple, Union, Any\n\n"
            + schema_code
        )

    # Выполняем код в новом пространстве имен
    namespace = {}
    exec(schema_code, namespace)

    # Возвращаем объект корневого класса
    return namespace.get(root_class_name)
