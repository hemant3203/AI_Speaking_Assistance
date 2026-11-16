"""second takes and daily challenges

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('practice_sessions', sa.Column('retry_of', sa.Uuid(as_uuid=False), nullable=True))
    op.add_column('practice_sessions', sa.Column('challenge_date', sa.Date(), nullable=True))
    op.create_foreign_key(
        op.f('fk_practice_sessions_retry_of_practice_sessions'),
        'practice_sessions', 'practice_sessions', ['retry_of'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_practice_sessions_retry_of', 'practice_sessions', ['retry_of'], unique=False)
    op.add_column('daily_activity', sa.Column('comebacks', sa.Integer(), server_default='0', nullable=False))
    op.add_column('profiles', sa.Column('challenges_completed', sa.Integer(), server_default='0', nullable=False))
    op.add_column('profiles', sa.Column('comebacks', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('profiles', 'comebacks')
    op.drop_column('profiles', 'challenges_completed')
    op.drop_column('daily_activity', 'comebacks')
    op.drop_index('ix_practice_sessions_retry_of', table_name='practice_sessions')
    op.drop_constraint(op.f('fk_practice_sessions_retry_of_practice_sessions'), 'practice_sessions', type_='foreignkey')
    op.drop_column('practice_sessions', 'challenge_date')
    op.drop_column('practice_sessions', 'retry_of')
