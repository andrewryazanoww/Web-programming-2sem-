# models.py
from datetime import datetime
from flask_login import UserMixin # Нужен для модели User
from werkzeug.security import generate_password_hash, check_password_hash # Для методов пароля
from extensions import db # Импортируем ИНИЦИАЛИЗИРОВАННЫЙ, но НЕ СВЯЗАННЫЙ db

# Определяем модели ЗДЕСЬ, используя импортированный 'db'

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    users = db.relationship('User', backref='role', lazy=True)
    def __repr__(self): return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Важно: Указываем модель VisitLog как строку, т.к. она определена ниже
    visit_logs = db.relationship('VisitLog', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password) if self.password_hash else False
    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part)
    def __repr__(self): return f'<User {self.username}>'
    def is_admin(self): return self.role and self.role.name == 'Admin'

class VisitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(100), nullable=False)
    # Важно: Указываем модель User как строку, чтобы избежать проблем с порядком определения
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    def __repr__(self):
        user_info = f"User ID: {self.user_id}" if self.user_id else "Anonymous"
        return f'<VisitLog {self.id}: {self.path} by {user_info} at {self.created_at}>'