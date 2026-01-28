"""
Модуль рендеринга результатов extraction режима.

Предоставляет рендерер для специального режима extraction, который извлекает
структурированные данные из документа (не только текст). Возвращает анализ,
структурированный JSON и оригинальный markdown.

Основные возможности:
- Рендеринг результатов DocumentExtractionSchema
- Сохранение анализа документа
- Включение структурированного JSON представления
- Сохранение оригинального markdown для референса
"""

from pydantic import BaseModel

from marker.extractors.document import DocumentExtractionSchema
from marker.renderers import BaseRenderer


class ExtractionOutput(BaseModel):
    """
    Модель выходных данных extraction рендеринга.
    
    Атрибуты:
        analysis: Текстовый анализ документа
        document_json: Структурированное JSON представление документа
        original_markdown: Оригинальный markdown текст для сравнения
    """
    analysis: str
    document_json: str
    original_markdown: str


class ExtractionRenderer(BaseRenderer):
    """
    Рендерер для extraction режима.
    
    Преобразует результаты DocumentExtractionSchema в удобный формат
    с анализом, структурированными данными и оригинальным markdown.
    """
    def __call__(
        self, output: DocumentExtractionSchema, markdown: str
    ) -> ExtractionOutput:
        """
        Рендерит результаты extraction в ExtractionOutput.
        
        Аргументы:
            output: Схема с результатами извлечения данных
            markdown: Оригинальный markdown текст документа
            
        Возвращает:
            ExtractionOutput: Объект с анализом, JSON и markdown
        """
        # В будущем здесь можно добавить более сложную обработку
        return ExtractionOutput(
            analysis=output.analysis,
            document_json=output.document_json,
            original_markdown=markdown,
        )
