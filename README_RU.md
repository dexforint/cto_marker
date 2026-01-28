# Marker - Конвертер документов в Markdown

Marker конвертирует документы в markdown, JSON, фрагменты (chunks) и HTML быстро и точно.

## 🌟 Возможности

- ✅ **Множество форматов**: Конвертирует PDF, изображения, PPTX, DOCX, XLSX, HTML, EPUB файлы на всех языках
- ✅ **Умное форматирование**: Обрабатывает таблицы, формы, уравнения, inline математику, ссылки, референсы и блоки кода
- ✅ **Извлечение изображений**: Извлекает и сохраняет изображения из документов
- ✅ **Очистка артефактов**: Удаляет колонтитулы и другие повторяющиеся элементы
- ✅ **Расширяемость**: Добавляйте собственное форматирование и логику
- ✅ **Структурированное извлечение**: Извлекает данные по JSON schema (beta)
- ✅ **LLM интеграция**: Опционально повышает точность с помощью больших языковых моделей
- ✅ **Кросс-платформенность**: Работает на GPU (CUDA), CPU, или Apple MPS

## 📊 Производительность

<img src="data/images/overall.png" width="800px"/>

Marker показывает лучшие результаты по сравнению с облачными сервисами (Llamaparse, Mathpix) и другими open source инструментами.

Результаты выше получены при последовательной обработке страниц. Marker значительно быстрее в batch режиме, с проекцией **25 страниц/секунду на H100**.

Подробные бенчмарки скорости и точности смотрите [ниже](#бенчмарки).

## 🚀 Гибридный режим (Hybrid Mode)

Для максимальной точности используйте флаг `--use_llm` для включения LLM вместе с marker. Это позволит:
- Объединять таблицы, разбитые на несколько страниц
- Обрабатывать inline математику
- Правильно форматировать таблицы
- Извлекать значения из форм

Поддерживаются модели gemini и ollama. По умолчанию используется `gemini-2.0-flash`.

<img src="data/images/table.png" width="400px"/>

Режим `--use_llm` обеспечивает более высокую точность, чем marker или gemini по отдельности.

## 📖 Примеры

| PDF | Тип файла | Markdown | JSON |
|-----|-----------|----------|------|
| [Think Python](https://greenteapress.com/thinkpython/thinkpython.pdf) | Учебник | [Просмотр](https://github.com/VikParuchuri/marker/blob/master/data/examples/markdown/thinkpython/thinkpython.md) | [Просмотр](https://github.com/VikParuchuri/marker/blob/master/data/examples/json/thinkpython.json) |
| [Switch Transformers](https://arxiv.org/pdf/2101.03961.pdf) | arXiv статья | [Просмотр](https://github.com/VikParuchuri/marker/blob/master/data/examples/markdown/switch_transformers/switch_trans.md) | [Просмотр](https://github.com/VikParuchuri/marker/blob/master/data/examples/json/switch_trans.json) |
| [Multi-column CNN](https://arxiv.org/pdf/1804.07821.pdf) | arXiv статья | [Просмотр](https://github.com/VikParuchuri/marker/blob/master/data/examples/markdown/multicolcnn/multicolcnn.md) | [Просмотр](https://github.com/VikParuchuri/marker/blob/master/data/examples/json/multicolcnn.json) |

## 💼 Коммерческое использование

Веса наших моделей используют модифицированную лицензию AI Pubs Open Rail-M (бесплатно для исследований, личного использования и стартапов с финансированием/доходом менее $2M), а код распространяется под GPL.

Для расширенного коммерческого лицензирования посетите [нашу страницу](https://www.datalab.to/pricing?utm_source=gh-marker).

## ☁️ Hosted API и On-prem решение

Доступны [hosted API](https://www.datalab.to?utm_source=gh-marker) и [on-prem решение](https://www.datalab.to/blog/self-serve-on-prem-licensing) для marker.

API преимущества:
- Поддержка PDF, image, PPT, PPTX, DOC, DOCX, XLS, XLSX, HTML, EPUB
- В 4 раза дешевле ведущих облачных конкурентов
- Быстрый - ~15 секунд для PDF на 250 страниц
- Поддержка LLM режима
- Высокая доступность (99.99%)

## 💬 Сообщество

[Discord](https://discord.gg//KuZwXNGnfH) - обсуждаем будущее развитие.

## 📦 Установка

Требования: Python 3.10+ и [PyTorch](https://pytorch.org/get-started/locally/).

### Базовая установка (только PDF):

```shell
pip install marker-pdf
```

### Полная установка (все форматы):

```shell
pip install marker-pdf[full]
```

## 🎯 Использование

### Конфигурация

- **Torch device**: Определяется автоматически, но можно переопределить: `TORCH_DEVICE=cuda`
- **Принудительный OCR**: Для PDF с плохим текстом используйте `--force_ocr`
- **Удаление существующего OCR**: Флаг `--strip_existing_ocr`
- **Inline математика**: Используйте `--force_ocr` для конвертации inline математики в LaTeX

### Интерактивное приложение

Запуск Streamlit приложения для интерактивного тестирования:

```shell
pip install streamlit streamlit-ace
marker_gui
```

### Конвертация одного файла

```shell
marker_single /path/to/file.pdf
```

Поддерживаются PDF и изображения.

#### Основные опции:

- `--page_range TEXT` - Диапазон страниц (например: `"0,5-10,20"`)
- `--output_format [markdown|json|html|chunks]` - Формат вывода
- `--output_dir PATH` - Директория для сохранения результатов
- `--paginate_output` - Пагинация вывода с номерами страниц
- `--use_llm` - Использовать LLM для повышения точности
- `--force_ocr` - Принудительный OCR всего документа
- `--block_correction_prompt` - Custom промпт для коррекции (с LLM)
- `--strip_existing_ocr` - Удалить существующий OCR и переделать
- `--redo_inline_math` - Максимальное качество inline математики (с `--use_llm`)
- `--disable_image_extraction` - Не извлекать изображения
- `--debug` - Режим отладки
- `--processors TEXT` - Переопределить процессоры
- `--config_json PATH` - Путь к JSON конфигурации
- `--converter_cls` - Класс конвертера (по умолчанию: `marker.converters.pdf.PdfConverter`)
- `--llm_service` - Сервис LLM (по умолчанию: `marker.services.gemini.GoogleGeminiService`)

Полный список опций: `marker_single --help`

Поддерживаемые языки для Surya OCR: [список](https://github.com/VikParuchuri/surya/blob/master/surya/recognition/languages.py)

### Конвертация нескольких файлов

```shell
marker /path/to/input/folder
```

- Поддерживает все опции `marker_single`
- `--workers` - Количество параллельных workers (автоматически по умолчанию)
  - Marker использует ~5GB VRAM на пике и ~3.5GB в среднем на worker

### Конвертация на нескольких GPU

```shell
NUM_DEVICES=4 NUM_WORKERS=15 marker_chunk_convert ../pdf_in ../md_out
```

- `NUM_DEVICES` - Количество GPU (≥2)
- `NUM_WORKERS` - Количество параллельных процессов на GPU

### Использование из Python

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

# Создание конвертера
converter = PdfConverter(
    artifact_dict=create_model_dict(),
)

# Конвертация
rendered = converter("FILEPATH")
text, _, images = text_from_rendered(rendered)
```

`rendered` - это Pydantic basemodel со свойствами:
- **Markdown** (по умолчанию): `markdown`, `metadata`, `images`
- **JSON**: `children`, `block_type`, `metadata`

#### Custom конфигурация

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser

# Настройки
config = {
    "output_format": "json",
    "use_llm": True,
    # Дополнительные параметры...
}
config_parser = ConfigParser(config)

# Создание конвертера с конфигурацией
converter = PdfConverter(
    config=config_parser.generate_config_dict(),
    artifact_dict=create_model_dict(),
    processor_list=config_parser.get_processors(),
    renderer=config_parser.get_renderer(),
    llm_service=config_parser.get_llm_service()
)

rendered = converter("FILEPATH")
```

#### Извлечение блоков

Документ состоит из страниц, содержащих блоки, которые могут содержать другие блоки.

Пример извлечения всех форм:

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import BlockTypes

converter = PdfConverter(
    artifact_dict=create_model_dict(),
)

document = converter.build_document("FILEPATH")
forms = document.contained_blocks((BlockTypes.Form,))
```

### Другие конвертеры

#### Извлечение таблиц (TableConverter)

Конвертирует только таблицы:

```python
from marker.converters.table import TableConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

converter = TableConverter(
    artifact_dict=create_model_dict(),
)
rendered = converter("FILEPATH")
text, _, images = text_from_rendered(rendered)
```

CLI вариант:
```shell
marker_single FILENAME --use_llm --force_layout_block Table \
  --converter_cls marker.converters.table.TableConverter --output_format json
```

Конфигурация `force_layout_block=Table` заставляет считать каждую страницу таблицей.

#### Только OCR (OCRConverter)

Если нужен только OCR:

```python
from marker.converters.ocr import OCRConverter
from marker.models import create_model_dict

converter = OCRConverter(
    artifact_dict=create_model_dict(),
)
rendered = converter("FILEPATH")
```

CLI вариант:
```shell
marker_single FILENAME --converter_cls marker.converters.ocr.OCRConverter
```

Флаг `--keep_chars` сохраняет отдельные символы и bounding boxes.

#### Структурированное извлечение (ExtractionConverter) - beta

Извлечение по JSON schema (требует LLM сервис):

```python
from marker.converters.extraction import ExtractionConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from pydantic import BaseModel

# Определение схемы
class Links(BaseModel):
    links: list[str]

schema = Links.model_json_schema()
config_parser = ConfigParser({
    "page_schema": schema
})

# Извлечение
converter = ExtractionConverter(
    artifact_dict=create_model_dict(),
    config=config_parser.generate_config_dict(),
    llm_service=config_parser.get_llm_service(),
)
rendered = converter("FILEPATH")
```

`rendered.original_markdown` можно использовать повторно как `existing_markdown` для пропуска повторного парсинга.

## 📄 Форматы вывода

### Markdown

- Ссылки на изображения (сохраняются в той же папке)
- Форматированные таблицы
- LaTeX уравнения (в `$$`)
- Код в тройных backticks
- Надстрочные индексы для сносок

### HTML

- Изображения через `<img>` теги
- Уравнения в `<math>` тегах
- Код в `<pre>` тегах

### JSON

Древовидная структура с листовыми узлами-блоками.

Вывод - список страниц. Каждая страница - это блок.

#### Ключи страницы:

- `id` - уникальный идентификатор
- `block_type` - тип блока (см. `BlockTypes` в `marker/schema/__init__.py`)
- `html` - HTML страницы с рекурсивными ссылками (`<content-ref>`)
- `polygon` - 4-угольный полигон в формате `[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]`
- `children` - дочерние блоки

#### Дополнительные ключи дочерних блоков:

- `section_hierarchy` - иерархия разделов (`1` = h1, `2` = h2, и т.д.)
- `images` - base64 изображения (ключ = block id, значение = закодированное изображение)

Пример:

```json
{
  "id": "/page/10/Page/366",
  "block_type": "Page",
  "html": "<content-ref src='/page/10/SectionHeader/0'></content-ref>...",
  "polygon": [[0.0, 0.0], [612.0, 0.0], [612.0, 792.0], [0.0, 792.0]],
  "children": [
    {
      "id": "/page/10/SectionHeader/0",
      "block_type": "SectionHeader",
      "html": "<h1>Заголовок</h1>",
      "polygon": [[217.8, 80.6], [374.7, 80.6], [374.7, 107.0], [217.8, 107.0]],
      "children": null,
      "section_hierarchy": {"1": "/page/10/SectionHeader/1"},
      "images": {}
    }
  ]
}
```

### Chunks

Похож на JSON, но с плоским списком вместо дерева. Только блоки верхнего уровня каждой страницы. Включает полный HTML каждого блока. Идеален для RAG систем.

### Metadata

Все форматы возвращают словарь метаданных:

```json
{
  "table_of_contents": [
    {
      "title": "Введение",
      "heading_level": 1,
      "page_id": 0,
      "polygon": [...]
    }
  ],
  "page_stats": [
    {
      "page_id": 0,
      "text_extraction_method": "pdftext",
      "block_counts": [["Span", 200], ...]
    }
  ]
}
```

## 🤖 LLM Сервисы

При использовании `--use_llm` доступны следующие сервисы:

### Gemini (по умолчанию)
```shell
--llm_service=marker.services.gemini.GoogleGeminiService
--gemini_api_key=YOUR_KEY
```

### Google Vertex (более надежный)
```shell
--llm_service=marker.services.vertex.GoogleVertexService
--vertex_project_id=YOUR_PROJECT
```

### Ollama (локальные модели)
```shell
--llm_service=marker.services.ollama.OllamaService
--ollama_base_url=http://localhost:11434
--ollama_model=llama2
```

### Claude
```shell
--llm_service=marker.services.claude.ClaudeService
--claude_api_key=YOUR_KEY
--claude_model_name=claude-3-opus-20240229
```

### OpenAI
```shell
--llm_service=marker.services.openai.OpenAIService
--openai_api_key=YOUR_KEY
--openai_model=gpt-4
--openai_base_url=https://api.openai.com/v1  # опционально
```

### Azure OpenAI
```shell
--llm_service=marker.services.azure_openai.AzureOpenAIService
--azure_endpoint=YOUR_ENDPOINT
--azure_api_key=YOUR_KEY
--deployment_name=YOUR_DEPLOYMENT
```

## 🔧 Внутренности (Internals)

Marker легко расширяется. Основные компоненты:

### Providers (`marker/providers`)
Предоставляют информацию из исходных файлов (PDF, изображения, DOCX и т.д.)

### Builders (`marker/builders`)
Генерируют начальные блоки документа и заполняют текст, используя данные providers.

### Processors (`marker/processors`)
Обрабатывают конкретные блоки (например, форматирование таблиц).

### Renderers (`marker/renderers`)
Используют блоки для рендеринга вывода в различных форматах.

### Schema (`marker/schema`)
Классы для всех типов блоков.

### Converters (`marker/converters`)
Выполняют полный end-to-end pipeline.

### Кастомизация

- **Processors**: Переопределите для изменения поведения обработки
- **Renderers**: Создайте новый для добавления формата вывода
- **Providers**: Добавьте новый для поддержки дополнительных форматов ввода

Processors и renderers можно напрямую передать в `PdfConverter`.

Подробнее см. [ARCHITECTURE_RU.md](ARCHITECTURE_RU.md)

## 🌐 API сервер

Простой FastAPI сервер:

```shell
pip install -U uvicorn fastapi python-multipart
marker_server --port 8001
```

Доступ: `localhost:8001` (документация: `localhost:8001/docs`)

Пример запроса:

```python
import requests
import json

post_data = {
    'filepath': 'FILEPATH',
    # Дополнительные параметры...
}

response = requests.post(
    "http://localhost:8001/marker",
    data=json.dumps(post_data)
).json()
```

**Примечание**: Это базовая реализация для небольших нагрузок. Для production рекомендуется [Datalab API](https://www.datalab.to/plans).

## 🔍 Решение проблем

### Проблемы с точностью
- Используйте `--use_llm` для повышения качества (требуется `GOOGLE_API_KEY`)
- Установите `--force_ocr` если видите искаженный текст

### Environment переменные
- `TORCH_DEVICE` - принудительное устройство для inference
- `GOOGLE_API_KEY` - API ключ для Gemini

### Out of Memory ошибки
- Уменьшите количество workers
- Разбейте длинные PDF на несколько файлов

### Debug режим

Флаг `--debug` активирует:
- Сохранение изображений страниц с визуализацией layout
- JSON файл с дополнительными bounding boxes
- Детальное логирование

## 📊 Бенчмарки

### Общая конвертация PDF

[Набор бенчмарков](https://huggingface.co/datasets/datalab-to/marker_benchmark) создан из PDF страниц common crawl.

| Метод | Среднее время | Heuristic Score | LLM Score |
|-------|---------------|-----------------|-----------|
| marker | 2.84s | 95.67 | 4.24 |
| llamaparse | 23.35s | 84.24 | 3.98 |
| mathpix | 6.36s | 86.43 | 4.16 |
| docling | 3.70s | 86.71 | 3.70 |

Бенчмарки выполнены на H100 для marker и docling. Llamaparse и mathpix - облачные сервисы.

### По типам документов

| Тип документа | Marker heuristic | Marker LLM | Llamaparse H | Llamaparse LLM | Mathpix H | Mathpix LLM |
|---------------|------------------|------------|--------------|----------------|-----------|-------------|
| Научная статья | 96.67 | 4.35 | 87.17 | 3.96 | 91.23 | 4.47 |
| Страница книги | 97.18 | 4.16 | 90.95 | 4.07 | 93.89 | 4.35 |
| Форма | 88.01 | 3.85 | 66.31 | 3.69 | 64.75 | 3.33 |
| Презентация | 95.16 | 4.14 | 81.23 | 4.00 | 83.67 | 3.96 |
| Финансовый документ | 95.37 | 4.39 | 82.58 | 4.16 | 81.31 | 4.06 |
| Письмо | 98.40 | 4.50 | 93.45 | 4.28 | 96.04 | 4.45 |

### Throughput

Бенчмарк на [длинном PDF](https://www.greenteapress.com/thinkpython/thinkpython.pdf):

| Метод | Время/страницу | Время/документ | VRAM |
|-------|----------------|----------------|------|
| marker | 0.18s | 43.42s | 3.17GB |

**Проекция throughput**: 122 страницы/секунду на H100 (22 параллельных процесса).

### Конвертация таблиц

Бенчмарк на [FinTabNet](https://developer.ibm.com/exchanges/data/all/fintabnet/) test split:

| Метод | Средний score | Всего таблиц |
|-------|---------------|--------------|
| marker | 0.816 | 99 |
| marker w/use_llm | 0.907 | 99 |
| gemini | 0.829 | 99 |

Флаг `--use_llm` значительно улучшает распознавание таблиц.

## 📚 Дополнительная документация

- [ARCHITECTURE_RU.md](ARCHITECTURE_RU.md) - Подробная архитектура системы
- [README.md](README.md) - Оригинальная английская документация
- [MODEL_LICENSE](MODEL_LICENSE) - Лицензия моделей
- [LICENSE](LICENSE) - Лицензия кода

## 🤝 Вклад в проект

Мы приветствуем вклад в проект! См. [CLA.md](CLA.md) для деталей.

## 📧 Контакты

- **Discord**: [Присоединяйтесь к сообществу](https://discord.gg//KuZwXNGnfH)
- **Веб-сайт**: [datalab.to](https://www.datalab.to)

## ⭐ Поддержите проект

Если вам понравился Marker, поставьте ⭐ на GitHub!

---

**Marker** - мощный, точный и быстрый конвертер документов с открытым исходным кодом. 🚀
