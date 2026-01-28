"""
Вспомогательный скрипт для запуска Streamlit приложений.

Модуль содержит утилитарные функции для запуска различных Streamlit
приложений с предварительно настроенными параметрами командной строки.
Используется для упрощения запуска веб-интерфейсов Marker.

Автор: Marker Team
"""

import subprocess
import os
import sys


def streamlit_app_cli(app_name: str = "streamlit_app.py"):
    """
    Запускает Streamlit приложение с предустановленными настройками.
    
    Функция формирует команду для запуска Streamlit приложения с
    оптимизированными параметрами для работы в серверной среде.
    
    Args:
        app_name (str): Имя файла приложения Streamlit (по умолчанию "streamlit_app.py")
    """
    # Получаем аргументы командной строки (исключая имя скрипта)
    argv = sys.argv[1:]
    
    # Определяем полный путь к директории текущего скрипта
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    # Формируем полный путь к приложению Streamlit
    app_path = os.path.join(cur_dir, app_name)
    
    # Формируем команду запуска Streamlit с настройками
    cmd = [
        "streamlit",      # Команда запуска Streamlit
        "run",           # Подкоманда для запуска приложения
        app_path,        # Путь к файлу приложения
        "--server.fileWatcherType", "none",  # Отключаем отслеживание файлов
        "--server.headless", "true",         # Запуск в безголовом режиме
    ]
    
    # Добавляем дополнительные аргументы, если они есть
    if argv:
        cmd += ["--"] + argv
    
    # Запускаем Streamlit с установкой переменной окружения
    subprocess.run(cmd, env={**os.environ, "IN_STREAMLIT": "true"})


def extraction_app_cli():
    """
    Запускает специальное Streamlit приложение для извлечения данных.
    
    Упрощенная функция для запуска extraction_app.py с теми же настройками.
    """
    streamlit_app_cli("extraction_app.py")
