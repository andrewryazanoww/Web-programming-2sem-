# app/service_bp.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
# Импортируем db из extensions и модели из models
from .extensions import db
from .models import Equipment, ServiceHistory, User
from .forms import ServiceRecordForm # Предполагаем, что эта форма есть в forms.py
# from .tools import ... # Если будут нужны вспомогательные классы

# Создаем Blueprint с именем 'service' и префиксом URL '/service'
bp = Blueprint('service', __name__, url_prefix='/service')

# Роут для добавления записи об обслуживании к конкретному оборудованию
@bp.route('/equipment/<int:equipment_id>/add_record', methods=['GET', 'POST'])
@login_required
# TODO: Добавить декоратор @check_rights (например, 'add_service_record')
# Права: Admin и TechSpecialist
def add_service_record(equipment_id):
    # Проверка прав вручную, пока декоратор не настроен для этого действия
    if not (current_user.is_admin() or (current_user.role and current_user.role.name == 'TechSpecialist')):
        flash('У вас нет прав для добавления записи об обслуживании.', 'danger')
        return redirect(url_for('equipment.show', equipment_id=equipment_id)) # Или на главную оборудования

    equipment = db.get_or_404(Equipment, equipment_id)
    form = ServiceRecordForm()

    # Заполняем choices для исполнителей (дублируем логику из forms.py,
    # т.к. форма могла быть создана вне контекста, где db был доступен для __init__)
    # Это более надежное место для заполнения choices.
    from .models import Role # Локальный импорт для избежания циклических зависимостей на старте
    tech_roles_query = db.session.query(Role).filter(Role.name.in_(['Admin', 'TechSpecialist']))
    tech_roles_ids = [role.id for role in tech_roles_query.all()]
    if tech_roles_ids:
        performers_query = db.session.query(User).filter(User.role_id.in_(tech_roles_ids)).order_by(User.last_name, User.first_name)
        form.performed_by_id.choices = [(0, '-- Не выбран --')] + [(user.id, user.full_name) for user in performers_query.all()]
    else:
        form.performed_by_id.choices = [(0, '-- Нет доступных исполнителей --')]


    if form.validate_on_submit():
        try:
            record = ServiceHistory(
                equipment_id=equipment.id,
                service_type=form.service_type.data,
                description=form.description.data,
                # Если 0 (не выбран), то ставим NULL, иначе ID пользователя
                performed_by_id=form.performed_by_id.data if form.performed_by_id.data != 0 else None
            )
            db.session.add(record)
            db.session.commit()
            flash('Запись об обслуживании успешно добавлена.', 'success')
            return redirect(url_for('equipment.show', equipment_id=equipment.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении записи: {e}', 'danger')
            current_app.logger.error(f"Ошибка добавления записи обслуживания: {e}")

    # Для GET-запроса или если форма невалидна
    # Можно передать equipment в шаблон, чтобы показать, для какого оборудования добавляется запись
    return render_template('service/add_record_form.html',
                           form=form,
                           equipment=equipment,
                           title=f"Добавить запись обслуживания для {equipment.name}")

# TODO: Можно добавить роут для просмотра всей истории обслуживания оборудования
# @bp.route('/equipment/<int:equipment_id>/history')
# @login_required
# @check_rights('view_service_history')
# def equipment_service_history(equipment_id):
#     equipment = db.get_or_404(Equipment, equipment_id)
#     # Логика пагинации для истории
#     return render_template('service/history.html', equipment=equipment, history=equipment.service_history.order_by(...).all())