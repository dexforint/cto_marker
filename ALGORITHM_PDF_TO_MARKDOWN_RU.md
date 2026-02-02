# Алгоритм конвертации PDF в Markdown в Marker (подробное описание)

> Связанные документы: [ARCHITECTURE_RU.md](ARCHITECTURE_RU.md), [DEVELOPER_GUIDE_RU.md](DEVELOPER_GUIDE_RU.md), [README_RU.md](README_RU.md)

## 1. Введение и обзор

### Что такое Marker и его назначение
Marker — это модульный движок конвертации документов (PDF, изображения, DOCX, PPTX, HTML, EPUB и др.) в структурированные форматы: Markdown, HTML, JSON и специальные «чанки» для RAG. Главная цель — максимально точное преобразование сложных PDF в читаемый, структурированный текст, сохранив таблицы, формулы, списки, заголовки, иллюстрации и ссылки.

### Общий процесс конвертации
Общий pipeline устроен как последовательность независимых этапов, где каждый компонент делает одну задачу:

```
Источник (PDF) → Provider → Builders → Processors → Renderer → Markdown/JSON/HTML
```

- **Provider** извлекает данные из файла: страницы, метаданные, текст, изображения.
- **Builders** строят первичную структуру документа: страницы, блоки, строки, OCR текст.
- **Processors** улучшают структуру: определяют порядок чтения, формируют заголовки, таблицы, списки, формулы, сноски и т.д.
- **Renderer** превращает структуру в итоговый формат (например, Markdown).

### Ключевые особенности алгоритма
- **Модульность**: каждый шаг можно заменить или расширить.
- **Layout detection**: нейросетевое определение структуры страницы (Surya).
- **Гибридный режим с LLM**: при необходимости используется LLM для сложных случаев (формулы, таблицы, формы).
- **Параллелизм**: batch-обработка, multi-GPU и масштабирование.
- **Семантика**: не просто OCR, а восстановление смысла документа.

---

## 2. Архитектура системы

### Основные компоненты

- **Providers** (`marker/providers/`): извлекают «сырые» данные из PDF.
- **Builders** (`marker/builders/`): создают начальную структуру блоков и текста.
- **Processors** (`marker/processors/`): улучшают блоки, добавляют семантику.
- **LLM Services** (`marker/services/`): опциональные улучшения через LLM.
- **Renderers** (`marker/renderers/`): вывод в Markdown/HTML/JSON.
- **Converters** (`marker/converters/`): управляют всем pipeline.

### Связи между компонентами

```
PdfConverter
   ├── ProviderRegistry → PdfProvider
   ├── Builders: DocumentBuilder → LayoutBuilder → LineBuilder → OcrBuilder → StructureBuilder
   ├── Processors (ordered list)
   ├── Renderer (например, MarkdownRenderer)
```

### Data flow (поток данных)

```
[PDF файл]
    ↓
[PdfProvider: страницы, размеры, изображения, текст]
    ↓
[DocumentBuilder: Document + Page]
    ↓
[LayoutBuilder: блоки (Text, Table, Figure, Formula…)]
    ↓
[LineBuilder: строки текста внутри блоков]
    ↓
[OcrBuilder: распознавание текста]
    ↓
[StructureBuilder: дерево блоков]
    ↓
[Processors: семантика, исправления]
    ↓
[Renderer: Markdown/HTML/JSON]
    ↓
[Файлы и метаданные]
```

---

## 3. Этап 1: Загрузка и подготовка документа

### Как система получает PDF файл
Marker принимает PDF через CLI (`marker_single`, `marker`) или Python API:

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

converter = PdfConverter(artifact_dict=create_model_dict())
rendered = converter("/path/to/file.pdf")
```

### Провайдеры (providers) — какой провайдер отвечает за PDF
За PDF отвечает `PdfProvider` (`marker/providers/pdf.py`). Реестр `ProviderRegistry` автоматически выбирает его по расширению `.pdf`:

```python
from marker.providers.registry import provider_from_filepath
provider = provider_from_filepath("document.pdf")  # вернет PdfProvider
```

### Что происходит на этапе подготовки
`PdfProvider`:
- Определяет количество страниц.
- Возвращает размеры страниц (bbox).
- Извлекает текст, если он есть (embedded text layer).
- Рендерит страницы в изображения для layout detection и OCR.

### Преобразование PDF в изображения страниц
Для нейросетевых моделей нужен rasterized вариант страниц. `PdfProvider.render_page(page_id)` возвращает изображение (обычно в RGB), которое затем используется Builder-ами:

```
PDF страница → Render → Image (PIL/NumPy) → Layout/OCR модели
```

---

## 4. Этап 2: Построение структуры документа (Builders)

### DocumentBuilder — общее описание
`DocumentBuilder` создает объект `Document` и список `Page`-блоков. Это «скелет» документа.

**Результат:**
```
Document
└── Page[0]
└── Page[1]
└── ...
```

### LayoutBuilder — определение структуры страницы (layout detection)
`LayoutBuilder` использует модель Surya для распознавания макета страницы.

#### Как работает layout detection
- Страница рендерится в изображение.
- Модель определяет bounding boxes и типы блоков.
- Полученные блоки добавляются в страницу.

#### Какие блоки выявляются
- Text (параграфы)
- Table (таблицы)
- Figure (изображения)
- Title / SectionHeader (заголовки)
- Caption (подписи)
- List (списки)
- Formula (формулы)

Пример структуры:

```
Page
├── TextBlock(…)
├── TableBlock(…)
├── FigureBlock(…)
└── CaptionBlock(…)
```

### OCRBuilder — распознавание текста
`OcrBuilder` использует Surya OCR.

#### Как работает OCR
- Для текстовых блоков определяется, нужен ли OCR.
- Если PDF содержит «плохой» текст или `--force_ocr`, выполняется OCR.
- Результаты распознавания записываются в строки (`Line` блоки).

#### Модели Surya
Surya включает модели:
- Layout detection
- Line detection
- OCR recognition

### LineBuilder — выявление строк текста
`LineBuilder` использует модель обнаружения строк. Это важно для:
- деления абзацев
- восстановления переносов
- привязки OCR результатов к строкам

### StructureBuilder — построение иерархии блоков
`StructureBuilder` связывает блоки в дерево:
- Заголовок → параграфы
- Таблица → строки → ячейки
- Figure → Caption
- Списки → пункты

Результат — дерево, пригодное для рендеринга:

```
Document
└── Page
    ├── SectionHeader
    ├── Text
    ├── List
    │   ├── ListItem
    │   └── ListItem
    └── Table
        ├── Row
        └── Row
```

---

## 5. Этап 3: Обработка и улучшение блоков (Processors)

Ниже перечислены все основные процессоры, которые встречаются в стандартном pipeline (см. `marker/processors/`). Они выполняются последовательно и «улучшают» документ.

### Базовые процессоры

- **OrderProcessor** (`order.py`) — определяет порядок чтения блоков, особенно для многоколоночных страниц.
- **LineMergeProcessor** (`line_merge.py`) — объединяет строки в абзацы, исправляет переносы слов.
- **BlockRelabelProcessor** (`block_relabel.py`) — исправляет типы блоков, если layout detection ошибся.
- **TextProcessor** (`text.py`) — нормализует текст, удаляет шум, исправляет пробелы и разрывы.
- **SectionHeaderProcessor** (`sectionheader.py`) — определяет заголовки и их уровни (H1/H2/H3...).
- **ListProcessor** (`list.py`) — распознает списки, определяет вложенность и тип (маркированный/нумерованный).
- **TableProcessor** (`table.py`) — строит структуру таблицы (строки/ячейки), формирует HTML/Markdown-таблицы.
- **EquationProcessor** (`equation.py`) — конвертирует формулы в LaTeX, различает inline и block-формулы.
- **CodeProcessor** (`code.py`) — распознает блоки кода, сохраняет форматирование.
- **BlockquoteProcessor** (`blockquote.py`) — выделяет цитаты (blockquote).
- **FootnoteProcessor** (`footnote.py`) — распознает сноски и связывает их с текстом.
- **ReferenceProcessor** (`reference.py`) — обрабатывает библиографию и ссылки.
- **PageHeaderProcessor** (`page_header.py`) — удаляет повторяющиеся колонтитулы.
- **DocumentTOCProcessor** (`document_toc.py`) — формирует оглавление по заголовкам.
- **DebugProcessor** (`debug.py`) — сохраняет отладочную информацию.
- **BlankPageProcessor** (`blank_page.py`) — помечает пустые страницы.
- **IgnoreTextProcessor** (`ignoretext.py`) — фильтрует шумовые блоки.
- **LineNumbersProcessor** (`line_numbers.py`) — удаляет номера строк (полезно для PDF с кодом/документацией).

### Детальный пример обработки текста

```
До TextProcessor:
"В   этом  тексте\nмного   пробелов"

После TextProcessor:
"В этом тексте много пробелов"
```

### Пример обработки таблицы

```
PDF-таблица:
+-----+-----+
|  A  |  B  |
+-----+-----+
|  1  |  2  |
+-----+-----+

После TableProcessor → Markdown:
| A | B |
|---|---|
| 1 | 2 |
```

---

## 6. Этап 4: Опциональное улучшение с помощью LLM (Services)

### Когда и зачем используются LLM
LLM-процессоры включаются флагом `--use_llm`. Они применяются для сложных участков: плохо распознанные таблицы, формулы, формы или смешанные регионы.

### Какие LLM поддерживаются
Сервисы в `marker/services/` поддерживают:
- Gemini (Google)
- OpenAI
- Claude (Anthropic)
- Vertex AI
- Ollama (локально)
- Azure OpenAI

### Какие аспекты улучшаются
LLM помогает:
- исправлять структуру таблиц
- объединять таблицы, разбитые по страницам
- распознавать сложные формулы
- формировать текстовые описания изображений
- корректировать заголовки

### Примеры улучшений

```
Таблица до LLM:
| A | B | C |
| 1 | 2 |

После LLMTableProcessor:
| A | B | C |
|---|---|---|
| 1 | 2 |   |
```

```
Сложная формула до LLM:
E = mc2

После LLMEquationProcessor:
E = mc^2
```

---

## 7. Этап 5: Рендеринг результатов (Renderers)

### MarkdownRenderer
`MarkdownRenderer` преобразует блоки в Markdown:
- Заголовки → `#`, `##`, `###`
- Таблицы → Markdown таблицы
- Формулы → `$$...$$`
- Код → ```
- Списки → `-` или `1.`

Пример:

```markdown
# Заголовок

Текст абзаца.

| A | B |
|---|---|
| 1 | 2 |
```

### HTMLRenderer
`HTMLRenderer` создает HTML-документ со структурой `<h1>`, `<p>`, `<table>` и `<img>`.

### JSONRenderer
`JSONRenderer` сохраняет дерево блоков с координатами и метаданными, удобен для анализа.

### Другие рендеры
- **ChunkRenderer** — создает «чанки» для RAG.
- **OCRJSONRenderer** — сохраняет только OCR результаты.
- **ExtractionRenderer** — структурированный JSON по схеме.

---

## 8. Полный пример с диаграммой

### Пример обработки PDF
Допустим, PDF содержит заголовок, абзац, таблицу и формулу.

```
Страница PDF:
[Заголовок]
[Абзац]
[Таблица]
[Формула]
```

### Диаграмма потока данных

```
PDF
 └─ PdfProvider
     └─ DocumentBuilder
         └─ LayoutBuilder
             └─ LineBuilder
                 └─ OcrBuilder
                     └─ StructureBuilder
                         └─ Processors
                             └─ Renderer
                                 └─ Markdown
```

### Пример результатов на каждом этапе

**После LayoutBuilder:**
```
Page:
- Block(Text)
- Block(Table)
- Block(Formula)
```

**После StructureBuilder:**
```
Document:
- SectionHeader
- Text
- Table
- Equation
```

**После Render:**
```markdown
# Заголовок

Текст абзаца...

| A | B |
|---|---|
| 1 | 2 |

$$E = mc^2$$
```

---

## 9. Оптимизация и производительность

### Батч-обработка нескольких документов
CLI `marker` позволяет обрабатывать целые папки. Используется multiprocessing:

```
marker /path/to/folder --workers 8
```

### Multi-GPU обработка
Команда `marker_chunk_convert` поддерживает распределение на несколько GPU:

```
NUM_DEVICES=4 NUM_WORKERS=15 marker_chunk_convert input output
```

### Управление памятью
- Автоматический подбор batch size
- Использование GPU-оптимизированных моделей
- Отдельные процессы для каждого worker

---

## 10. Примеры использования

### CLI команды

```bash
marker_single document.pdf --output_format markdown
```

```bash
marker document_folder --output_format html --use_llm
```

### Python API примеры

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

converter = PdfConverter(artifact_dict=create_model_dict())
rendered = converter("document.pdf")
text, _, images = text_from_rendered(rendered)
```

### Расширение для своих нужд
Можно создать собственный процессор:

```python
from marker.processors import BaseProcessor

class CustomProcessor(BaseProcessor):
    def __call__(self, document):
        # кастомная логика
        return document
```

И добавить в pipeline:

```python
from marker.config.parser import ConfigParser

config_parser = ConfigParser({"processors": ["order", "custom"]})
```

---

## Итог

Алгоритм Marker для конвертации PDF в Markdown — это многоступенчатый pipeline, где каждый шаг добавляет структуру и семантику: от сырых изображений страниц до аккуратного Markdown с таблицами, формулами и ссылками. Для новичка это понятный процесс «из файла в текст», а для опытного разработчика — гибкая система, которую можно расширять и оптимизировать под конкретные задачи.
