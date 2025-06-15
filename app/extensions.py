# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

login_manager.login_view = 'auth.login' # Blueprint 'auth', роут 'login'
login_manager.login_message = 'Для доступа к данной странице необходимо войти в систему.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    from .models import User # Относительный импорт
    return db.session.get(User, int(user_id))