# Модуль глобальных настроек приложения
# Использует Pydantic для валидации и управления конфигурацией
# Настройки могут быть переопределены через environment переменные или файл local.env

from typing import Optional

from dotenv import find_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings
import torch
import os


class Settings(BaseSettings):
    """
    Класс глобальных настроек для Marker.
    Все настройки могут быть переопределены через environment переменные.
    """
    
    # ===== Пути к директориям и файлам =====
    # Базовая директория проекта (родительская от marker/)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Директория для сохранения результатов конвертации
    OUTPUT_DIR: str = os.path.join(BASE_DIR, "conversion_results")
    # Директория со шрифтами
    FONT_DIR: str = os.path.join(BASE_DIR, "static", "fonts")
    # Директория для сохранения debug данных (при --debug флаге)
    DEBUG_DATA_FOLDER: str = os.path.join(BASE_DIR, "debug_data")
    # URL для загрузки артефактов моделей
    ARTIFACT_URL: str = "https://models.datalab.to/artifacts"
    # Имя файла шрифта по умолчанию
    FONT_NAME: str = "GoNotoCurrent-Regular.ttf"
    # Полный путь к файлу шрифта
    FONT_PATH: str = os.path.join(FONT_DIR, FONT_NAME)
    # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    LOGLEVEL: str = "INFO"

    # ===== Общие настройки =====
    # Кодировка для выходных файлов
    OUTPUT_ENCODING: str = "utf-8"
    # Формат для сохранения извлеченных изображений
    OUTPUT_IMAGE_FORMAT: str = "JPEG"

    # ===== LLM настройки =====
    # API ключ для Google Gemini (используется при --use_llm)
    GOOGLE_API_KEY: Optional[str] = ""

    # ===== Настройки моделей и вычислительного устройства =====
    # Устройство для PyTorch (cuda/cpu/mps). None = автоматическое определение
    # Примечание: MPS не работает для детекции текста и будет использовать CPU
    TORCH_DEVICE: Optional[str] = (
        None  # Note: MPS device does not work for text detection, and will default to CPU
    )

    @computed_field
    @property
    def TORCH_DEVICE_MODEL(self) -> str:
        """
        Вычисляемое свойство для определения устройства PyTorch.
        Автоматически выбирает доступное устройство в порядке: CUDA > MPS > CPU.
        
        Возвращает:
            Строка с именем устройства: "cuda", "mps" или "cpu"
        """
        # Если устройство явно задано, используем его
        if self.TORCH_DEVICE is not None:
            return self.TORCH_DEVICE

        # Проверяем доступность CUDA (NVIDIA GPU)
        if torch.cuda.is_available():
            return "cuda"

        # Проверяем доступность MPS (Apple Silicon GPU)
        if torch.backends.mps.is_available():
            return "mps"

        # По умолчанию используем CPU
        return "cpu"

    @computed_field
    @property
    def MODEL_DTYPE(self) -> torch.dtype:
        """
        Вычисляемое свойство для определения типа данных моделей.
        Использует bfloat16 для CUDA (более эффективно), float32 для остальных устройств.
        
        Возвращает:
            torch.dtype: Тип данных для моделей
        """
        # Для CUDA используем bfloat16 (экономия памяти и ускорение)
        if self.TORCH_DEVICE_MODEL == "cuda":
            return torch.bfloat16
        # Для CPU и MPS используем float32 (лучшая совместимость)
        else:
            return torch.float32

    class Config:
        # Загрузка настроек из файла local.env (если существует)
        env_file = find_dotenv("local.env")
        # Игнорировать дополнительные поля, которые не определены в классе
        extra = "ignore"


# Глобальный экземпляр настроек, используется во всем приложении
settings = Settings()
