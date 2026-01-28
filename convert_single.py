# Импортируем CLI функцию для конвертации одного документа
from marker.scripts.convert_single import convert_single_cli

# Точка входа для скрипта конвертации одного файла
# Этот файл является wrapper для marker.scripts.convert_single
if __name__ == "__main__":
    # Запускаем CLI интерфейс для конвертации одного файла
    convert_single_cli()
