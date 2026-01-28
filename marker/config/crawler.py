"""marker.config.crawler

Модуль обхода/сканирования конфигурации.

Здесь реализован `ConfigCrawler` — вспомогательный компонент, который
автоматически находит в пакете Marker все классы-наследники ключевых базовых
абстракций (BaseBuilder/BaseProcessor/BaseConverter/BaseProvider/BaseRenderer/
BaseService/BaseExtractor) и извлекает из них конфигурируемые параметры.

Сканирование опирается на аннотации типов атрибутов классов:
- атрибуты, объявленные через `Annotated[...]`, могут содержать дополнительную
  «мета-справку» (используется в CLI help);
- значения по умолчанию берутся напрямую с атрибута класса.

Результат работы (`class_config_map`) используется CLI для динамического
формирования параметров командной строки и печати справки.
"""

# Стандартная библиотека: динамические импорты, инспекция, обход пакетов.
import importlib
import inspect
import pkgutil
from functools import cached_property
from typing import Annotated, Dict, Set, Type, get_args, get_origin

# Локальные базовые классы, по которым выполняется поиск реализаций.
from marker.builders import BaseBuilder
from marker.converters import BaseConverter
from marker.extractors import BaseExtractor
from marker.processors import BaseProcessor
from marker.providers import BaseProvider
from marker.renderers import BaseRenderer
from marker.services import BaseService


class ConfigCrawler:
    """Сканер классов Marker для построения карты конфигурации.

    Класс:
    - обходит подпакеты, соответствующие базовым классам;
    - ищет все подклассы;
    - собирает аннотированные атрибуты (включая унаследованные);
    - формирует структуру `class_config_map` для использования в CLI.

    Атрибуты:
        base_classes: кортеж базовых классов, наследников которых нужно найти.
        class_config_map: словарь `{тип_компонента -> {имя_класса -> {class_type, config}}}`.
    """

    def __init__(
        self,
        base_classes=(
            BaseBuilder,
            BaseProcessor,
            BaseConverter,
            BaseProvider,
            BaseRenderer,
            BaseService,
            BaseExtractor,
        ),
    ):
        """Инициализирует сканер и запускает первичный обход.

        Аргументы:
            base_classes: Набор базовых классов, по которым выполняется поиск подклассов.

        Возвращает:
            None
        """

        # Сохраняем список базовых классов для последующего обхода.
        self.base_classes = base_classes

        # Здесь будет храниться итоговая карта конфигурации для всех найденных классов.
        self.class_config_map: Dict[str, dict] = {}

        # Сразу запускаем сбор конфигурации, чтобы данные были доступны при импорте.
        self._crawl_config()

    def _crawl_config(self):
        """Выполняет обход всех базовых классов и заполняет `class_config_map`.

        Возвращает:
            None
        """

        # Проходим по всем базовым классам (Builder/Processor/Converter/...)
        for base in self.base_classes:
            # Тип компонента формируем из имени класса: BaseBuilder -> Builder.
            base_class_type = base.__name__.removeprefix("Base")

            # Гарантируем существование словаря для данного типа.
            self.class_config_map.setdefault(base_class_type, {})

            # Находим все подклассы в соответствующем пакете.
            for class_name, class_type in self._find_subclasses(base).items():
                # Технические базовые реализации (Base*) не включаем.
                if class_name.startswith("Base"):
                    continue

                # Создаём запись для класса, если её ещё нет.
                self.class_config_map[base_class_type].setdefault(
                    class_name, {"class_type": class_type, "config": {}}
                )

                # Собираем аннотации атрибутов (включая наследование).
                for attr, attr_type in self._gather_super_annotations(
                    class_type
                ).items():
                    # Значение по умолчанию берём напрямую с класса.
                    default = getattr(class_type, attr)

                    # Метаданные по умолчанию: фиксируем default для справки.
                    metadata = (f"Default is {default}.",)

                    # Если тип Annotated, вытаскиваем metadata и реальный тип.
                    if get_origin(attr_type) is Annotated:
                        if any("Default" in desc for desc in attr_type.__metadata__):
                            metadata = attr_type.__metadata__
                        else:
                            metadata = attr_type.__metadata__ + metadata
                        attr_type = get_args(attr_type)[0]

                    # Преобразуем тип к строковому виду для отображения.
                    formatted_type = self._format_type(attr_type)

                    # Сохраняем описание параметра в карту конфигурации.
                    self.class_config_map[base_class_type][class_name]["config"][
                        attr
                    ] = (attr_type, formatted_type, default, metadata)

    @staticmethod
    def _gather_super_annotations(cls: Type) -> Dict[str, Type]:
        """Собирает все аннотации атрибутов из `cls` и его суперклассов.

        Важно: атрибуты подкласса должны «перекрывать» атрибуты суперкласса с тем же
        именем. Для этого MRO обходится в обратном порядке.

        Аргументы:
            cls: Класс, для которого нужно собрать аннотации.

        Возвращает:
            Словарь `имя_атрибута -> тип`.
        """

        # Идём по MRO от базового класса к производному.
        annotations = {}
        for base in reversed(cls.__mro__):
            # object не содержит пользовательских аннотаций.
            if base is object:
                continue
            if hasattr(base, "__annotations__"):
                for name, annotation in base.__annotations__.items():
                    annotations[name] = annotation
        return annotations

    @cached_property
    def attr_counts(self) -> Dict[str, int]:
        """Подсчитывает, сколько раз каждое имя атрибута встречается среди классов.

        Возвращает:
            Словарь `имя_атрибута -> количество`.
        """

        # Счётчик встречаемости имён параметров.
        counts: Dict[str, int] = {}
        for base_type_dict in self.class_config_map.values():
            for class_map in base_type_dict.values():
                for attr in class_map["config"].keys():
                    counts[attr] = counts.get(attr, 0) + 1
        return counts

    @cached_property
    def attr_set(self) -> Set[str]:
        """Возвращает множество доступных CLI-имён параметров.

        Помимо базового имени параметра (например, `batch_size`) добавляется и
        классо-специфичный вариант (например, `PdfConverter_batch_size`).

        Возвращает:
            Множество строк.
        """

        # Множество имён параметров (без дубликатов).
        attr_set: Set[str] = set()
        for base_type_dict in self.class_config_map.values():
            for class_name, class_map in base_type_dict.items():
                for attr in class_map["config"].keys():
                    # Общий параметр.
                    attr_set.add(attr)
                    # Параметр, адресованный конкретному классу.
                    attr_set.add(f"{class_name}_{attr}")
        return attr_set

    def _find_subclasses(self, base_class):
        """Ищет все подклассы `base_class` в пакете, где объявлен `base_class`.

        Алгоритм:
        - импортируем пакет, где находится базовый класс;
        - обходим все модули внутри пакета;
        - импортируем модуль и собираем все классы;
        - фильтруем по `issubclass`.

        Аргументы:
            base_class: Базовый класс, наследников которого нужно найти.

        Возвращает:
            Словарь `{имя_класса: тип_класса}`.
        """

        # Здесь накапливаем найденные реализации.
        subclasses = {}
        module_name = base_class.__module__
        package = importlib.import_module(module_name)

        # Обходим подпакеты только если это именно пакет (есть __path__).
        if hasattr(package, "__path__"):
            for _, module_name, _ in pkgutil.walk_packages(
                package.__path__, module_name + "."
            ):
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, base_class) and obj is not base_class:
                            subclasses[name] = obj
                except ImportError:
                    # Некоторые модули могут требовать необязательные зависимости.
                    pass
        return subclasses

    def _format_type(self, t: Type) -> str:
        """Преобразует typing-тип в строку, удобную для отображения в справке.

        Аргументы:
            t: Тип (включая typing-типы вроде Optional[int]).

        Возвращает:
            Строковое представление типа.
        """

        # typing-типы (Optional/Union и т. п.) имеют origin.
        if get_origin(t):  # Обрабатываем Optional и другие typing-типы с origin отдельно
            return f"{t}".removeprefix("typing.")
        else:  # Обычные типы вроде int/str
            return t.__name__


# Глобальный экземпляр сканера, чтобы карта конфигурации была доступна при импорте.
crawler = ConfigCrawler()
