# Модуль процессора заголовков страниц
# Перемещает блоки PageHeader в начало структуры страницы

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup


class PageHeaderProcessor(BaseProcessor):
    """
    Процессор для перемещения колонтитулов (PageHeader) в начало страницы.
    
    Несмотря на то что колонтитулы (headers) физически расположены вверху страницы,
    после layout detection они могут быть где угодно в порядке чтения. Этот процессор
    гарантирует, что они окажутся в начале структуры страницы.
    """
    block_types = (BlockTypes.PageHeader,)

    def __call__(self, document: Document):
        """
        Применяет перемещение колонтитулов ко всем страницам документа.
        
        Аргументы:
            document: Документ для обработки
        """
        # Обрабатываем каждую страницу документа
        for page in document.pages:
            self.move_page_header_to_top(page, document)

    def move_page_header_to_top(self, page: PageGroup, document: Document):
        """
        Перемещает все PageHeader-блоки в начало структуры страницы.
        
        Аргументы:
            page: Страница, структура которой будет изменена
            document: Документ для поиска блоков на странице
        """
        # Находим все блоки PageHeader на странице
        page_header_blocks = page.contained_blocks(document, self.block_types)
        page_header_block_ids = [block.id for block in page_header_blocks]
        # Удаляем их из текущих позиций в структуре
        for block_id in page_header_block_ids:
            page.structure.remove(block_id)
        # Вставляем все PageHeader в начало структуры страницы (перед индексом 0)
        page.structure[:0] = page_header_block_ids

