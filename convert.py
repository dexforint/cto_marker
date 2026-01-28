# Импортируем CLI функцию для массовой конвертации документов
from marker.scripts.convert import convert_cli

# Точка входа для скрипта batch конвертации
# Этот файл является wrapper для marker.scripts.convert
if __name__ == "__main__":
    # Запускаем CLI интерфейс для конвертации нескольких файлов
    convert_cli()
