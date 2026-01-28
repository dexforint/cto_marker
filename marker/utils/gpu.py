# Модуль для управления GPU ресурсами и MPS (Multi-Process Service)
# Обеспечивает контроль за видеопамятью, запуск/остановку MPS серверов и мониторинг GPU

import os
import subprocess
import torch

from marker.logger import get_logger
from marker.settings import settings

logger = get_logger()


class GPUManager:
    """
    Класс для управления GPU ресурсами и MPS (Multi-Process Service).
    
    Обеспечивает мониторинг и управление видеопамятью NVIDIA GPU,
    запуск MPS серверов для эффективного использования памяти,
    а также контроль за процессорными процессами.
    
    Основные возможности:
    - Получение информации о доступной видеопамяти
    - Запуск и остановка MPS серверов
    - Мониторинг доступности CUDA
    - Управление жизненным циклом GPU процессов
    """
    # Значение по умолчанию для видеопамяти (в GB) при отсутствии CUDA
    default_gpu_vram: int = 8

    def __init__(self, device_idx: int):
        """
        Инициализирует менеджер GPU для указанного устройства.
        
        Аргументы:
            device_idx: Индекс GPU устройства (0, 1, 2, ...)
        """
        self.device_idx = device_idx
        self.original_compute_mode = None  # Исходный режим вычислений GPU
        self.mps_server_process = None   # Процесс MPS сервера

    def __enter__(self):
        """
        Контекстный менеджер - вход в блок with.
        
        Запускает MPS сервер при использовании CUDA.
        
        Возвращает:
            self: Экземпляр GPUManager для использования в with блоке
        """
        # Если используем CUDA, запускаем MPS сервер для оптимизации памяти
        if self.using_cuda():
            self.start_mps_server()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Контекстный менеджер - выход из блок with.
        
        Очищает ресурсы и останавливает MPS сервер.
        
        Аргументы:
            exc_type: Тип исключения (если произошло)
            exc_val: Значение исключения
            exc_tb: Трассировка стека исключения
        """
        # Если используем CUDA, выполняем очистку ресурсов
        if self.using_cuda():
            self.cleanup()

    @staticmethod
    def using_cuda() -> bool:
        """
        Проверяет, используется ли CUDA в качестве устройства вычислений.
        
        Возвращает:
            bool: True если CUDA присутствует в настройках устройства
        """
        return "cuda" in settings.TORCH_DEVICE_MODEL

    def check_cuda_available(self) -> bool:
        """
        Проверяет доступность CUDA и nvidia-smi.
        
        Выполняет двойную проверку:
        1. Наличие CUDA в PyTorch
        2. Доступность утилиты nvidia-smi
        
        Возвращает:
            bool: True если CUDA полностью доступен и настроен
        """
        # Проверяем доступность CUDA в PyTorch
        if not torch.cuda.is_available():
            return False
        
        # Дополнительно проверяем наличие nvidia-smi
        try:
            subprocess.run(["nvidia-smi", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_gpu_vram(self) -> int:
        """
        Получает общее количество видеопамяти GPU в гигабайтах.
        
        Использует nvidia-smi для получения точной информации о памяти.
        В случае ошибки возвращает значение по умолчанию.
        
        Возвращает:
            int: Количество видеопамяти в GB
        """
        # Если CUDA не используется, возвращаем значение по умолчанию
        if not self.using_cuda():
            return self.default_gpu_vram

        try:
            # Выполняем nvidia-smi для получения информации о памяти
            result = subprocess.run(
                [
                    "nvidia-smi",                           # Утилита NVIDIA для мониторинга
                    "--query-gpu=memory.total",             # Запрос общего объема памяти
                    "--format=csv,noheader,nounits",       # Формат вывода без заголовков и единиц
                    "-i", str(self.device_idx),             # Индекс GPU устройства
                ],
                capture_output=True,                        # Перехватываем вывод
                text=True,                                 # Результат в виде текста
                check=True,                                # Проверяем успешность выполнения
            )

            # Парсим результат: извлекаем количество мегабайт и конвертируем в гигабайты
            vram_mb = int(result.stdout.strip())
            vram_gb = int(vram_mb / 1024)
            return vram_gb

        # Обрабатываем возможные ошибки: нет nvidia-smi, проблемы с GPU, некорректный вывод
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            return self.default_gpu_vram

    def start_mps_server(self) -> bool:
        """
        Запускает NVIDIA MPS (Multi-Process Service) сервер для данного GPU.
        
        MPS позволяет эффективно использовать GPU память при многопроцессной
        обработке документов, разделяя ресурсы между процессами.
        
        Возвращает:
            bool: True если сервер успешно запущен, False в противном случае
        """
        # Проверяем доступность CUDA перед запуском
        if not self.check_cuda_available():
            return False

        try:
            # Настраиваем переменные окружения для MPS с директориями для конкретного чанка
            env = os.environ.copy()
            pipe_dir = f"/tmp/nvidia-mps-{self.device_idx}"    # Директория для каналов MPS
            log_dir = f"/tmp/nvidia-log-{self.device_idx}"    # Директория для логов MPS
            env["CUDA_MPS_PIPE_DIRECTORY"] = pipe_dir
            env["CUDA_MPS_LOG_DIRECTORY"] = log_dir

            # Создаем необходимые директории для MPS
            os.makedirs(pipe_dir, exist_ok=True)
            os.makedirs(log_dir, exist_ok=True)

            # Запускаем MPS control daemon в фоновом режиме
            self.mps_server_process = subprocess.Popen(
                ["nvidia-cuda-mps-control", "-d"],          # Запуск демона MPS
                env=env,                                      # Передаем настроенное окружение
                stdout=subprocess.PIPE,                      # Перехватываем stdout
                stderr=subprocess.PIPE,                      # Перехватываем stderr
            )

            logger.info(f"Запущен NVIDIA MPS сервер для чанка {self.device_idx}")
            return True
            
        # Обрабатываем ошибки запуска MPS сервера
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(
                f"Не удалось запустить MPS сервер для чанка {self.device_idx}: {e}"
            )
            return False

    def stop_mps_server(self) -> None:
        """
        Останавливает NVIDIA MPS сервер для данного GPU.
        
        Корректно завершает работу MPS daemon и связанные процессы,
        освобождая ресурсы системы.
        """
        try:
            # Настраиваем переменные окружения для доступа к MPS
            env = os.environ.copy()
            env["CUDA_MPS_PIPE_DIRECTORY"] = f"/tmp/nvidia-mps-{self.device_idx}"
            env["CUDA_MPS_LOG_DIRECTORY"] = f"/tmp/nvidia-log-{self.device_idx}"

            # Отправляем команду завершения работы в MPS control
            subprocess.run(
                ["nvidia-cuda-mps-control"],                # Утилита управления MPS
                input="quit\n",                              # Команда завершения
                text=True,                                   # Ввод в виде текста
                env=env,                                     # Передаем настроенное окружение
                timeout=10,                                  # Таймаут выполнения команды
            )

            # Завершаем процесс MPS daemon
            if self.mps_server_process:
                # Сначала пытаемся корректно завершить процесс
                self.mps_server_process.terminate()
                try:
                    # Ждем завершения процесса в течение 5 секунд
                    self.mps_server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Если процесс не завершился, принудительно убиваем его
                    self.mps_server_process.kill()
                self.mps_server_process = None

            logger.info(f"Остановлен NVIDIA MPS сервер для чанка {self.device_idx}")
            
        # Обрабатываем ошибки при остановке MPS сервера
        except Exception as e:
            logger.warning(
                f"Не удалось остановить MPS сервер для чанка {self.device_idx}: {e}"
            )

    def cleanup(self) -> None:
        """
        Выполняет полную очистку ресурсов GPU.
        
        Останавливает MPS сервер и выполняет дополнительную очистку,
        если это необходимо.
        """
        self.stop_mps_server()