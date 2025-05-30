from flask import Flask, render_template, abort, send_from_directory
# Удалены импорты SQLAlchemy и Migrate, так как они теперь в __init__.py
# Удален импорт MetaData, так как он теперь в __init__.py

# <--- ИЗМЕНЕНО: Импортируем db и migrate из пакета 'app' (то есть из __init__.py)
from app import db, migrate

app = Flask(__name__)
application = app

app.config.from_pyfile('config.py')

app = Flask(__name__)
application = app

app.config.from_pyfile('config.py')

# <--- ДОБАВЬТЕ ЭТИ СТРОКИ ДЛЯ ДИАГНОСТИКИ
import logging
logging.basicConfig(level=logging.INFO) # Настраиваем логирование
app.logger.info(f"DEBUG: DATABASE_URL from os.environ: {os.environ.get('DATABASE_URL')}")
app.logger.info(f"DEBUG: SECRET_KEY from os.environ: {os.environ.get('SECRET_KEY')}")
app.logger.info(f"DEBUG: SQLALCHEMY_DATABASE_URI from config: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
# <--- КОНЕЦ ДИАГНОСТИЧЕСКИХ СТРОК

db.init_app(app)
migrate.init_app(app, db)

# <--- УДАЛЕНЫ convention и metadata (перенесено в __init__.py)

# <--- ИЗМЕНЕНО: Инициализируем db и migrate здесь, после создания Flask-приложения
db.init_app(app)
migrate.init_app(app, db)

# Правильные абсолютные импорты для модулей внутри пакета 'app'
from app.models import Category, Image # <--- ИСПРАВЛЕНО
from app.auth import bp as auth_bp, init_login_manager # <--- ИСПРАВЛЕНО
from app.courses import bp as courses_bp # <--- ИСПРАВЛЕНО

app.register_blueprint(auth_bp)
app.register_blueprint(courses_bp)

init_login_manager(app)

@app.route('/')
def index():
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template(
        'index.html',
        categories=categories,
    )

@app.route('/images/<image_id>')
def image(image_id):
    img = db.get_or_404(Image, image_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               img.storage_filename)