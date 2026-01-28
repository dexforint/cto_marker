"""
Модуль рендеринга документов в HTML формат.

Предоставляет рендерер для преобразования внутреннего представления документа
в полноценный HTML с изображениями и метаданными. Поддерживает пагинацию,
извлечение изображений и добавление block IDs для отслеживания.

Основные возможности:
- Преобразование документа в валидный HTML5
- Извлечение изображений в виде файлов PIL
- Поддержка пагинации по страницам
- Добавление data-block-id атрибутов для отслеживания
- Генерация метаданных документа и страниц
"""

import textwrap

from PIL import Image
from typing import Annotated, Tuple

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from pydantic import BaseModel

from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.settings import settings

# Игнорируем предупреждения beautifulsoup
import warnings

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Подавляем ошибку DecompressionBombError для больших изображений
Image.MAX_IMAGE_PIXELS = None


class HTMLOutput(BaseModel):
    """
    Модель выходных данных HTML рендеринга.
    
    Атрибуты:
        html: Полный HTML документ в виде строки
        images: Словарь изображений {имя_файла: PIL.Image}
        metadata: Метаданные документа (содержание, статистика страниц)
    """
    html: str
    images: dict
    metadata: dict


class HTMLRenderer(BaseRenderer):
    """
    Рендерер для преобразования документов в HTML формат.
    
    Создает полноценный HTML5 документ с изображениями, метаданными и опциональной
    пагинацией. Изображения извлекаются как PIL.Image объекты для последующего
    сохранения пользователем.
    
    Атрибуты:
        page_blocks: Типы блоков, которые считаются страницами
        paginate_output: Добавлять ли div обертки для страниц с data-page-id
    """

    page_blocks: Annotated[
        Tuple[BlockTypes],
        "The block types to consider as pages.",
    ] = (BlockTypes.Page,)
    paginate_output: Annotated[
        bool,
        "Whether to paginate the output.",
    ] = False

    def extract_image(self, document, image_id):
        """
        Извлекает изображение из документа как PIL.Image.
        
        Аргументы:
            document: Документ для извлечения изображения
            image_id: ID блока изображения
            
        Возвращает:
            PIL.Image: Извлеченное изображение
        """
        # Получаем блок изображения
        image_block = document.get_block(image_id)
        # Извлекаем в нужном качестве
        cropped = image_block.get_image(
            document, highres=self.image_extraction_mode == "highres"
        )
        return cropped

    def insert_block_id(self, soup, block_id: BlockId):
        """
        Вставляет ID блока в soup как data атрибут.
        
        Добавляет data-block-id атрибут к внешнему тегу в soup для отслеживания
        блоков в выходном HTML. Пропускает Line и Span блоки.
        
        Аргументы:
            soup: BeautifulSoup объект для модификации
            block_id: ID блока для вставки
            
        Возвращает:
            BeautifulSoup: Модифицированный soup с block ID
        """
        # Пропускаем Line и Span блоки (слишком детальные)
        if block_id.block_type in [BlockTypes.Line, BlockTypes.Span]:
            return soup

        if self.add_block_ids:
            # Находим самый внешний тег (первый тег который не NavigableString)
            outermost_tag = None
            for element in soup.contents:
                if hasattr(element, "name") and element.name:
                    outermost_tag = element
                    break

            # Если нашли внешний тег, добавляем атрибут data-block-id
            if outermost_tag:
                outermost_tag["data-block-id"] = str(block_id)

            # Если soup содержит только текст или нет тегов, оборачиваем в span
            elif soup.contents:
                wrapper = soup.new_tag("span")
                wrapper["data-block-id"] = str(block_id)

                # Перемещаем все содержимое в wrapper
                contents = list(soup.contents)
                for content in contents:
                    content.extract()
                    wrapper.append(content)
                soup.append(wrapper)
        return soup

    def extract_html(self, document, document_output, level=0):
        """
        Рекурсивно извлекает HTML из документа, обрабатывая content-ref теги.
        
        Заменяет content-ref теги на реальный контент или изображения,
        добавляет block IDs и обертки для страниц при пагинации.
        
        Аргументы:
            document: Документ для извлечения
            document_output: Выходные данные рендеринга документа
            level: Уровень рекурсии (0 = корневой уровень)
            
        Возвращает:
            tuple: (HTML строка, словарь изображений {имя_файла: PIL.Image})
        """
        # Парсим HTML
        soup = BeautifulSoup(document_output.html, "html.parser")

        # Находим все ссылки на дочерние блоки
        content_refs = soup.find_all("content-ref")
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get("src")
            sub_images = {}
            content = ""
            for item in document_output.children:
                if item.id == src:
                    content, sub_images_ = self.extract_html(document, item, level + 1)
                    sub_images.update(sub_images_)
                    ref_block_id: BlockId = item.id
                    break

            if ref_block_id.block_type in self.image_blocks:
                if self.extract_images:
                    image = self.extract_image(document, ref_block_id)
                    image_name = f"{ref_block_id.to_path()}.{settings.OUTPUT_IMAGE_FORMAT.lower()}"
                    images[image_name] = image
                    element = BeautifulSoup(
                        f"<p>{content}<img src='{image_name}'></p>", "html.parser"
                    )
                    ref.replace_with(self.insert_block_id(element, ref_block_id))
                else:
                    # This will be the image description if using llm mode, or empty if not
                    element = BeautifulSoup(f"{content}", "html.parser")
                    ref.replace_with(self.insert_block_id(element, ref_block_id))
            elif ref_block_id.block_type in self.page_blocks:
                images.update(sub_images)
                if self.paginate_output:
                    content = f"<div class='page' data-page-id='{ref_block_id.page_id}'>{content}</div>"
                element = BeautifulSoup(f"{content}", "html.parser")
                ref.replace_with(self.insert_block_id(element, ref_block_id))
            else:
                images.update(sub_images)
                element = BeautifulSoup(f"{content}", "html.parser")
                ref.replace_with(self.insert_block_id(element, ref_block_id))

        output = str(soup)
        if level == 0:
            output = self.merge_consecutive_tags(output, "b")
            output = self.merge_consecutive_tags(output, "i")
            output = self.merge_consecutive_math(
                output
            )  # Merge consecutive inline math tags
            output = textwrap.dedent(f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="utf-8" />
                </head>
                <body>
                    {output}
                </body>
            </html>
""")

        return output, images

    def __call__(self, document) -> HTMLOutput:
        """
        Рендерит документ в HTML формат.
        
        Аргументы:
            document: Document для рендеринга
            
        Возвращает:
            HTMLOutput: Объект с HTML, изображениями и метаданными
        """
        # Рендерим документ в BlockOutput структуру
        document_output = document.render(self.block_config)
        # Извлекаем HTML и изображения
        full_html, images = self.extract_html(document, document_output)
        # Форматируем HTML с отступами
        soup = BeautifulSoup(full_html, "html.parser")
        full_html = soup.prettify()  # Добавляем отступы для читаемости
        # Возвращаем результат
        return HTMLOutput(
            html=full_html,
            images=images,
            metadata=self.generate_document_metadata(document, document_output),
        )
