# Импортируем CLI функцию для запуска Streamlit приложения
from marker.scripts.run_streamlit_app import streamlit_app_cli

# Точка входа для интерактивного веб-приложения на Streamlit
# Позволяет конвертировать документы через веб-интерфейс
if __name__ == "__main__":
    # Запускаем Streamlit приложение для marker
    streamlit_app_cli()