# app/equipment_bp.py
import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename
from wtforms import ValidationError

from .extensions import db
from .models import Equipment, Category, Image, User, Role, ServiceHistory
from .forms import EquipmentForm
from .tools import ImageSaver # Убедитесь, что EquipmentFilter здесь не импортируется, если он не используется

bp = Blueprint('equipment', __name__, url_prefix='/equipment')

# --- Хелпер для декоратора прав (без изменений) ---
def role_required(role_name_or_names):
    # ... (код декоратора role_required) ...
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not current_user.role:
                flash('Вам не назначена роль для выполнения этого действия.', 'danger')
                return redirect(url_for('main_bp.index'))
            allowed_roles = role_name_or_names if isinstance(role_name_or_names, list) else [role_name_or_names]
            if current_user.role.name not in allowed_roles:
                flash('У вас недостаточно прав для доступа к этой странице.', 'danger')
                return redirect(url_for('main_bp.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Роуты ---

# Список оборудования
@bp.route('/')
@login_required
def index():
    # ... (код роуta index без изменений, связанных с ImageSaver) ...
    page = request.args.get('page', 1, type=int)
    equipment_query = db.select(Equipment).order_by(Equipment.purchase_date.desc())
    per_page = current_app.config.get('ITEMS_PER_PAGE_EQUIPMENT', 10)
    pagination = db.paginate(equipment_query, page=page, per_page=per_page, error_out=False)
    equipment_list = pagination.items
    categories = db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()
    statuses = ['В эксплуатации', 'На ремонте', 'Списано']
    return render_template(
        'equipment/index.html',
        equipment_list=equipment_list,
        pagination=pagination,
        categories=categories,
        statuses=statuses,
        title="Список оборудования"
    )

# Страница добавления нового оборудования (GET)
@bp.route('/new', methods=['GET'])
@login_required
@role_required('Admin')
def new():
    # ... (код роута new без изменений, связанных с ImageSaver) ...
    form = EquipmentForm()
    try:
        form.category_id.choices = [(0, '-- Выберите категорию --')] + \
                                   [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]
        if len(form.category_id.choices) == 1:
            flash("Внимание: Категории оборудования не найдены.", "warning")
    except Exception as e:
        current_app.logger.error(f"Ошибка при загрузке категорий: {e}")
        form.category_id.choices = [(0, "Ошибка загрузки категорий")]
        flash("Не удалось загрузить список категорий.", "danger")
    return render_template('equipment/new.html', form=form, title="Добавить оборудование")


# Обработка формы добавления нового оборудования (POST)
@bp.route('/create', methods=['POST'])
@login_required
@role_required('Admin')
def create():
    form = EquipmentForm()
    form.category_id.choices = [(0, '-- Выберите категорию --')] + \
                               [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]

    if form.validate_on_submit():
        try:
            image_file = form.image.data
            img_id_to_save = None

            if image_file and image_file.filename:
                # ПРАВИЛЬНЫЙ ВЫЗОВ ImageSaver: передаем КЛЮЧ конфигурации
                saver = ImageSaver(image_file, upload_folder_config_key='UPLOAD_FOLDER_EQUIPMENT')
                image_db_object = saver.save() # save() добавляет в сессию, но не коммитит
                if image_db_object:
                    img_id_to_save = image_db_object.id

            new_equipment = Equipment(
                name=form.name.data,
                inventory_number=form.inventory_number.data,
                category_id=form.category_id.data,
                purchase_date=form.purchase_date.data,
                cost=form.cost.data,
                status=form.status.data,
                notes=form.notes.data,
                image_id=img_id_to_save
            )
            db.session.add(new_equipment)
            db.session.commit()
            flash(f'Оборудование "{new_equipment.name}" успешно добавлено!', 'success')
            return redirect(url_for('equipment.show', equipment_id=new_equipment.id))
        except ValueError as ve: # Ловим ValueError от ImageSaver (например, пустой файл или не найден ключ конфиг.)
            db.session.rollback()
            flash(f'Ошибка обработки изображения: {ve}', 'danger')
            current_app.logger.error(f"Ошибка ValueError при создании оборудования (ImageSaver): {ve}")
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка IntegrityError при создании оборудования: {e}")
            if 'UNIQUE constraint failed: equipment.inventory_number' in str(e).lower():
                form.inventory_number.errors.append("Оборудование с таким инвентарным номером уже существует.")
                flash("Ошибка: Инвентарный номер уже используется.", 'danger')
            else:
                flash("Ошибка базы данных при сохранении. Проверьте уникальные поля.", 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Непредвиденная ошибка при создании оборудования: {e}")
            flash(f'Произошла ошибка: {str(e)}. Попробуйте еще раз.', 'danger')
    else:
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        current_app.logger.warning(f"Ошибки валидации формы создания оборудования: {form.errors}")

    return render_template('equipment/new.html', form=form, title="Добавить оборудование")


# Страница просмотра деталей оборудования
@bp.route('/<int:equipment_id>')
@login_required
def show(equipment_id):
    # ... (код роута show без изменений, связанных с ImageSaver) ...
    equipment = db.get_or_404(Equipment, equipment_id)
    service_records = equipment.service_history.order_by(ServiceHistory.service_date.desc()).all()
    service_form = None
    if current_user.role and (current_user.role.name == 'Admin' or current_user.role.name == 'TechSpecialist'):
        from .forms import ServiceRecordForm
        service_form = ServiceRecordForm()
        tech_roles_q = db.session.query(Role).filter(Role.name.in_(['Admin', 'TechSpecialist']))
        tech_ids = [r.id for r in tech_roles_q.all()]
        if tech_ids:
            performers_q = db.session.query(User).filter(User.role_id.in_(tech_ids)).order_by(User.last_name)
            service_form.performed_by_id.choices = [(0, '-- Не выбран --')] + [(u.id, u.full_name) for u in performers_q.all()]
        else:
            service_form.performed_by_id.choices = [(0, '-- Нет исполнителей --')]
    return render_template(
        'equipment/show.html',
        equipment=equipment,
        service_records=service_records,
        service_form=service_form,
        title=f"Оборудование: {equipment.name}"
    )


# Страница редактирования оборудования (GET)
@bp.route('/<int:equipment_id>/edit', methods=['GET'])
@login_required
@role_required('Admin')
def edit(equipment_id):
    # ... (код роута edit без изменений, связанных с ImageSaver) ...
    equipment = db.get_or_404(Equipment, equipment_id)
    form = EquipmentForm(obj=equipment)
    form.category_id.choices = [(0, '-- Выберите категорию --')] + \
                               [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]
    form.category_id.data = equipment.category_id
    form.status.data = equipment.status
    current_image_url = equipment.image.url if equipment.image else None
    return render_template('equipment/edit.html', form=form, equipment=equipment, current_image_url=current_image_url, title="Редактировать оборудование")


# Обработка формы редактирования оборудования (POST)
@bp.route('/<int:equipment_id>/update', methods=['POST'])
@login_required
@role_required('Admin')
def update(equipment_id):
    equipment = db.get_or_404(Equipment, equipment_id)
    form = EquipmentForm()
    form.category_id.choices = [(0, '-- Выберите категорию --')] + \
                               [(cat.id, cat.name) for cat in db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()]

    if form.validate_on_submit():
        try:
            old_image_id = equipment.image_id
            old_image_obj = equipment.image
            new_image_id = equipment.image_id

            image_file = form.image.data
            if image_file and image_file.filename:
                # ПРАВИЛЬНЫЙ ВЫЗОВ ImageSaver
                saver = ImageSaver(image_file, upload_folder_config_key='UPLOAD_FOLDER_EQUIPMENT')
                img = saver.save()
                if img:
                    new_image_id = img.id
                    if old_image_obj and old_image_id != new_image_id:
                        old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], old_image_obj.storage_filename)
                        if os.path.exists(old_image_path):
                            try:
                                os.remove(old_image_path)
                                current_app.logger.info(f"Старый файл изображения {old_image_path} удален.")
                                db.session.delete(old_image_obj) # Удаляем старую запись Image
                            except OSError as e:
                                current_app.logger.error(f"Ошибка удаления старого файла изображения {old_image_path}: {e}")
            # ... (остальная логика обновления полей equipment, как раньше) ...
            equipment.name = form.name.data
            if equipment.inventory_number != form.inventory_number.data:
                conflicting_equipment = db.session.execute(db.select(Equipment).filter_by(inventory_number=form.inventory_number.data)).scalar_one_or_none()
                if conflicting_equipment:
                    form.inventory_number.errors.append("Этот инвентарный номер уже используется.")
                    raise ValidationError("Инвентарный номер уже занят.")
            equipment.inventory_number = form.inventory_number.data
            equipment.category_id = form.category_id.data
            equipment.purchase_date = form.purchase_date.data
            equipment.cost = form.cost.data
            equipment.status = form.status.data
            equipment.notes = form.notes.data
            equipment.image_id = new_image_id

            db.session.commit()
            flash(f'Оборудование "{equipment.name}" успешно обновлено!', 'success')
            return redirect(url_for('equipment.show', equipment_id=equipment.id))
        except ValueError as ve: # От ImageSaver
            db.session.rollback()
            flash(f'Ошибка обработки изображения: {ve}', 'danger')
            current_app.logger.error(f"Ошибка ValueError при обновлении оборудования (ImageSaver): {ve}")
        except IntegrityError as e:
            # ... (обработка IntegrityError) ...
            db.session.rollback()
            current_app.logger.error(f"Ошибка IntegrityError при обновлении оборудования: {e}")
            if 'UNIQUE constraint failed: equipment.inventory_number' in str(e).lower():
                form.inventory_number.errors.append("Этот инвентарный номер уже используется.")
                flash("Ошибка: Инвентарный номер уже используется.", 'danger')
            else:
                flash("Ошибка базы данных при сохранении.", 'danger')
        except ValidationError:
             db.session.rollback()
             flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        except Exception as e:
            # ... (общая обработка ошибок) ...
            db.session.rollback()
            current_app.logger.error(f"Непредвиденная ошибка при обновлении оборудования: {e}")
            flash(f'Произошла ошибка: {str(e)}. Попробуйте еще раз.', 'danger')
    else:
        flash('Пожалуйста, исправьте ошибки в форме.', 'warning')
        current_app.logger.warning(f"Ошибки валидации формы редактирования оборудования: {form.errors}")

    current_image_url = equipment.image.url if equipment.image else None
    return render_template('equipment/edit.html', form=form, equipment=equipment, current_image_url=current_image_url, title="Редактировать оборудование")

# Удаление оборудования
@bp.route('/<int:equipment_id>/delete', methods=['POST'])
@login_required
@role_required('Admin')
def delete(equipment_id):
    # ... (код роута delete без изменений, связанных с ImageSaver, но он должен использовать его для удаления файла) ...
    equipment_to_delete = db.get_or_404(Equipment, equipment_id)
    try:
        image_to_remove = equipment_to_delete.image
        name_for_flash = equipment_to_delete.name
        db.session.delete(equipment_to_delete) # Сначала удаляем оборудование
        if image_to_remove: # Если было изображение
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], image_to_remove.storage_filename)
            # Удаляем запись Image из БД
            db.session.delete(image_to_remove)
            # Пытаемся удалить файл
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    current_app.logger.info(f"Файл изображения {image_path} удален.")
                except OSError as e:
                    current_app.logger.error(f"Ошибка удаления файла изображения {image_path}: {e}")
        db.session.commit()
        flash(f'Оборудование "{name_for_flash}" и все связанные записи успешно удалены.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при удалении оборудования ID {equipment_id}: {e}")
        flash(f'Произошла ошибка при удалении оборудования: {str(e)}', 'danger')
    return redirect(url_for('equipment.index'))