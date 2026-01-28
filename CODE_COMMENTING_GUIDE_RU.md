# Руководство по комментированию кода Marker

Этот документ содержит подробные примеры комментирования для всех типов файлов в проекте Marker. Используйте эти шаблоны как образец для понимания и документирования кода.

## Принципы комментирования

### 1. Комментарии на русском языке
Все комментарии в этом проекте написаны на русском языке для облегчения понимания.

### 2. Уровни комментариев

- **Модульный уровень** (в начале файла) - описание назначения модуля
- **Класс/функция** - docstring с описанием, аргументами и возвращаемыми значениями  
- **Код** - комментарии над строкой, объясняющие логику

### 3. Что комментировать

✅ Назначение модуля/класса/функции  
✅ Сложная логика и алгоритмы  
✅ Важные решения и архитектурные выборы  
✅ Нетривиальные параметры и их значение  
✅ Edge cases и особенности обработки  

❌ Очевидный код (например: `x = 1  # устанавливаем x в 1`)  
❌ Повторение того, что уже ясно из имен переменных

---

## Шаблоны комментирования

### Модуль (файл .py)

```python
# Краткое описание модуля на русском
# Может быть многострочное, объясняющее назначение и ключевые концепции

import ...

# Группы импортов разделяем комментариями при необходимости
# Стандартная библиотека
import os
import sys

# Сторонние библиотеки
import torch
from pydantic import BaseModel

# Локальные импорты
from marker.schema import BlockTypes
```

### Класс

```python
class MyClass:
    """
    Краткое описание класса.
    
    Более подробное описание, если необходимо.
    Может описывать назначение, использование, особенности.
    
    Атрибуты:
        attribute_name (type): Описание атрибута
        another_attr (type): Описание другого атрибута
    """
    
    # Атрибуты класса с комментариями
    # Это константа, используемая во всех экземплярах
    DEFAULT_VALUE = 42
    
    def __init__(self, param1: str, param2: int = 0):
        """
        Инициализирует экземпляр класса.
        
        Аргументы:
            param1: Описание первого параметра
            param2: Описание второго параметра (по умолчанию: 0)
        """
        # Сохраняем параметры как атрибуты экземпляра
        self.param1 = param1
        self.param2 = param2
```

### Функция

```python
def process_document(document: Document, config: dict) -> ProcessedDocument:
    """
    Обрабатывает документ согласно конфигурации.
    
    Функция выполняет последовательную обработку документа:
    1. Валидация входных данных
    2. Применение процессоров
    3. Генерация результата
    
    Аргументы:
        document: Документ для обработки
        config: Словарь с настройками обработки. Ключи:
            - "mode": Режим обработки ("fast" или "accurate")
            - "batch_size": Размер батча для обработки
            
    Возвращает:
        ProcessedDocument с результатами обработки
        
    Raises:
        ValueError: Если document пустой или config невалидный
        ProcessingError: Если произошла ошибка во время обработки
        
    Пример:
        >>> doc = Document("example.pdf")
        >>> config = {"mode": "fast", "batch_size": 10}
        >>> result = process_document(doc, config)
    """
    # Валидация входных данных
    if not document.pages:
        raise ValueError("Документ не содержит страниц")
    
    # Извлекаем настройки из конфигурации с значениями по умолчанию
    mode = config.get("mode", "fast")
    batch_size = config.get("batch_size", 32)
    
    # Обработка в зависимости от режима
    if mode == "fast":
        # Быстрая обработка - пропускаем некоторые шаги
        result = fast_process(document)
    else:
        # Полная обработка - более точная, но медленнее
        result = accurate_process(document, batch_size)
    
    return result
```

### Сложная логика

```python
# Вычисляем пересечение двух полигонов для определения перекрытия блоков
# Используется алгоритм Sutherland-Hodgman для clip polygons
intersection = compute_polygon_intersection(block1.polygon, block2.polygon)

# Если площадь пересечения больше 50% от меньшего блока,
# считаем блоки перекрывающимися
overlap_ratio = intersection_area / min(block1.area, block2.area)
if overlap_ratio > 0.5:
    # Объединяем перекрывающиеся блоки в один
    merged_block = merge_blocks(block1, block2)
```

### Циклы и условия

```python
# Проходим по всем страницам документа
for page_idx, page in enumerate(document.pages):
    # Пропускаем пустые страницы (без контента)
    if not page.blocks:
        continue
    
    # Для каждого блока на странице
    for block in page.blocks:
        # Обрабатываем только текстовые блоки
        if block.block_type != BlockTypes.Text:
            continue
        
        # Применяем очистку текста
        block.text = clean_text(block.text)
```

---

## Примеры по типам файлов

### 1. Builder файл

```python
# Модуль строителя layout структуры документа
# Использует модель Surya для определения блоков на страницах (layout detection)

from typing import List
from marker.schema.document import Document
from marker.schema.blocks import Block

class LayoutBuilder:
    """
    Строитель layout структуры документа.
    
    Определяет типы и расположение блоков на каждой странице
    используя модель layout detection. Создает блоки различных типов:
    Text, Table, Figure, Equation и другие.
    
    Атрибуты:
        layout_model: Модель Surya для layout detection
        batch_size: Размер батча для обработки страниц
    """
    
    def __init__(self, layout_model, batch_size: int = 4):
        """
        Инициализирует строитель layout.
        
        Аргументы:
            layout_model: Загруженная модель Surya layout detection
            batch_size: Количество страниц для одновременной обработки
        """
        # Сохраняем модель для последующего использования
        self.layout_model = layout_model
        # Размер батча влияет на использование памяти и скорость
        self.batch_size = batch_size
    
    def __call__(self, document: Document) -> Document:
        """
        Применяет layout detection к документу.
        
        Для каждой страницы документа:
        1. Рендерит страницу в изображение
        2. Прогоняет через модель layout detection
        3. Создает блоки с определенными типами и координатами
        
        Аргументы:
            document: Документ для обработки
            
        Возвращает:
            Документ с добавленными блоками layout
        """
        # Проходим по страницам батчами для эффективности
        for batch_start in range(0, len(document.pages), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(document.pages))
            batch_pages = document.pages[batch_start:batch_end]
            
            # Рендерим страницы в изображения для модели
            images = [page.render() for page in batch_pages]
            
            # Получаем predictions от модели layout detection
            # Модель возвращает список блоков с типами и координатами
            predictions = self.layout_model(images)
            
            # Для каждой страницы и её predictions
            for page, page_predictions in zip(batch_pages, predictions):
                # Создаем блоки из predictions модели
                blocks = self._create_blocks_from_predictions(page_predictions)
                # Добавляем блоки на страницу
                page.add_blocks(blocks)
        
        return document
    
    def _create_blocks_from_predictions(self, predictions) -> List[Block]:
        """
        Создает Block объекты из predictions модели.
        
        Аргументы:
            predictions: Результаты модели layout detection
            
        Возвращает:
            Список созданных Block объектов
        """
        blocks = []
        
        # Для каждого предсказанного блока
        for pred in predictions:
            # Создаем блок с типом и координатами из prediction
            block = Block(
                block_type=pred.type,  # Тип блока (Text, Table, и т.д.)
                polygon=pred.bbox,      # Координаты блока
                confidence=pred.confidence  # Уверенность модели
            )
            blocks.append(block)
        
        return blocks
```

### 2. Processor файл

```python
# Модуль процессора таблиц
# Обрабатывает блоки таблиц, определяет структуру ячеек и форматирует в HTML

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document

class TableProcessor(BaseProcessor):
    """
    Процессор для обработки таблиц в документе.
    
    Выполняет следующие задачи:
    1. Находит все блоки таблиц
    2. Определяет структуру ячеек (строки и колонки)
    3. Извлекает текст ячеек
    4. Форматирует таблицу в HTML/Markdown
    
    Конфигурация:
        min_table_cells (int): Минимальное количество ячеек для валидной таблицы (default: 2)
        detect_headers (bool): Определять ли заголовки таблиц (default: True)
    """
    
    # Минимальное количество ячеек для определения как таблица
    min_table_cells: int = 2
    # Определять ли строку заголовка в таблице
    detect_headers: bool = True
    
    def __call__(self, document: Document) -> Document:
        """
        Обрабатывает все таблицы в документе.
        
        Аргументы:
            document: Документ для обработки
            
        Возвращает:
            Документ с обработанными таблицами
        """
        # Находим все блоки таблиц в документе
        table_blocks = document.contained_blocks((BlockTypes.Table,))
        
        # Обрабатываем каждую таблицу
        for table_block in table_blocks:
            # Определяем структуру ячеек таблицы
            cells = self._extract_cells(table_block)
            
            # Пропускаем таблицы с недостаточным количеством ячеек
            # (вероятно, ошибка layout detection)
            if len(cells) < self.min_table_cells:
                continue
            
            # Строим структуру строк и колонок
            rows, cols = self._build_table_structure(cells)
            
            # Определяем строку заголовка, если нужно
            if self.detect_headers:
                header_row = self._detect_header(rows)
            else:
                header_row = None
            
            # Форматируем таблицу в HTML
            html = self._format_table_html(rows, cols, header_row)
            
            # Сохраняем HTML в блоке таблицы
            table_block.html = html
            # Сохраняем структуру для последующего использования
            table_block.structure.rows = rows
            table_block.structure.cols = cols
        
        return document
    
    def _extract_cells(self, table_block):
        """
        Извлекает ячейки из блока таблицы.
        
        Использует модель распознавания таблиц для определения ячеек.
        
        Аргументы:
            table_block: Блок таблицы
            
        Возвращает:
            Список ячеек с координатами и текстом
        """
        # Получаем изображение области таблицы
        table_image = table_block.render()
        
        # Применяем модель распознавания структуры таблиц
        cells = self.table_rec_model(table_image)
        
        return cells
```

### 3. Service файл

```python
# Модуль сервиса Google Gemini для LLM обработки
# Предоставляет интеграцию с Gemini API для улучшения качества конвертации

from typing import Optional
import google.generativeai as genai
from marker.services import BaseService

class GoogleGeminiService(BaseService):
    """
    Сервис для взаимодействия с Google Gemini API.
    
    Используется для LLM-powered обработки блоков документа:
    - Улучшение форматирования таблиц
    - Извлечение данных из форм
    - Генерация описаний изображений
    - Обработка сложных регионов
    
    Конфигурация:
        gemini_api_key (str): API ключ для Gemini (обязательно)
        gemini_model_name (str): Имя модели (default: "gemini-2.0-flash")
        max_retries (int): Максимальное количество повторных попыток (default: 3)
        timeout (int): Таймаут запроса в секундах (default: 30)
    """
    
    # Имя модели Gemini по умолчанию
    gemini_model_name: str = "gemini-2.0-flash"
    # API ключ (должен быть предоставлен)
    gemini_api_key: Optional[str] = None
    # Максимум попыток при ошибках
    max_retries: int = 3
    # Таймаут для запросов
    timeout: int = 30
    
    def __init__(self, **config):
        """
        Инициализирует сервис Gemini.
        
        Аргументы:
            **config: Параметры конфигурации (gemini_api_key и др.)
            
        Raises:
            ValueError: Если не предоставлен gemini_api_key
        """
        super().__init__(**config)
        
        # Проверяем наличие API ключа
        if not self.gemini_api_key:
            raise ValueError(
                "Требуется gemini_api_key для использования GoogleGeminiService"
            )
        
        # Конфигурируем библиотеку Google Generative AI
        genai.configure(api_key=self.gemini_api_key)
        
        # Инициализируем модель
        self.model = genai.GenerativeModel(self.gemini_model_name)
    
    def call_llm(self, prompt: str, image=None) -> str:
        """
        Отправляет запрос к Gemini API.
        
        Поддерживает текстовые промпты и изображения (vision).
        Автоматически повторяет запрос при ошибках.
        
        Аргументы:
            prompt: Текстовый промпт для модели
            image: PIL изображение (опционально, для vision задач)
            
        Возвращает:
            Ответ модели как строка
            
        Raises:
            APIError: Если все попытки исчерпаны
        """
        # Готовим контент для отправки
        if image is not None:
            # Vision запрос - отправляем промпт и изображение
            content = [prompt, image]
        else:
            # Текстовый запрос - только промпт
            content = prompt
        
        # Пытаемся выполнить запрос с повторами
        for attempt in range(self.max_retries):
            try:
                # Отправляем запрос к API
                response = self.model.generate_content(
                    content,
                    request_options={"timeout": self.timeout}
                )
                
                # Возвращаем текст ответа
                return response.text
                
            except Exception as e:
                # Логируем ошибку
                self.logger.warning(
                    f"Попытка {attempt + 1}/{self.max_retries} не удалась: {e}"
                )
                
                # Если это последняя попытка, выбрасываем ошибку
                if attempt == self.max_retries - 1:
                    raise
```

### 4. Schema/Block файл

```python
# Модуль определения блока таблицы
# Содержит класс для представления таблиц в документе

from typing import List, Optional
from marker.schema.blocks.base import Block
from marker.schema import BlockTypes

class Table(Block):
    """
    Блок таблицы в документе.
    
    Представляет табличные данные с структурой строк и колонок.
    Может содержать вложенные ячейки (TableCell блоки).
    
    Атрибуты:
        rows (int): Количество строк в таблице
        cols (int): Количество колонок в таблице
        has_header (bool): Есть ли строка заголовка
        html (str): HTML представление таблицы
    """
    
    # Тип блока - всегда Table
    block_type: BlockTypes = BlockTypes.Table
    # Количество строк и колонок
    rows: int = 0
    cols: int = 0
    # Флаг наличия заголовка
    has_header: bool = False
    
    def render(self, **kwargs) -> str:
        """
        Рендерит таблицу в HTML формат.
        
        Аргументы:
            **kwargs: Дополнительные параметры рендеринга
                - include_borders (bool): Добавить ли borders
                - css_class (str): CSS класс для таблицы
        
        Возвращает:
            HTML строка с таблицей
        """
        # Начинаем HTML таблицу
        html_parts = ['<table>']
        
        # Если есть заголовок, рендерим его отдельно
        if self.has_header and self.children:
            html_parts.append('<thead>')
            # Первая строка - заголовок
            header_cells = self.children[0].children
            html_parts.append('<tr>')
            for cell in header_cells:
                html_parts.append(f'<th>{cell.render()}</th>')
            html_parts.append('</tr>')
            html_parts.append('</thead>')
            
            # Остальные строки - тело таблицы
            body_rows = self.children[1:]
        else:
            # Нет заголовка - все строки в теле
            body_rows = self.children
        
        # Рендерим тело таблицы
        html_parts.append('<tbody>')
        for row in body_rows:
            html_parts.append('<tr>')
            for cell in row.children:
                html_parts.append(f'<td>{cell.render()}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
        
        # Закрываем таблицу
        html_parts.append('</table>')
        
        return ''.join(html_parts)
```

---

## Комментирование специфичных паттернов

### Context Manager

```python
@contextmanager
def temporary_file(content: bytes):
    """
    Context manager для создания временного файла.
    
    Автоматически удаляет файл при выходе из контекста,
    даже если произошла ошибка.
    
    Аргументы:
        content: Содержимое для записи в файл
        
    Yields:
        Путь к временному файлу
        
    Пример:
        >>> with temporary_file(b"data") as filepath:
        ...     process_file(filepath)
        # Файл автоматически удален после блока with
    """
    # Создаем временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        # Записываем содержимое
        temp_file.write(content)
        temp_file.close()
        # Возвращаем путь для использования
        yield temp_file.name
    finally:
        # Гарантированно удаляем файл (даже при ошибке)
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
```

### Декоратор

```python
def retry_on_failure(max_attempts: int = 3):
    """
    Декоратор для повторных попыток при ошибках.
    
    Автоматически повторяет функцию при возникновении исключений,
    с экспоненциальной задержкой между попытками.
    
    Аргументы:
        max_attempts: Максимальное количество попыток
        
    Пример:
        >>> @retry_on_failure(max_attempts=5)
        ... def unstable_api_call():
        ...     return api.get_data()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Перебираем попытки
            for attempt in range(max_attempts):
                try:
                    # Пытаемся выполнить функцию
                    return func(*args, **kwargs)
                except Exception as e:
                    # Если это не последняя попытка
                    if attempt < max_attempts - 1:
                        # Вычисляем задержку (экспоненциальный backoff)
                        delay = 2 ** attempt
                        logger.warning(
                            f"Попытка {attempt + 1} не удалась, "
                            f"повтор через {delay}с: {e}"
                        )
                        time.sleep(delay)
                    else:
                        # Последняя попытка - выбрасываем исключение
                        raise
        return wrapper
    return decorator
```

### List Comprehension

```python
# Извлекаем все текстовые блоки с непустым текстом
# List comprehension с условием для фильтрации
text_blocks = [
    block for block in document.blocks
    if block.block_type == BlockTypes.Text and block.text
]

# Создаем словарь ID блока -> текст блока
# Dict comprehension для быстрого поиска
block_text_map = {
    block.id: block.text
    for block in text_blocks
}
```

---

## Инструменты и best practices

### 1. Группировка кода

```python
# ===== Инициализация =====
self.model = load_model()
self.config = parse_config()

# ===== Валидация входных данных =====
if not document.pages:
    raise ValueError("Empty document")

# ===== Основная обработка =====
for page in document.pages:
    process_page(page)

# ===== Финализация =====
cleanup_resources()
```

### 2. TODO комментарии

```python
# TODO: Оптимизировать алгоритм для больших документов
# TODO(username): Добавить поддержку вертикального текста
# FIXME: Баг с многоколоночными таблицами
# NOTE: Этот код временный, будет заменен в следующей версии
# HACK: Временное решение для совместимости со старыми версиями
```

### 3. Ссылки на документацию

```python
# Используем алгоритм Ramer-Douglas-Peucker для упрощения полигонов
# См. https://en.wikipedia.org/wiki/Ramer–Douglas–Peucker_algorithm
simplified_polygon = rdp_simplify(polygon, epsilon=2.0)

# Формат bounding box: [x_min, y_min, x_max, y_max]
# Совместим с форматом COCO dataset
bbox = [10, 20, 100, 200]
```

---

## Итоговый чек-лист

При добавлении комментариев к коду проверьте:

- [ ] Модульный комментарий в начале файла
- [ ] Docstring для каждого класса
- [ ] Docstring для каждой функции/метода
- [ ] Комментарии для сложной логики
- [ ] Объяснение нетривиальных параметров
- [ ] Примеры использования где уместно
- [ ] Описание возвращаемых значений
- [ ] Список возможных исключений
- [ ] Комментарии на русском языке
- [ ] Правильное форматирование (над строкой кода)

---

## Заключение

Следуя этим принципам и шаблонам, вы сможете создать понятную и хорошо документированную кодовую базу. Комментарии должны помогать читателю понять **почему** код написан именно так, а не просто **что** он делает.

Хорошо прокомментированный код:
- Легче поддерживать
- Быстрее понимать новым разработчикам
- Проще расширять и модифицировать
- Уменьшает количество ошибок

Используйте эти шаблоны как основу для документирования всего проекта Marker.
