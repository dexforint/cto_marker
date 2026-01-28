"""marker.config.printer

Модуль вывода/«печати» конфигурации для CLI.

Здесь реализована интеграция с Click таким образом, чтобы:
- при вызове `marker config --help` пользователь видел полный список доступных
  Builder/Processor/Converter/Provider/Renderer/Service/Extractor классов;
- для каждого класса выводились его конфигурируемые параметры (аннотации типов);
- в саму Click-команду динамически добавлялись опции (как общие, так и
  классо-специфичные), на основе карты, собранной `ConfigCrawler`.

Ключевой момент: мы не «жёстко» описываем опции в коде, а строим их из метаданных
классов, что уменьшает дублирование и облегчает расширение системы.
"""

# Стандартная библиотека: typing для Optional.
from typing import Optional

# Сторонняя библиотека: Click — CLI фреймворк.
import click

# Локальный импорт: глобальный сканер конфигурации.
from marker.config.crawler import crawler


class CustomClickPrinter(click.Command):
    """Кастомная команда Click, которая динамически добавляет параметры конфигурации.

    Мы переопределяем `parse_args`, чтобы:
    1) перед парсингом аргументов добавить в команду `ctx.command.params` новые опции;
    2) при `config --help` красиво распечатать перечень классов и их параметров.
    """

    def parse_args(self, ctx, args):
        """Переопределяет парсинг аргументов Click и «впрыскивает» динамические опции.

        Аргументы:
            ctx: Контекст Click (содержит команду, параметры и т. п.).
            args: Список аргументов командной строки.

        Возвращает:
            None

        Поведение:
            - если пользователь запросил `config --help`, мы выводим расширенную справку
              и завершаем работу (через `ctx.exit()`);
            - иначе добавляем опции в команду и передаём управление стандартному Click.
        """

        # Определяем, надо ли выводить расширенную справку по конфигурации.
        display_help = "config" in args and "--help" in args

        # При запросе help печатаем вводное сообщение.
        if display_help:
            click.echo(
                "Here is a list of all the Builders, Processors, Converters, Providers and Renderers in Marker along with their attributes:"
            )

        # Словарь «общих» атрибутов: один и тот же параметр может встречаться у многих классов.
        shared_attrs = {}

        # Первый проход:
        # - собираем все атрибуты;
        # - группируем одинаковые по имени, чтобы затем добавить их как общие CLI-опции.
        for base_type, base_type_dict in crawler.class_config_map.items():
            for class_name, class_map in base_type_dict.items():
                for attr, (attr_type, formatted_type, default, metadata) in class_map[
                    "config"
                ].items():
                    # Если атрибут встречается впервые — создаём запись.
                    if attr not in shared_attrs:
                        shared_attrs[attr] = {
                            "classes": [],
                            "type": attr_type,
                            "is_flag": attr_type in [bool, Optional[bool]]
                            and not default,
                            "metadata": metadata,
                            "default": default,
                        }

                    # Запоминаем, в каких классах встречается параметр.
                    shared_attrs[attr]["classes"].append(class_name)

        # Список типов, которые можно безопасно задавать через командную строку.
        # (сложные структуры и пользовательские классы сюда не включаем).
        attr_types = [
            str,
            int,
            float,
            bool,
            Optional[int],
            Optional[float],
            Optional[str],
        ]

        # Добавляем общие атрибуты как глобальные CLI-опции (например, --batch_size).
        for attr, info in shared_attrs.items():
            if info["type"] in attr_types:
                ctx.command.params.append(
                    click.Option(
                        ["--" + attr],
                        type=info["type"],
                        help=" ".join(info["metadata"])
                        + f" (Applies to: {', '.join(info['classes'])})",
                        # Важно: default=None, иначе Click подмешает дефолты обратно в конфиг.
                        default=None,
                        is_flag=info["is_flag"],
                        flag_value=True if info["is_flag"] else None,
                    )
                )

        # Второй проход:
        # - формируем справку по конкретным классам;
        # - добавляем классо-специфичные опции вида --<ClassName>_<attr>.
        for base_type, base_type_dict in crawler.class_config_map.items():
            if display_help:
                click.echo(f"{base_type}s:")

            for class_name, class_map in base_type_dict.items():
                # Заголовок по классу, если у него есть конфиг-параметры.
                if display_help and class_map["config"]:
                    click.echo(
                        f"\n  {class_name}: {class_map['class_type'].__doc__ or ''}"
                    )
                    click.echo(" " * 4 + "Attributes:")

                # Проходим по всем параметрам класса.
                for attr, (attr_type, formatted_type, default, metadata) in class_map[
                    "config"
                ].items():
                    # Имя классо-специфичного параметра.
                    class_name_attr = class_name + "_" + attr

                    # В режиме help печатаем тип и метаданные.
                    if display_help:
                        click.echo(" " * 8 + f"{attr} ({formatted_type}):")
                        click.echo(
                            "\n".join([f"{' ' * 12}" + desc for desc in metadata])
                        )

                    # Добавляем опцию в CLI только если тип допустим.
                    if attr_type in attr_types:
                        is_flag = attr_type in [bool, Optional[bool]] and not default

                        # Добавляем классо-специфичную опцию.
                        ctx.command.params.append(
                            click.Option(
                                ["--" + class_name_attr, class_name_attr],
                                type=attr_type,
                                help=" ".join(metadata),
                                is_flag=is_flag,
                                # Важно: default=None (см. комментарий выше).
                                default=None,
                            )
                        )

        # Если мы печатали help, то дальнейший парсинг аргументов не нужен.
        if display_help:
            ctx.exit()

        # Передаём управление стандартной реализации Click.
        super().parse_args(ctx, args)
