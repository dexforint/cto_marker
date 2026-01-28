# Модуль для сохранения результатов конвертации документов
# Обрабатывает различные форматы вывода (Markdown, HTML, JSON) и сохраняет изображения

import json
import os

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel
from PIL import Image

# Импортируем типы выходных данных для различных renderers
from marker.renderers.extraction import ExtractionOutput
from marker.renderers.html import HTMLOutput
from marker.renderers.json import JSONOutput, JSONBlockOutput
from marker.renderers.markdown import MarkdownOutput
from marker.renderers.ocr_json import OCRJSONOutput
from marker.schema.blocks import BlockOutput
from marker.settings import settings


def unwrap_outer_tag(html: str):
    """
    Удаляет внешний тег <p> из HTML, если он единственный.
    Используется для очистки HTML от ненужных обертывающих тегов.
    
    Аргументы:
        html: HTML строка для обработки
        
    Возвращает:
        Обработанная HTML строка без внешнего <p> тега
    """
    # Парсим HTML с помощью BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # Получаем список всех элементов верхнего уровня
    contents = list(soup.contents)
    # Если есть только один элемент и это <p> тег
    if len(contents) == 1 and isinstance(contents[0], Tag) and contents[0].name == "p":
        # Удаляем обертку <p> тега (оставляем только содержимое)
        soup.p.unwrap()

    # Возвращаем обработанный HTML как строку
    return str(soup)


def json_to_html(block: JSONBlockOutput | BlockOutput):
    """
    Рекурсивно преобразует JSON блок в HTML.
    Заменяет теги <content-ref> на реальное содержимое дочерних блоков.
    
    Используется для сборки полного HTML из древовидной структуры блоков,
    где родительские блоки содержат ссылки на дочерние через <content-ref>.
    
    Аргументы:
        block: Блок JSON вывода (может иметь дочерние блоки)
        
    Возвращает:
        HTML строка с полностью разрешенными ссылками на дочерние блоки
    """
    # Если у блока нет дочерних элементов, возвращаем его HTML как есть
    if not getattr(block, "children", None):
        return block.html
    else:
        # Рекурсивно получаем HTML для всех дочерних блоков
        child_html = [json_to_html(child) for child in block.children]
        # Создаем список ID дочерних блоков для быстрого поиска
        child_ids = [child.id for child in block.children]

        # Парсим HTML текущего блока
        soup = BeautifulSoup(block.html, "html.parser")
        # Находим все теги <content-ref> (ссылки на дочерние блоки)
        content_refs = soup.find_all("content-ref")
        # Для каждой ссылки
        for ref in content_refs:
            # Получаем ID целевого дочернего блока
            src_id = ref.attrs["src"]
            # Если такой дочерний блок существует
            if src_id in child_ids:
                # Получаем HTML дочернего блока и парсим его
                child_soup = BeautifulSoup(
                    child_html[child_ids.index(src_id)], "html.parser"
                )
                # Заменяем <content-ref> на реальное содержимое дочернего блока
                ref.replace_with(child_soup)
        # Возвращаем собранный HTML
        return str(soup)


def output_exists(output_dir: str, fname_base: str):
    """
    Проверяет, существует ли уже файл с результатами конвертации.
    
    Аргументы:
        output_dir: Директория для проверки
        fname_base: Базовое имя файла (без расширения)
        
    Возвращает:
        True если найден файл с любым из поддерживаемых расширений (md, html, json)
    """
    # Список поддерживаемых расширений файлов
    exts = ["md", "html", "json"]
    # Проверяем наличие файла с каждым расширением
    for ext in exts:
        if os.path.exists(os.path.join(output_dir, f"{fname_base}.{ext}")):
            return True
    # Не найдено ни одного файла
    return False


def text_from_rendered(rendered: BaseModel):
    """
    Извлекает текст, расширение файла и изображения из отрендеренного результата.
    
    Обрабатывает различные типы выходных форматов (Markdown, HTML, JSON и др.)
    и возвращает единообразный кортеж.
    
    Аргументы:
        rendered: Отрендеренный результат (Pydantic модель от renderer)
        
    Возвращает:
        Кортеж из трех элементов:
        - text: Текст результата (markdown/html/json строка)
        - ext: Расширение файла ("md", "html", "json")
        - images: Словарь изображений {имя: PIL.Image}
        
    Raises:
        ValueError: Если тип результата не поддерживается
    """
    # Импортируем здесь, чтобы избежать циклических импортов
    from marker.renderers.chunk import ChunkOutput  # Has an import from this file

    # Определяем тип результата и возвращаем соответствующие данные
    if isinstance(rendered, MarkdownOutput):
        # Markdown формат - возвращаем markdown текст и изображения
        return rendered.markdown, "md", rendered.images
    elif isinstance(rendered, HTMLOutput):
        # HTML формат - возвращаем HTML текст и изображения
        return rendered.html, "html", rendered.images
    elif isinstance(rendered, JSONOutput):
        # JSON формат - сериализуем модель в JSON (без metadata)
        return rendered.model_dump_json(exclude=["metadata"], indent=2), "json", {}
    elif isinstance(rendered, ChunkOutput):
        # Chunks формат - сериализуем модель в JSON (без metadata)
        return rendered.model_dump_json(exclude=["metadata"], indent=2), "json", {}
    elif isinstance(rendered, OCRJSONOutput):
        # OCR JSON формат - сериализуем модель в JSON (без metadata)
        return rendered.model_dump_json(exclude=["metadata"], indent=2), "json", {}
    elif isinstance(rendered, ExtractionOutput):
        # Extraction формат - возвращаем JSON документа
        return rendered.document_json, "json", {}
    else:
        # Неподдерживаемый тип результата
        raise ValueError("Invalid output type")


def convert_if_not_rgb(image: Image.Image) -> Image.Image:
    """
    Конвертирует изображение в RGB режим, если оно в другом режиме.
    Необходимо для сохранения в JPEG (формат не поддерживает RGBA и другие режимы).
    
    Аргументы:
        image: PIL изображение
        
    Возвращает:
        PIL изображение в RGB режиме
    """
    # Проверяем режим изображения
    if image.mode != "RGB":
        # Конвертируем в RGB (например, RGBA -> RGB)
        image = image.convert("RGB")
    return image


def save_output(rendered: BaseModel, output_dir: str, fname_base: str):
    """
    Сохраняет результаты конвертации в файлы.
    
    Создает три типа файлов:
    1. Основной файл с результатом (markdown/html/json)
    2. Файл с метаданными (_meta.json)
    3. Извлеченные изображения (если есть)
    
    Аргументы:
        rendered: Отрендеренный результат конвертации
        output_dir: Директория для сохранения файлов
        fname_base: Базовое имя файла (без расширения)
    """
    # Извлекаем текст, расширение и изображения из результата
    text, ext, images = text_from_rendered(rendered)
    # Перекодируем текст с обработкой ошибок (заменяем неподдерживаемые символы)
    # Это предотвращает ошибки при наличии специальных символов
    text = text.encode(settings.OUTPUT_ENCODING, errors="replace").decode(
        settings.OUTPUT_ENCODING
    )

    # Сохраняем основной файл с результатом конвертации
    with open(
        os.path.join(output_dir, f"{fname_base}.{ext}"),
        "w+",
        encoding=settings.OUTPUT_ENCODING,
    ) as f:
        f.write(text)
    
    # Сохраняем метаданные в отдельный JSON файл
    # Содержит оглавление, статистику по страницам и другую информацию
    with open(
        os.path.join(output_dir, f"{fname_base}_meta.json"),
        "w+",
        encoding=settings.OUTPUT_ENCODING,
    ) as f:
        f.write(json.dumps(rendered.metadata, indent=2))

    # Сохраняем все извлеченные изображения
    for img_name, img in images.items():
        # Конвертируем в RGB если необходимо (RGBA нельзя сохранить как JPG)
        img = convert_if_not_rgb(img)  # RGBA images can't save as JPG
        # Сохраняем изображение в указанном формате (по умолчанию JPEG)
        img.save(os.path.join(output_dir, img_name), settings.OUTPUT_IMAGE_FORMAT)
