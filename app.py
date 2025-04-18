import os
import re
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, redirect, url_for, session,
                   flash, request, jsonify, abort, current_app)
# Импортируем UserMixin и др. НЕОБХОДИМЫЕ для роутов и декораторов
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Regexp
from wtforms_sqlalchemy.fields import QuerySelectField
# Убираем импорт werkzeug, т.к. методы пароля теперь в models.py
# from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc

# --- ИМПОРТ РАСШИРЕНИЙ ---
from extensions import db, login_manager

# --- ИМПОРТ МОДЕЛЕЙ ---
# Теперь модели импортируются из отдельного файла
from models import Role, User, VisitLog

# --- Валидаторы WTForms (остаются здесь, т.к. используются в формах здесь) ---
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9]+$")
def validate_username_chars(form, field):
    if not USERNAME_REGEX.match(field.data): raise ValidationError('Логин: лат. буквы и цифры.')
def validate_password_complexity(form, field):
    # ... (код валидатора без изменений) ...
    password = field.data; errors = []
    if not (8 <= len(password) <= 128): errors.append('Пароль: 8-128 симв.')
    if not (re.search(r"[a-zа-я]", password) and re.search(r"[A-ZА-Я]", password)): errors.append('Пароль: нужны разные регистры.')
    if not re.search(r"[0-9]", password): errors.append('Пароль: нужна цифра.')
    if re.search(r"\s", password): errors.append('Пароль: без пробелов.')
    allowed_chars_pattern = re.compile(r"^[a-zA-Zа-яА-Я0-9~!?@#$%^&*_\-+=`|\\(){}\[\]:;\"'<>,.?/]+$")
    if not allowed_chars_pattern.match(password):
        invalid_chars = "".join(sorted(list(set(re.sub(allowed_chars_pattern, '', password)))))
        errors.append(f'Пароль: недоп. символы ({invalid_chars})')
    if errors: raise ValidationError(" ".join(errors))

# --- Функции для форм (остаются здесь) ---
def role_query(): return Role.query.order_by(Role.name) # Использует импортированную модель Role
def get_role_label(role): return role.name

# --- Формы WTForms (остаются здесь) ---
# Используют импортированные валидаторы
class UserForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired("!")])
    first_name = StringField('Имя', validators=[DataRequired("!")])
    middle_name = StringField('Отчество')
    role = QuerySelectField('Роль', query_factory=role_query, get_label=get_role_label, allow_blank=True, blank_text='-- Не выбрана --')
    username = StringField('Логин', validators=[DataRequired("!"), Length(min=5), validate_username_chars])
    password = PasswordField('Пароль', validators=[DataRequired("!"), validate_password_complexity])
    confirm_password = PasswordField('Повтор пароля', validators=[DataRequired("!"), EqualTo('password', 'Пароли не совпадают.')])
    submit = SubmitField('Сохранить')

class PasswordChangeForm(FlaskForm):
    old_password = PasswordField('Старый пароль', validators=[DataRequired("!")])
    new_password = PasswordField('Новый пароль', validators=[DataRequired("!"), validate_password_complexity])
    confirm_new_password = PasswordField('Повтор нового', validators=[DataRequired("!"), EqualTo('new_password', 'Пароли не совпадают.')])
    submit = SubmitField('Изменить пароль')


# --- Декоратор проверки прав (остается здесь) ---
# Использует импортированный current_user
def check_rights(action):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # ... (код декоратора без изменений) ...
            if not current_user.is_authenticated:
                 flash("Требуется аутентификация.", "warning")
                 return redirect(url_for('login', next=request.url))
            if not current_user.role:
                 flash("Роль не назначена.", "danger")
                 return redirect(url_for('index'))
            user_role = current_user.role.name; user_id = current_user.id
            target_user_id = kwargs.get('user_id'); allowed = False
            if user_role == 'Admin': allowed = True
            elif user_role == 'User':
                if action == 'view_profile' and target_user_id == user_id: allowed = True
                elif action == 'edit_user' and target_user_id == user_id: allowed = True
                elif action == 'view_logs': allowed = True
            if not allowed:
                flash("Недостаточно прав.", "danger"); return redirect(url_for('index'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

# --- ФАБРИКА ПРИЛОЖЕНИЯ ---
def create_app():
    app = Flask(__name__) # Создаем экземпляр Flask
    basedir = os.path.abspath(os.path.dirname(__file__))

    # --- Конфигурация приложения ---
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    SECRET_KEY_FROM_ENV = os.environ.get('SECRET_KEY')
    if not SECRET_KEY_FROM_ENV:
        print("ПРЕДУПРЕЖДЕНИЕ ВНУТРИ create_app: SECRET_KEY не установлен!")
        app.config['SECRET_KEY'] = 'fallback-key-for-factory-pattern-!@#$-v5-models' # ЗАМЕНИТЬ НА RENDER
    else: app.config['SECRET_KEY'] = SECRET_KEY_FROM_ENV
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800
    app.config['ITEMS_PER_PAGE'] = 15

    # --- Инициализация расширений С приложением ---
    db.init_app(app) # <-- Инициализируем импортированный db
    login_manager.init_app(app) # <-- Инициализируем импортированный login_manager

    # --- Определяем обработчик before_request ВНУТРИ фабрики ---
    @app.before_request
    def log_visit():
        # Использует импортированные VisitLog, current_user и db
        if request.endpoint and 'static' not in request.endpoint and request.path != '/favicon.ico':
            user_id = current_user.id if current_user.is_authenticated else None
            log_entry = VisitLog(path=request.path, user_id=user_id)
            try:
                db.session.add(log_entry)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"ОШИБКА логирования посещения в before_request: {e}")

    # --- Основные маршруты приложения (определяем ВНУТРИ фабрики) ---
    # Используют импортированные модели, формы, декораторы
    @app.route('/')
    def index():
        users = User.query.order_by(User.id).all() # Используем модель User
        return render_template('index.html', users=users)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # ... (код роута login без изменений, использует User) ...
        if current_user.is_authenticated: return redirect(url_for('index'))
        class LoginForm(FlaskForm):
            username = StringField('Логин', validators=[DataRequired()])
            password = PasswordField('Пароль', validators=[DataRequired()])
            remember = BooleanField('Запомнить меня')
            submit = SubmitField('Войти')
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                flash('Вход выполнен!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page and next_page.startswith('/') else redirect(url_for('index'))
            else: flash('Неверный логин или пароль.', 'danger')
        return render_template('login.html', form=form)


    @app.route('/logout')
    @login_required
    def logout():
        # ... (код роута logout без изменений) ...
        logout_user(); flash('Вы вышли.', 'info'); return redirect(url_for('index'))


    @app.route('/user/<int:user_id>')
    @login_required
    @check_rights('view_profile')
    def view_user(user_id):
        # ... (код роута view_user без изменений, использует User, db.session.get, abort) ...
        if not current_user.is_admin() and current_user.id != user_id:
             flash("Нет прав для просмотра этого профиля.", "danger"); return redirect(url_for('index'))
        user = db.session.get(User, user_id) or abort(404)
        return render_template('user_view.html', user=user)


    @app.route('/user/create', methods=['GET', 'POST'])
    @login_required
    @check_rights('create_user')
    def create_user():
        # ... (код роута create_user без изменений, использует UserForm, User, db) ...
        form = UserForm()
        if form.validate_on_submit():
            try:
                new_user = User(username=form.username.data, last_name=form.last_name.data, first_name=form.first_name.data, middle_name=form.middle_name.data or None, role=form.role.data)
                new_user.set_password(form.password.data)
                db.session.add(new_user); db.session.commit()
                flash(f'Пользователь {new_user.username} создан!', 'success'); return redirect(url_for('index'))
            except IntegrityError: db.session.rollback(); form.username.errors.append("Логин занят."); flash('Ошибка: Логин занят.', 'danger')
            except Exception as e: db.session.rollback(); flash(f'Ошибка создания: {e}', 'danger'); print(f"Create User Err: {e}")
        elif request.method == 'POST': flash('Исправьте ошибки.', 'warning'); print(f"Create User Invalid: {form.errors}")
        return render_template('user_form.html', form=form, form_title="Создание пользователя", is_edit_mode=False)

    @app.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
    @login_required
    @check_rights('edit_user')
    def edit_user(user_id):
        # ... (код роута edit_user без изменений, использует User, UserForm, db) ...
        if not current_user.is_admin() and current_user.id != user_id:
            flash("Нет прав для редакт. этого пользователя.", "danger"); return redirect(url_for('index'))
        user_to_edit = db.session.get(User, user_id) or abort(404)
        form = UserForm(obj=user_to_edit if request.method == 'GET' else None)
        del form.username; del form.password; del form.confirm_password
        can_edit_role = current_user.is_admin()
        if not can_edit_role: form.role.render_kw = {'disabled': 'disabled'}

        if form.validate_on_submit():
            try:
                user_to_edit.last_name = form.last_name.data
                user_to_edit.first_name = form.first_name.data
                user_to_edit.middle_name = form.middle_name.data or None
                if can_edit_role: user_to_edit.role = form.role.data
                db.session.commit()
                flash(f'Данные {user_to_edit.username} обновлены!', 'success'); return redirect(url_for('index'))
            except Exception as e: db.session.rollback(); flash(f'Ошибка обновления: {e}', 'danger'); print(f"Edit User Err: {e}")
        elif request.method == 'POST': flash('Исправьте ошибки.', 'warning'); print(f"Edit User Invalid: {form.errors}")
        if request.method == 'GET': form.role.data = user_to_edit.role
        return render_template('user_form.html', form=form, user=user_to_edit, form_title="Редактирование", is_edit_mode=True, can_edit_role=can_edit_role)


    @app.route('/user/<int:user_id>/delete', methods=['POST'])
    @login_required
    @check_rights('delete_user')
    def delete_user(user_id):
        # ... (код роута delete_user без изменений, использует User, db) ...
        user_to_delete = db.session.get(User, user_id) or abort(404)
        if user_to_delete.id == current_user.id:
             flash('Нельзя удалить себя.', 'warning'); return redirect(url_for('index'))
        try:
            username = user_to_delete.username; db.session.delete(user_to_delete); db.session.commit()
            flash(f'Пользователь {username} удален.', 'success')
        except Exception as e: db.session.rollback(); flash(f'Ошибка удаления: {e}', 'danger'); print(f"Delete User Err: {e}")
        return redirect(url_for('index'))

    @app.route('/change_password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        # ... (код роута change_password без изменений, использует PasswordChangeForm, current_user, db) ...
        form = PasswordChangeForm()
        if form.validate_on_submit():
            if not current_user.check_password(form.old_password.data):
                form.old_password.errors.append("Неверный старый пароль."); flash('Проверьте старый пароль.', 'danger')
            else:
                try:
                    current_user.set_password(form.new_password.data); db.session.commit()
                    flash('Пароль изменен.', 'success'); return redirect(url_for('index'))
                except Exception as e: db.session.rollback(); flash(f'Ошибка смены пароля: {e}', 'danger'); print(f"Change Pass Err: {e}")
        elif request.method == 'POST': flash('Исправьте ошибки.', 'warning'); print(f"Change Pass Invalid: {form.errors}")
        return render_template('change_password.html', form=form)


    # --- Контекстный процессор (определяем ВНУТРИ фабрики) ---
    @app.context_processor
    def inject_permissions():
        # Использует импортированный current_user и модели
        def can(action, target_user_id=None):
            if not current_user.is_authenticated or not current_user.role: return False
            user_role = current_user.role.name; user_id = current_user.id
            if user_role == 'Admin': return action in ['create_user','edit_user','view_profile','delete_user','view_logs','view_reports','export_reports']
            elif user_role == 'User':
                if action == 'view_profile' and target_user_id == user_id: return True
                if action == 'edit_user' and target_user_id == user_id: return True
                if action == 'view_logs': return True
                return False
            return False
        return dict(can=can)

    # --- Импорт и регистрация Blueprint'ов ВНУТРИ фабрики ---
    # ИМПОРТ ЗДЕСЬ
    from reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/logs')
    print("Blueprint 'reports' зарегистрирован внутри create_app.")

    # --- Инициализация БД (вызываем ВНУТРИ фабрики) ---
    with app.app_context():
        db.create_all() # Создаем таблицы
        print("Инициализация БД: Таблицы созданы (если не существовали).")
        initialize_database_content() # Наполняем данными

    return app # Возвращаем настроенное приложение

# --- Функция инициализации КОНТЕНТА БД ---
# Использует глобальные модели Role, User и импортированный db
def initialize_database_content():
    print("Инициализация контента БД: Старт...")
    try:
        # Используем db.session для всех запросов
        if db.session.query(Role).count() == 0:
            print("Инициализация контента БД: Создаем роли Admin, User, Guest...")
            roles = [Role(name='Admin'), Role(name='User'), Role(name='Guest')]
            db.session.add_all(roles)
        else: print("Инициализация контента БД: Роли существуют.")

        admin_role = db.session.query(Role).filter_by(name='Admin').first()
        user_role = db.session.query(Role).filter_by(name='User').first()

        admin_exists = db.session.query(User).filter_by(username='admin').first() is not None
        if not admin_exists and admin_role:
            print("Инициализация контента БД: Создаем 'admin'...")
            admin_user = User(username='admin', last_name='Админов', first_name='Админ', role=admin_role)
            admin_user.set_password('Admin123!')
            db.session.add(admin_user)
        else:
             if admin_exists: print("Инициализация контента БД: 'admin' существует.")
             if not admin_role: print("Инициализация контента БД: Роль Admin не найдена для 'admin'.")

        user_obj = db.session.query(User).filter_by(username='user').first()
        if not user_obj and user_role:
            print("Инициализация контента БД: Создаем 'user'...")
            user_obj_new = User(username='user', last_name='Тестовый', first_name='Пользователь', role=user_role)
            user_obj_new.set_password('User123!')
            db.session.add(user_obj_new)
        elif user_obj and not user_obj.role and user_role:
             print("Инициализация контента БД: Обновляем роль для 'user'...")
             user_obj.role = user_role
             db.session.add(user_obj)
        else:
            if user_obj: print("Инициализация контента БД: 'user' существует/имеет роль.")
            if not user_role: print("Инициализация контента БД: Роль User не найдена для 'user'.")

        db.session.commit() # Делаем один commit в конце
        print("Инициализация контента БД: Завершена (commit выполнен).")

    except Exception as e:
        print(f"ОШИБКА инициализации контента БД: {e}"); db.session.rollback()


# --- Запуск приложения (если файл запущен напрямую) ---
if __name__ == '__main__':
    app = create_app() # Создаем экземпляр приложения с помощью фабрики
    port = int(os.environ.get('PORT', 5000))
    # debug=False для Render!
    app.run(host='0.0.0.0', port=port, debug=False)