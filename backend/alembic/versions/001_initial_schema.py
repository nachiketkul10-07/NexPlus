"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-02 04:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. services table
    op.create_table(
        'services',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('identifier', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('environment', sa.String(length=32), nullable=False, server_default='development'),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('health_path', sa.String(length=200), nullable=False, server_default='/api/health'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='unknown'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingest_key_hash', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_services_identifier', 'services', ['identifier'], unique=True)

    # 3. telemetry_events table
    op.create_table(
        'telemetry_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('endpoint', sa.String(length=300), nullable=True),
        sa.Column('status_code', sa.SmallInteger(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=24), nullable=False),
        sa.Column('error_type', sa.String(length=160), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_telemetry_events_service_occurred', 'telemetry_events', ['service_id', 'occurred_at'])
    op.create_index('ix_telemetry_events_service_outcome_occurred', 'telemetry_events', ['service_id', 'outcome', 'occurred_at'])

    # 4. metrics table
    op.create_table(
        'metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('metric_name', sa.String(length=80), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('window_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_metrics_service_name_recorded', 'metrics', ['service_id', 'metric_name', 'recorded_at'])

    # 5. logs table
    op.create_table(
        'logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.String(length=16), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('trace_id', sa.String(length=64), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_logs_service_occurred', 'logs', ['service_id', 'occurred_at'])

    # 6. alert_rules table
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('metric_name', sa.String(length=80), nullable=False),
        sa.Column('operator', sa.String(length=8), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('window_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('create_incident', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('cooldown_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alerts_service_status_triggered', 'alerts', ['service_id', 'status', 'triggered_at'])
    op.create_index('ix_alerts_rule_service_status', 'alerts', ['rule_id', 'service_id', 'status'])

    # 8. incidents table
    op.create_table(
        'incidents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('alert_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('assignee_user_id', sa.UUID(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('investigating_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assignee_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incidents_service_status_opened', 'incidents', ['service_id', 'status', 'opened_at'])


    # 9. incident_events table
    op.create_table(
        'incident_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('actor_user_id', sa.UUID(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incident_events_incident_created', 'incident_events', ['incident_id', 'created_at'])

    # 10. ai_analyses table
    op.create_table(
        'ai_analyses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('incident_id', sa.UUID(), nullable=False),
        sa.Column('model_name', sa.String(length=120), nullable=False),
        sa.Column('prompt_version', sa.String(length=32), nullable=False, server_default='v1'),
        sa.Column('evidence_snapshot', sa.JSON(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('possible_factors', sa.JSON(), nullable=True),
        sa.Column('limitations_note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_analyses_incident_created', 'ai_analyses', ['incident_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_analyses_incident_created', table_name='ai_analyses')
    op.drop_table('ai_analyses')
    op.drop_index('ix_incident_events_incident_created', table_name='incident_events')
    op.drop_table('incident_events')
    op.drop_index('ix_incidents_service_status_opened', table_name='incidents')
    op.drop_table('incidents')
    op.drop_index('ix_alerts_rule_service_status', table_name='alerts')
    op.drop_index('ix_alerts_service_status_triggered', table_name='alerts')
    op.drop_table('alerts')
    op.drop_table('alert_rules')
    op.drop_index('ix_logs_service_occurred', table_name='logs')
    op.drop_table('logs')
    op.drop_index('ix_metrics_service_name_recorded', table_name='metrics')
    op.drop_table('metrics')
    op.drop_index('ix_telemetry_events_service_outcome_occurred', table_name='telemetry_events')
    op.drop_index('ix_telemetry_events_service_occurred', table_name='telemetry_events')
    op.drop_table('telemetry_events')
    op.drop_index('ix_services_identifier', table_name='services')
    op.drop_table('services')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

