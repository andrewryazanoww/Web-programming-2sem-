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
# Путь к файлу БД SQLite. Файл будет создан в той же папке, что и app.py
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Рекомендуется отключать
# ВАЖНО: Установите СЕКРЕТНЫЙ КЛЮЧ через переменную окружения на Render!
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-very-fallback-secret-key-!@#$')
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
    password_hash = db.Column(db.String(128)) # Храним ХЕШ пароля

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Проверяем, что хеш вообще есть (на всякий случай)
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
# !!! ВАЖНО !!! Эта функция будет выполняться при КАЖДОМ запуске приложения на Render
# из-за эфемерной файловой системы. Она создаст БД и пользователя, если их нет.
def initialize_database():
    print("Проверка и инициализация базы данных...")
    # Создаем контекст приложения, чтобы иметь доступ к 'app' и 'db'
    with app.app_context():
        # Создаем все таблицы, определенные в моделях (если они еще не существуют)
        db.create_all()
        print(f"Таблицы проверены/созданы в {app.config['SQLALCHEMY_DATABASE_URI']}")

        # Проверяем, существует ли пользователь 'user'
        existing_user = User.query.filter_by(username='user').first()
        if not existing_user:
            print("Пользователь 'user' не найден, создаем...")
            # Создаем пользователя 'user' с паролем 'qwerty'
            default_user = User(username='user')
            default_user.set_password('qwerty') # Пароль хешируется
            db.session.add(default_user) # Добавляем в сессию SQLAlchemy
            db.session.commit() # Сохраняем изменения в БД
            print("Пользователь 'user' успешно создан.")
        else:
            print("Пользователь 'user' уже существует.")

# !!! ВЫЗОВ ИНИЦИАЛИЗАЦИИ БАЗЫ ДАННЫХ !!!
# Вызываем функцию сразу после определения 'app' и 'db',
# чтобы она выполнилась при импорте модуля Gunicorn'ом на Render.
initialize_database()

# --- Маршруты (Views) ---
@app.route('/')
def index():
    session['visits'] = session.get('visits', 0) + 1
    visits = session['visits']
    if current_user.is_authenticated and session.permanent:
         session.modified = True
    return render_template('index.html', visits=visits)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        # Проверяем пользователя и пароль (с использованием хеша)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Вы успешно вошли!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

@app.route('/secret')
@login_required
def secret_page():
    return render_template('secret.html')

# --- Запуск для локальной разработки ---
# Этот блок НЕ используется Render'ом напрямую, Render использует Procfile и Gunicorn
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # debug=True удобно для локальной разработки, но НИКОГДА не используйте в продакшене (на Render)
    app.run(host='0.0.0.0', port=port, debug=True) # Установите debug=False перед коммитом!