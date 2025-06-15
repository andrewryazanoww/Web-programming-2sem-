# app/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, DateField, DecimalField, RadioField, SelectMultipleField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, NumberRange, ValidationError

# Импортируем db и модели, если нужны для QuerySelectField или кастомных валидаторов
# В данной версии форм db напрямую не используется в __init__ для choices
from .extensions import db # Может понадобиться, если захотите вернуть логику в __init__
from .models import Category, User, Role # Role нужна для ServiceRecordForm, если бы choices заполнялись тут

# --- Формы для аутентификации ---
class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired("Поле 'Логин' не может быть пустым.")])
    password = PasswordField('Пароль', validators=[DataRequired("Поле 'Пароль' не может быть пустым.")])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

# --- Формы для оборудования ---
class EquipmentForm(FlaskForm):
    name = StringField('Название оборудования', validators=[DataRequired("Поле 'Название' обязательно для заполнения.")])
    inventory_number = StringField('Инвентарный номер', validators=[DataRequired("Поле 'Инвентарный номер' обязательно для заполнения.")])
    category_id = SelectField('Категория', coerce=int, validators=[DataRequired("Пожалуйста, выберите категорию.")])
    purchase_date = DateField('Дата покупки (ГГГГ-ММ-ДД)', format='%Y-%m-%d', validators=[DataRequired("Поле 'Дата покупки' обязательно для заполнения.")])
    cost = DecimalField('Стоимость', places=2, validators=[DataRequired("Поле 'Стоимость' обязательно для заполнения."), NumberRange(min=0.01, message="Стоимость должна быть положительным числом.")])
    status_choices = [
        ('В эксплуатации', 'В эксплуатации'),
        ('На ремонте', 'На ремонте'),
        ('Списано', 'Списано')
    ]
    status = RadioField('Статус', choices=status_choices, validators=[DataRequired("Пожалуйста, выберите статус.")], default='В эксплуатации')
    notes = TextAreaField('Примечание (опционально)', validators=[Optional(), Length(max=5000)])
    image = FileField('Фотография оборудования (опционально)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Разрешены только изображения форматов: jpg, jpeg, png, gif!')
    ])
    responsible_person_ids = SelectMultipleField(
        'Ответственные лица',
        coerce=int,
        validators=[Optional()]
    )
    submit = SubmitField('Сохранить')

    def __init__(self, *args, **kwargs):
        super(EquipmentForm, self).__init__(*args, **kwargs)
        # Заполнение choices для category_id и responsible_person_ids происходит в роутах
        pass


# --- Формы для истории обслуживания ---
class ServiceRecordForm(FlaskForm):
    service_type = StringField('Тип обслуживания/работ', validators=[DataRequired("Укажите тип обслуживания.")], description="Например: Ремонт, Плановое ТО, Замена картриджа")
    description = TextAreaField('Описание работ и комментарий', validators=[DataRequired("Опишите выполненные работы.")])
    planned_date = DateField('Плановая дата (ГГГГ-ММ-ДД)', format='%Y-%m-%d', validators=[Optional()])
    service_date = DateField('Фактическая дата выполнения (ГГГГ-ММ-ДД)', format='%Y-%m-%d', validators=[Optional()])
    status_choices = [
        ('Запланировано', 'Запланировано'),
        ('В процессе', 'В процессе'),
        ('Выполнено', 'Выполнено'),
        ('Отменено', 'Отменено')
    ]
    status = SelectField('Статус ТО', choices=status_choices, validators=[DataRequired("Выберите статус.")], default='Запланировано')
    performed_by_id = SelectField('Выполнил (сотрудник)', coerce=int, validators=[Optional()])
    submit = SubmitField('Сохранить запись')

    def __init__(self, *args, **kwargs):
        super(ServiceRecordForm, self).__init__(*args, **kwargs)
        # Начальная установка choices. Они будут ПЕРЕЗАПОЛНЕНЫ в роуте.
        self.performed_by_id.choices = [(0, '-- Не выбран (внешний исполнитель) --')]

    def validate_service_date(form, field):
        if form.status.data == 'Выполнено' and not field.data:
            raise ValidationError('Для статуса "Выполнено" необходимо указать фактическую дату выполнения.')
        if field.data and form.status.data == 'Запланировано':
            raise ValidationError('Если указана фактическая дата выполнения, статус не может быть "Запланировано". Выберите "В процессе" или "Выполнено".')
        if field.data and form.planned_date.data and field.data < form.planned_date.data:
             raise ValidationError('Фактическая дата выполнения не может быть раньше плановой даты.')

    def validate_planned_date(form, field):
        if form.status.data == 'Запланировано' and not field.data:
            raise ValidationError('Для статуса "Запланировано" необходимо указать плановую дату.')