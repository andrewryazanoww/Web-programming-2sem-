# app/migrations/versions/xxxx_initial_migration.py
import sqlalchemy as sa
from alembic import op
from datetime import datetime # Добавьте этот импорт

# revision identifiers, used by Alembic.
revision = 'ваше_значение_ревизии' # Пример: '0123456789ab'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Ваши команды создания таблиц, сгенерированные Alembic
    # Например:
    # op.create_table('users', ...)
    # op.create_table('categories', ...)
    # op.create_table('courses', ...)
    # op.create_table('images', ...)

    # ... (много сгенерированного кода) ...

    data_upgrades() # Вызов функции data_upgrades

def downgrade():
    # Ваши команды удаления таблиц, сгенерированные Alembic
    # Например:
    # op.drop_table('images')
    # op.drop_table('courses')
    # op.drop_table('categories')
    # op.drop_table('users')
    pass # Или соответствующие downgrade операции

def data_upgrades():
    """Add any optional data upgrade migrations here!"""
    table = sa.sql.table('categories', sa.sql.column('name', sa.String))

    op.bulk_insert(table,
        [
            {'name': 'Программирование'},
            {'name': 'Математика'},
            {'name': 'Языкознание'},
        ]
    )