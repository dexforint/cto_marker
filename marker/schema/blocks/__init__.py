# Модуль типов блоков документа
# Экспортирует все основные модели блоков, представляющих элементы документа

from __future__ import annotations

# Базовые классы
from marker.schema.blocks.base import Block, BlockId, BlockOutput  # Базовый класс блока, его идентификатор и модель вывода

# Блоки текстового контента
from marker.schema.blocks.caption import Caption  # Подпись к элементу (рисунок, таблица)
from marker.schema.blocks.code import Code  # Блок программного кода
from marker.schema.blocks.text import Text  # Обычный текстовый параграф
from marker.schema.blocks.sectionheader import SectionHeader  # Заголовок раздела (H1, H2 и т.д.)

# Блоки со специальным контентом
from marker.schema.blocks.equation import Equation  # Математическое уравнение (блочное)
from marker.schema.blocks.inlinemath import InlineMath  # Inline математические формулы
from marker.schema.blocks.figure import Figure  # Рисунок или диаграмма
from marker.schema.blocks.picture import Picture  # Изображение/картинка
from marker.schema.blocks.table import Table  # Таблица
from marker.schema.blocks.tablecell import TableCell  # Ячейка таблицы

# Списки и их элементы
from marker.schema.blocks.listitem import ListItem  # Элемент списка (маркированного или нумерованного)

# Элементы оформления страницы
from marker.schema.blocks.pageheader import PageHeader  # Верхний колонтитул страницы
from marker.schema.blocks.pagefooter import PageFooter  # Нижний колонтитул страницы
from marker.schema.blocks.footnote import Footnote  # Сноска (дополнительная информация)

# Другие типы блоков
from marker.schema.blocks.handwriting import Handwriting  # Рукописный текст
from marker.schema.blocks.form import Form  # Форма для ввода данных
from marker.schema.blocks.toc import TableOfContents  # Оглавление документа
from marker.schema.blocks.reference import Reference  # Библиографическая ссылка
from marker.schema.blocks.complexregion import ComplexRegion  # Сложный регион с mixed content (для LLM обработки)
