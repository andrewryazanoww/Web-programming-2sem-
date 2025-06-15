# app/models.py
import os
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import UserMixin
from flask import url_for, current_app
from sqlalchemy import event, Enum as SQLAlchemyEnum
from .extensions import db

# УДАЛЯЕМ или комментируем определение таблицы equipment_responsible_persons,
# так как теперь у оборудования будет только ОДИН ответственный (связь многие-к-одному)
# equipment_responsible_persons = db.Table('equipment_responsible_persons',
#     db.Column('id', db.Integer, primary_key=True, autoincrement=True),
#     db.Column('equipment_id', db.Integer, db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False),
#     db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
#     db.UniqueConstraint('equipment_id', 'user_id', name='uq_equipment_user_responsible')
# )

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    users = db.relationship('User', backref='role', lazy='select')
    def __repr__(self): return f'<Role {self.name}>'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=True)
    position = db.Column(db.String(150), nullable=True)
    contact_info = db.Column(db.String(255), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    performed_services = db.relationship('ServiceHistory', backref='performed_by', lazy='dynamic', foreign_keys='ServiceHistory.performed_by_id')
    # ИЗМЕНЕНИЕ: Связь "один пользователь - много оборудования, за которое он ответственен"
    # backref 'responsible_user' будет создан в Equipment
    assigned_equipment = db.relationship('Equipment', backref='responsible_user', lazy='dynamic', foreign_keys='Equipment.responsible_user_id')

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    @property
    def full_name(self): return ' '.join(filter(None, [self.last_name, self.first_name, self.middle_name]))
    def __repr__(self): return f'<User {self.login}>'
    def is_admin(self): return self.role and self.role.name == 'Admin'
    def is_tech_specialist(self): return self.role and self.role.name == 'TechSpecialist'

class Image(db.Model):
    # ... (Код модели Image без изменений, как в предыдущем полном файле) ...
    __tablename__ = 'images'
    id = db.Column(db.String(100), primary_key=True)
    file_name = db.Column(db.String(100), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    def __repr__(self): return f'<Image {self.file_name}>'
    @property
    def storage_filename(self): _, ext = os.path.splitext(self.file_name); return self.id + ext
    @property
    def url(self): return url_for('main_bp.image_file', image_id=self.id, _external=False)

class Category(db.Model):
    # ... (Код модели Category без изменений) ...
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    equipment = db.relationship('Equipment', backref='category', lazy='select')
    def __repr__(self): return f'<Category {self.name}>'


class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    inventory_number = db.Column(db.String(100), unique=True, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    cost = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(SQLAlchemyEnum("В эксплуатации", "На ремонте", "Списано", name="equipment_status_enum_type", create_constraint=True), nullable=False, default="В эксплуатации")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    image_id = db.Column(db.String(100), db.ForeignKey('images.id', ondelete='SET NULL'), nullable=True)

    # ИЗМЕНЕНИЕ: Поле для ID ответственного пользователя (связь многие-к-одному)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    # 'responsible_user' создается через backref в модели User.

    # Связи
    image = db.relationship('Image', backref=db.backref('equipment_item', uselist=False), lazy='joined')
    service_history = db.relationship('ServiceHistory', backref='equipment', lazy='dynamic', cascade="all, delete-orphan")
    # УДАЛЯЕМ старое отношение responsible_persons (многие-ко-многим)
    # responsible_persons = db.relationship('User', secondary=equipment_responsible_persons, ...)

    def __repr__(self): return f'<Equipment {self.name} ({self.inventory_number})>'

# Событие after_delete для Equipment остается без изменений
@event.listens_for(Equipment, 'after_delete')
def receive_after_delete_equipment(mapper, connection, target):
    # ... (код события) ...
    if target.image_id:
        img_to_delete_from_db = db.session.get(Image, target.image_id)
        if img_to_delete_from_db:
            other_equipment_with_same_image_query = db.select(Equipment).filter_by(image_id=img_to_delete_from_db.id)
            other_equipment_with_same_image = db.session.execute(other_equipment_with_same_image_query).first()
            if not other_equipment_with_same_image:
                image_path = os.path.join(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img_to_delete_from_db.storage_filename)
                db.session.delete(img_to_delete_from_db)
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        current_app.logger.info(f"Файл изображения {image_path} удален.")
                    except OSError as e:
                        current_app.logger.error(f"Ошибка удаления файла {image_path}: {e}")
            else:
                current_app.logger.info(f"Изображение {img_to_delete_from_db.id} используется, не удаляем.")


class ServiceHistory(db.Model):
    # ... (Код модели ServiceHistory без изменений, как в последнем полном файле) ...
    __tablename__ = 'service_history'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    service_date = db.Column(db.DateTime, nullable=True, default=None)
    planned_date = db.Column(db.Date, nullable=True)
    service_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    performed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(SQLAlchemyEnum("Запланировано", "В процессе", "Выполнено", "Отменено", name="service_status_enum_type", create_constraint=True), nullable=False, default="Запланировано")
    def __repr__(self): return f'<ServiceHistory {self.id} for Eq {self.equipment_id}>'