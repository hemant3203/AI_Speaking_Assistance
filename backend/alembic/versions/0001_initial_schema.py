"""initial schema

Revision ID: 0001
Revises: 
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=40), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('equipped_coach', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('daily_activity',
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('local_date', sa.Date(), nullable=False),
    sa.Column('sessions', sa.Integer(), nullable=False),
    sa.Column('speaking_seconds', sa.Float(), nullable=False),
    sa.Column('live_seconds', sa.Float(), nullable=False),
    sa.Column('best_score', sa.Integer(), nullable=False),
    sa.Column('low_filler_done', sa.Boolean(), nullable=False),
    sa.Column('on_pace_done', sa.Boolean(), nullable=False),
    sa.Column('modes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_daily_activity_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'local_date', name=op.f('pk_daily_activity'))
    )
    op.create_table('owned_items',
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('item_id', sa.String(length=32), nullable=False),
    sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_owned_items_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'item_id', name=op.f('pk_owned_items'))
    )
    op.create_table('practice_sessions',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('mode', sa.String(length=32), nullable=False),
    sa.Column('topic', sa.String(length=200), nullable=False),
    sa.Column('language', sa.String(length=16), nullable=False),
    sa.Column('coach_id', sa.String(length=32), nullable=False),
    sa.Column('target_seconds', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('local_date', sa.Date(), nullable=False),
    sa.Column('speaking_seconds', sa.Float(), nullable=True),
    sa.Column('live_seconds', sa.Float(), nullable=False),
    sa.Column('word_count', sa.Integer(), nullable=True),
    sa.Column('wpm', sa.Float(), nullable=True),
    sa.Column('filler_count', sa.Integer(), nullable=True),
    sa.Column('filler_per_100', sa.Float(), nullable=True),
    sa.Column('filler_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('hedge_count', sa.Integer(), nullable=True),
    sa.Column('pause_count', sa.Integer(), nullable=True),
    sa.Column('longest_pause_seconds', sa.Float(), nullable=True),
    sa.Column('pause_ratio', sa.Float(), nullable=True),
    sa.Column('volume_variation', sa.Float(), nullable=True),
    sa.Column('vocabulary_ratio', sa.Float(), nullable=True),
    sa.Column('scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('overall_score', sa.Integer(), nullable=True),
    sa.Column('ai_scored', sa.Boolean(), nullable=False),
    sa.Column('analysis_model', sa.String(length=64), nullable=True),
    sa.Column('filler_counts_reliable', sa.Boolean(), nullable=False),
    sa.Column('feedback', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('transcript', sa.Text(), nullable=True),
    sa.Column('coach_transcript', sa.Text(), nullable=True),
    sa.Column('xp_awarded', sa.Integer(), nullable=False),
    sa.Column('sparks_awarded', sa.Integer(), nullable=False),
    sa.Column('result_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('finalised_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_practice_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_practice_sessions'))
    )
    op.create_index('ix_practice_sessions_status', 'practice_sessions', ['status'], unique=False)
    op.create_index('ix_practice_sessions_user_local_date', 'practice_sessions', ['user_id', 'local_date'], unique=False)
    op.create_index('ix_practice_sessions_user_status_started', 'practice_sessions', ['user_id', 'status', 'started_at'], unique=False)
    op.create_table('profiles',
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('xp', sa.Integer(), nullable=False),
    sa.Column('sparks', sa.Integer(), nullable=False),
    sa.Column('streak_current', sa.Integer(), nullable=False),
    sa.Column('streak_longest', sa.Integer(), nullable=False),
    sa.Column('last_practice_date', sa.Date(), nullable=True),
    sa.Column('freezes', sa.Integer(), nullable=False),
    sa.Column('total_sessions', sa.Integer(), nullable=False),
    sa.Column('total_speaking_seconds', sa.Float(), nullable=False),
    sa.Column('best_score', sa.Integer(), nullable=True),
    sa.Column('clean_sessions', sa.Integer(), nullable=False),
    sa.Column('pace_in_band_sessions', sa.Integer(), nullable=False),
    sa.Column('modes_practised', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_profiles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_profiles'))
    )
    op.create_table('quest_completions',
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('local_date', sa.Date(), nullable=False),
    sa.Column('quest_id', sa.String(length=32), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_quest_completions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'local_date', 'quest_id', name=op.f('pk_quest_completions'))
    )
    op.create_table('streak_days',
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('local_date', sa.Date(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_streak_days_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'local_date', name=op.f('pk_streak_days'))
    )
    op.create_table('user_badges',
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('badge_id', sa.String(length=32), nullable=False),
    sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_badges_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'badge_id', name=op.f('pk_user_badges'))
    )
    op.create_table('ledger_entries',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('session_id', sa.Uuid(as_uuid=False), nullable=True),
    sa.Column('dedupe_key', sa.String(length=96), nullable=True),
    sa.Column('reason', sa.String(length=120), nullable=False),
    sa.Column('xp', sa.Integer(), nullable=False),
    sa.Column('sparks', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['practice_sessions.id'], name=op.f('fk_ledger_entries_session_id_practice_sessions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ledger_entries_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ledger_entries')),
    sa.UniqueConstraint('user_id', 'dedupe_key', name='uq_ledger_entries_user_dedupe_key')
    )
    op.create_index(op.f('ix_ledger_entries_session_id'), 'ledger_entries', ['session_id'], unique=False)
    op.create_index('ix_ledger_entries_user_created', 'ledger_entries', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ledger_entries_user_created', table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_session_id'), table_name='ledger_entries')
    op.drop_table('ledger_entries')
    op.drop_table('user_badges')
    op.drop_table('streak_days')
    op.drop_table('quest_completions')
    op.drop_table('profiles')
    op.drop_index('ix_practice_sessions_user_status_started', table_name='practice_sessions')
    op.drop_index('ix_practice_sessions_user_local_date', table_name='practice_sessions')
    op.drop_index('ix_practice_sessions_status', table_name='practice_sessions')
    op.drop_table('practice_sessions')
    op.drop_table('owned_items')
    op.drop_table('daily_activity')
    op.drop_table('users')
