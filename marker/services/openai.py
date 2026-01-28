"""
Модуль интеграции с OpenAI API.

Предоставляет класс для работы с OpenAI моделями (GPT-3.5, GPT-4, GPT-4o и т.д.)
для улучшения результатов конвертации документов. Поддерживает мультимодальные запросы
с изображениями и структурированные JSON ответы.

Основные возможности:
- Обработка мультимодальных запросов (текст + изображения)
- Автоматические повторные попытки при rate limit
- Поддержка структурированных JSON ответов через response_format
- Совместимость с OpenAI-like API (настраиваемый base_url)
"""

import json
import time
from typing import Annotated, List

import openai
import PIL
from marker.logger import get_logger
from openai import APITimeoutError, RateLimitError
from PIL import Image
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

logger = get_logger()


class OpenAIService(BaseService):
    """
    Сервис для работы с OpenAI API и совместимыми API.
    
    Поддерживает работу с OpenAI моделями (GPT-4o, GPT-4, GPT-3.5) и другими
    совместимыми API через настройку base_url. Использует beta.chat.completions.parse
    для получения структурированных JSON ответов.
    
    Атрибуты:
        openai_base_url: Базовый URL для API (без trailing slash). Можно использовать
                         для подключения к OpenAI-совместимым API
        openai_model: Имя модели для использования (например, "gpt-4o-mini")
        openai_api_key: API ключ для доступа к сервису
        openai_image_format: Формат изображений ("webp" или "png"). Используйте "png"
                             для лучшей совместимости с некоторыми API
    """
    openai_base_url: Annotated[
        str, "The base url to use for OpenAI-like models.  No trailing slash."
    ] = "https://api.openai.com/v1"
    openai_model: Annotated[str, "The model name to use for OpenAI-like model."] = (
        "gpt-4o-mini"
    )
    openai_api_key: Annotated[
        str, "The API key to use for the OpenAI-like service."
    ] = None
    openai_image_format: Annotated[
        str,
        "The image format to use for the OpenAI-like service. Use 'png' for better compatability",
    ] = "webp"

    def process_images(self, images: List[Image.Image]) -> List[dict]:
        """
        Генерирует base64-кодированные сообщения для отправки в OpenAI-совместимую
        мультимодальную модель.

        Преобразует PIL изображения в формат, который принимает OpenAI API -
        словари с типом "image_url" и data URL в base64.

        Аргументы:
            images: Изображение или список PIL изображений для включения в запрос

        Возвращает:
            Список OpenAI-совместимых мультимодальных сообщений с base64-кодированными изображениями
        """
        # Нормализуем входные данные в список
        if isinstance(images, Image.Image):
            images = [images]

        # Используем настроенный формат изображения
        img_fmt = self.openai_image_format
        # Формируем список сообщений с изображениями в формате data URL
        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/{};base64,{}".format(
                        img_fmt, self.img_to_base64(img, format=img_fmt)
                    ),
                },
            }
            for img in images
        ]

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
        Выполняет запрос к OpenAI API для обработки изображения и текста.
        
        Отправляет мультимодальный запрос с автоматическими повторными попытками
        при rate limit ошибках. Использует beta.chat.completions.parse для
        получения структурированного JSON ответа.
        
        Аргументы:
            prompt: Текстовый промпт с инструкциями
            image: Изображение или список изображений для анализа
            block: Блок для обновления метаданных использования токенов
            response_schema: Pydantic схема для валидации ответа
            max_retries: Переопределение количества повторных попыток
            timeout: Переопределение таймаута в секундах
            
        Возвращает:
            dict: Ответ от OpenAI в виде словаря, или {} при ошибке
        """
        # Используем значения по умолчанию если не переопределены
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        # Получаем клиент OpenAI
        client = self.get_client()
        # Форматируем изображения в формат OpenAI
        image_data = self.format_image_for_llm(image)

        # Формируем сообщения в формате OpenAI chat API
        messages = [
            {
                "role": "user",
                "content": [
                    *image_data,  # Сначала изображения
                    {"type": "text", "text": prompt},  # Затем текстовый промпт
                ],
            }
        ]

        # Общее количество попыток
        total_tries = max_retries + 1
        for tries in range(1, total_tries + 1):
            try:
                # Используем beta.chat.completions.parse для структурированного ответа
                response = client.beta.chat.completions.parse(
                    extra_headers={
                        "X-Title": "Marker",  # Идентифицируем приложение
                        "HTTP-Referer": "https://github.com/datalab-to/marker",
                    },
                    model=self.openai_model,
                    messages=messages,
                    timeout=timeout,
                    response_format=response_schema,  # Схема для структурированного JSON
                )
                # Извлекаем содержимое ответа
                response_text = response.choices[0].message.content
                # Получаем информацию об использованных токенах
                total_tokens = response.usage.total_tokens
                # Обновляем метаданные блока если он передан
                if block:
                    block.update_metadata(
                        llm_tokens_used=total_tokens, llm_request_count=1
                    )
                # Парсим и возвращаем JSON ответ
                return json.loads(response_text)
            except (APITimeoutError, RateLimitError) as e:
                # Обрабатываем ошибки таймаута и rate limit
                if tries == total_tries:
                    # Последняя попытка не удалась - сдаемся
                    logger.error(
                        f"Rate limit error: {e}. Max retries reached. Giving up. (Attempt {tries}/{total_tries})",
                    )
                    break
                else:
                    # Ждем экспоненциально увеличивающееся время и повторяем
                    wait_time = tries * self.retry_wait_time
                    logger.warning(
                        f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{total_tries})",
                    )
                    time.sleep(wait_time)
            except Exception as e:
                # Любая другая ошибка - логируем и прекращаем
                logger.error(f"OpenAI inference failed: {e}")
                break

        # Если все попытки не удались, возвращаем пустой словарь
        return {}

    def get_client(self) -> openai.OpenAI:
        """
        Создает клиент OpenAI API.
        
        Возвращает:
            openai.OpenAI: Настроенный клиент с API ключом и base URL
        """
        return openai.OpenAI(api_key=self.openai_api_key, base_url=self.openai_base_url)
