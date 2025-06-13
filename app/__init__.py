# app/__init__.py
import os
from flask import (Flask, render_template, send_from_directory, current_app,
                   abort, Blueprint, redirect, url_for) # Добавил Blueprint, redirect, url_for
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime as dt_for_context # Переименовал для ясности в контекстном процессоре

# Импортируем расширения из extensions.py
from .extensions import db, login_manager
# Импортируем модели из models.py (только те, что нужны для main_bp или инициализации)
from .models import Category, Image # User и Role будут импортированы в initialize_database_content

# --- ФАБРИКА ПРИЛОЖЕНИЯ ---
def create_app(config_filename='config.py'): # Можно передать имя файла конфигурации
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # --- Загрузка конфигурации ---
    # Предполагаем, что config.py находится в той же папке, что и __init__.py (т.е. в 'app/')
    # app.config.from_pyfile(config_filename, silent=False)
    # Более надежный способ, если config.py точно в папке 'app'
    cfg_path = os.path.join(os.path.dirname(__file__), config_filename)
    if os.path.exists(cfg_path):
        app.config.from_pyfile(cfg_path, silent=False)
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл конфигурации '{cfg_path}' не найден. Используются значения по умолчанию.")
        app.config.setdefault('SECRET_KEY', 'default_ بسیار_secret_key_please_change_in_prod')
        project_root_for_db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///' + os.path.join(project_root_for_db, 'default_office_ais.db'))
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        app.config.setdefault('SQLALCHEMY_ECHO', False)
        app.config.setdefault('UPLOAD_FOLDER_EQUIPMENT', os.path.join(app.root_path, 'media', 'equipment_images'))
        app.config.setdefault('ITEMS_PER_PAGE_EQUIPMENT', 10)
        app.config.setdefault('ITEMS_PER_PAGE_REVIEWS', 5) # Добавил для отзывов

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

    # --- Обработчики ошибок ---
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(err):
        app.logger.error(f"SQLAlchemy Error: {err}") # Логируем ошибку
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
        app.logger.error(f"Internal Server Error: {e}") # Логируем исходную ошибку
        # В боевом режиме исходную ошибку 'e' пользователю не показываем
        return render_template('error.html', error_message="Произошла внутренняя ошибка сервера. Пожалуйста, попробуйте позже.", status_code=500), 500


    # --- Регистрация Blueprint'ов ---
    # Импортируем Blueprint'ы здесь, чтобы избежать циклических зависимостей
    from .auth_bp import bp as auth_blueprint
    from .equipment_bp import bp as equipment_blueprint
    from .service_bp import bp as service_blueprint

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(equipment_blueprint)
    app.register_blueprint(service_blueprint)
    print("Blueprint'ы auth, equipment, service зарегистрированы.")

    # Создаем основной Blueprint для общих роутов (index, images)
    main_bp = Blueprint('main_bp', __name__)

    @main_bp.route('/')
    def index():
        # Главная страница теперь редиректит на список оборудования
        return redirect(url_for('equipment.index'))

    @main_bp.route('/images/equipment/<image_id>') # Путь для изображений оборудования
    def image_file(image_id):
        # Используем модели, импортированные в начале этого файла
        img = db.session.get(Image, image_id)
        if img is None:
            app.logger.warning(f"Запрошено несуществующее изображение: {image_id}")
            abort(404)
        # current_app доступен внутри роута
        return send_from_directory(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img.storage_filename)

    app.register_blueprint(main_bp)
    print("Blueprint 'main_bp' зарегистрирован.")

    # --- Контекстный процессор для передачи 'now' и 'can()' в шаблоны ---
    @app.context_processor
    def inject_current_time_and_permissions():
        from flask_login import current_user # Импортируем current_user здесь
        # from .models import User, Role # Модели уже импортированы глобально или в auth_bp
                                        # но для ясности можно импортировать User и Role здесь,
                                        # если check_rights их использует напрямую

        def can(action, target_user_id=None):
            if not current_user.is_authenticated or not current_user.role:
                return False

            user_role = current_user.role.name
            # Права для Администратора
            if user_role == 'Admin':
                return action in [
                    'view_equipment_list', 'view_equipment_detail',
                    'create_equipment', 'edit_equipment', 'delete_equipment',
                    'add_service_record', 'view_service_history',
                    # Добавьте другие действия, если они есть (например, управление пользователями)
                ]
            # Права для Технического специалиста
            elif user_role == 'TechSpecialist':
                if action == 'view_equipment_list': return True
                if action == 'view_equipment_detail': return True
                if action == 'add_service_record': return True
                if action == 'view_service_history': return True
                # Тех. специалист не может создавать, редактировать, удалять оборудование
                return False
            # Права для Пользователя
            elif user_role == 'User':
                if action == 'view_equipment_list': return True
                if action == 'view_equipment_detail': return True
                # Пользователь не может ничего другого
                return False
            return False # Для других ролей или если роль не определена

        # Передаем 'now' для использования в футере (например, {{ now.year }})
        # и функцию 'can' для проверки прав в шаблонах
        return dict(now=dt_for_context.utcnow(), can=can)


    # --- Инициализация БД: создание таблиц и начальных данных ---
    # Выполняется при каждом создании экземпляра приложения,
    # но initialize_database_content имеет проверки на существование данных
    with app.app_context():
        db.create_all() # Создает все таблицы на основе моделей, если их еще нет
        print("Таблицы базы данных проверены/созданы.")
        initialize_database_content(app) # Передаем app для доступа к config, если он там нужен

    return app # Фабрика возвращает настроенный экземпляр приложения

# --- Функция для создания начальных данных в БД ---
def initialize_database_content(current_app_instance): # Принимает экземпляр app
    # Импортируем модели здесь, чтобы избежать проблем с контекстом при инициализации
    # и гарантировать, что db уже связан с app
    from .models import User, Role, Category
    print("Инициализация контента БД: Старт...")
    try:
        # Создаем Роли, если их нет
        if db.session.query(Role).count() == 0:
            print("Создание ролей по умолчанию: Admin, TechSpecialist, User...")
            roles_data = [
                {'name': 'Admin', 'description': 'Полный доступ ко всем функциям системы.'},
                {'name': 'TechSpecialist', 'description': 'Технический специалист, доступ к оборудованию и добавлению записей обслуживания.'},
                {'name': 'User', 'description': 'Пользователь, только просмотр информации об оборудовании.'}
            ]
            for role_data in roles_data:
                db.session.add(Role(**role_data))
            # Коммит после добавления всех ролей
            db.session.commit()
            print("Роли созданы.")
        else:
            print("Роли уже существуют.")

        # Создаем Категории, если их нет
        if db.session.query(Category).count() == 0:
            print("Создание категорий оборудования по умолчанию...")
            categories_data = [
                {'name': 'Компьютеры', 'description': 'Настольные ПК, моноблоки, серверы.'},
                {'name': 'Ноутбуки', 'description': 'Портативные компьютеры.'},
                {'name': 'Принтеры и МФУ', 'description': 'Лазерные, струйные, многофункциональные устройства.'},
                {'name': 'Сканеры', 'description': 'Планшетные, протяжные сканеры.'},
                {'name': 'Сетевое оборудование', 'description': 'Маршрутизаторы, коммутаторы, точки доступа.'},
                {'name': 'Периферия', 'description': 'Мониторы, клавиатуры, мыши, ИБП.'}
            ]
            for cat_data in categories_data:
                db.session.add(Category(**cat_data))
            db.session.commit() # Коммит после добавления всех категорий
            print("Категории созданы.")
        else:
            print("Категории уже существуют.")

        # Получаем созданные роли для присвоения пользователям
        admin_role = db.session.query(Role).filter_by(name='Admin').first()
        tech_role = db.session.query(Role).filter_by(name='TechSpecialist').first()
        user_role = db.session.query(Role).filter_by(name='User').first()

        # Создаем пользователей по умолчанию
        if db.session.query(User).filter_by(login='admin').first() is None and admin_role:
            print("Создание пользователя 'admin'...")
            admin = User(login='admin', last_name='Администраторов', first_name='Главный', role=admin_role)
            admin.set_password('admin123') # ВАЖНО: Смените этот пароль при деплое!
            db.session.add(admin)
        else: print("Пользователь 'admin' уже существует или роль Admin не найдена.")

        if db.session.query(User).filter_by(login='tech').first() is None and tech_role:
            print("Создание пользователя 'tech'...")
            tech = User(login='tech', last_name='Специалистов', first_name='Техник', role=tech_role)
            tech.set_password('tech123') # ВАЖНО: Смените этот пароль!
            db.session.add(tech)
        else: print("Пользователь 'tech' уже существует или роль TechSpecialist не найдена.")

        if db.session.query(User).filter_by(login='user').first() is None and user_role:
            print("Создание пользователя 'user'...")
            user_ = User(login='user', last_name='Пользователев', first_name='Обычный', role=user_role)
            user_.set_password('user123') # ВАЖНО: Смените этот пароль!
            db.session.add(user_)
        else: print("Пользователь 'user' уже существует или роль User не найдена.")

        db.session.commit() # Финальный коммит для пользователей
        print("Инициализация контента БД: Завершена.")
    except Exception as e:
        print(f"ОШИБКА инициализации контента БД: {e}")
        db.session.rollback() # Откатываем транзакцию при любой ошибке