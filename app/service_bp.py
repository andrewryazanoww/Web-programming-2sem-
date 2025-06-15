# app/service_bp.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload # Для жадной загрузки
from sqlalchemy.exc import SQLAlchemyError # Для обработки ошибок БД
from math import ceil # Для пагинации (хотя здесь не используется, но было в прошлой версии)

# Импортируем из наших модулей
from .extensions import db
from .models import Equipment, ServiceHistory, User, Role # Убедитесь, что все модели импортированы
from .forms import ServiceRecordForm
# Импортируем декоратор role_required, если он в equipment_bp или в общем auth_utils.py
from .equipment_bp import role_required # Предполагаем, что он определен в equipment_bp

bp = Blueprint('service', __name__, url_prefix='/service')

@bp.route('/equipment/<int:equipment_id>/add_record', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'TechSpecialist') # Только Админ и Тех.Специалист могут добавлять записи
def add_service_record(equipment_id):
    equipment = db.get_or_404(Equipment, equipment_id)
    # Если POST, форма заполняется из request.form, иначе пустая
    form = ServiceRecordForm(request.form if request.method == 'POST' else None)

    # Динамическое заполнение списка исполнителей (Админы и Тех.Специалисты)
    # Это нужно делать при каждом запросе (GET или POST с ошибками) для корректного отображения
    tech_roles_query = db.session.query(Role).filter(Role.name.in_(['Admin', 'TechSpecialist']))
    tech_role_ids = [role.id for role in tech_roles_query.all()]

    current_choices = [(0, '-- Не выбран (внешний исполнитель) --')] # Вариант по умолчанию
    if tech_role_ids:
        performers_query = db.session.query(User).filter(User.role_id.in_(tech_role_ids)).order_by(User.last_name, User.first_name)
        current_choices.extend([(user.id, user.full_name) for user in performers_query.all()])
    form.performed_by_id.choices = current_choices


    if form.validate_on_submit():
        try:
            record = ServiceHistory(
                equipment_id=equipment.id,
                service_type=form.service_type.data,
                description=form.description.data,
                planned_date=form.planned_date.data,
                service_date=form.service_date.data, # Может быть None
                status=form.status.data,
                # Сохраняем None, если выбрано "-- Не выбран --" (ID=0) или поле не отправлено
                performed_by_id=form.performed_by_id.data if form.performed_by_id.data and form.performed_by_id.data > 0 else None
            )
            db.session.add(record)
            db.session.commit()
            flash('Запись об обслуживании успешно добавлена.', 'success')
            return redirect(url_for('equipment.show', equipment_id=equipment.id)) # Возвращаемся на страницу оборудования
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении записи об обслуживании: {e}', 'danger')
            current_app.logger.error(f"Ошибка добавления записи обслуживания для оборудования ID {equipment.id}: {e}")
    elif request.method == 'POST' and not form.validate(): # Если POST и есть ошибки валидации
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        current_app.logger.warning(f"Ошибки валидации формы ServiceRecordForm: {form.errors}")

    # Для GET-запроса или если форма POST невалидна, отображаем шаблон с формой
    # Форма добавления может быть на отдельной странице или встроенной.
    # Этот роут предполагает отдельную страницу.
    return render_template(
        'service/add_record_form.html',
        form=form,
        equipment=equipment,
        title=f"Добавить запись обслуживания для {equipment.name}"
    )

@bp.route('/')
@login_required
@role_required('Admin', 'TechSpecialist') # Только они видят календарь
def index():
    # Загружаем все записи ServiceHistory с жадной загрузкой связанных данных
    service_events_query = db.select(ServiceHistory).options(
        joinedload(ServiceHistory.equipment).joinedload(Equipment.category), # Загружаем оборудование и его категорию
        joinedload(ServiceHistory.performed_by) # Загружаем исполнителя
    ).order_by(ServiceHistory.planned_date.asc().nullsfirst(), ServiceHistory.service_date.asc().nullsfirst()) # Сортируем
    
    all_service_records = db.session.execute(service_events_query).scalars().all()

    return render_template(
        'service/calendar.html',
        all_service_records=all_service_records,
        title="Календарь технического обслуживания"
    )

# TODO: Добавить роуты для редактирования и удаления записей ServiceHistory, если это требуется по ТЗ.
# Например:
# @bp.route('/record/<int:record_id>/edit', methods=['GET', 'POST'])
# @login_required
# @role_required('Admin', 'TechSpecialist')
# def edit_service_record(record_id):
#     pass

# @bp.route('/record/<int:record_id>/delete', methods=['POST'])
# @login_required
# @role_required('Admin') # Возможно, только админ может удалять записи
# def delete_service_record(record_id):
#     pass