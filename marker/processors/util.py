# Модуль утилит для processors
# Вспомогательные функции для работы с математическими формулами и span-блоками

import re

from bs4 import BeautifulSoup

from marker.schema import BlockTypes
from marker.schema.groups import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text import Line


def escape_latex_commands(text: str):
    """
    Экранирует управляющие символы внутри LaTeX/Math-разметки.
    
    В некоторых сценариях математический контент помещается внутрь HTML-тега <math>.
    Чтобы не «сломать» структуру строк и корректно передавать значения дальше,
    переносы строк и табуляции заменяются на явные последовательности "\\n", "\\t", "\\r".
    
    Аргументы:
        text: Строка с LaTeX/математическим контентом
    
    Возвращает:
        Строку с экранированными управляющими символами
    """
    # Заменяем реальные управляющие символы на текстовые последовательности
    text = (text
            .replace('\n', '\\n')
            .replace('\t', '\\t')
            .replace('\r', '\\r'))
    return text


def add_math_spans_to_line(corrected_text: str, text_line: Line, page: PageGroup):
    """
    Преобразует HTML-размеченный текст (с тегами <math>, <b>, <i> и др.) в последовательность Span-блоков.
    
    Используется при LLM-коррекции текста: LLM возвращает размеченный HTML (с тегами для математики,
    жирного/наклонного текста, ссылок), который мы разбираем на отдельные span'ы и добавляем в структуру
    текстовой линии (Line).
    
    Аргументы:
        corrected_text: HTML-строка с разметкой от LLM (например, "Пример: <math>x^2</math> и <b>жирный</b> текст.")
        text_line: Текстовая линия (Line), в структуру которой будут добавлены Span-блоки
        page: Страница, на которой создаются блоки
    """
    # Получаем класс Span из registry
    SpanClass = get_block_class(BlockTypes.Span)
    # Разбираем HTML на список span'ов (словарей с 'type', 'content', 'url', суб/суперскрипт-флагами)
    corrected_spans = text_to_spans(corrected_text)

    # Создаём блоки Span для каждого фрагмента размеченного текста
    for span_idx, span in enumerate(corrected_spans):
        # Добавляем перевод строки после последнего span'а, чтобы не склеивать с последующей линией
        if span_idx == len(corrected_spans) - 1:
            span['content'] += "\n"

        # Создаём Span-блок (полноценный блок в дереве документа)
        span_block = page.add_full_block(
            SpanClass(
                polygon=text_line.polygon,  # Берём полигон исходной линии (реальные координаты могут быть неизвестны)
                text=span['content'],  # Сам текст span'а
                font='Unknown',  # Шрифт неизвестен после LLM-обработки
                font_weight=0,
                font_size=0,
                minimum_position=0,
                maximum_position=0,
                formats=[span['type']],  # Тип форматирования: 'plain', 'bold', 'italic', 'math'
                url=span.get('url'),  # Ссылка, если span — это <a href="...">
                page_id=text_line.page_id,
                text_extraction_method="gemini",  # Отмечаем, что этот span создан LLM
                has_superscript=span["has_superscript"],  # Флаг <sup>
                has_subscript=span["has_subscript"]  # Флаг <sub>
            )
        )
        # Добавляем созданный Span-блок в структуру текстовой линии
        text_line.structure.append(span_block.id)


def text_to_spans(text):
    """
    Разбирает HTML-строку и превращает её в плоский список «span-описаний».
    
    На вход ожидается простой HTML без глубокой вложенности, где верхнеуровневые теги
    могут быть <b>, <i>, <math>, <sub>, <sup>, <span>, а также обычный текст.
    
    Аргументы:
        text: HTML-строка
    
    Возвращает:
        Список словарей, каждый из которых описывает один span-фрагмент:
        - type: тип форматирования ('plain', 'bold', 'italic', 'math')
        - content: текстовое содержимое
        - url: ссылка (если была)
        - has_superscript / has_subscript: признаки <sup>/<sub>
    """
    # Парсим HTML в дерево BeautifulSoup
    soup = BeautifulSoup(text, 'html.parser')

    # Сопоставление тегов и внутренних типов форматирования в Marker
    tag_types = {
        'b': 'bold',
        'i': 'italic',
        'math': 'math',
        'sub': 'plain',
        'sup': 'plain',
        'span': 'plain'
    }
    # Накопитель итоговых span-фрагментов
    spans = []

    # Проходим по всем узлам дерева HTML
    for element in soup.descendants:
        # Поддерживаем только элементы первого уровня вложенности относительно корневого soup
        # (это защищает от неожиданной структуры HTML)
        if not len(list(element.parents)) == 1:
            continue

        # Если у элемента есть атрибуты и среди них href — считаем это ссылкой
        url = element.attrs.get('href') if hasattr(element, 'attrs') else None

        # Если это известный тег форматирования, извлекаем его текст и тип
        if element.name in tag_types:
            text = element.get_text()
            # Для математики экранируем управляющие символы
            if element.name == "math":
                text = escape_latex_commands(text)
            spans.append({
                'type': tag_types[element.name],
                'content': text,
                'url': url,
                "has_superscript": element.name == "sup",
                "has_subscript": element.name == "sub"
            })
        # Иначе, если это текстовый узел, добавляем его как обычный plain span
        elif element.string:
            spans.append({
                'type': 'plain',
                'content': element.string,
                'url': url,
                "has_superscript": False,
                "has_subscript": False
            })

    return spans