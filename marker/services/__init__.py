"""
Модуль базовых LLM сервисов для улучшения результатов конвертации.

Этот модуль предоставляет базовый класс BaseService, который служит основой
для всех интеграций с различными языковыми моделями (LLM). Сервисы используются
для улучшения качества конвертации документов через обработку изображений и текста
с помощью AI-моделей.

Основные возможности:
- Конвертация изображений в base64 для передачи в LLM API
- Форматирование изображений для различных LLM провайдеров
- Управление таймаутами и повторными попытками запросов
- Гибкая конфигурация через Pydantic модели
"""

from typing import Optional, List, Annotated
from io import BytesIO

import PIL
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.util import assign_config, verify_config_keys
import base64


class BaseService:
    """
    Базовый класс для всех LLM сервисов.
    
    Предоставляет общую функциональность для работы с различными LLM провайдерами,
    включая конвертацию изображений, управление запросами и обработку ошибок.
    Все конкретные сервисы (OpenAI, Claude, Gemini и т.д.) наследуются от этого класса.
    
    Атрибуты:
        timeout: Таймаут в секундах для запросов к API сервиса
        max_retries: Максимальное количество повторных попыток при ошибках
        retry_wait_time: Время ожидания в секундах между повторными попытками
        max_output_tokens: Максимальное количество токенов для генерации ответа (None = без ограничений)
    """
    timeout: Annotated[int, "The timeout to use for the service."] = 30
    max_retries: Annotated[
        int, "The maximum number of retries to use for the service."
    ] = 2
    retry_wait_time: Annotated[int, "The wait time between retries."] = 3
    max_output_tokens: Annotated[
        int, "The maximum number of output tokens to generate."
    ] = None

    def img_to_base64(self, img: PIL.Image.Image, format: str = "WEBP"):
        """
        Конвертирует PIL изображение в base64 строку.
        
        Используется для подготовки изображений к отправке в LLM API,
        так как большинство API принимают изображения в виде base64 строк.
        
        Аргументы:
            img: PIL изображение для конвертации
            format: Формат изображения для сохранения (по умолчанию WEBP для сжатия)
            
        Возвращает:
            str: Base64-кодированная строка изображения в UTF-8
        """
        # Создаем буфер в памяти для сохранения изображения
        image_bytes = BytesIO()
        # Сохраняем изображение в буфер в указанном формате
        img.save(image_bytes, format=format)
        # Кодируем байты изображения в base64 и декодируем в строку UTF-8
        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    def process_images(self, images: List[PIL.Image.Image]) -> list:
        """
        Обрабатывает список изображений для конкретного LLM провайдера.
        
        Этот метод должен быть переопределен в дочерних классах,
        так как каждый провайдер требует свой формат данных изображений.
        
        Аргументы:
            images: Список PIL изображений для обработки
            
        Возвращает:
            list: Список обработанных изображений в формате провайдера
            
        Raises:
            NotImplementedError: Если метод не переопределен в дочернем классе
        """
        raise NotImplementedError

    def format_image_for_llm(self, image):
        """
        Форматирует изображение или список изображений для передачи в LLM.
        
        Универсальный метод, который нормализует входные данные (одиночное
        изображение или список) и вызывает process_images для обработки.
        
        Аргументы:
            image: Одно PIL изображение, список изображений или None
            
        Возвращает:
            list: Список обработанных изображений в формате провайдера,
                  или пустой список если изображение не предоставлено
        """
        # Если изображение не предоставлено, возвращаем пустой список
        if not image:
            return []

        # Нормализуем входные данные: если это не список, делаем список из одного элемента
        if not isinstance(image, list):
            image = [image]

        # Обрабатываем изображения через провайдер-специфичный метод
        image_parts = self.process_images(image)
        return image_parts

    def __init__(self, config: Optional[BaseModel | dict] = None):
        """
        Инициализирует сервис с заданной конфигурацией.
        
        Аргументы:
            config: Конфигурация сервиса в виде Pydantic модели или словаря.
                    Содержит API ключи, URL эндпоинтов и другие параметры.
        """
        # Применяем конфигурацию к атрибутам класса
        assign_config(self, config)

        # Проверяем что все необходимые поля заполнены (API ключи и т.д.)
        verify_config_keys(self)

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
        Выполняет запрос к LLM для обработки изображения и текста.
        
        Основной метод для взаимодействия с LLM. Должен быть переопределен
        в дочерних классах для реализации специфичной логики каждого провайдера.
        
        Аргументы:
            prompt: Текстовый промпт с инструкциями для LLM
            image: Изображение или список изображений для анализа (может быть None)
            block: Блок документа для обновления метаданных об использовании токенов
            response_schema: Pydantic схема для валидации и парсинга ответа LLM
            max_retries: Переопределение количества повторных попыток (по умолчанию из self.max_retries)
            timeout: Переопределение таймаута (по умолчанию из self.timeout)
            
        Возвращает:
            dict: Ответ LLM в виде словаря, валидированный по response_schema
            
        Raises:
            NotImplementedError: Если метод не переопределен в дочернем классе
        """
        raise NotImplementedError
