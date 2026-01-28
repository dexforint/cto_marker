"""
Провайдер для обработки документов (DOCX, ODT и подобных форматов).

Модуль предоставляет DocumentProvider, который конвертирует документы
в формат PDF для последующей обработки единообразным способом.
Конвертация выполняется через промежуточное преобразование в HTML
с использованием библиотек mammoth и weasyprint.

Автор: Marker Team
"""

import base64
import os
import re
import tempfile
from io import BytesIO

from PIL import Image
from marker.logger import get_logger

from marker.providers.pdf import PdfProvider

# Инициализируем логгер для записи ошибок и отладочной информации
logger = get_logger()

# CSS стили для конвертации HTML в PDF
# Определяют внешний вид документа при конвертации
css = """
@page {
    size: A4;  # Размер страницы A4
    margin: 2cm;  # Отступы по 2 см со всех сторон
}

img {
    max-width: 100%;  # Максимальная ширина изображения 100%
    max-height: 25cm;  # Максимальная высота изображения 25 см
    object-fit: contain;  # Сохранение пропорций изображения
    margin: 12pt auto;  # Центрирование с отступами
}

div, p {
    max-width: 100%;  # Максимальная ширина элементов
    word-break: break-word;  # Перенос длинных слов
    font-size: 10pt;  # Размер шрифта 10 пунктов
}

table {
    width: 100%;  # Ширина таблицы 100%
    border-collapse: collapse;  # Слияние границ ячеек
    break-inside: auto;  # Автоматический перенос таблиц
    font-size: 10pt;  # Размер шрифта таблиц
}

tr {
    break-inside: avoid;  # Избегать переноса строк таблицы
    page-break-inside: avoid;  # Избегать разрыва страницы внутри строки
}

td {
    border: 0.75pt solid #000;  # Границы ячеек: 0.75pt, сплошные, черные
    padding: 6pt;  # Внутренние отступы ячеек
}
"""


class DocumentProvider(PdfProvider):
    """
    Провайдер для обработки документов форматов DOCX, ODT и других.
    
    Наследуется от PdfProvider и обеспечивает конвертацию документов
    в промежуточный формат PDF для последующей обработки.
    
    Процесс обработки:
    1. Создание временного PDF файла
    2. Конвертация исходного документа в HTML (используя mammoth)
    3. Конвертация HTML в PDF (используя weasyprint)
    4. Инициализация родительского PdfProvider с временным PDF
    """
    def __init__(self, filepath: str, config=None):
        """
        Инициализация провайдера документов.
        
        Args:
            filepath (str): Путь к файлу документа
            config: Конфигурация провайдера (опционально)
        """
        # Создаем временный PDF файл для промежуточного хранения
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        # Конвертируем DOCX в PDF
        try:
            self.convert_docx_to_pdf(filepath)
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

    def convert_docx_to_pdf(self, filepath: str):
        """
        Конвертирует DOCX документ в PDF формат.
        
        Процесс включает:
        1. Чтение DOCX файла как бинарных данных
        2. Конвертацию в HTML с помощью mammoth
        3. Обработку встроенных изображений
        4. Создание PDF с CSS стилями и настройками шрифтов
        
        Args:
            filepath (str): Путь к исходному DOCX файлу
        """
        from weasyprint import CSS, HTML
        import mammoth

        # Открываем DOCX файл как бинарный поток
        with open(filepath, "rb") as docx_file:
            # Конвертируем DOCX в HTML с помощью mammoth
            result = mammoth.convert_to_html(docx_file)
            html = result.value

            # Конвертируем HTML в PDF с применением стилей
            HTML(string=self._preprocess_base64_images(html)).write_pdf(
                self.temp_pdf_path, stylesheets=[CSS(string=css), self.get_font_css()]
            )

    @staticmethod
    def _preprocess_base64_images(html_content):
        """
        Обрабатывает встроенные в HTML изображения в формате base64.
        
        Функция декодирует base64 изображения, пересохраняет их в памяти
        и перекодирует обратно для обеспечения совместимости с weasyprint.
        
        Args:
            html_content (str): HTML содержимое с встроенными изображениями
            
        Returns:
            str: HTML содержимое с обработанными изображениями
        """
        # Регулярное выражение для поиска изображений в формате data:...;base64,...
        pattern = r'data:([^;]+);base64,([^"\'>\s]+)'

        def convert_image(match):
            try:
                # Декодируем base64 данные изображения
                img_data = base64.b64decode(match.group(2))

                with BytesIO(img_data) as bio:
                    with Image.open(bio) as img:
                        # Пересохраняем изображение в памяти для обеспечения совместимости
                        output = BytesIO()
                        img.save(output, format=img.format)
                        # Перекодируем изображение в base64
                        new_base64 = base64.b64encode(output.getvalue()).decode()
                        return f"data:{match.group(1)};base64,{new_base64}"

            except Exception as e:
                # Логируем ошибку обработки изображения
                logger.error(f"Failed to process image: {e}")
                return ""  # Возвращаем пустую строку для поврежденных изображений

        # Применяем обработку ко всем найденным изображениям в HTML
        return re.sub(pattern, convert_image, html_content)
