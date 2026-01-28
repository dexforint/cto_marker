# Импортируем CLI функцию для multi-GPU конвертации документов
from marker.scripts.chunk_convert import chunk_convert_cli

# Точка входа для скрипта multi-GPU batch конвертации
# Этот файл является wrapper для marker.scripts.chunk_convert
# Используется для распределения задач конвертации между несколькими GPU
if __name__ == "__main__":
    # Запускаем CLI интерфейс для multi-GPU конвертации
    chunk_convert_cli()