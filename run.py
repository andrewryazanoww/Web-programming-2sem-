# run.py
from app import create_app # Импортируем фабрику из пакета app (из app/__init__.py)
import os

# Создаем экземпляр приложения Flask с помощью фабрики
app = create_app()

if __name__ == '__main__':
    # Получаем порт из переменной окружения (для Render) или используем 5000 по умолчанию
    port = int(os.environ.get("PORT", 5000))
    # debug=True для локальной разработки. На Render Gunicorn сам управляет этим.
    # host='0.0.0.0' чтобы сервер был доступен извне (например, в Docker или локальной сети)
    app.run(host='0.0.0.0', port=port, debug=True)