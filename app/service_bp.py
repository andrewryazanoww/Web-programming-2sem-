# app/service_bp.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import Equipment, ServiceHistory, User, Role
from .forms import ServiceRecordForm
# Импортируем декоратор role_required, если он определен в equipment_bp или в общем месте
from .equipment_bp import role_required # Предполагаем, что он в equipment_bp

bp = Blueprint('service', __name__, url_prefix='/service')

@bp.route('/equipment/<int:equipment_id>/add_record', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'TechSpecialist')
def add_service_record(equipment_id):
    equipment = db.get_or_404(Equipment, equipment_id)
    form = ServiceRecordForm(request.form if request.method == 'POST' else None)

    tech_roles_q = db.session.query(Role).filter(Role.name.in_(['Admin', 'TechSpecialist']))
    tech_ids = [r.id for r in tech_roles_q.all()]
    form.performed_by_id.choices = [(0, '-- Не выбран (внешний исполнитель) --')]
    if tech_ids:
        performers_q = db.session.query(User).filter(User.role_id.in_(tech_ids)).order_by(User.last_name, User.first_name)
        form.performed_by_id.choices.extend([(u.id, u.full_name) for u in performers_q.all()])
    else:
        form.performed_by_id.choices.append((0,'Нет доступных исполнителей')) # Если вдруг нет Admin/Tech ролей

    if form.validate_on_submit():
        try:
            record = ServiceHistory(
                equipment_id=equipment.id,
                service_type=form.service_type.data,
                description=form.description.data,
                planned_date=form.planned_date.data,
                service_date=form.service_date.data,
                status=form.status.data,
                performed_by_id=form.performed_by_id.data if form.performed_by_id.data and form.performed_by_id.data > 0 else None
            )
            db.session.add(record)
            db.session.commit()
            flash('Запись об обслуживании успешно добавлена.', 'success')
            return redirect(url_for('equipment.show', equipment_id=equipment.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении записи: {e}', 'danger')
            current_app.logger.error(f"Ошибка добавления записи обслуживания для {equipment.id}: {e}")
    elif request.method == 'POST':
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')

    return render_template('service/add_record_form.html',
                           form=form,
                           equipment=equipment,
                           title=f"Добавить запись обслуживания для {equipment.name}")

@bp.route('/')
@login_required
@role_required('Admin', 'TechSpecialist')
def index():
    service_events_query = db.select(ServiceHistory).options(
        joinedload(ServiceHistory.equipment).joinedload(Equipment.category),
        joinedload(ServiceHistory.performed_by)
    ).order_by(ServiceHistory.planned_date.asc().nullsfirst(), ServiceHistory.service_date.asc().nullsfirst())
    
    all_service_records = db.session.execute(service_events_query).scalars().all()

    return render_template('service/calendar.html',
                           all_service_records=all_service_records,
                           title="Календарь технического обслуживания")
# TODO: Добавить роуты для редактирования и удаления записей ServiceHistory (если требуется по ТЗ)