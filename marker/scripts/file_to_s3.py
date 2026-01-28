"""
Скрипт для загрузки файлов на S3 хранилище.

Утилита для загрузки локальных файлов в S3-совместимое хранилище
с использованием библиотеки boto3. Поддерживает настройку параметров
подключения через командную строку.

Автор: Marker Team
"""

import json
import shutil
import datetime
from pathlib import Path
import boto3

from huggingface_hub import snapshot_download

import click

# URL API S3 хранилища CloudFlare R2
S3_API_URL = "https://1afbe4656a6b40d982ab5e730a39f6b9.r2.cloudflarestorage.com"


@click.command(help="Загружает файлы в S3 бакет")
@click.argument("filepath", type=str)
@click.argument("s3_path", type=str)
@click.option("--bucket_name", type=str, default="datalab")
@click.option("--access_key_id", type=str, default="<access_key_id>")
@click.option("--access_key_secret", type=str, default="<access_key_secret>")
def main(filepath: str, s3_path: str, bucket_name: str, access_key_id: str, access_key_secret: str):
    """
    Основная функция для загрузки файла в S3 хранилище.
    
    Args:
        filepath (str): Путь к локальному файлу для загрузки
        s3_path (str): Путь назначения в S3
        bucket_name (str): Имя S3 бакета (по умолчанию "datalab")
        access_key_id (str): Идентификатор ключа доступа S3
        access_key_secret (str): Секретный ключ доступа S3
    """
    filepath = Path(filepath)
    
    # Создаем клиент S3 с настройками подключения
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_API_URL,  # URL S3 API
        aws_access_key_id=access_key_id,  # Идентификатор ключа доступа
        aws_secret_access_key=access_key_secret,  # Секретный ключ доступа
        region_name="enam"  # Регион (может быть любым для CloudFlare R2)
    )

    # Формируем полный путь в S3
    s3_key = f"{s3_path}/{filepath.name}"

    try:
        # Загружаем файл в S3
        s3_client.upload_file(
            str(filepath),  # Локальный путь к файлу
            bucket_name,   # Имя бакета
            s3_key        # Ключ (путь) в S3
        )
    except Exception as e:
        # Выводим сообщение об ошибке при неудачной загрузке
        print(f"Error uploading {filepath}: {str(e)}")

    # Сообщение об успешной загрузке
    print(f"Uploaded files to {s3_path}")


if __name__ == "__main__":
    main()



