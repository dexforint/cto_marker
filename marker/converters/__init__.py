"""marker.converters

Пакет конвертеров Marker.

Конвертер в Marker — это верхнеуровневый объект, который оркестрирует пайплайн:
- получает вход (файл/поток) и «артефакты» (модели, сервисы);
- создаёт билдеры/процессоры/рендерер с учётом конфигурации;
- запускает обработку и возвращает результат.

В этом файле определён базовый класс `BaseConverter`, который:
- применяет конфигурацию к атрибутам конвертера;
- предоставляет вспомогательный механизм «инъекции зависимостей» (dependency injection)
  по сигнатуре __init__ создаваемого класса;
- умеет преобразовывать набор простых LLM-процессоров в единый мета-процессор
  (`LLMSimpleBlockMetaProcessor`).

Важно: данный модуль не содержит конкретных конвертеров (PDF/Table/OCR/Extraction) —
они определены в соответствующих файлах пакета.
"""

# Стандартная библиотека: анализ сигнатур для простого DI.
import inspect
from typing import Optional, List, Type

from pydantic import BaseModel

from marker.processors import BaseProcessor
from marker.processors.llm import BaseLLMSimpleBlockProcessor
from marker.processors.llm.llm_meta import LLMSimpleBlockMetaProcessor
from marker.util import assign_config, download_font


class BaseConverter:
    """Базовый класс конвертеров.

    Ключевая ответственность — дать единый интерфейс и общие утилиты:
    - хранение `config` и применение значений конфигурации к атрибутам экземпляра;
    - создание зависимостей (процессоров/рендереров/сервисов) на основе
      `self.config` и `self.artifact_dict`;
    - группировка простых LLM-процессоров в один мета-процессор.

    Атрибуты:
        config: Конфигурация конвертера (dict или Pydantic-модель).
        llm_service: Экземпляр LLM-сервиса (если используется).
    """

    def __init__(self, config: Optional[BaseModel | dict] = None):
        """Инициализирует конвертер и применяет конфигурацию.

        Аргументы:
            config: Конфигурация конвертера.

        Возвращает:
            None
        """

        # Применяем конфигурацию (значения из config попадают в одноимённые атрибуты).
        assign_config(self, config)
        self.config = config

        # По умолчанию LLM-сервис не задан — конкретный конвертер может установить его.
        self.llm_service = None

        # Скачиваем шрифт для рендера (нужен некоторым провайдерам).
        download_font()

    def __call__(self, *args, **kwargs):
        """Запускает конвертацию.

        Базовая реализация не знает, как именно выполнять конвертацию — это
        ответственность конкретных конвертеров.

        Raises:
            NotImplementedError: если подкласс не переопределил метод.
        """

        raise NotImplementedError

    def resolve_dependencies(self, cls):
        """Создаёт экземпляр `cls`, автоматически подставляя зависимости.

        Механизм использует сигнатуру `cls.__init__` и подставляет параметры по правилам:
        - `self` пропускается;
        - параметр `config` получает `self.config`;
        - если имя параметра есть в `self.artifact_dict`, берём значение оттуда;
        - иначе, если у параметра есть default, используем default;
        - иначе выбрасываем исключение.

        Аргументы:
            cls: Класс, который нужно инстанцировать.

        Возвращает:
            Экземпляр `cls`.

        Raises:
            ValueError: если зависимость для обязательного параметра не удалось найти.
        """

        # Считываем сигнатуру конструктора.
        init_signature = inspect.signature(cls.__init__)
        parameters = init_signature.parameters

        # Сюда собираем аргументы, которые будут переданы в конструктор.
        resolved_kwargs = {}

        # Проходим по всем параметрам конструктора.
        for param_name, param in parameters.items():
            # `self` не передаётся явно.
            if param_name == 'self':
                continue
            # Единый конфиг пробрасываем во все зависимости через параметр `config`.
            elif param_name == 'config':
                resolved_kwargs[param_name] = self.config
            # Артефакты (модели/сервисы/и т. п.) доступны по имени параметра.
            elif param.name in self.artifact_dict:
                resolved_kwargs[param_name] = self.artifact_dict[param_name]
            # Если есть значение по умолчанию — используем его.
            elif param.default != inspect.Parameter.empty:
                resolved_kwargs[param_name] = param.default
            # Иначе создать объект невозможно.
            else:
                raise ValueError(f"Cannot resolve dependency for parameter: {param_name}")

        # Инстанцируем класс с разрешёнными зависимостями.
        return cls(**resolved_kwargs)

    def initialize_processors(self, processor_cls_lst: List[Type[BaseProcessor]]) -> List[BaseProcessor]:
        """Инстанцирует процессоры и при необходимости объединяет LLM-процессоры.

        В Marker есть класс простых LLM-процессоров (`BaseLLMSimpleBlockProcessor`).
        Их удобно запускать через единый `LLMSimpleBlockMetaProcessor`, который:
        - агрегирует вызовы LLM;
        - позволяет централизованно управлять сервисом LLM;
        - сохраняет логический порядок обработки.

        Аргументы:
            processor_cls_lst: Список классов процессоров.

        Возвращает:
            Список экземпляров процессоров (возможно с мета-процессором).
        """

        # Создаём экземпляры процессоров через DI.
        processors = []
        for processor_cls in processor_cls_lst:
            processors.append(self.resolve_dependencies(processor_cls))

        # Отделяем простые LLM-процессоры от остальных.
        simple_llm_processors = [p for p in processors if issubclass(type(p), BaseLLMSimpleBlockProcessor)]
        other_processors = [p for p in processors if not issubclass(type(p), BaseLLMSimpleBlockProcessor)]

        # Если LLM-процессоров нет — возвращаем исходный список.
        if not simple_llm_processors:
            return processors

        # Вычисляем позицию, куда вставить мета-процессор, чтобы сохранить порядок.
        llm_positions = [i for i, p in enumerate(processors) if issubclass(type(p), BaseLLMSimpleBlockProcessor)]
        insert_position = max(0, llm_positions[-1] - len(simple_llm_processors) + 1)

        # Создаём мета-процессор, который будет запускать все LLM-процессоры.
        meta_processor = LLMSimpleBlockMetaProcessor(
            processor_lst=simple_llm_processors,
            llm_service=self.llm_service,
            config=self.config,
        )

        # Вставляем мета-процессор в список «прочих» процессоров.
        other_processors.insert(insert_position, meta_processor)
        return other_processors
