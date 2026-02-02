# Модуль процессора оглавления документа
# Собирает все заголовки разделов в структурированное оглавление (Table of Contents)

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class DocumentTOCProcessor(BaseProcessor):
    """
    Процессор для генерации оглавления документа (Table of Contents).
    
    Собирает все блоки типа SectionHeader со всех страниц документа
    и формирует из них структурированное оглавление с заголовками,
    уровнями вложенности, координатами и номерами страниц.
    """
    block_types = (BlockTypes.SectionHeader, )

    def __call__(self, document: Document):
        """
        Генерирует оглавление документа.
        
        Проходит по всем страницам документа, находит заголовки разделов
        и формирует список элементов оглавления с метаданными.
        
        Аргументы:
            document: Документ для обработки
        """
        # Накопитель элементов оглавления
        toc = []
        # Проходим по всем страницам
        for page in document.pages:
            # Находим все заголовки разделов на странице
            for block in page.contained_blocks(document, self.block_types):
                # Добавляем элемент оглавления с метаданными
                toc.append({
                    "title": block.raw_text(document).strip(),  # Текст заголовка
                    "heading_level": block.heading_level,  # Уровень вложенности (H1, H2, H3 и т.д.)
                    "page_id": page.page_id,  # Номер страницы
                    "polygon": block.polygon.polygon  # Координаты заголовка на странице
                })
        # Сохраняем оглавление в документе
        document.table_of_contents = toc
