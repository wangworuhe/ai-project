"""Initial migration.

Revision ID: 4f12c8dae5b7
Revises: 
Create Date: 2025-03-21 15:37:20.910542

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f12c8dae5b7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('_alembic_tmp_assessments')
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.alter_column('pronunciation_score',
               existing_type=sa.FLOAT(),
               nullable=True)
        batch_op.alter_column('accuracy_score',
               existing_type=sa.FLOAT(),
               nullable=True)
        batch_op.alter_column('fluency_score',
               existing_type=sa.FLOAT(),
               nullable=True)
        batch_op.alter_column('completeness_score',
               existing_type=sa.FLOAT(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.alter_column('completeness_score',
               existing_type=sa.FLOAT(),
               nullable=False)
        batch_op.alter_column('fluency_score',
               existing_type=sa.FLOAT(),
               nullable=False)
        batch_op.alter_column('accuracy_score',
               existing_type=sa.FLOAT(),
               nullable=False)
        batch_op.alter_column('pronunciation_score',
               existing_type=sa.FLOAT(),
               nullable=False)

    op.create_table('_alembic_tmp_assessments',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('text', sa.TEXT(), nullable=True),
    sa.Column('pronunciation_score', sa.FLOAT(), nullable=False),
    sa.Column('accuracy_score', sa.FLOAT(), nullable=False),
    sa.Column('fluency_score', sa.FLOAT(), nullable=False),
    sa.Column('completeness_score', sa.FLOAT(), nullable=False),
    sa.Column('prosody_score', sa.FLOAT(), nullable=False),
    sa.Column('vocabulary_score', sa.FLOAT(), nullable=False),
    sa.Column('grammar_score', sa.FLOAT(), nullable=False),
    sa.Column('topic_score', sa.FLOAT(), nullable=False),
    sa.Column('audio_path', sa.VARCHAR(length=255), nullable=False),
    sa.Column('audio_duration', sa.FLOAT(), nullable=False),
    sa.Column('language', sa.VARCHAR(length=10), nullable=False),
    sa.Column('assessment_type', sa.VARCHAR(length=20), nullable=False),
    sa.Column('error_message', sa.TEXT(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('processed_at', sa.DATETIME(), nullable=False),
    sa.Column('content_assessment_result', sa.TEXT(), nullable=False),
    sa.Column('words', sa.TEXT(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
