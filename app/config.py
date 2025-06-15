# app/config.py
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key_!@#_office_ais_final_full_code')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(project_root, 'office_ais.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False

UPLOAD_FOLDER_EQUIPMENT = os.path.join(os.path.dirname(__file__), 'media', 'equipment_images')

REMEMBER_COOKIE_DURATION = 2592000
LOGIN_DISABLED = False

ITEMS_PER_PAGE_EQUIPMENT = 10
ITEMS_PER_PAGE_SERVICE_HISTORY = 10