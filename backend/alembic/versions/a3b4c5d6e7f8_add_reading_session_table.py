"""add reading_session table and reading_progress.session_id

Revision ID: a3b4c5d6e7f8
Revises: d7e8f9a0b1c2
Create Date: 2026-10-22 00:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _session_status(status: str, date_started, date_finished) -> str:
    """Map a book's reading status to the equivalent session status."""
    if status == 'currently_reading':
        return 'currently_reading'
    if status == 'did_not_finish':
        return 'did_not_finish'
    if status == 'read':
        return 'read'
    # want_to_read book that still carries reading evidence
    return 'read' if date_finished is not None else 'currently_reading'


def upgrade() -> None:
    op.create_table('reading_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.VARCHAR(), nullable=False),
        sa.Column('date_started', sa.DateTime(), nullable=True),
        sa.Column('date_finished', sa.DateTime(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['book.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reading_session_book_id'), 'reading_session', ['book_id'], unique=False)
    op.create_index(op.f('ix_reading_session_user_id'), 'reading_session', ['user_id'], unique=False)
    op.create_index(op.f('ix_reading_session_status'), 'reading_session', ['status'], unique=False)
    op.create_index(op.f('ix_reading_session_date_started'), 'reading_session', ['date_started'], unique=False)
    op.create_index(op.f('ix_reading_session_date_finished'), 'reading_session', ['date_finished'], unique=False)
    op.create_index(op.f('ix_reading_session_is_current'), 'reading_session', ['is_current'], unique=False)
    op.create_index(
        'uq_reading_session_book_current', 'reading_session', ['book_id'],
        unique=True, sqlite_where=sa.text('is_current = 1'),
    )

    op.add_column('reading_progress', sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_reading_progress_session_id'), 'reading_progress', ['session_id'], unique=False)
    op.create_foreign_key(
        'fk_reading_progress_session_id', 'reading_progress', 'reading_session',
        ['session_id'], ['id'],
    )

    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Backfill: one session per book with reading evidence, mirroring the book
    # dates verbatim so a single-session book behaves identically to before.
    books = bind.execute(
        sa.text("SELECT id, user_id, reading_status, date_started, date_finished FROM book")
    ).fetchall()
    for book_id, user_id, status, date_started, date_finished in books:
        has_progress = bind.execute(
            sa.text("SELECT 1 FROM reading_progress WHERE book_id = :bid LIMIT 1"),
            {"bid": book_id},
        ).first()
        if status == 'want_to_read' and date_started is None and date_finished is None and not has_progress:
            continue

        session_status = _session_status(status, date_started, date_finished)
        is_current = 1 if session_status == 'currently_reading' else 0
        bind.execute(
            sa.text(
                "INSERT INTO reading_session "
                "(book_id, user_id, status, date_started, date_finished, is_current, created_at, updated_at) "
                "VALUES (:book_id, :user_id, :status, :date_started, :date_finished, :is_current, :now, :now)"
            ),
            {
                "book_id": book_id,
                "user_id": user_id,
                "status": session_status,
                "date_started": date_started,
                "date_finished": date_finished,
                "is_current": is_current,
                "now": now,
            },
        )
        session_id = bind.execute(
            sa.text("SELECT id FROM reading_session WHERE book_id = :bid ORDER BY id DESC LIMIT 1"),
            {"bid": book_id},
        ).scalar()
        if session_id is not None:
            bind.execute(
                sa.text("UPDATE reading_progress SET session_id = :sid WHERE book_id = :bid"),
                {"sid": session_id, "bid": book_id},
            )


def downgrade() -> None:
    op.drop_constraint('fk_reading_progress_session_id', 'reading_progress', type_='foreignkey')
    op.drop_index(op.f('ix_reading_progress_session_id'), table_name='reading_progress')
    op.drop_column('reading_progress', 'session_id')
    op.drop_index('uq_reading_session_book_current', table_name='reading_session')
    op.drop_index(op.f('ix_reading_session_is_current'), table_name='reading_session')
    op.drop_index(op.f('ix_reading_session_date_finished'), table_name='reading_session')
    op.drop_index(op.f('ix_reading_session_date_started'), table_name='reading_session')
    op.drop_index(op.f('ix_reading_session_status'), table_name='reading_session')
    op.drop_index(op.f('ix_reading_session_user_id'), table_name='reading_session')
    op.drop_index(op.f('ix_reading_session_book_id'), table_name='reading_session')
    op.drop_table('reading_session')
