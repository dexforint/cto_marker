"""
Провайдер для обработки HTML файлов.

Модуль предоставляет HTMLProvider, который конвертирует HTML файлы
в формат PDF для последующей обработки единообразным способом.
Использует библиотеку weasyprint для конвертации.

Автор: Marker Team
"""

import os
import tempfile

from marker.providers.pdf import PdfProvider


class HTMLProvider(PdfProvider):
    """
    Провайдер для обработки HTML файлов.
    
    Наследуется от PdfProvider и обеспечивает конвертацию HTML файлов
    в промежуточный формат PDF для последующей обработки.
    
    Процесс обработки:
    1. Создание временного PDF файла
    2. Конвертация HTML в PDF с помощью weasyprint
    3. Инициализация родительского PdfProvider с временным PDF
    """
    def __init__(self, filepath: str, config=None):
        """
        Инициализация провайдера HTML.
        
        Args:
            filepath (str): Путь к HTML файлу
            config: Конфигурация провайдера (опционально)
        """
        # Создаем временный PDF файл для промежуточного хранения
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        # Конвертируем HTML в PDF
        try:
            self.convert_html_to_pdf(filepath)
        except Exception as e:
            # В случае ошибки конвертации удаляем временный файл и выбрасываем исключение
            raise RuntimeError(f"Failed to convert {filepath} to PDF: {e}")

        # Инициализируем родительский PdfProvider с временным PDF файлом
        super().__init__(self.temp_pdf_path, config)

    def __del__(self):
        """
        Деструктор для очистки временных файлов.
        
        Удаляет временный PDF файл при уничтожении объекта.
        """
        if os.path.exists(self.temp_pdf_path):
            os.remove(self.temp_pdf_path)

    def convert_html_to_pdf(self, filepath: str):
        """
        Конвертирует HTML файл в PDF формат.
        
        Использует weasyprint для рендеринга HTML с применением CSS стилей шрифтов.
        
        Args:
            filepath (str): Путь к исходному HTML файлу
        """
        from weasyprint import HTML

        # Получаем CSS стили для корректного отображения шрифтов
        font_css = self.get_font_css()
        # Конвертируем HTML в PDF с применением стилей шрифтов
        HTML(filename=filepath, encoding="utf-8").write_pdf(
            self.temp_pdf_path, stylesheets=[font_css]
        )
