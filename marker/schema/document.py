# Модуль модели документа
# Определяет структуру полного документа с страницами, оглавлением и методами навигации

from __future__ import annotations

from typing import List, Sequence, Optional

from pydantic import BaseModel

from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockId, BlockOutput
from marker.schema.groups.page import PageGroup


# Модель вывода документа для рендеринга
# Содержит отрендеренные дочерние блоки и HTML представление
class DocumentOutput(BaseModel):
    children: List[BlockOutput]  # Список отрендеренных дочерних блоков (страницы)
    html: str  # HTML представление всего документа
    block_type: BlockTypes = BlockTypes.Document  # Тип блока - документ


# Элемент оглавления
# Описывает отдельный пункт в содержании документа
class TocItem(BaseModel):
    title: str  # Заголовок пункта оглавления
    heading_level: int  # Уровень заголовка (1 для H1, 2 для H2 и т.д.)
    page_id: int  # Идентификатор страницы, где находится заголовок
    polygon: List[List[float]]  # Координаты заголовка на странице в формате [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]


# Модель полного документа
# Корневая модель, содержащая все страницы документа и метаданные
class Document(BaseModel):
    filepath: str  # Путь к исходному файлу документа
    pages: List[PageGroup]  # Список страниц документа
    block_type: BlockTypes = BlockTypes.Document  # Тип блока - документ
    table_of_contents: List[TocItem] | None = None  # Оглавление документа (если доступно)
    debug_data_path: str | None = None  # Путь к сохраненным отладочным данным

    # Получить блок по его идентификатору
    # Находит страницу по block_id.page_id, затем ищет блок на этой странице
    def get_block(self, block_id: BlockId):
        page = self.get_page(block_id.page_id)  # Находим страницу по ID
        block = page.get_block(block_id)  # Ищем блок на странице
        if block:
            return block
        return None  # Блок не найден

    # Получить страницу по её идентификатору
    # Ищет страницу в списке pages по page_id
    def get_page(self, page_id):
        for page in self.pages:
            if page.page_id == page_id:
                return page  # Страница найдена
        return None  # Страница не найдена

    # Получить следующий блок после указанного
    # Сначала ищет на текущей странице, затем на последующих страницах
    # ignored_block_types: типы блоков, которые нужно пропустить при поиске
    def get_next_block(
        self, block: Block, ignored_block_types: List[BlockTypes] = None
    ):
        if ignored_block_types is None:
            ignored_block_types = []  # По умолчанию не игнорируем никакие типы
        next_block = None

        # Пытаемся найти следующий блок на текущей странице
        page = self.get_page(block.page_id)
        next_block = page.get_next_block(block, ignored_block_types)
        if next_block:
            return next_block  # Блок найден на текущей странице

        # Если блок не найден, ищем на последующих страницах
        for page in self.pages[self.pages.index(page) + 1 :]:
            next_block = page.get_next_block(None, ignored_block_types)
            if next_block:
                return next_block  # Блок найден на одной из следующих страниц
        return None  # Блок не найден нигде

    # Получить следующую страницу после указанной
    # Возвращает None, если это последняя страница
    def get_next_page(self, page: PageGroup):
        page_idx = self.pages.index(page)  # Находим индекс текущей страницы
        if page_idx + 1 < len(self.pages):
            return self.pages[page_idx + 1]  # Возвращаем следующую страницу
        return None  # Это последняя страница

    # Получить предыдущий блок перед указанным
    # Сначала ищет на текущей странице, затем на предыдущих страницах
    def get_prev_block(self, block: Block):
        page = self.get_page(block.page_id)  # Находим страницу блока
        prev_block = page.get_prev_block(block)  # Ищем предыдущий на странице
        if prev_block:
            return prev_block  # Блок найден на текущей странице
        prev_page = self.get_prev_page(page)  # Получаем предыдущую страницу
        if not prev_page:
            return None  # Нет предыдущей страницы
        return prev_page.get_block(prev_page.structure[-1])  # Возвращаем последний блок предыдущей страницы

    # Получить предыдущую страницу перед указанной
    # Возвращает None, если это первая страница
    def get_prev_page(self, page: PageGroup):
        page_idx = self.pages.index(page)  # Находим индекс текущей страницы
        if page_idx > 0:
            return self.pages[page_idx - 1]  # Возвращаем предыдущую страницу
        return None  # Это первая страница

    # Собрать HTML из дочерних блоков
    # Создает шаблон с ссылками на содержимое дочерних блоков
    def assemble_html(
        self, child_blocks: List[Block], block_config: Optional[dict] = None
    ):
        template = ""
        for c in child_blocks:
            template += f"<content-ref src='{c.id}'></content-ref>"  # Добавляем ссылку на блок
        return template

    # Отрендерить весь документ
    # Рендерит все страницы и собирает результат в DocumentOutput
    # section_hierarchy: иерархия заголовков разделов, сохраняется между страницами
    def render(self, block_config: Optional[dict] = None):
        child_content = []
        section_hierarchy = None  # Иерархия заголовков между страницами
        for page in self.pages:
            rendered = page.render(self, None, section_hierarchy, block_config)
            section_hierarchy = rendered.section_hierarchy.copy()  # Сохраняем для следующей страницы
            child_content.append(rendered)  # Добавляем отрендеренную страницу

        return DocumentOutput(
            children=child_content,
            html=self.assemble_html(child_content, block_config),
        )

    # Получить все блоки указанных типов из документа
    # Если block_types=None, возвращает все блоки
    def contained_blocks(self, block_types: Sequence[BlockTypes] = None) -> List[Block]:
        blocks = []
        for page in self.pages:
            blocks += page.contained_blocks(self, block_types)  # Собираем блоки с каждой страницы
        return blocks
