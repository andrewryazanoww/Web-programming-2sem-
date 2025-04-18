import io
import csv
from math import ceil
from flask import (Blueprint, render_template, request, abort, flash,
                   redirect, url_for, Response, stream_with_context, current_app)
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from sqlalchemy.orm import selectinload
# Импорты из других модулей
from extensions import db
from app import VisitLog, User, check_rights # Убедитесь, что в app.py нет глобального 'app'

# Создаем Blueprint
reports_bp = Blueprint('reports', __name__)

# --- Роуты Blueprint'а ---

@reports_bp.route('/')
@login_required
@check_rights('view_logs')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    # Используем контекст приложения для операций с БД
    with current_app.app_context():
        logs_query_base = db.select(VisitLog)
        if not current_user.is_admin():
            logs_query_base = logs_query_base.filter(VisitLog.user_id == current_user.id)
        total_items = db.session.execute(db.select(func.count()).select_from(logs_query_base.subquery())).scalar_one()
        offset = (page - 1) * per_page
        logs_query_paginated = logs_query_base.order_by(VisitLog.created_at.desc()
            ).options(selectinload(VisitLog.user) # Жадная загрузка пользователя
            ).limit(per_page
            ).offset(offset)
        logs = db.session.execute(logs_query_paginated).scalars().all()
        total_pages = ceil(total_items / per_page) if total_items > 0 else 1
        pagination_info = {
            'page': page, 'per_page': per_page, 'total': total_items, 'pages': total_pages,
            'has_prev': page > 1, 'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None, 'next_num': page + 1 if page < total_pages else None,
            'iter_pages': lambda left_edge=1, right_edge=1, left_current=2, right_current=2:
                          range(max(1, page - left_current), min(total_pages, page + right_current) + 1)
        }
    # Строка return должна быть ВНЕ блока with, с отступом на том же уровне, что и 'with'
    return render_template('logs_index.html', logs=logs, pagination=pagination_info)

@reports_bp.route('/pages')
@login_required
@check_rights('view_reports')
def pages_stat():
    with current_app.app_context():
        page_stats = db.session.query(
                VisitLog.path, func.count(VisitLog.id).label('visits')
            ).group_by(VisitLog.path).order_by(desc('visits')).all()
    # Строка return должна быть ВНЕ блока with, с тем же отступом
    return render_template('logs_pages.html', stats=page_stats)

@reports_bp.route('/users')
@login_required
@check_rights('view_reports')
def users_stat():
    with current_app.app_context():
        user_stats_raw = db.session.query(
                User.id, User.last_name, User.first_name, User.middle_name,
                func.count(VisitLog.id).label('visits')
            ).outerjoin(User, VisitLog.user_id == User.id
            # Убираем options(selectinload(User.visit_logs)), т.к. они не нужны здесь
            ).group_by(User.id, User.last_name, User.first_name, User.middle_name
            ).order_by(desc('visits')).all()
    # Обработка и рендеринг происходят вне контекста
    stats_processed = []
    for stat in user_stats_raw:
        user_id, last_name, first_name, middle_name, visits = stat
        full_name = "Неаутентифицированный пользователь"
        if user_id: parts = [last_name, first_name, middle_name]; full_name = " ".join(part for part in parts if part)
        stats_processed.append({'user': full_name, 'visits': visits})
    # Строка return должна быть ВНЕ блока with, с тем же отступом
    return render_template('logs_users.html', stats=stats_processed)

@reports_bp.route('/pages/export')
@login_required
@check_rights('export_reports')
def export_pages_stat():
    with current_app.app_context():
        page_stats = db.session.query(VisitLog.path,func.count(VisitLog.id).label('visits')).group_by(VisitLog.path).order_by(desc('visits')).all()
    # Генерация CSV вне контекста
    si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(['Страница', 'Количество посещений']); cw.writerows(page_stats)
    output = si.getvalue()
    # Строка return должна быть ВНЕ блока with, с тем же отступом
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=report_pages.csv"})

@reports_bp.route('/users/export')
@login_required
@check_rights('export_reports')
def export_users_stat():
    with current_app.app_context():
        user_stats_raw = db.session.query(User.id, User.last_name, User.first_name, User.middle_name, func.count(VisitLog.id).label('visits')).outerjoin(User, VisitLog.user_id == User.id).group_by(User.id, User.last_name, User.first_name, User.middle_name).order_by(desc('visits')).all()
    # Генерация CSV вне контекста
    si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(['Пользователь', 'Количество посещений'])
    for stat in user_stats_raw:
        user_id, last_name, first_name, middle_name, visits = stat
        full_name = "Неаутентифицированный пользователь"
        if user_id: parts = [last_name, first_name, middle_name]; full_name = " ".join(part for part in parts if part)
        cw.writerow([full_name, visits])
    output = si.getvalue()
    # Строка return должна быть ВНЕ блока with, с тем же отступом
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=report_users.csv"})