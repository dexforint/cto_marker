"""marker.extractors

Пакет экстракторов (Extractors) Marker.

Экстрактор в Marker — это компонент, который получает уже построенный документ
(или промежуточное представление) и извлекает из него структурированные данные,
как правило с помощью LLM-сервиса.

Экстракторы отличаются от конвертеров тем, что:
- не строят документ из «сырого» файла (это задача конвертера/билдеров);
- работают поверх уже подготовленных структур (страницы, блоки, Markdown);
- часто ориентированы на конкретный сценарий вывода (например, structured extraction).

Этот файл содержит базовый класс `BaseExtractor`, который задаёт общий интерфейс:
- хранит LLM-сервис;
- предоставляет вспомогательный метод `extract_image` для получения изображения
  страницы (с возможностью удаления некоторых типов блоков);
- требует реализации `__call__` в конкретных экстракторах.
"""

# Типизация.
from typing import Annotated, Sequence

# Схема документа и типы блоков.
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups import PageGroup

# PIL используется для работы с изображениями страниц.
from PIL import Image

# Базовый интерфейс LLM-сервиса.
from marker.services import BaseService

# Утилита для применения конфигурации к объекту.
from marker.util import assign_config


class BaseExtractor:
    """Базовый класс для экстракторов, работающих с LLM.

    Экземпляр экстрактора обычно создаётся конвертером через dependency injection,
    и получает:
    - `llm_service`: сервис, умеющий выполнять запросы к LLM;
    - `config`: произвольные настройки экстрактора.

    Атрибуты класса (конфигурируемые):
        max_concurrency: Максимальное число параллельных запросов к LLM.
        disable_tqdm: Отключает прогресс-бар tqdm.
    """

    max_concurrency: Annotated[
        int,
        "The maximum number of concurrent requests to make to the Gemini model.",
    ] = 3
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False

    def __init__(self, llm_service: BaseService, config=None):
        """Инициализирует экстрактор.

        Аргументы:
            llm_service: Сервис LLM, который будет использоваться для извлечения.
            config: Конфигурация экстрактора.

        Возвращает:
            None
        """

        # Применяем конфигурацию к атрибутам экземпляра (если совпадают имена).
        assign_config(self, config)

        # Сохраняем LLM-сервис как обязательную зависимость.
        self.llm_service = llm_service

    def extract_image(
        self,
        document: Document,
        page: PageGroup,
        remove_blocks: Sequence[BlockTypes] | None = None,
        highres: bool = False,  # По умолчанию False, чтобы экономить токены
    ) -> Image.Image:
        """Извлекает изображение страницы для подачи в LLM (или другие задачи).

        Метод делегирует работу `page.get_image`, но централизует типы аргументов
        и делает интерфейс удобным для конкретных экстракторов.

        Аргументы:
            document: Документ, к которому относится страница.
            page: Группа страницы (PageGroup), откуда берётся изображение.
            remove_blocks: Список типов блоков, которые следует «вырезать» перед
                рендером изображения (например, чтобы убрать большие таблицы).
            highres: Если True, использовать high-resolution рендер.

        Возвращает:
            Объект PIL.Image.Image с изображением страницы.
        """

        # Получаем изображение страницы через метод PageGroup.
        return page.get_image(
            document,
            highres=highres,
            remove_blocks=remove_blocks,
        )

    def __call__(self, document: Document, *args, **kwargs):
        """Запускает извлечение.

        Конкретные экстракторы должны переопределить этот метод.

        Аргументы:
            document: Документ (или другой объект), из которого извлекаются данные.
            *args: Дополнительные аргументы конкретного экстрактора.
            **kwargs: Дополнительные именованные аргументы.

        Возвращает:
            Результат извлечения (тип зависит от конкретного экстрактора).

        Raises:
            NotImplementedError: если метод не переопределён.
        """

        raise NotImplementedError
