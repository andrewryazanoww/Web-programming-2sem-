# config.py

import os
from dotenv import load_dotenv

load_dotenv() # Загрузка переменных из .env

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-that-should-be-strong'
    # <--- ИЗМЕНЕНО: DATABASE_URL из переменных окружения
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///./app.db' # Локально используем SQLite

    SQLALCHEMY_TRACK_MODIFICATIONS = False # Рекомендуется для Flask-SQLAlchemy

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    # Создайте папку uploads, если её нет.
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)