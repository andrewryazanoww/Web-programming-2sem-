# app/__init__.py
import os
from flask import (Flask, render_template, send_from_directory, current_app,
                   abort, Blueprint, redirect, url_for)
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime as dt_for_context

from .extensions import db, login_manager
from .models import Category, Image, User, Role, VisitLog, ServiceHistory, Equipment # Импортируем все модели для create_all и initialize

def create_app(config_filename='config.py'):
    app = Flask(__name__,
                template_folder='templates',  # Папка для шаблонов относительно текущего файла (__init__.py)
                static_folder='static')      # Папка для статики относительно текущего файла (__init__.py)

    # --- Загрузка конфигурации ---
    cfg_path = os.path.join(os.path.dirname(__file__), config_filename)
    if os.path.exists(cfg_path):
        app.config.from_pyfile(cfg_path, silent=False)
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл конфигурации '{cfg_path}' не найден. Используются значения по умолчанию.")
        # ... (блок setdefault как в предыдущем ответе) ...
        app.config.setdefault('SECRET_KEY', 'default_ بسیار_secret_key_please_change_in_prod_v2')
        project_root_for_db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///' + os.path.join(project_root_for_db, 'office_ais.db'))
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        app.config.setdefault('SQLALCHEMY_ECHO', False)
        app.config.setdefault('UPLOAD_FOLDER_EQUIPMENT', os.path.join(app.root_path, 'media', 'equipment_images')) # app.root_path указывает на папку 'app'
        app.config.setdefault('ITEMS_PER_PAGE_EQUIPMENT', 10)
        app.config.setdefault('ITEMS_PER_PAGE_REVIEWS', 5)
        app.config.setdefault('REMEMBER_COOKIE_DURATION', 2592000)


    upload_folder_path = app.config.get('UPLOAD_FOLDER_EQUIPMENT')
    if upload_folder_path and not os.path.exists(upload_folder_path):
        try:
            os.makedirs(upload_folder_path)
            print(f"Создана папка UPLOAD_FOLDER_EQUIPMENT: {upload_folder_path}")
        except OSError as e:
            print(f"Не удалось создать папку UPLOAD_FOLDER_EQUIPMENT {upload_folder_path}: {e}")

    db.init_app(app)
    login_manager.init_app(app)

    # --- Обработчики ошибок ---
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(err):
        app.logger.error(f"SQLAlchemy Error: {err}")
        db.session.rollback()
        return render_template('error.html', error_message='Ошибка при работе с базой данных.', status_code=500), 500

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', error_message="Запрашиваемая страница не найдена.", status_code=404), 404

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template('error.html', error_message="Доступ запрещен. У вас нет прав для просмотра этой страницы.", status_code=403), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        original_exception = getattr(e, "original_exception", None)
        app.logger.error(f"Internal Server Error: {e} (Original: {original_exception})")
        return render_template('error.html', error_message="Произошла внутренняя ошибка сервера.", status_code=500), 500

    # --- Регистрация Blueprint'ов ---
    from .auth_bp import bp as auth_blueprint
    from .equipment_bp import bp as equipment_blueprint
    from .service_bp import bp as service_blueprint

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(equipment_blueprint)
    app.register_blueprint(service_blueprint)
    print("Blueprint'ы auth, equipment, service зарегистрированы.")

    main_bp = Blueprint('main_bp', __name__)
    @main_bp.route('/')
    def index(): return redirect(url_for('equipment.index'))
    @main_bp.route('/images/equipment/<image_id>')
    def image_file(image_id):
        img = db.session.get(Image, image_id)
        if img is None: abort(404)
        return send_from_directory(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img.storage_filename)
    app.register_blueprint(main_bp)
    print("Blueprint 'main_bp' зарегистрирован.")

    # --- Контекстный процессор ---
    # (Код inject_current_time_and_permissions без изменений, как в предыдущем полном app/__init__.py)
    @app.context_processor
    def inject_current_time_and_permissions():
        from flask_login import current_user
        def can(action, target_user_id=None):
            if not current_user.is_authenticated or not current_user.role: return False
            user_role = current_user.role.name;
            if user_role == 'Admin': return action in ['view_equipment_list', 'view_equipment_detail','create_equipment', 'edit_equipment', 'delete_equipment','add_service_record', 'view_service_history']
            elif user_role == 'TechSpecialist':
                if action == 'view_equipment_list': return True
                if action == 'view_equipment_detail': return True
                if action == 'add_service_record': return True
                if action == 'view_service_history': return True
                return False
            elif user_role == 'User':
                if action == 'view_equipment_list': return True
                if action == 'view_equipment_detail': return True
                return False
            return False
        return dict(now=dt_for_context.utcnow(), can=can)

    # --- Инициализация БД ---
    with app.app_context():
        db.create_all()
        print("Таблицы базы данных проверены/созданы.")
        initialize_database_content() # Убрал передачу app, т.к. current_app доступен

    return app

# --- Функция инициализации контента БД ---
# (Код initialize_database_content без изменений, как в предыдущем полном app/__init__.py)
def initialize_database_content(): # Убрал current_app_instance
    # Используем модели, импортированные в начале файла
    print("Инициализация контента БД: Старт...")
    try:
        if db.session.query(Role).count() == 0:
            print("Создание ролей по умолчанию...")
            roles_data = [ {'name': 'Admin', 'description': 'Полный доступ.'}, {'name': 'TechSpecialist', 'description': 'Доступ к оборудованию и обслуживанию.'}, {'name': 'User', 'description': 'Только просмотр.'}]
            for role_data in roles_data: db.session.add(Role(**role_data))
            db.session.commit(); print("Роли созданы.")
        else: print("Роли уже существуют.")
        if db.session.query(Category).count() == 0:
            print("Создание категорий по умолчанию...")
            categories_data = [ {'name': 'Компьютеры'}, {'name': 'Ноутбуки'}, {'name': 'Принтеры и МФУ'}, {'name': 'Сканеры'}, {'name': 'Сетевое оборудование'}, {'name': 'Периферия'}]
            for cat_data in categories_data: db.session.add(Category(**cat_data))
            db.session.commit(); print("Категории созданы.")
        else: print("Категории уже существуют.")
        admin_role = db.session.query(Role).filter_by(name='Admin').first()
        tech_role = db.session.query(Role).filter_by(name='TechSpecialist').first()
        user_role = db.session.query(Role).filter_by(name='User').first()
        if db.session.query(User).filter_by(login='admin').first() is None and admin_role:
            print("Создание пользователя 'admin'..."); admin = User(login='admin', last_name='Администраторов', first_name='Главный', role=admin_role); admin.set_password('admin123'); db.session.add(admin)
        else: print("Пользователь 'admin' уже существует или роль Admin не найдена.")
        if db.session.query(User).filter_by(login='tech').first() is None and tech_role:
            print("Создание пользователя 'tech'..."); tech = User(login='tech', last_name='Специалистов', first_name='Техник', role=tech_role); tech.set_password('tech123'); db.session.add(tech)
        else: print("Пользователь 'tech' уже существует или роль TechSpecialist не найдена.")
        if db.session.query(User).filter_by(login='user').first() is None and user_role:
            print("Создание пользователя 'user'..."); user_ = User(login='user', last_name='Пользователев', first_name='Обычный', role=user_role); user_.set_password('user123'); db.session.add(user_)
        else: print("Пользователь 'user' уже существует или роль User не найдена.")
        db.session.commit(); print("Инициализация контента БД: Завершена.")
    except Exception as e: print(f"ОШИБКА инициализации контента БД: {e}"); db.session.rollback()