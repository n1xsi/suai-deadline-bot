from cryptography.fernet import Fernet
import base64
import os

# Генерация ключа для шифрования.
#
# ЗАПУСТИТЕ ЭТУ КОМАНДУ В ТЕРМИНАЛЕ ОДИН РАЗ:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#
# И скопируйте полученный ключ в ваш .env файл:
# ENCRYPTION_KEY="СГЕНЕРИРОВАННЫЙ_КЛЮЧ"

# Прочитаем ключ из config файла
from src.config import ENCRYPTION_KEY

if not ENCRYPTION_KEY:
    raise ValueError("Не найден ключ шифрования ENCRYPTION_KEY в .env файле!")

f_key = Fernet(ENCRYPTION_KEY.encode())

def encrypt_data(data: str) -> str:
    """Шифрует строку и возвращает зашифрованную строку."""
    return f_key.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Расшифровывает строку и возвращает исходную."""
    return f_key.decrypt(encrypted_data.encode()).decode()