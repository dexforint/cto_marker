"""
Модуль интеграции с Anthropic Claude API.

Предоставляет класс для работы с Anthropic Claude моделями (Claude 3.5 Sonnet и др.)
для улучшения результатов конвертации документов. Включает специальную обработку
JSON ответов и валидацию с исправлением escape-последовательностей.

Основные возможности:
- Обработка мультимодальных запросов (текст + изображения)
- Автоматические повторные попытки при rate limit
- Специальная валидация JSON с исправлением экранирования
- Настраиваемый system prompt для структурированных ответов
"""

import json
import time
from typing import List, Annotated, T

import PIL
from PIL import Image
import anthropic
from anthropic import RateLimitError, APITimeoutError
from marker.logger import get_logger
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

logger = get_logger()


class ClaudeService(BaseService):
    """
    Сервис для работы с Anthropic Claude API.
    
    Обеспечивает интеграцию с моделями Claude для анализа документов.
    Особенность: Claude не поддерживает нативное structured output, поэтому
    используется system prompt с JSON схемой и специальная валидация ответов.
    
    Атрибуты:
        claude_model_name: Имя модели Claude (например, "claude-3-7-sonnet-20250219")
        claude_api_key: API ключ Anthropic для доступа к Claude
        max_claude_tokens: Максимальное количество токенов для одного запроса Claude
    """
    claude_model_name: Annotated[
        str, "The name of the Google model to use for the service."
    ] = "claude-3-7-sonnet-20250219"
    claude_api_key: Annotated[str, "The Claude API key to use for the service."] = None
    max_claude_tokens: Annotated[
        int, "The maximum number of tokens to use for a single Claude request."
    ] = 8192

    def process_images(self, images: List[Image.Image]) -> List[dict]:
        """
        Обрабатывает список изображений в формат для Claude API.
        
        Конвертирует PIL изображения в формат, который принимает Claude API -
        словари с типом "image" и base64 данными.
        
        Аргументы:
            images: Список PIL изображений
            
        Возвращает:
            Список словарей с изображениями в формате Claude API
        """
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/webp",
                    "data": self.img_to_base64(img),
                },
            }
            for img in images
        ]

    def validate_response(self, response_text: str, schema: type[T]) -> T:
        """
        Валидирует и парсит ответ Claude в соответствии со схемой.
        
        Claude может возвращать JSON в markdown блоках (```json...```) или с
        неправильным экранированием. Этот метод пробует различные стратегии парсинга.
        
        Аргументы:
            response_text: Текст ответа от Claude
            schema: Pydantic схема для валидации
            
        Возвращает:
            dict: Валидированный ответ в виде словаря, или None при ошибке
        """
        # Очищаем текст от пробелов
        response_text = response_text.strip()
        # Удаляем markdown обертку если присутствует
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        try:
            # Пробуем распарсить JSON напрямую
            out_schema = schema.model_validate_json(response_text)
            out_json = out_schema.model_dump()
            return out_json
        except Exception:
            try:
                # Если не получилось, пробуем исправить экранирование обратных слешей
                escaped_str = response_text.replace("\\", "\\\\")
                out_schema = schema.model_validate_json(escaped_str)
                return out_schema.model_dump()
            except Exception:
                # Если все попытки не удались, возвращаем None
                return

    def get_client(self):
        """
        Создает клиент Anthropic API.
        
        Возвращает:
            anthropic.Anthropic: Настроенный клиент с API ключом
        """
        return anthropic.Anthropic(
            api_key=self.claude_api_key,
        )

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
        Выполняет запрос к Claude API для обработки изображения и текста.
        
        Отправляет мультимодальный запрос с system prompt, содержащим JSON схему,
        так как Claude не поддерживает нативное structured output. Включает
        автоматические повторные попытки при rate limit.
        
        Аргументы:
            prompt: Текстовый промпт с инструкциями
            image: Изображение или список изображений для анализа
            block: Блок для обновления метаданных использования токенов
            response_schema: Pydantic схема для валидации ответа
            max_retries: Переопределение количества повторных попыток
            timeout: Переопределение таймаута в секундах
            
        Возвращает:
            dict: Ответ от Claude в виде словаря, или {} при ошибке
        """
        # Используем значения по умолчанию если не переопределены
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        # Получаем JSON схему для включения в system prompt
        schema_example = response_schema.model_json_schema()
        # Формируем system prompt с инструкциями по формату ответа
        system_prompt = f"""
Follow the instructions given by the user prompt.  You must provide your response in JSON format matching this schema:

{json.dumps(schema_example, indent=2)}

Respond only with the JSON schema, nothing else.  Do not include ```json, ```,  or any other formatting.
""".strip()

        # Получаем клиент Claude
        client = self.get_client()
        # Форматируем изображения в формат Claude
        image_data = self.format_image_for_llm(image)

        # Формируем сообщения в формате Claude API
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
                # Отправляем запрос к Claude API
                response = client.messages.create(
                    system=system_prompt,  # System prompt с JSON схемой
                    model=self.claude_model_name,
                    max_tokens=self.max_claude_tokens,
                    messages=messages,
                    timeout=timeout,
                )
                # Извлекаем и валидируем ответ
                response_text = response.content[0].text
                return self.validate_response(response_text, response_schema)
            except (RateLimitError, APITimeoutError) as e:
                # Обрабатываем ошибки rate limit и таймаута
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
                logger.error(f"Error during Claude API call: {e}")
                break

        # Если все попытки не удались, возвращаем пустой словарь
        return {}
