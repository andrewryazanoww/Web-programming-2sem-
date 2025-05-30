# config.py

import os
from dotenv import load_dotenv

load_dotenv() # Загрузка переменных из .env

# <--- ИЗМЕНЕНО: ПЕРЕМЕЩЕНО ИЗ КЛАССА В ГЛОБАЛЬНУЮ ОБЛАСТЬ ВИДИМОСТИ
SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-that-should-be-strong'
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                          'sqlite:///./app.db' # Локально используем SQLite

SQLALCHEMY_TRACK_MODIFICATIONS = False # Рекомендуется для Flask-SQLAlchemy

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
# Создайте папку uploads, если её нет.
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# <--- ВЕСЬ КЛАСС CONFIG ТЕПЕРЬ МОЖЕТ БЫТЬ УДАЛЕН ИЛИ ЗАКОММЕНТИРОВАН,
#      так как from_pyfile не использует его.
# class Config:
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-that-should-be-strong'
#     SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
#                               'sqlite:///./app.db'
#     SQLALCHEMY_TRACK_MODIFICATIONS = False
#     UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
#     if not os.path.exists(UPLOAD_FOLDER):
#         os.makedirs(UPLOAD_FOLDER)