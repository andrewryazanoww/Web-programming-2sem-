import os
from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash, check_password_hash

# --- Конфигурация приложения ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# Настройка пути к БД SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Получение SECRET_KEY ---
# ПРАВИЛЬНЫЙ СПОСОБ: Получаем ключ из переменной окружения 'SECRET_KEY'.
# На Render вы ДОЛЖНЫ установить эту переменную окружения в настройках сервиса.
# Второе значение ('a_very_secret_key_for_dev_only') - это ЗАПАСНОЙ ключ, который будет
# использоваться ТОЛЬКО если переменная окружения 'SECRET_KEY' не найдена.
# НЕ ИСПОЛЬЗУЙТЕ ЭТОТ ЗАПАСНОЙ КЛЮЧ В ПРОДАКШЕНЕ (на Render)!
# Сгенерируйте СИЛЬНЫЙ ключ и установите его на Render.
SECRET_KEY_FROM_ENV = os.environ.get('SECRET_KEY')
if not SECRET_KEY_FROM_ENV:
    print("ПРЕДУПРЕЖДЕНИЕ: Переменная окружения SECRET_KEY не установлена! Используется небезопасный запасной ключ. Установите SECRET_KEY на хостинге.")
    app.config['SECRET_KEY'] = 'a_very_secret_key_for_dev_only_$%^&*' # Запасной, не безопасный!
else:
    app.config['SECRET_KEY'] = SECRET_KEY_FROM_ENV
    print("SECRET_KEY успешно загружен из переменной окружения.") # Для отладки на Render

app.config['PERMANENT_SESSION_LIFETIME'] = 1800 # 30 минут

# --- Инициализация расширений ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."
login_manager.login_message_category = "info"

# --- Модель пользователя SQLAlchemy ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# --- Загрузчик пользователя Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Форма входа (без изменений) ---
class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(message="Введите логин.")])
    password = PasswordField('Пароль', validators=[DataRequired(message="Введите пароль.")])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

# --- Функция для инициализации БД и пользователя ---
# Эта функция будет выполняться при КАЖДОМ запуске приложения на Render
# из-за эфемерной файловой системы, создавая БД и пользователя, если их нет.
def initialize_database():
    print("Инициализация БД: Проверка и создание таблиц/пользователя...")
    try:
        # Контекст приложения необходим для операций с БД вне запроса
        with app.app_context():
            db.create_all() # Создает таблицы, если их нет
            print(f"Инициализация БД: Таблицы проверены/созданы в {app.config['SQLALCHEMY_DATABASE_URI']}")

            # Проверяем наличие пользователя 'user'
            existing_user = User.query.filter_by(username='user').first()
            if not existing_user:
                print("Инициализация БД: Пользователь 'user' не найден, создаем...")
                default_user = User(username='user')
                default_user.set_password('qwerty') # Пароль хешируется
                db.session.add(default_user)
                db.session.commit()
                print("Инициализация БД: Пользователь 'user' успешно создан.")
            else:
                print("Инициализация БД: Пользователь 'user' уже существует.")
        print("Инициализация БД: Завершена успешно.")
    except Exception as e:
        # Логируем ошибку, если что-то пошло не так при инициализации
        print(f"ОШИБКА при инициализации базы данных: {e}")
        # В зависимости от критичности, можно либо продолжить работу,
        # либо вызвать sys.exit(1), чтобы контейнер перезапустился.
        # Для этой лабораторной просто логируем.

# --- ВЫЗОВ ИНИЦИАЛИЗАЦИИ БАЗЫ ДАННЫХ ---
# Вызываем функцию сразу после определения 'app' и 'db',
# чтобы она гарантированно выполнилась при старте сервера Gunicorn на Render.
initialize_database()

# --- Маршруты (Views) ---
@app.route('/')
def index():
    # Логика счетчика посещений
    session['visits'] = session.get('visits', 0) + 1
    visits = session['visits']
    # Обработка постоянной сессии
    if current_user.is_authenticated and session.permanent:
         session.modified = True # Явно помечаем для сохранения
    return render_template('index.html', visits=visits)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Логика входа пользователя
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Вы успешно вошли!', 'success')
            next_page = request.args.get('next')
            # Безопасное перенаправление
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    # Логика выхода
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

@app.route('/secret')
@login_required
def secret_page():
    # Доступ только для аутентифицированных
    return render_template('secret.html')

# --- Запуск для локальной разработки ---
# Этот блок НЕ используется Render'ом напрямую (он использует Procfile -> Gunicorn)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Установите debug=True только для локальной разработки!
    # НЕ ЗАБУДЬТЕ ВЫКЛЮЧИТЬ DEBUG ПЕРЕД ДЕПЛОЕМ НА RENDER (установить False)!
    app.run(host='0.0.0.0', port=port, debug=False)