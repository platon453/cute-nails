"""sync_models_username_slot_id_firstname

Revision ID: a1b2c3d4e5f6
Revises: 9002ba9cf653
Create Date: 2026-07-08 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9002ba9cf653'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем колонку username в таблицу users
    op.add_column('users', sa.Column('username', sa.String(length=32), nullable=True))

    # 2. Убираем ограничение unique на slot_id в bookings
    #    (имя constraint генерируется Alembic как uq_bookings_slot_id)
    op.drop_constraint('bookings_slot_id_key', 'bookings', type_='unique')

    # 3. Меняем длину first_name с 150 на 64
    op.alter_column('users', 'first_name',
                     existing_type=sa.String(length=150),
                     type_=sa.String(length=64),
                     existing_nullable=False)


def downgrade() -> None:
    # Откат: убираем username, возвращаем unique, возвращаем длину
    op.alter_column('users', 'first_name',
                     existing_type=sa.String(length=64),
                     type_=sa.String(length=150),
                     existing_nullable=False)

    op.create_unique_constraint('bookings_slot_id_key', 'bookings', ['slot_id'])

    op.drop_column('users', 'username')
