# app/__init__.py
import os
import re
from markupsafe import escape, Markup # Для nl2br
from datetime import datetime as dt_for_context
from functools import wraps
from flask import (Flask, render_template, send_from_directory, current_app,
                   abort, Blueprint, redirect, url_for, session, flash)
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db, login_manager
from .models import Category, Image, User, Role, Equipment, ServiceHistory

def create_app(config_filename='config.py'):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    cfg_path = os.path.join(os.path.dirname(__file__), config_filename)
    if os.path.exists(cfg_path): app.config.from_pyfile(cfg_path, silent=False)
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл конфигурации '{cfg_path}' не найден.")
        app.config.setdefault('SECRET_KEY', 'dev_key_!@#_ais_office_final_v_all_files')
        project_root_for_db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///' + os.path.join(project_root_for_db, 'office_ais.db'))
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False); app.config.setdefault('SQLALCHEMY_ECHO', False)
        app.config.setdefault('UPLOAD_FOLDER_EQUIPMENT', os.path.join(app.root_path, 'media', 'equipment_images'))
        app.config.setdefault('ITEMS_PER_PAGE_EQUIPMENT', 10); app.config.setdefault('ITEMS_PER_PAGE_SERVICE_HISTORY', 10)
        app.config.setdefault('REMEMBER_COOKIE_DURATION', 2592000)

    upload_folder_path = app.config.get('UPLOAD_FOLDER_EQUIPMENT')
    if upload_folder_path and not os.path.exists(upload_folder_path):
        try: os.makedirs(upload_folder_path); print(f"Папка {upload_folder_path} создана")
        except OSError as e: print(f"Ошибка создания папки {upload_folder_path}: {e}")

    db.init_app(app)
    login_manager.init_app(app)

    def nl2br_filter(value):
        if value is None: return ''
        escaped_value = escape(str(value))
        return Markup(re.sub(r'(\r\n|\n|\r)', '<br>\n', escaped_value))
    app.jinja_env.filters['nl2br'] = nl2br_filter
    print("Фильтр 'nl2br' зарегистрирован.")

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(err): app.logger.error(f"SQLAlchemy Err: {err}"); db.session.rollback(); return render_template('error.html', error_message='Ошибка БД.', status_code=500), 500
    @app.errorhandler(404)
    def page_not_found(e): return render_template('error.html', error_message="Страница не найдена.", status_code=404), 404
    @app.errorhandler(403)
    def forbidden_error(e): return render_template('error.html', error_message="Доступ запрещен.", status_code=403), 403
    @app.errorhandler(500)
    def internal_server_error(e):
        original_exception = getattr(e, "original_exception", None)
        app.logger.error(f"Internal Server Err: {e} (Original: {original_exception})")
        return render_template('error.html', error_message="Внутренняя ошибка.", status_code=500), 500

    from .auth_bp import bp as auth_blueprint
    from .equipment_bp import bp as equipment_blueprint
    from .service_bp import bp as service_blueprint
    app.register_blueprint(auth_blueprint); app.register_blueprint(equipment_blueprint); app.register_blueprint(service_blueprint)
    print("Blueprint'ы auth, equipment, service зарегистрированы.")

    main_bp = Blueprint('main_bp', __name__)
    @main_bp.route('/')
    def index(): return redirect(url_for('equipment.index'))
    @main_bp.route('/images/equipment/<image_id>')
    def image_file(image_id):
        img = db.session.get(Image, image_id);
        if img is None: abort(404)
        return send_from_directory(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img.storage_filename)
    app.register_blueprint(main_bp); print("Blueprint 'main_bp' зарегистрирован.")

    @app.context_processor
    def inject_current_time_and_permissions():
        from flask_login import current_user
        def can(action, target_user_id=None):
            if not current_user.is_authenticated or not current_user.role: return False
            user_role = current_user.role.name;
            if user_role == 'Admin': return action in ['view_equipment_list','view_equipment_detail','create_equipment','edit_equipment','delete_equipment','add_service_record','view_service_history']
            elif user_role == 'TechSpecialist': return action in ['view_equipment_list','view_equipment_detail','add_service_record','view_service_history']
            elif user_role == 'User': return action in ['view_equipment_list','view_equipment_detail']
            return False
        return dict(now=dt_for_context.utcnow(), can=can)

    with app.app_context():
        db.create_all(); print("Таблицы БД проверены/созданы.")
        initialize_database_content()
    return app

def initialize_database_content():
    print("Инициализация контента БД: Старт...")
    try:
        if db.session.query(Role).count() == 0:
            print("Создание ролей..."); roles_data = [{'name': 'Admin'},{'name': 'TechSpecialist'},{'name': 'User'}]
            for rd in roles_data: db.session.add(Role(**rd))
            db.session.commit(); print("Роли созданы.")
        if db.session.query(Category).count() == 0:
            print("Создание категорий..."); categories_data = [{'name': 'Компьютеры'},{'name': 'Ноутбуки'},{'name': 'Принтеры и МФУ'}]
            for cd in categories_data: db.session.add(Category(**cd))
            db.session.commit(); print("Категории созданы.")
        admin_role = db.session.query(Role).filter_by(name='Admin').first()
        tech_role = db.session.query(Role).filter_by(name='TechSpecialist').first()
        user_role = db.session.query(Role).filter_by(name='User').first()
        if admin_role and db.session.query(User).filter_by(login='admin').first() is None:
            print("Создание 'admin'..."); admin = User(login='admin',last_name='Администраторов',first_name='Главный',role=admin_role); admin.set_password('admin123'); db.session.add(admin)
        if tech_role and db.session.query(User).filter_by(login='tech').first() is None:
            print("Создание 'tech'..."); tech = User(login='tech',last_name='Специалистов',first_name='Техник',role=tech_role); tech.set_password('tech123'); db.session.add(tech)
        if user_role and db.session.query(User).filter_by(login='user').first() is None:
            print("Создание 'user'..."); user_ = User(login='user',last_name='Пользователев',first_name='Обычный',role=user_role); user_.set_password('user123'); db.session.add(user_)
        db.session.commit(); print("Пользователи проверены/созданы.")
        print("Инициализация контента БД: Завершена.")
    except Exception as e: print(f"ОШИБКА инициализации контента БД: {e}"); db.session.rollback()