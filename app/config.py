# app/config.py
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key_!@#_office_ais_replace_me')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(project_root, 'office_ais.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False # Установите True для отладки SQL

# Папка для загрузки изображений оборудования
UPLOAD_FOLDER_EQUIPMENT = os.path.join(project_root, 'app', 'media', 'equipment_images')

REMEMBER_COOKIE_DURATION = 2592000  # 30 дней

# Пагинация
ITEMS_PER_PAGE_EQUIPMENT = 10