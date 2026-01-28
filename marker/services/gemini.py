"""
Модуль интеграции с Google Gemini API.

Предоставляет классы для работы с Google Gemini моделями (включая Gemini 2.0 Flash)
для улучшения результатов конвертации документов. Поддерживает как прямое использование
Gemini API, так и через Google Vertex AI.

Основные возможности:
- Обработка мультимодальных запросов (текст + изображения)
- Автоматические повторные попытки при ошибках rate limit
- Поддержка thinking budget для моделей с расширенными возможностями
- Гибкая настройка температуры генерации и максимального количества токенов
"""

import json
import time
import traceback
from io import BytesIO
from typing import List, Annotated

import PIL
from google import genai
from google.genai import types
from google.genai.errors import APIError
from marker.logger import get_logger
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

logger = get_logger()


class BaseGeminiService(BaseService):
    """
    Базовый класс для всех Gemini-based сервисов.
    
    Предоставляет общую функциональность для работы с Google Gemini моделями.
    Используется как базовый класс для GoogleGeminiService и GoogleVertexService.
    
    Атрибуты:
        gemini_model_name: Имя модели Gemini для использования (например, "gemini-2.0-flash")
        thinking_budget: Бюджет токенов для "размышления" модели (None = без ограничений).
                         Используется в моделях с расширенными reasoning возможностями.
    """
    gemini_model_name: Annotated[
        str, "The name of the Google model to use for the service."
    ] = "gemini-2.0-flash"
    thinking_budget: Annotated[
        int, "The thinking token budget to use for the service."
    ] = None

    def img_to_bytes(self, img: PIL.Image.Image):
        """
        Конвертирует PIL изображение в байты в формате WEBP.
        
        Аргументы:
            img: PIL изображение для конвертации
            
        Возвращает:
            bytes: Байтовое представление изображения в формате WEBP
        """
        # Создаем буфер в памяти
        image_bytes = BytesIO()
        # Сохраняем изображение в формате WEBP для оптимизации размера
        img.save(image_bytes, format="WEBP")
        # Возвращаем байтовое содержимое
        return image_bytes.getvalue()

    def get_google_client(self, timeout: int):
        """
        Создает клиент для Google API.
        
        Этот метод должен быть переопределен в дочерних классах для создания
        специфичного клиента (обычный Gemini API или Vertex AI).
        
        Аргументы:
            timeout: Таймаут для запросов в секундах
            
        Возвращает:
            genai.Client: Клиент для работы с Google API
            
        Raises:
            NotImplementedError: Если метод не переопределен в дочернем классе
        """
        raise NotImplementedError

    def process_images(self, images):
        """
        Обрабатывает список изображений в формат для Gemini API.
        
        Конвертирует PIL изображения в типы Part, которые принимает Gemini API.
        
        Аргументы:
            images: Список PIL изображений
            
        Возвращает:
            list: Список объектов types.Part с изображениями в формате WEBP
        """
        # Преобразуем каждое изображение в Part с MIME-типом image/webp
        image_parts = [
            types.Part.from_bytes(data=self.img_to_bytes(img), mime_type="image/webp")
            for img in images
        ]
        return image_parts

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
        Выполняет запрос к Gemini API для обработки изображения и текста.
        
        Отправляет мультимодальный запрос в Gemini с автоматическими повторными попытками
        при ошибках rate limit и JSON parsing. Согласно документации Gemini, изображения
        передаются первыми для лучшей производительности.
        
        Аргументы:
            prompt: Текстовый промпт с инструкциями
            image: Изображение или список изображений для анализа
            block: Блок для обновления метаданных использования токенов
            response_schema: Pydantic схема для валидации ответа
            max_retries: Переопределение количества повторных попыток
            timeout: Переопределение таймаута в секундах
            
        Возвращает:
            dict: Ответ от Gemini в виде словаря, или {} при ошибке
        """
        # Используем значения по умолчанию если не переопределены
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        # Получаем клиент Google API с нужным таймаутом
        client = self.get_google_client(timeout=timeout)
        # Форматируем изображения в нужный формат
        image_parts = self.format_image_for_llm(image)

        # Общее количество попыток = начальная попытка + повторы
        total_tries = max_retries + 1
        # Начинаем с температуры 0 для детерминированного вывода
        temperature = 0
        for tries in range(1, total_tries + 1):
            # Формируем конфигурацию для запроса
            config = {
                "temperature": temperature,  # Контролирует случайность вывода (0 = детерминированный)
                "response_schema": response_schema,  # Схема для структурированного JSON ответа
                "response_mime_type": "application/json",  # Требуем JSON формат
            }
            # Добавляем ограничение на количество токенов если задано
            if self.max_output_tokens:
                config["max_output_tokens"] = self.max_output_tokens

            # Для моделей Gemini можно опционально установить thinking budget
            # (бюджет токенов для внутреннего "размышления" модели)
            if self.thinking_budget is not None:
                config["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=self.thinking_budget
                )

            try:
                # Отправляем запрос к Gemini API
                # Согласно документации Gemini, лучше передавать изображения первыми
                responses = client.models.generate_content(
                    model=self.gemini_model_name,
                    contents=image_parts
                    + [
                        prompt
                    ],  # Изображения идут первыми, затем промпт
                    config=config,
                )
                # Извлекаем текст ответа из первого кандидата
                output = responses.candidates[0].content.parts[0].text
                # Получаем информацию об использованных токенах
                total_tokens = responses.usage_metadata.total_token_count
                # Обновляем метаданные блока если он передан
                if block:
                    block.update_metadata(
                        llm_tokens_used=total_tokens, llm_request_count=1
                    )
                # Парсим JSON ответ и возвращаем
                return json.loads(output)
            except APIError as e:
                # Обрабатываем ошибки API (rate limit, сервер недоступен и т.д.)
                if e.code in [429, 443, 503]:
                    # Rate limit превышен или временная недоступность сервера
                    if tries == total_tries:
                        # Последняя попытка не удалась - сдаемся
                        logger.error(
                            f"APIError: {e}. Max retries reached. Giving up. (Attempt {tries}/{total_tries})",
                        )
                        break
                    else:
                        # Ждем экспоненциально увеличивающееся время и повторяем
                        wait_time = tries * self.retry_wait_time
                        logger.warning(
                            f"APIError: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{total_tries})",
                        )
                        time.sleep(wait_time)
                else:
                    # Другие типы ошибок API - логируем и прекращаем попытки
                    logger.error(f"APIError: {e}")
                    break
            except json.JSONDecodeError as e:
                # Ответ не является валидным JSON - пробуем с повышенной температурой
                temperature = 0.2  # Немного увеличиваем температуру для получения другого ответа

                # Ответ не был валидным JSON
                if tries == total_tries:
                    # Последняя попытка не удалась - сдаемся
                    logger.error(
                        f"JSONDecodeError: {e}. Max retries reached. Giving up. (Attempt {tries}/{total_tries})",
                    )
                    break
                else:
                    # Пробуем еще раз
                    logger.warning(
                        f"JSONDecodeError: {e}. Retrying... (Attempt {tries}/{total_tries})",
                    )
            except Exception as e:
                # Неожиданная ошибка - логируем трейсбек и прекращаем
                logger.error(f"Exception: {e}")
                traceback.print_exc()
                break

        # Если все попытки не удались, возвращаем пустой словарь
        return {}


class GoogleGeminiService(BaseGeminiService):
    """
    Сервис для работы с Google Gemini API напрямую.
    
    Использует прямое подключение к Google Gemini API через API ключ.
    Для использования через Google Vertex AI см. GoogleVertexService.
    
    Атрибуты:
        gemini_api_key: API ключ Google для доступа к Gemini API
    """
    gemini_api_key: Annotated[str, "The Google API key to use for the service."] = None

    def get_google_client(self, timeout: int):
        """
        Создает клиент для прямого подключения к Gemini API.
        
        Аргументы:
            timeout: Таймаут для запросов в секундах
            
        Возвращает:
            genai.Client: Настроенный клиент для Gemini API
        """
        return genai.Client(
            api_key=self.gemini_api_key,
            http_options={"timeout": timeout * 1000},  # Конвертируем в миллисекунды
        )
