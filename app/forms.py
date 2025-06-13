# app/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed # Убрал FileRequired, т.к. фото не обязательно
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, DateField, DecimalField, RadioField
from wtforms.validators import DataRequired, Length, EqualTo, Email, Optional, Regexp, NumberRange, ValidationError

# Импортируем db и модели, необходимые для заполнения полей SelectField
# или для кастомных валидаторов (если понадобятся)
from .extensions import db
from .models import Category, User, Role # Добавил Role для ServiceRecordForm

# --- Формы для аутентификации ---
class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired("Поле 'Логин' не может быть пустым.")])
    password = PasswordField('Пароль', validators=[DataRequired("Поле 'Пароль' не может быть пустым.")])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

# Если понадобится форма регистрации (по заданию она не требуется через UI)
# class RegistrationForm(FlaskForm):
#     login = StringField('Логин', validators=[DataRequired(), Length(min=4, max=100)])
#     password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
#     confirm_password = PasswordField('Повторите пароль', validators=[DataRequired(), EqualTo('password')])
#     last_name = StringField('Фамилия', validators=[DataRequired()])
#     first_name = StringField('Имя', validators=[DataRequired()])
#     middle_name = StringField('Отчество', validators=[Optional()])
#     submit = SubmitField('Зарегистрироваться')

# --- Формы для оборудования ---
class EquipmentForm(FlaskForm):
    name = StringField('Название оборудования', validators=[DataRequired("Поле 'Название' обязательно для заполнения.")])
    inventory_number = StringField('Инвентарный номер', validators=[DataRequired("Поле 'Инвентарный номер' обязательно для заполнения.")])
    
    # Выпадающий список для категорий
    # coerce=int нужен, чтобы значение из формы корректно преобразовывалось в ID
    # choices будут заполняться в view-функции
    category_id = SelectField('Категория', coerce=int, validators=[DataRequired("Пожалуйста, выберите категорию.")])
    
    purchase_date = DateField('Дата покупки (ГГГГ-ММ-ДД)', format='%Y-%m-%d', validators=[DataRequired("Поле 'Дата покупки' обязательно для заполнения.")])
    cost = DecimalField('Стоимость', places=2, validators=[DataRequired("Поле 'Стоимость' обязательно для заполнения."), NumberRange(min=0.01, message="Стоимость должна быть положительным числом.")])
    
    # Радиокнопки для статуса
    # Значения должны точно совпадать с теми, что в db.Enum в модели Equipment
    status_choices = [
        ('В эксплуатации', 'В эксплуатации'),
        ('На ремонте', 'На ремонте'),
        ('Списано', 'Списано')
    ]
    status = RadioField('Статус', choices=status_choices, validators=[DataRequired("Пожалуйста, выберите статус.")], default='В эксплуатации')
    
    notes = TextAreaField('Примечание (опционально)', validators=[Optional(), Length(max=5000)])
    
    # Поле для загрузки изображения
    image = FileField('Фотография оборудования (опционально)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Разрешены только изображения форматов: jpg, jpeg, png, gif!')
    ])
    
    submit = SubmitField('Сохранить')

    # Конструктор для заполнения choices для category_id
    def __init__(self, *args, **kwargs):
        super(EquipmentForm, self).__init__(*args, **kwargs)
        # Заполняем категории. Это должно быть сделано в контексте приложения,
        # поэтому лучше передавать choices из view или использовать QuerySelectField,
        # но для простоты SelectField можно заполнить так, если db доступен при создании формы.
        # Однако, более правильный подход - заполнять choices в роуте.
        # Здесь мы предполагаем, что категории будут переданы в роут и установлены там.
        # Если используется QuerySelectField, он сам позаботится о запросе.
        # Оставим это для заполнения в view-функции:
        # self.category_id.choices = [(cat.id, cat.name) for cat in Category.query.order_by(Category.name).all()]
        pass # choices для category_id будут установлены в view


# --- Формы для истории обслуживания ---
class ServiceRecordForm(FlaskForm):
    service_type = StringField('Тип обслуживания/работ', validators=[DataRequired("Укажите тип обслуживания.")], description="Например: Ремонт, Плановое ТО, Замена картриджа")
    description = TextAreaField('Описание работ и комментарий', validators=[DataRequired("Опишите выполненные работы.")])
    # Поле для выбора исполнителя (Тех. специалисты и Администраторы)
    # coerce=int, чтобы значение корректно преобразовывалось в ID
    # validators=[Optional()] означает, что поле может быть не заполнено (если исполнитель не из списка)
    performed_by_id = SelectField('Выполнил (сотрудник)', coerce=int, validators=[Optional()])
    submit = SubmitField('Добавить запись об обслуживании')

    def __init__(self, *args, **kwargs):
        super(ServiceRecordForm, self).__init__(*args, **kwargs)
        # Динамически заполняем список исполнителей
        # Это должно выполняться в контексте приложения, чтобы db был доступен.
        # Если форма создается вне контекста, этот код вызовет ошибку.
        # Лучше передавать choices из view-функции или использовать QuerySelectField.
        # Для демонстрации, как это могло бы работать, если db доступен:
        try:
            tech_roles_query = db.session.query(Role).filter(Role.name.in_(['Admin', 'TechSpecialist']))
            tech_roles_ids = [role.id for role in tech_roles_query.all()]

            if tech_roles_ids:
                performers_query = db.session.query(User).filter(User.role_id.in_(tech_roles_ids)).order_by(User.last_name, User.first_name)
                self.performed_by_id.choices = [(0, '-- Не выбран (внешний исполнитель) --')] + [(user.id, user.full_name) for user in performers_query.all()]
            else:
                self.performed_by_id.choices = [(0, '-- Нет доступных исполнителей --')]
        except Exception as e:
            # Если db еще не инициализирован или нет контекста приложения,
            # просто оставляем choices пустыми или с заглушкой.
            # Окончательное заполнение будет в роуте.
            print(f"Ошибка при заполнении исполнителей в ServiceRecordForm: {e}")
            self.performed_by_id.choices = [(0, '-- Ошибка загрузки исполнителей --')]