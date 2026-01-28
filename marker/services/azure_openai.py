"""
Модуль интеграции с Azure OpenAI Service.

Предоставляет класс для работы с OpenAI моделями (GPT-4, GPT-4o и др.)
через Azure OpenAI Service для улучшения результатов конвертации документов.
Azure OpenAI предоставляет enterprise-уровень доступа к моделям OpenAI с
дополнительными возможностями безопасности и соответствия требованиям.

Основные возможности:
- Доступ к OpenAI моделям через Azure
- Обработка мультимодальных запросов (текст + изображения)
- Автоматические повторные попытки при rate limit
- Поддержка структурированных JSON ответов
- Enterprise безопасность и соответствие требованиям Azure
"""

import json
import time
from typing import Annotated, List

import PIL
from marker.logger import get_logger
from openai import AzureOpenAI, APITimeoutError, RateLimitError
from PIL import Image
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

logger = get_logger()


class AzureOpenAIService(BaseService):
    """
    Сервис для работы с Azure OpenAI Service.
    
    Использует Azure OpenAI для доступа к моделям GPT-4/GPT-4o.
    Требует настройки Azure ресурса OpenAI и deployment модели.
    Подходит для enterprise использования с требованиями к безопасности и compliance.
    
    Атрибуты:
        azure_endpoint: URL эндпоинта Azure OpenAI (без trailing slash)
        azure_api_key: API ключ для доступа к Azure OpenAI Service
        azure_api_version: Версия Azure OpenAI API для использования
        deployment_name: Имя развертывания (deployment) модели в Azure
    """
    azure_endpoint: Annotated[
        str, "The Azure OpenAI endpoint URL. No trailing slash."
    ] = None
    azure_api_key: Annotated[
        str, "The API key to use for the Azure OpenAI service."
    ] = None
    azure_api_version: Annotated[str, "The Azure OpenAI API version to use."] = None
    deployment_name: Annotated[
        str, "The deployment name for the Azure OpenAI model."
    ] = None

    def process_images(self, images: List[PIL.Image.Image]) -> list:
        """
        Обрабатывает список изображений в формат для Azure OpenAI API.
        
        Конвертирует PIL изображения в формат, который принимает Azure OpenAI API -
        словари с типом "image_url" и data URL в base64 (формат WEBP).
        
        Аргументы:
            images: Список PIL изображений
            
        Возвращает:
            Список словарей с изображениями в формате Azure OpenAI API
        """
        # Нормализуем входные данные в список
        if isinstance(images, Image.Image):
            images = [images]

        # Формируем список сообщений с изображениями в формате data URL (WEBP)
        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/webp;base64,{}".format(self.img_to_base64(img)),
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
        Выполняет запрос к Azure OpenAI для обработки изображения и текста.
        
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
            dict: Ответ от Azure OpenAI в виде словаря, или {} при ошибке
        """
        # Используем значения по умолчанию если не переопределены
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        # Получаем клиент Azure OpenAI
        client = self.get_client()
        # Форматируем изображения в формат Azure OpenAI
        image_data = self.format_image_for_llm(image)

        # Формируем сообщения в формате Azure OpenAI chat API
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
                    model=self.deployment_name,  # В Azure используется deployment name
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
                        f"Rate limit error: {e}. Max retries reached. Giving up. (Attempt {tries}/{total_tries})"
                    )
                    break
                else:
                    # Ждем экспоненциально увеличивающееся время и повторяем
                    wait_time = tries * self.retry_wait_time
                    logger.warning(
                        f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{total_tries})"
                    )
                    time.sleep(wait_time)
            except Exception as e:
                # Любая другая ошибка - логируем и прекращаем
                logger.error(f"Azure OpenAI inference failed: {e}")
                break

        # Если все попытки не удались, возвращаем пустой словарь
        return {}

    def get_client(self) -> AzureOpenAI:
        """
        Создает клиент Azure OpenAI API.
        
        Возвращает:
            AzureOpenAI: Настроенный клиент с параметрами Azure
        """
        return AzureOpenAI(
            api_version=self.azure_api_version,  # Версия API
            azure_endpoint=self.azure_endpoint,  # URL эндпоинта Azure
            api_key=self.azure_api_key,  # API ключ
        )
