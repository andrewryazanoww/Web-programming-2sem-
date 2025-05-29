from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange

class ReviewForm(FlaskForm):
    rating = SelectField(
        'Оценка',
        choices=[
            ('5', '5 -- отлично'),
            ('4', '4 -- хорошо'),
            ('3', '3 -- удовлетворительно'),
            ('2', '2 -- неудовлетворительно'),
            ('1', '1 -- плохо'),
            ('0', '0 -- ужасно')
        ],
        validators=[DataRequired()],
        coerce=int # Преобразует строковое значение в целое число
    )
    text = TextAreaField('Текст отзыва', validators=[DataRequired()])
    submit = SubmitField('Оставить отзыв')