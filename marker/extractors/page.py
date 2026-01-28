"""marker.extractors.page

Постраничный экстрактор для режима structured extraction.

`PageExtractor` принимает Markdown-страницы (уже полученные на этапе конвертации)
и для каждой пачки страниц формирует «заметки» (notes), которые затем будут
использованы `DocumentExtractor` для сборки итогового JSON.

Основные идеи:
- извлечение выполняется через LLM-сервис (`self.llm_service`);
- страницы группируются в чанки (`extraction_page_chunk_size`) для уменьшения числа
  запросов и лучшего контекста;
- запросы к LLM выполняются параллельно через ThreadPoolExecutor;
- прогресс отображается через tqdm, если не отключено.

Важно: сам JSON-результат здесь не собирается — на этом этапе мы получаем
подробные текстовые заметки и черновые JSON-фрагменты.
"""

# Стандартная библиотека: JSON и пул потоков.
import json
from concurrent.futures import ThreadPoolExecutor

# Типизация и базовая модель.
from pydantic import BaseModel
from typing import Annotated, Optional, List

# Прогресс-бар.
from tqdm import tqdm

# Базовый класс экстрактора.
from marker.extractors import BaseExtractor

# Логирование.
from marker.logger import get_logger

logger = get_logger()


class PageExtractionSchema(BaseModel):
    """Pydantic-схема результата извлечения для одного чанка страниц.

    Поля:
        description: Краткое описание того, какие поля схемы и значения присутствуют.
        detailed_notes: Подробные заметки, которые помогут позже собрать итоговый JSON.
    """

    description: str
    detailed_notes: str


class PageExtractor(BaseExtractor):
    """Экстрактор, который извлекает информацию на уровне страниц.

    На вход получает список строк Markdown (обычно одна строка на страницу),
    затем:
    - группирует их в чанки;
    - по каждому чанку делает запрос к LLM;
    - возвращает список объектов `PageExtractionSchema`.

    Атрибуты класса (конфигурируемые):
        extraction_page_chunk_size: Сколько страниц объединять в один запрос.
        page_schema: JSON-схема (в виде строки/объекта), по которой нужно собирать заметки.
    """

    extraction_page_chunk_size: Annotated[
        int, "The number of pages to chunk together for extraction."
    ] = 3

    page_schema: Annotated[
        str,
        "The JSON schema to be extracted from the page.",
    ] = ""

    # Основной prompt для LLM.
    # Важно: это пользовательский текст для модели, поэтому он остаётся на исходном языке.
    page_extraction_prompt = """You are an expert document analyst who reads documents and pulls data out in JSON format. You will receive the markdown representation of a document page, and a JSON schema that we want to extract from the document. Your task is to write detailed notes on this page, so that when you look at all your notes from across the document, you can fill in the schema.
    
Some notes:
- The schema may contain a single object to extract from the entire document, or an array of objects. 
- The schema may contain nested objects, arrays, and other complex structures.

Some guidelines:
- Write very thorough notes, and include specific JSON snippets that can be extracted from the page.
- You may need information from prior or subsequent pages to fully fill in the schema, so make sure to write detailed notes that will let you join entities across pages later on.
- Estimate your confidence in the values you extract, so you can reconstruct the JSON later when you only have your notes.
- Some tables and other data structures may continue on a subsequent page, so make sure to store the positions that data comes from where appropriate.

**Instructions:**
1. Analyze the provided markdown representation of the page.
2. Analyze the JSON schema.
3. Write a short description of the fields in the schema, and the associated values in the markdown.
4. Write detailed notes on the page, including any values that can be extracted from the markdown.  Include snippets of JSON that can be extracted from the page where possible.

**Example:**
Input:

Markdown
```markdown
| Make   | Sales |
|--------|-------|
| Honda  | 100   |
| Toyota | 200   |
```

Schema

```json
{'$defs': {'Cars': {'properties': {'make': {'title': 'Make', 'type': 'string'}, 'sales': {'title': 'Sales', 'type': 'integer'}, 'color': {'title': 'Color', 'type': 'string'}}, 'required': ['make', 'sales', 'color'], 'title': 'Cars', 'type': 'object'}}, 'properties': {'cars': {'items': {'$ref': '#/$defs/Cars'}, 'title': 'Cars', 'type': 'array'}}, 'required': ['cars'], 'title': 'CarsList', 'type': 'object'}
```

Output:

Description: The schema has a list of cars, each with a make, sales, and color. The image and markdown contain a table with 2 cars: Honda with 100 sales and Toyota with 200 sales. The color is not present in the table.
Detailed Notes: On this page, I see a table with car makes and sales. The makes are Honda and Toyota, with sales of 100 and 200 respectively. The color is not present in the table, so I will leave it blank in the JSON.  That information may be present on another page.  Some JSON snippets I may find useful later are:
```json
{
    "make": "Honda",
    "sales": 100,
}
```
```json
{
    "make": "Toyota",
    "sales": 200,
}
```

Honda is the first row in the table, and Toyota is the second row.  Make is the first column, and sales is the second.

**Input:**

Markdown
```markdown
{{page_md}}
```

Schema
```json
{{schema}}
```
"""

    def chunk_page_markdown(self, page_markdown: List[str]) -> List[str]:
        """Группирует список страниц Markdown в чанки фиксированного размера.

        Зачем это нужно:
        - уменьшить количество запросов к LLM;
        - дать модели чуть больше контекста (несколько соседних страниц).

        Аргументы:
            page_markdown: Список строк Markdown (обычно одна строка на страницу).

        Возвращает:
            Список строк, где каждая строка — объединённый Markdown-чанк.
        """

        # Список итоговых чанков.
        chunks = []

        # Идём по страницам с шагом chunk_size.
        for i in range(0, len(page_markdown), self.extraction_page_chunk_size):
            # Берём подсписок страниц.
            chunk = page_markdown[i : i + self.extraction_page_chunk_size]

            # Склеиваем страницы двойным переносом строки, чтобы сохранить читаемость.
            chunks.append("\n\n".join(chunk))

        return chunks

    def inference_single_chunk(
        self, page_markdown: str
    ) -> Optional[PageExtractionSchema]:
        """Выполняет один запрос к LLM для конкретного Markdown-чанка.

        Аргументы:
            page_markdown: Markdown-текст чанка страниц.

        Возвращает:
            Экземпляр `PageExtractionSchema` или None, если модель вернула
            неполный/невалидный ответ.
        """

        # Подставляем Markdown и схему в prompt.
        prompt = self.page_extraction_prompt.replace(
            "{{page_md}}", page_markdown
        ).replace("{{schema}}", json.dumps(self.page_schema))

        # Делаем вызов LLM. Параметры (image/attachments) здесь не используются.
        response = self.llm_service(prompt, None, None, PageExtractionSchema)
        logger.debug(f"Page extraction response: {response}")

        # Валидация минимального набора ключей.
        if not response or any(
            [
                key not in response
                for key in [
                    "description",
                    "detailed_notes",
                ]
            ]
        ):
            return None

        # Приводим ответ к Pydantic-модели.
        return PageExtractionSchema(
            description=response["description"],
            detailed_notes=response["detailed_notes"],
        )

    def __call__(
        self,
        page_markdown: List[str],
        **kwargs,
    ) -> List[PageExtractionSchema]:
        """Запускает постраничное извлечение и возвращает список заметок.

        Аргументы:
            page_markdown: Список страниц в Markdown.
            **kwargs: Дополнительные параметры (на текущий момент не используются).

        Возвращает:
            Список объектов `PageExtractionSchema` (по одному на каждый чанк).

        Raises:
            ValueError: если `page_schema` не задан.
        """

        # Без схемы structured extraction не имеет смысла.
        if not self.page_schema:
            raise ValueError(
                "Page schema must be defined for structured extraction to work."
            )

        # Разбиваем страницы на чанки.
        chunks = self.chunk_page_markdown(page_markdown)

        # Сюда будем собирать результаты по каждому чанку.
        results = []

        # Создаём прогресс-бар.
        pbar = tqdm(
            desc="Running page extraction",
            disable=self.disable_tqdm,
            total=len(chunks),
        )

        # Параллельно выполняем запросы к LLM.
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for future in [
                executor.submit(self.inference_single_chunk, chunk) for chunk in chunks
            ]:
                # future.result() также пробросит исключения, если они произошли в потоке.
                results.append(future.result())  # Поднимет исключение, если оно возникло
                pbar.update(1)

        # Закрываем прогресс-бар и возвращаем результаты.
        pbar.close()
        return results
