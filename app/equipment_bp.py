# app/equipment_bp.py
# ... (импорты и декоратор role_required без изменений) ...
import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy.orm import joinedload, selectinload

from .extensions import db
from .models import Equipment, Category, Image, User, Role, ServiceHistory
from .forms import EquipmentForm
from .tools import ImageSaver, EquipmentFilter

bp = Blueprint('equipment', __name__, url_prefix='/equipment')

from functools import wraps
def role_required(*role_names):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated: return current_app.login_manager.unauthorized()
            if not current_user.role or current_user.role.name not in role_names:
                flash('Недостаточно прав.', 'danger'); return redirect(url_for('main_bp.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_eligible_responsible_users():
    eligible_roles_q = db.session.query(Role.id).filter(Role.name.in_(['Admin', 'TechSpecialist']))
    eligible_role_ids = [r[0] for r in eligible_roles_q.all()]
    if not eligible_role_ids: return []
    return db.session.execute(db.select(User).filter(User.role_id.in_(eligible_role_ids)).order_by(User.last_name, User.first_name)).scalars().all()

# Роут index - без изменений, но убедитесь, что он передает responsible_user в шаблон, если нужно
@bp.route('/')
@login_required
def index():
    # ... (Код роута index без изменений) ...
    page = request.args.get('page', 1, type=int)
    category_id_filter = request.args.get('category_id', default=None, type=int)
    status_filter = request.args.get('status', default=None, type=str)
    purchase_date_from_str = request.args.get('purchase_date_from', default=None, type=str)
    purchase_date_to_str = request.args.get('purchase_date_to', default=None, type=str)
    name_filter_str = request.args.get('name_filter', default=None, type=str)
    sort_by_param = request.args.get('sort_by', 'purchase_date')
    sort_direction_param = request.args.get('sort_direction', 'desc')

    date_from, date_to = None, None
    if purchase_date_from_str:
        try: date_from = datetime.strptime(purchase_date_from_str, '%Y-%m-%d').date()
        except ValueError: flash("Некорректный формат 'Дата покупки от'.", "warning")
    if purchase_date_to_str:
        try: date_to = datetime.strptime(purchase_date_to_str, '%Y-%m-%d').date()
        except ValueError: flash("Некорректный формат 'Дата покупки до'.", "warning")

    equipment_query_builder = EquipmentFilter(
        name_filter=name_filter_str,
        category_id=category_id_filter if category_id_filter and category_id_filter > 0 else None,
        status=status_filter if status_filter else None,
        purchase_date_from=date_from,
        purchase_date_to=date_to,
        sort_by=sort_by_param,
        sort_direction=sort_direction_param
    )
    equipment_query = equipment_query_builder.perform().options(
        joinedload(Equipment.category),
        joinedload(Equipment.responsible_user) # ИЗМЕНЕНО: загружаем одного ответственного
    )
    per_page = current_app.config.get('ITEMS_PER_PAGE_EQUIPMENT', 10)
    pagination = db.paginate(equipment_query, page=page, per_page=per_page, error_out=False)
    equipment_list = pagination.items
    categories = db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()
    statuses = [choice[0] for choice in EquipmentForm.status_choices]
    return render_template(
        'equipment/index.html', equipment_list=equipment_list, pagination=pagination,
        categories=categories, statuses=statuses, current_filters={
            'name_filter': name_filter_str, 'category_id': category_id_filter, 'status': status_filter,
            'purchase_date_from': purchase_date_from_str, 'purchase_date_to': purchase_date_to_str,
            'sort_by': sort_by_param, 'sort_direction': sort_direction_param },
        title="Список оборудования"
    )


@bp.route('/new', methods=['GET'])
@login_required
@role_required('Admin')
def new():
    form = EquipmentForm()
    form.category_id.choices = [(0, '-- Выберите категорию --')] + [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]
    eligible_users = get_eligible_responsible_users()
    # ИЗМЕНЕНО: choices для responsible_user_id
    form.responsible_user_id.choices = [(0, '-- Не назначено --')] + [(user.id, f"{user.full_name} ({user.login})") for user in eligible_users]
    if len(form.category_id.choices) <= 1: flash("Категории не найдены.", "warning")
    if len(form.responsible_user_id.choices) <=1 : flash("Пользователи (Admin/TechSpecialist) для назначения ответственными не найдены.", "warning")
    return render_template('equipment/new.html', form=form, title="Добавить оборудование")

@bp.route('/create', methods=['POST'])
@login_required
@role_required('Admin')
def create():
    form = EquipmentForm(request.form)
    form.category_id.choices = [(0, '-- Выберите категорию --')] + [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]
    eligible_users = get_eligible_responsible_users()
    form.responsible_user_id.choices = [(0, '-- Не назначено --')] + [(user.id, f"{user.full_name} ({user.login})") for user in eligible_users]

    if form.validate_on_submit():
        try:
            # ... (логика ImageSaver) ...
            image_file = request.files.get('image')
            img_id_to_save = None
            if image_file and image_file.filename:
                saver = ImageSaver(image_file, upload_folder_config_key='UPLOAD_FOLDER_EQUIPMENT')
                image_db_object = saver.save()
                if image_db_object: img_id_to_save = image_db_object.id
            
            existing_equipment_inv = db.session.execute(db.select(Equipment).filter_by(inventory_number=form.inventory_number.data)).scalar_one_or_none()
            if existing_equipment_inv:
                form.inventory_number.errors.append("Оборудование с таким инвентарным номером уже существует.")
                raise ValueError("Инвентарный номер уже используется.")

            new_equipment = Equipment(
                name=form.name.data,
                inventory_number=form.inventory_number.data,
                category_id=form.category_id.data if form.category_id.data != 0 else None,
                purchase_date=form.purchase_date.data,
                cost=form.cost.data,
                status=form.status.data,
                notes=form.notes.data,
                image_id=img_id_to_save,
                # ИЗМЕНЕНО: сохраняем responsible_user_id
                responsible_user_id=form.responsible_user_id.data if form.responsible_user_id.data and form.responsible_user_id.data > 0 else None
            )
            db.session.add(new_equipment)
            db.session.commit()
            flash(f'Оборудование "{new_equipment.name}" успешно добавлено!', 'success')
            return redirect(url_for('equipment.show', equipment_id=new_equipment.id))
        # ... (обработка исключений) ...
        except ValueError as ve: db.session.rollback(); flash(str(ve), 'danger')
        except IntegrityError as e: db.session.rollback(); current_app.logger.error(f"IntegrityError: {e}"); flash("Ошибка БД.", 'danger')
        except Exception as e: db.session.rollback(); current_app.logger.error(f"Error: {e}"); flash(f'Ошибка: {str(e)}.', 'danger')
    else: flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
    return render_template('equipment/new.html', form=form, title="Добавить оборудование")

# Роут show - убедитесь, что используется joinedload(Equipment.responsible_user)
@bp.route('/<int:equipment_id>')
@login_required
def show(equipment_id):
    equipment = db.session.query(Equipment).options(
        joinedload(Equipment.category),
        joinedload(Equipment.image),
        joinedload(Equipment.responsible_user), # ИЗМЕНЕНО
    ).filter(Equipment.id == equipment_id).first_or_404()
    service_records_query = equipment.service_history.options(joinedload(ServiceHistory.performed_by)).order_by(ServiceHistory.service_date.desc())
    service_records = service_records_query.all()
    service_form = None
    if current_user.is_authenticated and current_user.role and (current_user.role.name == 'Admin' or current_user.role.name == 'TechSpecialist'):
        from .forms import ServiceRecordForm
        service_form = ServiceRecordForm()
        tech_roles_q = db.session.query(Role).filter(Role.name.in_(['Admin', 'TechSpecialist']))
        tech_ids = [r.id for r in tech_roles_q.all()]
        service_form.performed_by_id.choices = [(0, '-- Не выбран --')]
        if tech_ids:
            performers_q = db.session.query(User).filter(User.role_id.in_(tech_ids)).order_by(User.last_name, User.first_name)
            service_form.performed_by_id.choices.extend([(u.id, u.full_name) for u in performers_q.all()])
    return render_template('equipment/show.html', equipment=equipment, service_records=service_records, service_form=service_form, title=f"Оборудование: {equipment.name}")


@bp.route('/<int:equipment_id>/edit', methods=['GET'])
@login_required
@role_required('Admin')
def edit(equipment_id):
    equipment = db.get_or_404(Equipment, equipment_id)
    form = EquipmentForm(obj=equipment)
    form.category_id.choices = [(0, '-- Выберите категорию --')] + [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]
    eligible_users = get_eligible_responsible_users()
    # ИЗМЕНЕНО: choices для responsible_user_id
    form.responsible_user_id.choices = [(0, '-- Не назначено --')] + [(user.id, f"{user.full_name} ({user.login})") for user in eligible_users]
    form.category_id.data = equipment.category_id
    form.status.data = equipment.status
    # ИЗМЕНЕНО: data для responsible_user_id
    form.responsible_user_id.data = equipment.responsible_user_id if equipment.responsible_user_id else 0
    current_image_url = equipment.image.url if equipment.image else None
    return render_template('equipment/edit.html', form=form, equipment=equipment, current_image_url=current_image_url, title="Редактировать оборудование")

@bp.route('/<int:equipment_id>/update', methods=['POST'])
@login_required
@role_required('Admin')
def update(equipment_id):
    equipment = db.get_or_404(Equipment, equipment_id)
    form = EquipmentForm(request.form)
    form.category_id.choices = [(0, '-- Выберите категорию --')] + [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]
    eligible_users = get_eligible_responsible_users()
    form.responsible_user_id.choices = [(0, '-- Не назначено --')] + [(user.id, f"{user.full_name} ({user.login})") for user in eligible_users]

    if form.validate_on_submit():
        try:
            # ... (логика обновления изображения и проверки инв. номера) ...
            old_image_id = equipment.image_id; old_image_obj = equipment.image
            new_image_id = equipment.image_id; image_file = request.files.get('image')
            if image_file and image_file.filename:
                saver = ImageSaver(image_file, upload_folder_config_key='UPLOAD_FOLDER_EQUIPMENT')
                img_db_object = saver.save()
                if img_db_object: new_image_id = img_db_object.id
                if old_image_obj and old_image_id != new_image_id:
                    other_eq = db.session.execute(db.select(Equipment).filter(Equipment.image_id == old_image_id, Equipment.id != equipment_id)).first()
                    if not other_eq:
                        old_path = os.path.join(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], old_image_obj.storage_filename)
                        if os.path.exists(old_path): 
                            try: os.remove(old_path)
                            except OSError as e: current_app.logger.error(f"Err removing: {e}")
                        db.session.delete(old_image_obj)
                    else: current_app.logger.info(f"Old image {old_image_id} used.")
            if equipment.inventory_number != form.inventory_number.data:
                conflict = db.session.execute(db.select(Equipment).filter_by(inventory_number=form.inventory_number.data).filter(Equipment.id != equipment_id)).scalar_one_or_none()
                if conflict: form.inventory_number.errors.append("Инв. номер занят."); raise ValueError("Инв. номер занят.")

            equipment.name=form.name.data; equipment.inventory_number=form.inventory_number.data
            equipment.category_id=form.category_id.data if form.category_id.data!=0 else None
            equipment.purchase_date=form.purchase_date.data; equipment.cost=form.cost.data
            equipment.status=form.status.data; equipment.notes=form.notes.data
            equipment.image_id=new_image_id
            # ИЗМЕНЕНО: обновляем responsible_user_id
            equipment.responsible_user_id = form.responsible_user_id.data if form.responsible_user_id.data and form.responsible_user_id.data > 0 else None

            db.session.commit(); flash(f'"{equipment.name}" обновлено!', 'success')
            return redirect(url_for('equipment.show', equipment_id=equipment.id))
        # ... (обработка исключений) ...
        except ValueError as ve: db.session.rollback(); flash(str(ve), 'danger')
        except IntegrityError as e: db.session.rollback(); current_app.logger.error(f"IntegrityError: {e}"); flash("Ошибка БД.", 'danger')
        except Exception as e: db.session.rollback(); current_app.logger.error(f"Error: {e}"); flash(f'Ошибка.', 'danger')
    else: flash('Исправьте ошибки.', 'warning')
    current_image_url = equipment.image.url if equipment.image else None
    return render_template('equipment/edit.html', form=form, equipment=equipment, current_image_url=current_image_url, title="Редактировать оборудование")

# Роут delete - без изменений
@bp.route('/<int:equipment_id>/delete', methods=['POST'])
@login_required
@role_required('Admin')
def delete(equipment_id):
    # ... (код роута delete) ...
    eq_del = db.get_or_404(Equipment, equipment_id)
    try:
        name_flash = eq_del.name; img_remove = eq_del.image
        db.session.delete(eq_del) # Связи many-to-many с responsible_persons удалятся из связующей таблицы автоматически, если ondelete='CASCADE'
        if img_remove:
            other_eq = db.session.execute(db.select(Equipment).filter_by(image_id=img_remove.id)).first()
            if not other_eq:
                img_path = os.path.join(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img_remove.storage_filename)
                db.session.delete(img_remove)
                if os.path.exists(img_path):
                    try: os.remove(img_path)
                    except OSError as e: current_app.logger.error(f"Err removing file: {e}")
            else: current_app.logger.info(f"Image {img_remove.id} used elsewhere.")
        db.session.commit(); flash(f'"{name_flash}" удалено.', 'success')
    except Exception as e: db.session.rollback(); current_app.logger.error(f"Error deleting: {e}"); flash(f'Ошибка удаления.', 'danger')
    return redirect(url_for('equipment.index'))