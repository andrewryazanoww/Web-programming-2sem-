import os
import re # Для валидации пароля
from datetime import datetime # Для даты создания
# ИСПРАВЛЕНО: Добавлен импорт abort
from flask import Flask, render_template, redirect, url_for, session, flash, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
# Обновляем импорты WTForms для ясности
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Regexp
from wtforms_sqlalchemy.fields import QuerySelectField # Для выбора роли из БД
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError # Для отлова ошибок уникальности

# --- Конфигурация приложения ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Получение SECRET_KEY ---
SECRET_KEY_FROM_ENV = os.environ.get('SECRET_KEY')
if not SECRET_KEY_FROM_ENV:
    print("ПРЕДУПРЕЖДЕНИЕ: Переменная окружения SECRET_KEY не установлена! Используется небезопасный запасной ключ.")
    # Используйте уникальный и сложный запасной ключ для локальной разработки
    app.config['SECRET_KEY'] = 'local-dev-unsafe-!@#$%^&*()-lab4-final'
else:
    app.config['SECRET_KEY'] = SECRET_KEY_FROM_ENV
    print("SECRET_KEY успешно загружен из переменной окружения.")

app.config['PERMANENT_SESSION_LIFETIME'] = 1800 # 30 минут

# --- Инициализация расширений ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # URL-имя функции входа
login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."
login_manager.login_message_category = "warning" # Категория для flash-сообщений

# --- Модели SQLAlchemy ---

# Модель Роли
class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False) # Название роли
    description = db.Column(db.String(255)) # Описание роли
    # Отношение "один ко многим": одна роль может быть у многих пользователей
    # backref='role' создает виртуальный атрибут user.role
    # lazy='joined' может быть эффективнее для загрузки роли вместе с пользователем, если она часто нужна
    users = db.relationship('User', backref='role', lazy=True)

    def __repr__(self):
        # Строковое представление объекта для отладки
        return f'<Role {self.name}>'

# Модель Пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # Уникальный ID пользователя
    username = db.Column(db.String(80), unique=True, nullable=False) # Логин, уникальный
    password_hash = db.Column(db.String(128), nullable=False) # Хеш пароля, не может быть пустым
    last_name = db.Column(db.String(100), nullable=False) # Фамилия, обязательна
    first_name = db.Column(db.String(100), nullable=False) # Имя, обязательно
    middle_name = db.Column(db.String(100)) # Отчество, может быть пустым (NULL)
    # Внешний ключ, связывающий с таблицей 'role'. nullable=True - роль необязательна.
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)
    # Дата создания записи, устанавливается автоматически при создании
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Метод для установки хеша пароля
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Метод для проверки введенного пароля с хешем
    def check_password(self, password):
        # Проверяем наличие хеша перед сравнением
        return check_password_hash(self.password_hash, password) if self.password_hash else False

    # Динамическое свойство для получения полного имени
    @property
    def full_name(self):
        # Собираем ФИО из частей, пропуская пустые (например, отчество)
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part)

    def __repr__(self):
        # Строковое представление объекта User
        return f'<User {self.username}>'

# --- Загрузчик пользователя для Flask-Login ---
# Эта функция вызывается Flask-Login для получения объекта User по ID из сессии
@login_manager.user_loader
def load_user(user_id):
    # Используем db.session.get (рекомендуется для SQLAlchemy 2.0+)
    return db.session.get(User, int(user_id))

# --- Валидаторы WTForms ---

# Валидатор для символов логина (только латиница и цифры)
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9]+$")
def validate_username_chars(form, field):
    if not USERNAME_REGEX.match(field.data):
        raise ValidationError('Логин должен содержать только латинские буквы и цифры.')

# Валидатор сложности пароля
def validate_password_complexity(form, field):
    password = field.data
    errors = [] # Собираем все ошибки
    # Длина
    if not (8 <= len(password) <= 128):
        errors.append('Пароль должен быть от 8 до 128 символов.')
    # Наличие разных регистров (латиница или кириллица)
    if not (re.search(r"[a-zа-я]", password) and re.search(r"[A-ZА-Я]", password)):
        errors.append('Пароль должен содержать хотя бы одну строчную и одну заглавную букву (лат. или кир.).')
    # Наличие цифры
    if not re.search(r"[0-9]", password):
        errors.append('Пароль должен содержать хотя бы одну цифру.')
    # Отсутствие пробелов
    if re.search(r"\s", password):
        errors.append('Пароль не должен содержать пробелов.')
    # Проверка на допустимые символы (все разрешенные в ТЗ)
    # Экранируем метасимволы regex: \ ] -
    allowed_chars_pattern = re.compile(r"^[a-zA-Zа-яА-Я0-9~!?@#$%^&*_\-+=`|\\(){}\[\]:;\"'<>,.?/]+$")
    if not allowed_chars_pattern.match(password):
        # Находим и показываем недопустимые символы
        invalid_chars = "".join(sorted(list(set(re.sub(allowed_chars_pattern, '', password)))))
        errors.append(f'Пароль содержит недопустимые символы: {invalid_chars}')
    # Если были ошибки, вызываем ValidationError со всеми сообщениями
    if errors:
        raise ValidationError(" ".join(errors))

# --- Формы WTForms ---

# Фабрика запросов для QuerySelectField (получение ролей)
def role_query():
    return Role.query.order_by(Role.name) # Сортируем роли по имени для удобства

# Функция для отображения имени роли в QuerySelectField
def get_role_label(role):
    return role.name

# Общая форма для создания и редактирования пользователя
class UserForm(FlaskForm):
    # Общие поля
    last_name = StringField('Фамилия', validators=[DataRequired("Поле не может быть пустым.")])
    first_name = StringField('Имя', validators=[DataRequired("Поле не может быть пустым.")])
    middle_name = StringField('Отчество') # Необязательное
    role = QuerySelectField('Роль',
                            query_factory=role_query,
                            get_label=get_role_label,
                            allow_blank=True, # Разрешаем не выбирать роль
                            blank_text='-- Не выбрана --') # Текст для пустого варианта

    # Поля только для создания (валидаторы применяются только при создании)
    username = StringField('Логин', validators=[
        DataRequired(message="Поле не может быть пустым."),
        Length(min=5, message="Логин должен быть не менее 5 символов."),
        validate_username_chars # Валидатор символов
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(message="Поле не может быть пустым."),
        validate_password_complexity # Валидатор сложности
    ])
    # Поле для подтверждения пароля, связанное с полем 'password'
    confirm_password = PasswordField('Повторите пароль', validators=[
        DataRequired(message="Поле не может быть пустым."),
        EqualTo('password', message='Пароли должны совпадать.')
    ])

    submit = SubmitField('Сохранить') # Кнопка отправки

# Форма для смены пароля
class PasswordChangeForm(FlaskForm):
    old_password = PasswordField('Старый пароль', validators=[DataRequired("Введите старый пароль.")])
    new_password = PasswordField('Новый пароль', validators=[
        DataRequired("Поле не может быть пустым."),
        validate_password_complexity # Проверяем сложность нового пароля
    ])
    confirm_new_password = PasswordField('Повторите новый пароль', validators=[
        DataRequired("Поле не может быть пустым."),
        EqualTo('new_password', message='Новые пароли должны совпадать.') # Проверяем совпадение новых
    ])
    submit = SubmitField('Изменить пароль')

# --- Инициализация БД и начальных данных ---
# Функция для создания таблиц и начальных данных (роли, пользователь 'user')
def initialize_database():
    print("Инициализация БД: Старт...")
    try:
        # Операции с БД выполняются в контексте приложения
        with app.app_context():
            db.create_all() # Создает таблицы по моделям, если их нет
            print(f"Инициализация БД: Таблицы проверены/созданы в {app.config['SQLALCHEMY_DATABASE_URI']}")

            # Создаем роли по умолчанию, если их нет
            if Role.query.count() == 0:
                print("Инициализация БД: Роли не найдены, создаем Admin, User, Guest...")
                roles = [
                    Role(name='Admin', description='Администратор системы'),
                    Role(name='User', description='Обычный зарегистрированный пользователь'),
                    Role(name='Guest', description='Гость с ограниченным доступом')
                ]
                db.session.add_all(roles)
                db.session.commit()
                print(f"Инициализация БД: Роли созданы.")
            else:
                print("Инициализация БД: Роли уже существуют.")

            # Создаем пользователя 'user' по умолчанию, если его нет
            if not User.query.filter_by(username='user').first():
                print("Инициализация БД: Пользователь 'user' не найден, создаем...")
                default_role = Role.query.filter_by(name='User').first()
                # Создаем пользователя с данными и ролью по умолчанию
                default_user = User(
                    username='user',
                    last_name='Тестовый',
                    first_name='Пользователь',
                    role=default_role # Присваиваем роль 'User'
                )
                # Устанавливаем пароль, который проходит валидацию
                default_user.set_password('Qwerty123!')
                db.session.add(default_user)
                db.session.commit() # Сохраняем пользователя в БД
                role_name = default_role.name if default_role else 'None'
                print(f"Инициализация БД: Пользователь 'user' с ролью '{role_name}' успешно создан.")
            else:
                print("Инициализация БД: Пользователь 'user' уже существует.")
        print("Инициализация БД: Завершена успешно.")
    except Exception as e:
        # Логируем ошибку, если что-то пошло не так
        print(f"ОШИБКА при инициализации базы данных: {e}")
        db.session.rollback() # Откатываем изменения в БД

# Вызываем функцию инициализации при старте приложения
initialize_database()

# --- Маршруты (Представления Flask) ---

# Главная страница - Список пользователей
@app.route('/')
def index():
    # Получаем всех пользователей, сортируем по ID
    users = User.query.order_by(User.id).all()
    # Передаем список пользователей в шаблон
    return render_template('index.html', users=users)

# Страница входа (аутентификация)
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Если пользователь уже вошел, перенаправляем на главную
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # Простая форма входа (можно вынести в отдельный класс)
    class LoginForm(FlaskForm):
        username = StringField('Логин', validators=[DataRequired()])
        password = PasswordField('Пароль', validators=[DataRequired()])
        remember = BooleanField('Запомнить меня')
        submit = SubmitField('Войти')

    form = LoginForm()
    # Если форма отправлена и валидна
    if form.validate_on_submit():
        # Ищем пользователя в БД по логину
        user = User.query.filter_by(username=form.username.data).first()
        # Проверяем, найден ли пользователь и верен ли пароль
        if user and user.check_password(form.password.data):
            # Вход успешен, регистрируем сессию пользователя
            login_user(user, remember=form.remember.data)
            flash('Вы успешно вошли!', 'success')
            # Перенаправляем на запрошенную страницу или на главную
            next_page = request.args.get('next')
            # Безопасное перенаправление только на внутренние страницы
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            # Неверные учетные данные
            flash('Неверный логин или пароль.', 'danger')
    # Отображаем шаблон с формой входа
    return render_template('login.html', form=form)

# Выход пользователя
@app.route('/logout')
@login_required # Доступно только вошедшим пользователям
def logout():
    logout_user() # Завершаем сессию пользователя
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index')) # Перенаправляем на главную

# Просмотр данных конкретного пользователя
@app.route('/user/<int:user_id>')
def view_user(user_id):
    # Получаем пользователя по ID, или возвращаем 404 если не найден
    user = db.session.get(User, user_id) or abort(404)
    # Передаем пользователя в шаблон
    return render_template('user_view.html', user=user)

# Создание нового пользователя
@app.route('/user/create', methods=['GET', 'POST'])
@login_required # Доступно только вошедшим пользователям
def create_user():
    # Используем полную форму UserForm
    form = UserForm()

    # Если форма отправлена (POST) и прошла все валидации
    if form.validate_on_submit():
        try:
            # Создаем новый объект User
            new_user = User(
                username=form.username.data,
                last_name=form.last_name.data,
                first_name=form.first_name.data,
                # Сохраняем None, если отчество не введено
                middle_name=form.middle_name.data or None,
                # Присваиваем выбранную роль (объект Role)
                role=form.role.data
            )
            # Устанавливаем хешированный пароль
            new_user.set_password(form.password.data)
            # Добавляем нового пользователя в сессию БД
            db.session.add(new_user)
            # Сохраняем изменения в БД
            db.session.commit()
            flash(f'Пользователь {new_user.username} успешно создан!', 'success')
            # Перенаправляем на список пользователей
            return redirect(url_for('index'))
        except IntegrityError: # Если логин уже существует (нарушение unique constraint)
            db.session.rollback() # Откатываем транзакцию
            # Добавляем ошибку к полю 'username' для отображения в форме
            form.username.errors.append("Этот логин уже используется.")
            flash('Ошибка создания пользователя: Логин уже занят.', 'danger')
            print("Create User IntegrityError: Username exists") # Лог для отладки
        except Exception as e: # Другие возможные ошибки
            db.session.rollback()
            flash(f'Произошла непредвиденная ошибка при создании пользователя: {e}', 'danger')
            print(f"Create User Exception: {e}") # Лог для отладки
    elif request.method == 'POST':
        # Если метод POST, но валидация не пройдена
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        print(f"Create User Form Validation FAILED. Errors: {form.errors}") # Лог ошибок валидации

    # Отображаем шаблон с формой (для GET или если POST не прошел валидацию)
    # is_edit_mode=False указывает шаблону, что это режим создания
    return render_template('user_form.html', form=form, form_title="Создание пользователя", is_edit_mode=False)


# Редактирование существующего пользователя
@app.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required # Доступно только вошедшим пользователям
def edit_user(user_id):
    # Получаем пользователя для редактирования или 404
    user_to_edit = db.session.get(User, user_id) or abort(404)
    # Создаем форму. При GET-запросе заполняем ее данными пользователя (obj=...)
    form = UserForm(obj=user_to_edit if request.method == 'GET' else None)

    # --- АДАПТАЦИЯ ФОРМЫ ДЛЯ РЕДАКТИРОВАНИЯ ---
    # Удаляем поля, которые не должны изменяться при редактировании
    del form.username
    del form.password
    del form.confirm_password
    # -----------------------------------------

    # Валидация применяется к оставшимся полям (ФИО, Роль)
    if form.validate_on_submit():
        try:
            # Обновляем данные пользователя из формы
            user_to_edit.last_name = form.last_name.data
            user_to_edit.first_name = form.first_name.data
            user_to_edit.middle_name = form.middle_name.data or None
            user_to_edit.role = form.role.data # Обновляем роль
            # Сохраняем изменения
            db.session.commit()
            flash(f'Данные пользователя {user_to_edit.username} успешно обновлены!', 'success')
            # Возвращаемся к списку пользователей
            return redirect(url_for('index'))
        except Exception as e: # Обработка общих ошибок
            db.session.rollback()
            flash(f'Произошла ошибка при обновлении пользователя: {e}', 'danger')
            print(f"Edit User Exception for user {user_id}: {e}") # Лог
    elif request.method == 'POST':
        # Если метод POST, но валидация не пройдена
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        print(f"Edit User Form Validation FAILED. Errors: {form.errors}") # Лог

    # Если GET-запрос, явно устанавливаем текущую роль в селекторе
    # (Иногда obj=... может не сработать для QuerySelectField)
    if request.method == 'GET':
        form.role.data = user_to_edit.role

    # Отображаем шаблон с формой
    # is_edit_mode=True указывает шаблону, что это режим редактирования
    return render_template('user_form.html', form=form, user=user_to_edit, form_title="Редактирование пользователя", is_edit_mode=True)


# Удаление пользователя (обработка POST-запроса из модального окна)
@app.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required # Доступно только вошедшим пользователям
def delete_user(user_id):
    # Получаем пользователя для удаления или 404
    user_to_delete = db.session.get(User, user_id) or abort(404)

    # Запрещаем удалять самого себя
    if user_to_delete.id == current_user.id:
         flash('Вы не можете удалить свою собственную учетную запись.', 'warning')
         return redirect(url_for('index'))

    try:
        username = user_to_delete.username # Сохраняем имя для сообщения
        # Удаляем пользователя из сессии БД
        db.session.delete(user_to_delete)
        # Сохраняем изменения
        db.session.commit()
        flash(f'Пользователь {username} успешно удален.', 'success')
    except Exception as e: # Обработка ошибок при удалении
        db.session.rollback()
        flash(f'Произошла ошибка при удалении пользователя: {e}', 'danger')
        print(f"Error deleting user {user_id}: {e}") # Лог

    # Возвращаемся к списку пользователей
    return redirect(url_for('index'))


# Смена пароля текущего пользователя
@app.route('/change_password', methods=['GET', 'POST'])
@login_required # Доступно только вошедшим пользователям
def change_password():
    form = PasswordChangeForm()
    # Если форма отправлена и валидна (проверены все поля, включая сложность и совпадение новых)
    if form.validate_on_submit():
        # Дополнительно проверяем правильность старого пароля
        if not current_user.check_password(form.old_password.data):
            # Добавляем ошибку к полю old_password для отображения в шаблоне
            form.old_password.errors.append("Неверный старый пароль.")
            flash('Проверьте правильность ввода старого пароля.', 'danger')
        else:
            # Если старый пароль верен, устанавливаем новый
            try:
                current_user.set_password(form.new_password.data)
                db.session.commit() # Сохраняем изменения
                flash('Пароль успешно изменен.', 'success')
                # Перенаправляем на главную страницу
                return redirect(url_for('index'))
            except Exception as e: # Обработка ошибок при сохранении
                 db.session.rollback()
                 flash(f'Произошла ошибка при смене пароля: {e}', 'danger')
                 print(f"Error changing password for user {current_user.id}: {e}") # Лог
    elif request.method == 'POST':
         # Если метод POST, но валидация не пройдена
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        print(f"Change Password Form Validation FAILED. Errors: {form.errors}") # Лог

    # Отображаем шаблон с формой смены пароля
    return render_template('change_password.html', form=form)


# --- Запуск приложения ---
# Этот блок выполняется только при запуске скрипта напрямую (python app.py)
# Он НЕ используется Gunicorn'ом на Render (там используется Procfile)
if __name__ == '__main__':
    # Получаем порт из переменной окружения PORT (устанавливается Render) или используем 5000
    port = int(os.environ.get('PORT', 5000))
    # debug=False ОБЯЗАТЕЛЬНО для продакшена на Render!
    # Установите debug=True только для локальной разработки/отладки
    app.run(host='0.0.0.0', port=port, debug=False)