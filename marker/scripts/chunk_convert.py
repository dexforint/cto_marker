"""
CLI скрипт для multi-GPU batch конвертации документов.

Упрощенная обертка для запуска shell-скрипта chunk_convert.sh, который
выполняет пакетную конвертацию документов с использованием множественных
GPU для ускорения обработки больших объемов файлов.

Автор: Marker Team
"""

import argparse
import os
import subprocess
import pkg_resources


def chunk_convert_cli():
    """
    Функция для запуска batch конвертации документов по частям.
    
    Парсит аргументы командной строки и запускает shell-скрипт
    для обработки папки с PDF файлами и сохранения результатов
    в указанную папку назначения.
    """
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(description="Конвертирует папку с PDF в папку с markdown файлами по частям.")
    parser.add_argument("in_folder", help="Входная папка с PDF файлами.")
    parser.add_argument("out_folder", help="Выходная папка")
    args = parser.parse_args()

    # Определяем текущую директорию и путь к shell-скрипту
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(cur_dir, "chunk_convert.sh")

    # Формируем команду для выполнения
    cmd = f"{script_path} {args.in_folder} {args.out_folder}"

    # Выполняем shell-скрипт
    subprocess.run(cmd, shell=True, check=True)