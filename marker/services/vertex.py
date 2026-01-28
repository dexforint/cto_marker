"""
Модуль интеграции с Google Vertex AI.

Предоставляет класс для работы с Google Gemini моделями через Vertex AI
для улучшения результатов конвертации документов. Vertex AI предоставляет
enterprise-уровень доступа к Gemini моделям с дополнительными возможностями
управления и безопасности.

Основные возможности:
- Доступ к Gemini моделям через Google Cloud Vertex AI
- Поддержка dedicated instances для повышенной производительности
- Настройка региона развертывания (location)
- Все возможности BaseGeminiService
"""

from typing import Annotated

from google import genai

from marker.services.gemini import BaseGeminiService

class GoogleVertexService(BaseGeminiService):
    """
    Сервис для работы с Google Gemini через Vertex AI.
    
    Использует Google Cloud Vertex AI для доступа к Gemini моделям.
    Требует настройки Google Cloud проекта и аутентификации.
    Подходит для enterprise использования с требованиями к безопасности и SLA.
    
    Атрибуты:
        vertex_project_id: ID Google Cloud проекта для Vertex AI
        vertex_location: Регион Google Cloud для развертывания (например, "us-central1")
        gemini_model_name: Имя модели Gemini (например, "gemini-2.0-flash-001")
        vertex_dedicated: Использовать ли dedicated Vertex AI instance для повышенной производительности
    """
    vertex_project_id: Annotated[
        str,
        "Google Cloud Project ID for Vertex AI.",
    ] = None
    vertex_location: Annotated[
        str,
        "Google Cloud Location for Vertex AI.",
    ] = "us-central1"
    gemini_model_name: Annotated[
        str,
        "The name of the Google model to use for the service."
    ] = "gemini-2.0-flash-001"
    vertex_dedicated: Annotated[
        bool,
        "Whether to use a dedicated Vertex AI instance."
    ] = False

    def get_google_client(self, timeout: int):
        """
        Создает клиент для подключения к Vertex AI.
        
        Настраивает клиент с параметрами Google Cloud проекта и региона.
        Опционально включает заголовки для dedicated instance.
        
        Аргументы:
            timeout: Таймаут для запросов в секундах
            
        Возвращает:
            genai.Client: Настроенный клиент для Vertex AI
        """
        # Настраиваем HTTP опции с таймаутом
        http_options = {"timeout": timeout * 1000} # Конвертируем в миллисекунды
        # Если используется dedicated instance, добавляем специальный заголовок
        if self.vertex_dedicated:
            http_options["headers"] = {"x-vertex-ai-llm-request-type": "dedicated"}
        # Создаем и возвращаем клиент с настройками Vertex AI
        return genai.Client(
            vertexai=True,  # Указываем что используем Vertex AI
            project=self.vertex_project_id,  # ID проекта Google Cloud
            location=self.vertex_location,  # Регион развертывания
            http_options=http_options,
        )
