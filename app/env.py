# app/migrations/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

# Импортируйте вашу модель и другие необходимые объекты
import sys
import os
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..'))
from app import db # Убедитесь, что app.db доступен

# Этот блок обычно уже есть
config = context.config
fileConfig(config.config_file_name)
target_metadata = db.metadata # Используйте метаданные вашей базы данных Flask-SQLAlchemy

# Если требуется, раскомментируйте и измените этот блок
# SKIP_TABLES = ['questions', 'attributes', 'visit_logs', 'incidents', 'users2', 'users', 'users1', 'roles', 'roles1', 'roles2', 'students', 'restaurants']
# def include_object(object, name, type_, reflected, compare_to):
#     if type_ == 'table' and name in SKIP_TABLES:
#         return False
#     # Можно добавить условия для индексов или других объектов
#     return True

# context.configure(
#     url=config.get_main_option("sqlalchemy.url"),
#     target_metadata=target_metadata,
#     literal_binds=True,
#     dialect_opts={"paramstyle": "named"},
#     # include_object=include_object # Раскомментировать, если используете include_object
# )