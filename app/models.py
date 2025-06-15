# app/models.py
import os
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import UserMixin
from flask import url_for, current_app
from sqlalchemy import event
from .extensions import db

# Таблица для связи "многие-ко-многим" между Оборудованием и Ответственными лицами
equipment_responsible_persons = db.Table('equipment_responsible_persons',
    db.Column('equipment_id', db.Integer, db.ForeignKey('equipment.id'), primary_key=True),
    db.Column('responsible_person_id', db.Integer, db.ForeignKey('responsible_persons.id'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False) # Admin, TechSpecialist, User
    description = db.Column(db.String(255))
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
    position = db.Column(db.String(150), nullable=True) # Должность
    contact_info = db.Column(db.String(255), nullable=True) # Контактные данные
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    @property
    def full_name(self): return ' '.join(filter(None, [self.last_name, self.first_name, self.middle_name]))
    def __repr__(self): return f'<User {self.login}>'
    def is_admin(self): return self.role and self.role.name == 'Admin'
    def is_tech_specialist(self): return self.role and self.role.name == 'TechSpecialist'

class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.String(100), primary_key=True) # UUID
    file_name = db.Column(db.String(100), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # Связь с оборудованием (одно изображение - одно оборудование)
    equipment = db.relationship("Equipment", backref="image", uselist=False, lazy='select')

    def __repr__(self): return f'<Image {self.file_name}>'
    @property
    def storage_filename(self): _, ext = os.path.splitext(self.file_name); return self.id + ext
    @property
    def url(self):
        # 'main_bp.image_file' - предполагаем, что роут для изображений будет в main_bp
        return url_for('main_bp.image_file', image_id=self.id, _external=True)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    equipment = db.relationship('Equipment', backref='category', lazy='dynamic')
    def __repr__(self): return f'<Category {self.name}>'

class EquipmentStatus(db.Enum): # Используем Enum из SQLAlchemy, если нужно
    IN_OPERATION = "В эксплуатации"
    UNDER_REPAIR = "На ремонте"
    WRITTEN_OFF = "Списано"
    # Python Enum для более строгого контроля
    # import enum
    # class StatusEnum(enum.Enum):
    #     IN_OPERATION = "В эксплуатации"
    #     UNDER_REPAIR = "На ремонте"
    #     WRITTEN_OFF = "Списано"

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    inventory_number = db.Column(db.String(100), unique=True, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    cost = db.Column(db.Numeric(10, 2), nullable=False) # DECIMAL
    status = db.Column(db.Enum("В эксплуатации", "На ремонте", "Списано", name="equipment_status_enum"), nullable=False)
    notes = db.Column(db.Text, nullable=True) # Примечание
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    image_id = db.Column(db.String(100), db.ForeignKey('images.id'), nullable=True) # Фотография может отсутствовать

    # Связи
    service_history = db.relationship('ServiceHistory', backref='equipment', lazy='dynamic', cascade="all, delete-orphan")
    responsible_persons = db.relationship('ResponsiblePerson',
                                          secondary=equipment_responsible_persons,
                                          backref=db.backref('equipment_items', lazy='dynamic'),
                                          lazy='dynamic')

    def __repr__(self): return f'<Equipment {self.name} ({self.inventory_number})>'

# Удаление файла изображения при удалении записи Equipment с изображением
@event.listens_for(Equipment, 'after_delete')
def receive_after_delete_equipment(mapper, connection, target):
    if target.image_id:
        img_to_delete = db.session.get(Image, target.image_id)
        if img_to_delete:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER_EQUIPMENT'], img_to_delete.storage_filename)
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    print(f"Изображение {image_path} удалено для оборудования ID {target.id}")
                except OSError as e:
                    print(f"Ошибка удаления файла изображения {image_path}: {e}")
            # Саму запись Image можно не удалять, если она может использоваться где-то еще
            # или если MD5 хеширование подразумевает одно изображение на несколько записей.
            # Если изображение уникально для оборудования, то:
            # db.session.delete(img_to_delete)
            # db.session.commit() # Коммит будет в основном потоке

class ServiceHistory(db.Model):
    __tablename__ = 'service_history'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    service_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    service_type = db.Column(db.String(100), nullable=False) # Например, "Ремонт", "Обслуживание", "Замена компонента"
    description = db.Column(db.Text, nullable=False) # Комментарий/описание работ
    performed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Кто выполнял (может быть тех. специалист)

    performed_by = db.relationship('User', backref='performed_services', lazy='select')

    def __repr__(self): return f'<ServiceHistory {self.id} for Equipment {self.equipment_id}>'

class ResponsiblePerson(db.Model):
    __tablename__ = 'responsible_persons' # Это могут быть те же пользователи или отдельная таблица
    id = db.Column(db.Integer, primary_key=True)
    # Если это те же пользователи, то можно использовать ForeignKey на users.id
    # user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    # user = db.relationship('User', backref=db.backref('responsible_for_one', uselist=False))
    # Или если это отдельные сущности:
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=True)
    position = db.Column(db.String(150)) # Должность
    contact_info = db.Column(db.String(255)) # Контактная информация (телефон, email)

    @property
    def full_name(self): return ' '.join(filter(None, [self.last_name, self.first_name, self.middle_name]))
    def __repr__(self): return f'<ResponsiblePerson {self.full_name}>'