import re
from flask import Flask, request, render_template, make_response, session

app = Flask(__name__)
# Добавим секретный ключ для работы с сессиями (нужно для cookies)
# В реальном приложении используйте более надежный ключ и храните его безопасно
app.secret_key = 'your secret key'

# --- Главная страница и установка Cookie для теста ---
@app.route('/')
def index():
    # Установим тестовый cookie при первом заходе для демонстрации
    resp = make_response(render_template('index.html'))
    if 'test_cookie' not in request.cookies:
        resp.set_cookie('test_cookie', 'Flask_Lab_Value')
    return resp

# --- 1. Отображение данных запроса ---
@app.route('/request-info', methods=['GET', 'POST'])
def request_info():
    # Данные для передачи в шаблон
    context = {
        'url_params': request.args,
        'headers': request.headers,
        'cookies': request.cookies,
        'form_data': None # Будет заполнено при POST-запросе
    }
    # Если это POST запрос (например, с тестовой формы), получим данные формы
    if request.method == 'POST':
        context['form_data'] = request.form

    return render_template('request_info.html', **context)

# --- 2. Форма с обработкой ошибок ---
@app.route('/phone', methods=['GET', 'POST'])
def phone_form():
    error_message = None
    input_class = "form-control" # Начальный класс для поля ввода
    phone_number_input = "" # Сохраняем введенное значение
    formatted_number = None

    if request.method == 'POST':
        phone_number_input = request.form.get('phone_number', '')
        original_number = phone_number_input # Сохраняем оригинальный ввод

        # 1. Проверка на недопустимые символы
        allowed_chars = set("0123456789 +-().")
        if not all(char in allowed_chars for char in phone_number_input):
            error_message = "Недопустимый ввод. В номере телефона встречаются недопустимые символы."
            input_class += " is-invalid"
        else:
            # 2. Очистка номера от лишних символов
            # Удаляем все, кроме цифр
            cleaned_number = re.sub(r'\D', '', phone_number_input)

            # 3. Проверка длины
            has_plus_seven_or_eight = phone_number_input.lstrip().startswith('+7') or phone_number_input.lstrip().startswith('8')
            expected_len = 11 if has_plus_seven_or_eight else 10
            actual_len = len(cleaned_number)

            # Корректируем длину, если номер начинался не с +7/8, но цифр 11 (неявно подразумевается 8)
            # Или если начинался с +7/8, но цифр 10 (некорректно)
            if not has_plus_seven_or_eight and actual_len == 11 and cleaned_number.startswith('7'):
                 # Если ввели 79xxxxxxxxx без +, считаем его как 10-значный без 7 в начале
                 cleaned_number = cleaned_number[1:]
                 actual_len = 10
                 expected_len = 10 # Переопределяем ожидаемую длину

            if actual_len != expected_len:
                 # Особый случай: если длина 11, но номер не начинается с 7 или 8 - это ошибка
                if actual_len == 11 and not (cleaned_number.startswith('7') or cleaned_number.startswith('8')):
                     error_message = "Недопустимый ввод. Неверное количество цифр."
                     input_class += " is-invalid"
                # Основная проверка длины
                elif actual_len != 10 and actual_len != 11:
                    error_message = "Недопустимый ввод. Неверное количество цифр."
                    input_class += " is-invalid"
                # Случай, когда ожидалось 10, а получили 11 (и не начинается с 7/8)
                elif expected_len == 10 and actual_len == 11 and not (cleaned_number.startswith('7') or cleaned_number.startswith('8')):
                     error_message = "Недопустимый ввод. Неверное количество цифр."
                     input_class += " is-invalid"
                 # Случай, когда ожидалось 11, а получили 10
                elif expected_len == 11 and actual_len == 10:
                     error_message = "Недопустимый ввод. Неверное количество цифр."
                     input_class += " is-invalid"

            # 4. Форматирование (если нет ошибок)
            if error_message is None:
                # Приводим к 11-значному формату с 8 в начале
                if actual_len == 10:
                    final_number = '8' + cleaned_number
                elif actual_len == 11:
                    if cleaned_number.startswith('7'):
                        final_number = '8' + cleaned_number[1:]
                    else: # Уже начинается с 8
                        final_number = cleaned_number
                else:
                    # Эта ветка не должна выполниться из-за проверок выше, но на всякий случай
                    final_number = None

                if final_number and len(final_number) == 11:
                     # Форматируем как 8-XXX-XXX-XX-XX
                    formatted_number = f"8-{final_number[1:4]}-{final_number[4:7]}-{final_number[7:9]}-{final_number[9:11]}"
                else:
                    # Если что-то пошло не так при форматировании
                     error_message = "Ошибка форматирования номера." # Маловероятно
                     input_class += " is-invalid"


    return render_template('phone_form.html',
                           error_message=error_message,
                           input_class=input_class,
                           phone_number_input=phone_number_input, # Возвращаем введенное значение в поле
                           formatted_number=formatted_number)


if __name__ == '__main__':
    # debug=True удобен для разработки, но его нужно ВЫКЛЮЧИТЬ для Render
    # Render будет использовать gunicorn, эта часть не будет выполняться на сервере
    app.run(debug=True)