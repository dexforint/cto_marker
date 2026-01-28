"""
Модуль интеграции с локальным Ollama сервером.

Предоставляет класс для работы с локально размещенными моделями через Ollama
для улучшения результатов конвертации документов. Позволяет использовать
мультимодальные модели (например, llama3.2-vision) без облачных API.

Основные возможности:
- Работа с локальными моделями через Ollama API
- Поддержка мультимодальных запросов (текст + изображения)
- Структурированные JSON ответы с валидацией по схеме
- Низкие латентность и стоимость по сравнению с облачными API
"""

import json
from typing import Annotated, List

import PIL
import requests
from marker.logger import get_logger
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

logger = get_logger()


class OllamaService(BaseService):
    """
    Сервис для работы с локальным Ollama сервером.
    
    Позволяет использовать локально развернутые модели через Ollama для обработки
    документов. Отлично подходит для конфиденциальных данных или работы без интернета.
    
    Атрибуты:
        ollama_base_url: Базовый URL Ollama сервера (без trailing slash)
        ollama_model: Имя модели Ollama для использования (например, "llama3.2-vision")
    """
    ollama_base_url: Annotated[
        str, "The base url to use for ollama.  No trailing slash."
    ] = "http://localhost:11434"
    ollama_model: Annotated[str, "The model name to use for ollama."] = (
        "llama3.2-vision"
    )

    def process_images(self, images):
        """
        Обрабатывает список изображений в формат для Ollama API.
        
        Конвертирует PIL изображения в base64 строки, которые принимает Ollama.
        
        Аргументы:
            images: Список PIL изображений
            
        Возвращает:
            Список base64-кодированных строк изображений
        """
        # Конвертируем каждое изображение в base64
        image_bytes = [self.img_to_base64(img) for img in images]
        return image_bytes

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image] | None,
        block: Block | None,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        """
        Выполняет запрос к Ollama для обработки изображения и текста.
        
        Отправляет мультимодальный запрос к локальному Ollama серверу с
        JSON схемой для структурированного ответа.
        
        Аргументы:
            prompt: Текстовый промпт с инструкциями
            image: Изображение или список изображений для анализа
            block: Блок для обновления метаданных использования токенов
            response_schema: Pydantic схема для валидации ответа
            max_retries: Переопределение количества повторных попыток (не используется)
            timeout: Переопределение таймаута в секундах (не используется)
            
        Возвращает:
            dict: Ответ от Ollama в виде словаря, или {} при ошибке
        """
        # Формируем URL эндпоинта для генерации
        url = f"{self.ollama_base_url}/api/generate"
        headers = {"Content-Type": "application/json"}

        # Получаем JSON схему из Pydantic модели
        schema = response_schema.model_json_schema()
        # Формируем format schema для Ollama (требует только свойства и required поля)
        format_schema = {
            "type": "object",
            "properties": schema["properties"],
            "required": schema["required"],
        }

        # Форматируем изображения в base64
        image_bytes = self.format_image_for_llm(image)

        # Формируем payload для запроса
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,  # Отключаем стриминг для получения полного ответа
            "format": format_schema,  # Схема для структурированного JSON ответа
            "images": image_bytes,
        }

        try:
            # Отправляем POST запрос к Ollama
            response = requests.post(url, json=payload, headers=headers)
            # Проверяем что запрос успешен
            response.raise_for_status()
            # Парсим JSON ответ
            response_data = response.json()

            # Вычисляем общее количество использованных токенов
            total_tokens = (
                response_data["prompt_eval_count"] + response_data["eval_count"]
            )

            # Обновляем метаданные блока если он передан
            if block:
                block.update_metadata(llm_request_count=1, llm_tokens_used=total_tokens)

            # Извлекаем текст ответа и парсим JSON
            data = response_data["response"]
            return json.loads(data)
        except Exception as e:
            # Логируем ошибку и возвращаем пустой словарь
            logger.warning(f"Ollama inference failed: {e}")

        # Если запрос не удался, возвращаем пустой словарь
        return {}
