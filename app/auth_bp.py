# app/auth_bp.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
# Импортируем db из extensions и User из models
from .extensions import db
from .models import User
from .forms import LoginForm # Используем нашу WTForms форму

# Создаем Blueprint с именем 'auth' и префиксом URL '/auth'
bp = Blueprint('auth', __name__, url_prefix='/auth')

# load_user теперь находится в extensions.py и регистрируется через login_manager

@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Если пользователь уже аутентифицирован, перенаправляем на главную
    if current_user.is_authenticated:
        return redirect(url_for('main_bp.index')) # Используем main_bp.index

    form = LoginForm() # Создаем экземпляр нашей формы
    if form.validate_on_submit(): # Если форма отправлена и валидна
        login_val = form.login.data
        password = form.password.data
        remember = form.remember_me.data

        # Ищем пользователя в БД по логину
        user = db.session.execute(
            db.select(User).filter_by(login=login_val)
        ).scalar_one_or_none()

        # Проверяем, найден ли пользователь и правильный ли пароль
        if user and user.check_password(password):
            login_user(user, remember=remember) # Регистрируем сессию пользователя
            flash('Вы успешно вошли в систему.', 'success')
            # Перенаправляем на запрошенную страницу (если есть) или на главную
            next_page = request.args.get('next')
            # Безопасное перенаправление: только на относительные URL внутри сайта
            if next_page and not next_page.startswith(('/', 'http://', 'https://')):
                # Если next_page некорректный, перенаправляем на главную
                current_app.logger.warning(f"Попытка небезопасного редиректа на: {next_page}")
                next_page = url_for('main_bp.index')
            return redirect(next_page or url_for('main_bp.index'))
        else:
            flash('Введены неверные логин и/или пароль.', 'danger')
    # Если GET-запрос или форма невалидна, отображаем шаблон с формой
    return render_template('auth/login.html', form=form, title="Вход в систему")

@bp.route('/logout')
@login_required # Только аутентифицированный пользователь может выйти
def logout():
    logout_user() # Завершаем сессию
    flash('Вы успешно вышли из системы.', 'info')
    return redirect(url_for('main_bp.index')) # Перенаправляем на главную