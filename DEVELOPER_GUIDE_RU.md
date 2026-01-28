# Руководство разработчика Marker

## Обзор

Этот документ содержит подробное описание структуры кода, соглашений и руководство по пониманию каждого модуля системы Marker.

## Структура проекта

```
marker/
├── builders/          # Строители структуры документа из сырых данных
├── config/            # Система конфигурации и парсинг настроек
├── converters/        # Конвертеры для полного pipeline обработки
├── extractors/        # Извлекатели данных (для structured extraction)
├── processors/        # Процессоры для обработки и улучшения блоков
│   └── llm/          # LLM-процессоры (требуют --use_llm)
├── providers/         # Поставщики данных из различных форматов файлов
├── renderers/         # Рендереры для генерации выходных форматов
├── schema/            # Схемы данных (типы блоков, модели Pydantic)
│   └── blocks/       # Классы для каждого типа блока
├── scripts/           # CLI скрипты (convert, convert_single и т.д.)
├── services/          # Сервисы LLM (Gemini, Claude, OpenAI и др.)
├── utils/             # Утилиты (работа с изображениями, GPU, batch)
├── logger.py          # Настройка логирования
├── models.py          # Загрузка ML моделей Surya
├── output.py          # Сохранение результатов
├── settings.py        # Глобальные настройки
└── util.py            # Общие вспомогательные функции
```

---

## Подробное описание модулей

### 1. **builders/** - Строители документа

Строители создают начальную структуру документа из данных providers. Работают последовательно.

#### **DocumentBuilder** (`builders/document.py`)
**Назначение**: Создает корневой объект Document  
**Вход**: Provider с данными файла  
**Выход**: Document с инициализированными страницами  
**Ключевые методы**:
- `__call__(provider)` - создает документ из provider

#### **LayoutBuilder** (`builders/layout.py`)
**Назначение**: Определяет макет страниц (layout detection)  
**Модель**: Surya Layout Model  
**Вход**: Document с пустыми страницами  
**Выход**: Document с блоками (Text, Table, Figure и т.д.)  
**Процесс**:
1. Рендерит страницы в изображения
2. Прогоняет через модель layout detection
3. Создает Block объекты с типами и координатами
4. Добавляет блоки на страницы документа

**Типы блоков, которые может определить**:
- Text - текстовые параграфы
- Table - таблицы
- Figure - рисунки и диаграммы
- Title - заголовки
- Caption - подписи
- List - списки
- Formula - формулы

#### **LineBuilder** (`builders/line.py`)
**Назначение**: Определяет строки текста внутри блоков  
**Модель**: Surya Detection Model  
**Вход**: Document с блоками  
**Выход**: Document с Line блоками внутри текстовых блоков  
**Процесс**:
1. Для каждого текстового блока
2. Детектирует строки с помощью модели
3. Создает Line блоки с координатами
4. Вкладывает Line в родительские блоки

#### **OcrBuilder** (`builders/ocr.py`)
**Назначение**: Распознает текст (OCR)  
**Модель**: Surya OCR Model  
**Вход**: Document с Line блоками  
**Выход**: Document с текстом в блоках  
**Процесс**:
1. Определяет, нужен ли OCR (проверяет качество текста из PDF)
2. Рендерит области для OCR
3. Прогоняет через модель распознавания
4. Заполняет текст в Line блоках
5. Может создавать Span и Char блоки (детализация)

**Режимы**:
- `force_ocr=True` - OCR для всего документа
- `strip_existing_ocr=True` - удалить существующий OCR и переделать
- Автоматический - OCR только для плохого текста

#### **StructureBuilder** (`builders/structure.py`)
**Назначение**: Создает иерархическую структуру  
**Вход**: Document с плоским списком блоков  
**Выход**: Document с древовидной структурой блоков  
**Процесс**:
1. Анализирует пространственные отношения блоков
2. Определяет родительско-дочерние связи
3. Группирует связанные блоки (например, Figure + Caption)
4. Строит дерево блоков

---

### 2. **processors/** - Процессоры

Процессоры обрабатывают и улучшают блоки документа. Выполняются последовательно в порядке, определенном в converter.

#### Базовые процессоры:

**OrderProcessor** (`processors/order.py`)
- Определяет порядок чтения блоков
- Важно для многоколоночных документов
- Использует reading order модель

**LineMergeProcessor** (`processors/line_merge.py`)
- Объединяет строки в параграфы
- Определяет границы абзацев
- Обрабатывает переносы слов

**BlockRelabelProcessor** (`processors/block_relabel.py`)
- Переклассифицирует блоки
- Исправляет ошибки layout detection
- Использует эвристики и паттерны

**TextProcessor** (`processors/text.py`)
- Обрабатывает текстовые блоки
- Очищает и форматирует текст
- Удаляет артефакты

**SectionHeaderProcessor** (`processors/sectionheader.py`)
- Идентифицирует заголовки
- Определяет уровни (H1-H6)
- Строит иерархию разделов

**ListProcessor** (`processors/list.py`)
- Распознает списки
- Определяет тип (маркированный/нумерованный)
- Создает иерархическую структуру списков

**TableProcessor** (`processors/table.py`)
- Обрабатывает таблицы
- Определяет структуру ячеек
- Форматирует в HTML/Markdown

**EquationProcessor** (`processors/equation.py`)
- Обрабатывает математические формулы
- Конвертирует в LaTeX
- Различает inline и block формулы

**CodeProcessor** (`processors/code.py`)
- Распознает блоки кода
- Сохраняет форматирование и отступы

**FootnoteProcessor** (`processors/footnote.py`)
- Идентифицирует сноски
- Связывает с основным текстом

**PageHeaderProcessor** (`processors/page_header.py`)
- Удаляет повторяющиеся колонтитулы
- Очищает артефакты

**DocumentTOCProcessor** (`processors/document_toc.py`)
- Создает оглавление
- Извлекает структуру документа

**ReferenceProcessor** (`processors/reference.py`)
- Обрабатывает библиографические ссылки
- Форматирует citations

**DebugProcessor** (`processors/debug.py`)
- Сохраняет отладочную информацию
- Рендерит визуализации (при --debug)

#### LLM процессоры (`processors/llm/`):

Активируются при `--use_llm`. Используют большие языковые модели для повышения точности.

**LLMSimpleBlockMetaProcessor** (`processors/llm/llm_simple.py`)
- Базовый класс для LLM процессоров
- Управляет отправкой запросов к LLM
- Обрабатывает ответы и ошибки
- Кеширует результаты

**LLMTableProcessor** (`processors/llm/llm_table.py`)
- Улучшает форматирование таблиц
- Исправляет ошибки структуры
- Преобразует в чистый HTML

**LLMTableMergeProcessor** (`processors/llm/llm_table_merge.py`)
- Объединяет таблицы, разбитые на страницы
- Определяет продолжения таблиц
- Сохраняет структуру ячеек

**LLMFormProcessor** (`processors/llm/llm_form.py`)
- Извлекает данные из форм
- Идентифицирует поля и значения
- Структурирует данные форм

**LLMImageDescriptionProcessor** (`processors/llm/llm_image_description.py`)
- Генерирует описания изображений
- Использует vision модели LLM
- Заменяет изображения текстом (если --disable_image_extraction)

**LLMEquationProcessor** (`processors/llm/llm_equation.py`)
- Улучшает распознавание формул
- Конвертирует сложные формулы в LaTeX
- Обрабатывает inline и block формулы

**LLMHandwritingProcessor** (`processors/llm/llm_handwriting.py`)
- Распознает рукописный текст
- Использует vision модели

**LLMMathBlockProcessor** (`processors/llm/llm_mathblock.py`)
- Обрабатывает блоки с математикой
- Форматирует сложные математические выражения

**LLMSectionHeaderProcessor** (`processors/llm/llm_sectionheader.py`)
- Улучшает распознавание заголовков
- Определяет уровни заголовков

**LLMPageCorrectionProcessor** (`processors/llm/llm_page_correction.py`)
- Общая коррекция страницы
- Использует custom prompt (--block_correction_prompt)
- Применяет пользовательскую логику

**LLMComplexRegionProcessor** (`processors/llm/llm_complex.py`)
- Обрабатывает сложные регионы
- Mixed content (текст + формулы + таблицы)

---

### 3. **providers/** - Поставщики данных

Providers извлекают низкоуровневую информацию из файлов.

#### **BaseProvider** (`providers/provider.py`)
Базовый класс для всех providers. Определяет интерфейс.

#### **PdfProvider** (`providers/pdf.py`)
**Форматы**: PDF  
**Библиотеки**: pdftext, pymupdf  
**Возможности**:
- Извлечение текста из PDF
- Получение изображений страниц
- Метаданные документа
- Размеры страниц

**Методы**:
- `get_page_count()` - количество страниц
- `get_page_bbox(page_id)` - размеры страницы
- `get_images(page_id)` - изображения со страницы
- `get_page_text(page_id)` - текст страницы
- `render_page(page_id)` - рендер страницы в изображение

#### **ImageProvider** (`providers/image.py`)
**Форматы**: PNG, JPG, TIFF и др.  
**Возможности**:
- Загрузка изображений
- Одна страница = одно изображение

#### **DocxProvider** (`providers/docx.py`)
**Форматы**: DOCX (Microsoft Word)  
**Библиотека**: python-docx  
**Возможности**:
- Извлечение структуры документа
- Параграфы, таблицы, изображения
- Стили и форматирование

#### **PptxProvider** (`providers/pptx.py`)
**Форматы**: PPTX (Microsoft PowerPoint)  
**Библиотека**: python-pptx  
**Возможности**:
- Извлечение слайдов
- Текст, изображения, фигуры

#### **EpubProvider** (`providers/epub.py`)
**Форматы**: EPUB (электронные книги)  
**Возможности**:
- Извлечение глав
- HTML контент
- Изображения и метаданные

#### **HtmlProvider** (`providers/html.py`)
**Форматы**: HTML  
**Возможности**:
- Парсинг HTML структуры
- Извлечение текста и изображений

#### **ProviderRegistry** (`providers/registry.py`)
Реестр для автоматического выбора provider по расширению файла.

```python
# Регистрация
ProviderRegistry.register(".pdf", PdfProvider)
ProviderRegistry.register(".png", ImageProvider)

# Использование
provider = provider_from_filepath("document.pdf")
```

---

### 4. **renderers/** - Рендереры

Renderers преобразуют структуру блоков в выходные форматы.

#### **BaseRenderer** (`renderers/base.py`)
Базовый класс. Определяет интерфейс `__call__(document)`.

#### **MarkdownRenderer** (`renderers/markdown.py`)
**Формат**: Markdown (.md)  
**Вывод**: MarkdownOutput (markdown, images, metadata)  
**Особенности**:
- Таблицы в Markdown формате
- LaTeX формулы в `$$...$$`
- Код в triple backticks
- Ссылки на изображения `![alt](image.jpg)`
- Сноски как superscript

#### **HTMLRenderer** (`renderers/html.py`)
**Формат**: HTML (.html)  
**Вывод**: HTMLOutput (html, images, metadata)  
**Особенности**:
- Семантические HTML теги
- `<img>` для изображений
- `<math>` для формул
- `<table>` для таблиц
- CSS классы для стилизации

#### **JSONRenderer** (`renderers/json.py`)
**Формат**: JSON (.json)  
**Вывод**: JSONOutput (pages, metadata)  
**Структура**:
```json
{
  "pages": [
    {
      "id": "/page/0/Page/0",
      "block_type": "Page",
      "html": "...",
      "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
      "children": [...]
    }
  ],
  "metadata": {...}
}
```
**Особенности**:
- Древовидная структура
- Полные bounding boxes
- Рекурсивные дочерние блоки
- `<content-ref>` для ссылок на детей

#### **ChunkedRenderer** (`renderers/chunk.py`)
**Формат**: JSON (.json)  
**Вывод**: ChunkOutput (chunks, metadata)  
**Особенности**:
- Плоский список блоков (не дерево)
- Каждый chunk - самодостаточный фрагмент
- Полный HTML внутри каждого chunk
- Идеален для RAG систем

#### **OCRJSONRenderer** (`renderers/ocr_json.py`)
**Формат**: JSON (.json)  
**Назначение**: Только OCR результаты  
**Особенности**:
- Детальные позиции символов
- Confidence scores
- Без структурирования

#### **ExtractionRenderer** (`renderers/extraction.py`)
**Формат**: JSON (.json)  
**Назначение**: Структурированное извлечение  
**Особенности**:
- Соответствие JSON schema
- LLM-driven extraction
- Валидация Pydantic

---

### 5. **converters/** - Конвертеры

Converters управляют полным pipeline конвертации.

#### **BaseConverter** (`converters/base.py`)
**Базовый класс** для всех конвертеров.

**Основные методы**:
- `__call__(filepath)` - полная конвертация
- `build_document(filepath)` - только построение структуры
- `process_document(document)` - только обработка процессорами
- `render_document(document)` - только рендеринг

**Pipeline**:
```
filepath → provider → builders → processors → renderer → output
```

#### **PdfConverter** (`converters/pdf.py`)
**Назначение**: Полная конвертация PDF/изображений  
**Поддерживает**: Все форматы вывода  
**Builders**:
1. DocumentBuilder
2. LayoutBuilder
3. LineBuilder
4. OcrBuilder
5. StructureBuilder

**Processors**: Все базовые + опционально LLM процессоры  
**Renderer**: Выбирается по `output_format`

**Конфигурация**:
```python
converter = PdfConverter(
    artifact_dict=models,          # Загруженные модели
    config=config_dict,             # Настройки
    processor_list=processors,      # Список процессоров
    renderer=renderer,              # Renderer для вывода
    llm_service=llm_service,        # LLM сервис (опционально)
)
```

#### **TableConverter** (`converters/table.py`)
**Назначение**: Извлечение только таблиц  
**Особенности**:
- Оптимизирован для таблиц
- Может использовать `force_layout_block=Table`
- LLM режим для высокой точности

#### **OCRConverter** (`converters/ocr.py`)
**Назначение**: Только OCR, без layout  
**Особенности**:
- Быстрый режим
- Простой OCR текста
- Без структурирования

#### **ExtractionConverter** (`converters/extraction.py`)
**Назначение**: Структурированное извлечение (beta)  
**Требует**: LLM service  
**Вход**: JSON schema (Pydantic модель)  
**Выход**: Структурированные данные по schema

**Использование**:
```python
from pydantic import BaseModel

class MySchema(BaseModel):
    name: str
    date: str
    amount: float

schema = MySchema.model_json_schema()
converter = ExtractionConverter(
    config={"page_schema": schema},
    llm_service=llm_service,
)
result = converter("invoice.pdf")
```

---

### 6. **services/** - LLM сервисы

Services предоставляют интеграцию с LLM API.

#### **BaseService** (`services/base.py`)
Базовый интерфейс для всех LLM сервисов.

**Методы**:
- `call_llm(prompt, image)` - основной вызов LLM
- `retry logic` - обработка ошибок и повторы

#### **GoogleGeminiService** (`services/gemini.py`)
**API**: Google Gemini  
**Модель по умолчанию**: gemini-2.0-flash  
**Конфигурация**:
- `gemini_api_key` - API ключ
- `gemini_model_name` - имя модели

**Особенности**:
- Vision support (изображения)
- Быстрый и дешевый
- Хорошее качество

#### **GoogleVertexService** (`services/vertex.py`)
**API**: Google Vertex AI  
**Требует**: GCP проект  
**Конфигурация**:
- `vertex_project_id` - ID проекта GCP
- `vertex_location` - регион

**Особенности**:
- Более надежный для production
- Требует GCP аутентификации
- Лучший SLA

#### **OllamaService** (`services/ollama.py`)
**API**: Ollama (локальные модели)  
**Конфигурация**:
- `ollama_base_url` - URL сервера Ollama
- `ollama_model` - имя модели

**Особенности**:
- Полностью локальные модели
- Нет ограничений API
- Требует мощного железа

#### **ClaudeService** (`services/claude.py`)
**API**: Anthropic Claude  
**Конфигурация**:
- `claude_api_key` - API ключ
- `claude_model_name` - модель (claude-3-opus и др.)

**Особенности**:
- Высокое качество
- Хороший для сложных задач
- Дороже альтернатив

#### **OpenAIService** (`services/openai.py`)
**API**: OpenAI (или совместимые)  
**Конфигурация**:
- `openai_api_key` - API ключ
- `openai_model` - модель (gpt-4 и др.)
- `openai_base_url` - URL (для совместимых API)

**Особенности**:
- Стандарт индустрии
- Совместим с многими провайдерами
- Vision support

#### **AzureOpenAIService** (`services/azure_openai.py`)
**API**: Azure OpenAI  
**Конфигурация**:
- `azure_endpoint` - endpoint Azure
- `azure_api_key` - API ключ
- `deployment_name` - имя deployment

**Особенности**:
- Enterprise support
- Compliance и безопасность
- Интеграция с Azure

---

### 7. **schema/** - Схемы данных

Schema определяет структуры данных для представления документов.

#### **BlockTypes** (`schema/__init__.py`)
Enum всех типов блоков. См. комментарии в файле.

#### **Block** (`schema/blocks/base.py`)
Базовый класс для всех блоков.

**Поля**:
- `id` - уникальный ID
- `block_type` - тип (BlockTypes)
- `polygon` - координаты (4 угла)
- `structure` - метаданные структуры
- `children` - дочерние блоки

**Методы**:
- `render()` - рендеринг в HTML/Markdown
- `contained_blocks(types)` - поиск вложенных блоков
- `assemble_html(child_blocks)` - сборка HTML

#### Специализированные блоки:

**Page** (`schema/blocks/page.py`) - Страница документа  
**Text** (`schema/blocks/text.py`) - Текстовый параграф  
**SectionHeader** (`schema/blocks/sectionheader.py`) - Заголовок  
**Table** (`schema/blocks/table.py`) - Таблица  
**Figure** (`schema/blocks/figure.py`) - Рисунок  
**Equation** (`schema/blocks/equation.py`) - Формула  
**Code** (`schema/blocks/code.py`) - Код  
**ListItem** (`schema/blocks/listitem.py`) - Элемент списка  
...и другие

Каждый специализированный блок:
- Наследуется от Block
- Добавляет специфичные поля
- Переопределяет `render()` для custom форматирования

#### **Document** (`schema/document.py`)
Корневой контейнер документа.

**Поля**:
- `filepath` - путь к исходному файлу
- `pages` - список страниц
- `block_type` = BlockTypes.Document

**Методы**:
- `contained_blocks(types)` - поиск блоков по типу
- `add_page(page)` - добавить страницу

---

### 8. **config/** - Конфигурация

#### **ConfigParser** (`config/parser.py`)
Центральная система конфигурации.

**Функции**:
- Парсинг CLI аргументов
- Чтение JSON конфигурации
- Создание словаря настроек
- Инстанцирование компонентов

**Методы**:
- `generate_config_dict()` - создать словарь настроек
- `get_processors()` - создать список процессоров
- `get_renderer()` - создать renderer
- `get_llm_service()` - создать LLM service

**Использование**:
```python
config_parser = ConfigParser({
    "output_format": "json",
    "use_llm": True,
})
converter = PdfConverter(
    config=config_parser.generate_config_dict(),
    processor_list=config_parser.get_processors(),
    renderer=config_parser.get_renderer(),
    llm_service=config_parser.get_llm_service(),
)
```

---

### 9. **utils/** - Утилиты

#### **image.py**
Функции для работы с изображениями:
- Ресайз
- Crop
- Конвертация форматов
- Сохранение

#### **batch.py**
Батчирование задач:
- Группировка файлов
- Распределение по workers
- Мониторинг прогресса

#### **gpu.py**
Управление GPU:
- Определение доступных GPU
- Распределение нагрузки
- Мониторинг памяти

---

## Поток данных (подробно)

### Полный цикл конвертации PDF:

1. **Инициализация**
   ```python
   models = create_model_dict()  # Загрузка моделей
   converter = PdfConverter(artifact_dict=models)
   ```

2. **Provider фаза**
   ```python
   provider = PdfProvider(filepath)
   page_count = provider.get_page_count()
   ```

3. **DocumentBuilder**
   ```python
   document = Document(filepath=filepath)
   for i in range(page_count):
       page = Page(page_id=i)
       document.add_page(page)
   ```

4. **LayoutBuilder**
   ```python
   for page in document.pages:
       image = provider.render_page(page.page_id)
       layout_result = layout_model(image)
       for block_data in layout_result:
           block = Block(
               block_type=block_data.type,
               polygon=block_data.bbox,
           )
           page.add_block(block)
   ```

5. **LineBuilder**
   ```python
   for block in text_blocks:
       image = crop_block(page_image, block.polygon)
       lines = detection_model(image)
       for line_data in lines:
           line = Line(polygon=line_data.bbox)
           block.add_child(line)
   ```

6. **OcrBuilder**
   ```python
   for line in lines:
       image = crop_line(page_image, line.polygon)
       text = recognition_model(image)
       line.text = text
   ```

7. **StructureBuilder**
   ```python
   # Строит иерархию блоков
   for page in document.pages:
       build_hierarchy(page.blocks)
   ```

8. **Processors** (последовательно)
   ```python
   document = OrderProcessor()(document)
   document = LineMergeProcessor()(document)
   document = TableProcessor()(document)
   # ... все остальные процессоры
   ```

9. **Renderer**
   ```python
   output = MarkdownRenderer()(document)
   # output = MarkdownOutput(markdown, images, metadata)
   ```

10. **Сохранение**
    ```python
    save_output(output, output_dir, filename)
    ```

---

## Расширяемость

### Добавление нового Processor

1. Создайте класс, наследующий от `BaseProcessor`:

```python
from marker.processors import BaseProcessor
from marker.schema import BlockTypes

class MyCustomProcessor(BaseProcessor):
    """Описание процессора"""
    
    def __call__(self, document):
        """
        Обрабатывает документ.
        
        Аргументы:
            document: Document для обработки
            
        Возвращает:
            Обработанный Document
        """
        # Находим нужные блоки
        blocks = document.contained_blocks((BlockTypes.Text,))
        
        # Обрабатываем каждый блок
        for block in blocks:
            # Ваша логика
            block.text = process_text(block.text)
        
        return document
```

2. Добавьте в список процессоров:

```python
converter = PdfConverter(
    processor_list=[
        ...,
        MyCustomProcessor(),
        ...,
    ]
)
```

### Добавление нового Renderer

```python
from marker.renderers import BaseRenderer
from pydantic import BaseModel

class MyOutputFormat(BaseModel):
    content: str
    metadata: dict

class MyCustomRenderer(BaseRenderer):
    """Описание renderer'а"""
    
    def __call__(self, document):
        """
        Рендерит документ в custom формат.
        
        Аргументы:
            document: Document для рендеринга
            
        Возвращает:
            MyOutputFormat с результатом
        """
        content = self.generate_content(document)
        metadata = self.extract_metadata(document)
        
        return MyOutputFormat(
            content=content,
            metadata=metadata
        )
    
    def generate_content(self, document):
        # Ваша логика генерации контента
        pass
```

### Добавление нового Provider

```python
from marker.providers import BaseProvider

class MyFormatProvider(BaseProvider):
    """Provider для custom формата"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        # Инициализация
    
    def get_page_count(self):
        # Возвращает количество страниц
        pass
    
    def get_page_bbox(self, page_id):
        # Возвращает размеры страницы
        pass
    
    def render_page(self, page_id):
        # Рендерит страницу в изображение
        pass

# Регистрация
from marker.providers.registry import ProviderRegistry
ProviderRegistry.register(".myext", MyFormatProvider)
```

---

## Паттерны и best practices

### 1. Работа с блоками

```python
# Поиск блоков по типу
tables = document.contained_blocks((BlockTypes.Table,))
headers = document.contained_blocks((BlockTypes.SectionHeader,))

# Поиск по нескольким типам
special = document.contained_blocks((
    BlockTypes.Table,
    BlockTypes.Figure,
    BlockTypes.Equation,
))

# Обход дерева блоков
def visit_blocks(block, callback):
    callback(block)
    if block.children:
        for child in block.children:
            visit_blocks(child, callback)
```

### 2. Модификация блоков

```python
# Изменение типа блока
block.block_type = BlockTypes.SectionHeader

# Добавление метаданных
block.structure.add_metadata("key", "value")

# Изменение текста
block.text = "Новый текст"

# Добавление дочернего блока
parent.children.append(child)
```

### 3. Работа с изображениями

```python
from PIL import Image

# Crop блока из страницы
def crop_block(page_image, polygon):
    bbox = polygon_to_bbox(polygon)
    return page_image.crop(bbox)

# Ресайз с сохранением пропорций
def resize_image(image, max_size):
    ratio = max_size / max(image.size)
    new_size = (int(image.width * ratio), int(image.height * ratio))
    return image.resize(new_size)
```

### 4. Логирование

```python
from marker.logger import get_logger

logger = get_logger()

# Различные уровни
logger.debug("Детальная информация")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")
logger.critical("Критическая ошибка")
```

### 5. Обработка ошибок

```python
try:
    result = process_document(document)
except Exception as e:
    logger.error(f"Ошибка обработки: {e}")
    # Fallback логика
```

---

## Производительность и оптимизация

### Советы по оптимизации:

1. **Батчирование**
   - Обрабатывайте несколько страниц за раз
   - Используйте батчи для inference моделей

2. **Кеширование**
   - Загружайте модели один раз
   - Кешируйте промежуточные результаты
   - Повторно используйте provider'ы

3. **Параллелизм**
   - Multi-processing для обработки файлов
   - Multi-GPU для масштабирования
   - Асинхронная обработка где возможно

4. **Память**
   - Освобождайте изображения после использования
   - Используйте генераторы для больших документов
   - Контролируйте размер батчей

### Мониторинг производительности:

```python
import time

start = time.time()
result = converter(filepath)
elapsed = time.time() - start

logger.info(f"Обработка заняла {elapsed:.2f} секунд")
```

---

## Заключение

Этот гид охватывает все основные компоненты Marker. Для более глубокого понимания:

1. Изучите код конкретных модулей
2. Читайте docstrings в функциях
3. Изучайте тесты в `tests/`
4. Экспериментируйте с custom processors и renderers

Marker спроектирован быть модульным и расширяемым. Каждый компонент имеет четкую ответственность и может быть заменен или расширен.
