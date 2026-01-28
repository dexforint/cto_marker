"""
Провайдер для обработки электронных книг в формате EPUB.

Модуль предоставляет EpubProvider, который конвертирует EPUB книги
в формат PDF для последующей обработки единообразным способом.
Процесс включает извлечение HTML содержимого, изображений и стилей
из EPUB архива с последующей конвертацией в PDF через weasyprint.

Автор: Marker Team
"""

import base64
import os
import tempfile

from bs4 import BeautifulSoup

from marker.providers.pdf import PdfProvider

# CSS стили для конвертации HTML в PDF
# Определяют внешний вид книги при конвертации из EPUB
css = '''
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
'''


class EpubProvider(PdfProvider):
    """
    Провайдер для обработки электронных книг в формате EPUB.
    
    Наследуется от PdfProvider и обеспечивает конвертацию EPUB книг
    в промежуточный формат PDF для последующей обработки.
    
    Процесс обработки:
    1. Создание временного PDF файла
    2. Извлечение и обработка содержимого из EPUB архива
    3. Конвертация HTML содержимого в PDF
    4. Инициализация родительского PdfProvider с временным PDF
    """
    def __init__(self, filepath: str, config=None):
        """
        Инициализация провайдера EPUB.
        
        Args:
            filepath (str): Путь к EPUB файлу
            config: Конфигурация провайдера (опционально)
        """
        # Создаем временный PDF файл для промежуточного хранения
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=f".pdf")
        self.temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        # Конвертируем EPUB в PDF
        try:
            self.convert_epub_to_pdf(filepath)
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

    def convert_epub_to_pdf(self, filepath):
        """
        Конвертирует EPUB книгу в PDF формат.
        
        Процесс включает:
        1. Чтение EPUB файла с помощью ebooklib
        2. Извлечение изображений и кодирование их в base64
        3. Извлечение HTML документа и стилей
        4. Замену ссылок на изображения inline base64 данными
        5. Конвертацию HTML в PDF с применением стилей
        
        Args:
            filepath (str): Путь к исходному EPUB файлу
        """
        from weasyprint import CSS, HTML
        from ebooklib import epub
        import ebooklib

        # Читаем EPUB файл
        ebook = epub.read_epub(filepath)

        # Инициализируем списки для стилей и HTML содержимого
        styles = []
        html_content = ""
        # Словарь для хранения изображений в формате base64
        img_tags = {}

        # Первый проход: извлекаем изображения и стили
        for item in ebook.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                # Кодируем изображение в base64 и сохраняем с привязкой к имени файла
                img_data = base64.b64encode(item.get_content()).decode("utf-8")
                img_tags[item.file_name] = f'data:{item.media_type};base64,{img_data}'
            elif item.get_type() == ebooklib.ITEM_STYLE:
                # Сохраняем стили CSS из EPUB
                styles.append(item.get_content().decode('utf-8'))

        # Второй проход: извлекаем HTML документы
        for item in ebook.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Декодируем и объединяем все HTML документы в одно содержимое
                html_content += item.get_content().decode("utf-8")

        # Парсим HTML содержимое с помощью BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Обрабатываем теги img и заменяем ссылки на изображения
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                # Нормализуем путь к изображению (удаляем '../')
                normalized_src = src.replace('../', '')
                if normalized_src in img_tags:
                    # Заменяем ссылку на изображение inline base64 данными
                    img['src'] = img_tags[normalized_src]

        # Обрабатываем теги image (для SVG и других форматов)
        for image in soup.find_all('image'):
            src = image.get('xlink:href')
            if src:
                # Нормализуем путь к изображению
                normalized_src = src.replace('../', '')
                if normalized_src in img_tags:
                    # Заменяем ссылку на изображение inline base64 данными
                    image['xlink:href'] = img_tags[normalized_src]

        # Преобразуем обратно в строку HTML
        html_content = str(soup)
        # Объединяем основные CSS стили (стили из EPUB игнорируются)
        full_style = ''.join([css])  # + styles)

        # Конвертируем HTML в PDF с применением стилей и настроек шрифтов
        HTML(string=html_content, base_url=filepath).write_pdf(
            self.temp_pdf_path,
            stylesheets=[CSS(string=full_style), self.get_font_css()]
        )
