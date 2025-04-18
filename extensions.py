# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

login_manager.login_view = 'login' # Имя роута входа (определяется в app.py)
login_manager.login_message = "Пожалуйста, войдите для доступа к этой странице."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    # ИСПРАВЛЕНО: Импортируем User из models.py
    from models import User
    # db должен быть инициализирован с app к моменту вызова этой функции
    return db.session.get(User, int(user_id))