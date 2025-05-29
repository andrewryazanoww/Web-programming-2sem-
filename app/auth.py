from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required
from app import db # Правильный импорт db из пакета app
from app.models import User # <--- ИСПРАВЛЕНО: добавлено 'app.'
from flask_login import LoginManager, current_user # Добавьте, если нет, или убедитесь, что LoginManager доступен

bp = Blueprint('auth', __name__, url_prefix='/auth')
login_manager = LoginManager() # Инициализируем LoginManager здесь, если он не инициализирован в другом месте

def init_login_manager(app):
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."

@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one_or_none()

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        remember = request.form.get('remember_me') == 'on'

        user = db.session.execute(db.select(User).filter_by(login=login)).scalar_one_or_none()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash('Вы успешно вошли!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверный логин или пароль.', 'danger')

    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))