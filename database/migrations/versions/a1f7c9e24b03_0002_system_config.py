"""tabla system_config: parametros operativos editables (§6.13 configuracion).

Revision posterior a `0001_inicial`. En desarrollo la API crea el esquema con
`Base.metadata.create_all`; en produccion aplique: `alembic upgrade head`.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1f7c9e24b03'
down_revision = '6c55f56ea084'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('system_config')
