# Модуль для создания и загрузки ML моделей Surya
# Модели используются для layout detection, OCR, распознавания таблиц и определения ошибок OCR

import os

# Включаем fallback для MPS (Apple Silicon GPU)
# Необходимо, так как Transformers использует операцию .isin, которая не поддерживается на MPS
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # Transformers uses .isin for an op, which is not supported on MPS
)

# Импортируем предикторы из библиотеки Surya
# Surya - это набор моделей для анализа и распознавания документов
from surya.foundation import FoundationPredictor
from surya.detection import DetectionPredictor
from surya.layout import LayoutPredictor
from surya.ocr_error import OCRErrorPredictor
from surya.recognition import RecognitionPredictor
from surya.table_rec import TableRecPredictor
from surya.settings import settings as surya_settings


def create_model_dict(
    device=None, dtype=None, attention_implementation: str | None = None
) -> dict:
    """
    Создает и инициализирует все необходимые модели Surya для обработки документов.
    
    Аргументы:
        device: Устройство для загрузки моделей (cuda/cpu/mps). Если None, определяется автоматически.
        dtype: Тип данных для моделей (float32/float16/bfloat16). Если None, определяется автоматически.
        attention_implementation: Реализация attention механизма ("flash_attention_2" или None).
    
    Возвращает:
        Словарь с загруженными моделями:
        - layout_model: Модель для определения структуры страницы (layout detection)
        - recognition_model: Модель для распознавания текста (OCR)
        - table_rec_model: Модель для распознавания структуры таблиц
        - detection_model: Модель для детекции текстовых регионов и строк
        - ocr_error_model: Модель для определения качества OCR
    """
    return {
        # Модель распознавания макета - определяет блоки на странице (текст, таблицы, рисунки и т.д.)
        "layout_model": LayoutPredictor(FoundationPredictor(checkpoint=surya_settings.LAYOUT_MODEL_CHECKPOINT, attention_implementation=attention_implementation, device=device, dtype=dtype)),
        # Модель распознавания текста - выполняет OCR для извлечения текста из изображений
        "recognition_model": RecognitionPredictor(FoundationPredictor(checkpoint=surya_settings.RECOGNITION_MODEL_CHECKPOINT, attention_implementation=attention_implementation, device=device, dtype=dtype)),
        # Модель распознавания таблиц - определяет структуру ячеек в таблицах
        "table_rec_model": TableRecPredictor(device=device, dtype=dtype),
        # Модель детекции - находит текстовые регионы и строки на странице
        "detection_model": DetectionPredictor(device=device, dtype=dtype),
        # Модель определения ошибок OCR - оценивает качество распознанного текста
        "ocr_error_model": OCRErrorPredictor(device=device, dtype=dtype),
    }
