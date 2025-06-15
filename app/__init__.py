# app/__init__.py
import os
import re
from markupsafe import escape, Markup # Для nl2br фильтра
from datetime import datetime as dt_for_context # Переименован для ясности в контекстном процессоре
from functools import wraps # Для декораторов
from flask import (Flask, render_template, send_from_directory, current_app,
                   abort, Blueprint, redirect, url_for, session, flash) # Добавлены session и flash
from sqlalchemy.exc import SQLAlchemyError

# Импортируем расширения из extensions.py
from .extensions import db, login_manager
# Импортируем модели из models.py
# Важно импортировать ВСЕ модели, которые будут использоваться в db.create_all()
# и в функции initialize_database_content()
from .models import Category, Image, User, Role, Equipment, ServiceHistory

# --- ФАБРИКА ПРИЛОЖЕНИЯ ---
def create_app(config_filename='config.py'):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # --- Загрузка конфигурации ---
    cfg_path = os.path.join(os.path.dirname(__file__), config_filename)
    if os.path.exists(cfg_path):
        app.config.from_pyfile(cfg_path, silent=False)
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл конфигурации '{cfg_path}' не найден. Используются значения по умолчанию.")
        app.config.setdefault('SECRET_KEY', 'a_very_secure_default_secret_key_!@#$_exam_final')
        project_root_for_db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///' + os.path.join(project_root_for_db, 'office_ais.db'))
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        app.config.setdefault('SQLALCHEMY_ECHO', False) # Установите True для отладки SQL
        app.config.setdefault('UPLOAD_FOLDER_EQUIPMENT', os.path.join(app.root_path, 'media', 'equipment_images'))
        app.config.setdefault('ITEMS_PER_PAGE_EQUIPMENT', 10)
        app.config.setdefault('ITEMS_PER_PAGE_SERVICE_HISTORY', 10) # Если будет отдельная пагинация для истории
        app.config.setdefault('REMEMBER_COOKIE_DURATION', 2592000) # 30 дней

    # Убедимся, что папка для загрузок существует
    upload_folder_path = app.config.get('UPLOAD_FOLDER_EQUIPMENT')
    if upload_folder_path and not os.path.exists(upload_folder_path):
        try:
            os.makedirs(upload_folder_path)
            print(f"Создана папка UPLOAD_FOLDER_EQUIPMENT: {upload_folder_path}")
        except OSError as e:
            print(f"Не удалось создать папку UPLOAD_FOLDER_EQUIPMENT {upload_folder_path}: {e}")

    # --- Инициализация расширений ---
    db.init_app(app)
    login_manager.init_app(app)
    # login_manager.user_loader уже определен в extensions.py

    # --- Кастомный фильтр Jinja2 для nl2br ---
    def nl2br_filter(value):
        if value is None:
            return ''
        escaped_value = escape(str(value)) # Экранируем HTML для безопасности
        return Markup(re.sub(r'(\r\n|\n|\r)', '<br>\n', escaped_value)) # Заменяем переносы на <br>
    app.jinja_env.filters['nl2br'] = nl2br_filter
    print("Кастомный фильтр 'nl2br' зарегистрирован.")

    # --- Обработчики ошибок ---
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(err):
        app.logger.error(f"SQLAlchemy Error: {err}") # Логируем ошибку
        db.session.rollback() # Важно откатить транзакцию
        return render_template('error.html', error_message='Ошибка при работе с базой данных. Попробуйте позже.', status_code=500), 500

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
        return render_template('error.html', error_message="Произошла внутренняя ошибка сервера. Пожалуйста, попробуйте позже.", status_code=500), 500

    # --- Регистрация Blueprint'ов ---
    # Импортируем Blueprint'ы здесь, ПОСЛЕ инициализации app и расширений
    from .auth_bp import bp as auth_blueprint
    from .equipment_bp import bp as equipment_blueprint
    from .service_bp import bp as service_blueprint

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(equipment_blueprint)
    app.register_blueprint(service_blueprint)
    print("Blueprint'ы auth, equipment, service зарегистрированы.")

    # Создаем основной Blueprint для общих роутов
    main_bp = Blueprint('main_bp', __name__)
    @main_bp.route('/')
    def index():
        return redirect(url_for('equipment.index')) # Главная редиректит на список оборудования

    @main_bp.route('/images/equipment/<image_id>')
    def image_file(image_id): # Имя параметра совпадает с тем, что в url_for в модели Image
        img = db.session.get(Image, image_id)
        if img is None:
            app.logger.warning(f"Запрошено несуществующее изображение по ID: {image_id}")
            abort(404)
        return send_from_directory(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img.storage_filename)
    app.register_blueprint(main_bp)
    print("Blueprint 'main_bp' зарегистрирован.")

    # --- Контекстный процессор для передачи 'now' и 'can()' в шаблоны ---
    @app.context_processor
    def inject_current_time_and_permissions():
        from flask_login import current_user # Импорт внутри функции

        def can(action, target_user_id=None): # target_user_id пока не используется в логике, но может пригодиться
            if not current_user.is_authenticated or not current_user.role:
                return False
            user_role = current_user.role.name
            # Права для Администратора
            if user_role == 'Admin':
                return action in [
                    'view_equipment_list', 'view_equipment_detail',
                    'create_equipment', 'edit_equipment', 'delete_equipment',
                    'add_service_record', 'view_service_history' # Для ссылки в меню и доступа к календарю
                ]
            # Права для Технического специалиста
            elif user_role == 'TechSpecialist':
                return action in [
                    'view_equipment_list', 'view_equipment_detail',
                    'add_service_record', 'view_service_history' # Для ссылки в меню и доступа к календарю
                ]
            # Права для Пользователя
            elif user_role == 'User':
                return action in [
                    'view_equipment_list', 'view_equipment_detail'
                ]
            return False
        return dict(now=dt_for_context.utcnow(), can=can)

    # --- Инициализация БД: создание таблиц и начальных данных ---
    with app.app_context():
        db.create_all() # Создает все таблицы на основе моделей, если их еще нет
        print("Таблицы базы данных проверены/созданы.")
        initialize_database_content() # Наполняем начальными данными

    return app

# --- Функция для создания начальных данных в БД ---
def initialize_database_content():
    # Модели Role, User, Category уже импортированы в начале этого файла __init__.py
    print("Инициализация контента БД: Старт...")
    try:
        # Создаем Роли
        if db.session.query(Role).count() == 0:
            print("Создание ролей по умолчанию: Admin, TechSpecialist, User...")
            roles_data = [
                {'name': 'Admin', 'description': 'Полный доступ ко всем функциям системы.'},
                {'name': 'TechSpecialist', 'description': 'Технический специалист, доступ к оборудованию и добавлению записей обслуживания.'},
                {'name': 'User', 'description': 'Пользователь, только просмотр информации об оборудовании.'}
            ]
            for role_data in roles_data:
                db.session.add(Role(**role_data))
            db.session.commit()
            print("Роли созданы.")
        else:
            print("Роли уже существуют.")

        # Создаем Категории
        if db.session.query(Category).count() == 0:
            print("Создание категорий оборудования по умолчанию...")
            categories_data = [
                {'name': 'Компьютеры', 'description': 'Настольные ПК, моноблоки, серверы.'},
                {'name': 'Ноутбуки', 'description': 'Портативные компьютеры.'},
                {'name': 'Принтеры и МФУ', 'description': 'Лазерные, струйные, многофункциональные устройства.'},
                {'name': 'Сканеры', 'description': 'Планшетные, протяжные сканеры.'},
                {'name': 'Сетевое оборудование', 'description': 'Маршрутизаторы, коммутаторы, точки доступа.'},
                {'name': 'Периферия', 'description': 'Мониторы, клавиатуры, мыши, ИБП.'},
                {'name': 'IP Телефоны', 'description': 'Стационарные IP-телефоны.'}
            ]
            for cat_data in categories_data:
                db.session.add(Category(**cat_data))
            db.session.commit()
            print("Категории созданы.")
        else:
            print("Категории уже существуют.")

        # Получаем созданные роли для присвоения пользователям
        admin_role = db.session.query(Role).filter_by(name='Admin').first()
        tech_role = db.session.query(Role).filter_by(name='TechSpecialist').first()
        user_role = db.session.query(Role).filter_by(name='User').first()

        # Создаем пользователей по умолчанию
        if admin_role and db.session.query(User).filter_by(login='admin').first() is None:
            print("Создание пользователя 'admin'...")
            admin = User(login='admin', last_name='Администраторов', first_name='Главный', role=admin_role)
            admin.set_password('admin123') # ВАЖНО: Используйте более надежный пароль!
            db.session.add(admin)
        else:
            if not admin_role: print("Роль 'Admin' не найдена, пользователь 'admin' не создан.")
            elif db.session.query(User).filter_by(login='admin').first(): print("Пользователь 'admin' уже существует.")


        if tech_role and db.session.query(User).filter_by(login='tech').first() is None:
            print("Создание пользователя 'tech'...")
            tech = User(login='tech', last_name='Специалистов', first_name='Техник', role=tech_role)
            tech.set_password('tech123') # ВАЖНО: Используйте более надежный пароль!
            db.session.add(tech)
        else:
            if not tech_role: print("Роль 'TechSpecialist' не найдена, пользователь 'tech' не создан.")
            elif db.session.query(User).filter_by(login='tech').first(): print("Пользователь 'tech' уже существует.")


        if user_role and db.session.query(User).filter_by(login='user').first() is None:
            print("Создание пользователя 'user'...")
            user_ = User(login='user', last_name='Пользователев', first_name='Обычный', role=user_role)
            user_.set_password('user123') # ВАЖНО: Используйте более надежный пароль!
            db.session.add(user_)
        else:
            if not user_role: print("Роль 'User' не найдена, пользователь 'user' не создан.")
            elif db.session.query(User).filter_by(login='user').first(): print("Пользователь 'user' уже существует.")


        db.session.commit() # Финальный коммит для пользователей, если они были добавлены
        print("Пользователи проверены/созданы.")
        print("Инициализация контента БД: Завершена.")
    except Exception as e:
        print(f"ОШИБКА инициализации контента БД: {e}")
        db.session.rollback() # Откатываем транзакцию при любой ошибке

# Этот блок if __name__ == '__main__': здесь не нужен, если вы всегда запускаете через run.py
# Но он не мешает, если его оставить.
# if __name__ == '__main__':
#     app = create_app()
#     port = int(os.environ.get('PORT', 5000))
#     app.run(host='0.0.0.0', port=port, debug=True)