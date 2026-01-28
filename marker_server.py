# Импортируем CLI функцию для запуска FastAPI сервера
from marker.scripts.server import server_cli

# Точка входа для FastAPI API сервера
# Предоставляет REST API для конвертации документов
if __name__ == "__main__":
    # Запускаем FastAPI сервер для marker
    server_cli()
