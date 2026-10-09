"""add_compliance_core_and_agent_tables

Revision ID: c1f543e0d892
Revises: e9bb67c3fcff
Create Date: 2026-10-07 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1f543e0d892'
down_revision: Union[str, Sequence[str], None] = 'e9bb67c3fcff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. regulatory_obligations
    op.create_table(
        'regulatory_obligations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('version_id', sa.UUID(), nullable=False),
        sa.Column('obligation_text', sa.Text(), nullable=False),
        sa.Column('actor', sa.String(length=256), nullable=True),
        sa.Column('requirement', sa.Text(), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('frequency', sa.String(length=128), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_section', sa.String(length=256), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),
        sa.Column('source_text_snippet', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('extraction_model', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending_review'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['version_id'], ['regulatory_versions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regulatory_obligations_organization_id'), 'regulatory_obligations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_regulatory_obligations_version_id'), 'regulatory_obligations', ['version_id'], unique=False)

    # 2. policies
    op.create_table(
        'policies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner', sa.String(length=256), nullable=True),
        sa.Column('file_reference', sa.String(length=1024), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policies_organization_id'), 'policies', ['organization_id'], unique=False)
    op.create_index(op.f('ix_policies_title'), 'policies', ['title'], unique=False)

    # 3. controls
    op.create_table(
        'controls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('policy_id', sa.UUID(), nullable=True),
        sa.Column('control_id_code', sa.String(length=64), nullable=True),
        sa.Column('objective', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner', sa.String(length=256), nullable=True),
        sa.Column('frequency', sa.String(length=128), nullable=True),
        sa.Column('procedure', sa.Text(), nullable=True),
        sa.Column('evidence_requirement', sa.Text(), nullable=True),
        sa.Column('business_unit', sa.String(length=256), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_controls_organization_id'), 'controls', ['organization_id'], unique=False)
    op.create_index(op.f('ix_controls_policy_id'), 'controls', ['policy_id'], unique=False)
    op.create_index(op.f('ix_controls_control_id_code'), 'controls', ['control_id_code'], unique=False)

    # 4. regulation_control_mappings
    op.create_table(
        'regulation_control_mappings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('obligation_id', sa.UUID(), nullable=False),
        sa.Column('control_id', sa.UUID(), nullable=False),
        sa.Column('mapping_status', sa.String(length=32), nullable=False, server_default='mapped'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['obligation_id'], ['regulatory_obligations.id']),
        sa.ForeignKeyConstraint(['control_id'], ['controls.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regulation_control_mappings_organization_id'), 'regulation_control_mappings', ['organization_id'], unique=False)
    op.create_index(op.f('ix_regulation_control_mappings_obligation_id'), 'regulation_control_mappings', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_regulation_control_mappings_control_id'), 'regulation_control_mappings', ['control_id'], unique=False)

    # 5. evidence
    op.create_table(
        'evidence',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('control_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_reference', sa.String(length=1024), nullable=True),
        sa.Column('evidence_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('coverage_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('coverage_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending_review'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['control_id'], ['controls.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evidence_organization_id'), 'evidence', ['organization_id'], unique=False)
    op.create_index(op.f('ix_evidence_control_id'), 'evidence', ['control_id'], unique=False)

    # 6. control_tests
    op.create_table(
        'control_tests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('control_id', sa.UUID(), nullable=False),
        sa.Column('test_type', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('result', sa.String(length=32), nullable=True),
        sa.Column('effectiveness_score', sa.Float(), nullable=True),
        sa.Column('findings', sa.Text(), nullable=True),
        sa.Column('tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tester', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['control_id'], ['controls.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_control_tests_organization_id'), 'control_tests', ['organization_id'], unique=False)
    op.create_index(op.f('ix_control_tests_control_id'), 'control_tests', ['control_id'], unique=False)

    # 7. gaps
    op.create_table(
        'gaps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('obligation_id', sa.UUID(), nullable=True),
        sa.Column('control_id', sa.UUID(), nullable=True),
        sa.Column('gap_type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['obligation_id'], ['regulatory_obligations.id']),
        sa.ForeignKeyConstraint(['control_id'], ['controls.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gaps_organization_id'), 'gaps', ['organization_id'], unique=False)
    op.create_index(op.f('ix_gaps_obligation_id'), 'gaps', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_gaps_control_id'), 'gaps', ['control_id'], unique=False)

    # 8. risk_assessments
    op.create_table(
        'risk_assessments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('gap_id', sa.UUID(), nullable=False),
        sa.Column('likelihood', sa.Float(), nullable=True),
        sa.Column('impact', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(length=32), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('assessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['gap_id'], ['gaps.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gap_id')
    )
    op.create_index(op.f('ix_risk_assessments_gap_id'), 'risk_assessments', ['gap_id'], unique=True)
    op.create_index(op.f('ix_risk_assessments_risk_level'), 'risk_assessments', ['risk_level'], unique=False)

    # 9. remediation_plans
    op.create_table(
        'remediation_plans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('gap_id', sa.UUID(), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=32), nullable=True),
        sa.Column('estimated_effort', sa.String(length=128), nullable=True),
        sa.Column('assigned_to', sa.String(length=256), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='proposed'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['gap_id'], ['gaps.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gap_id')
    )
    op.create_index(op.f('ix_remediation_plans_organization_id'), 'remediation_plans', ['organization_id'], unique=False)
    op.create_index(op.f('ix_remediation_plans_gap_id'), 'remediation_plans', ['gap_id'], unique=True)

    # 10. regulatory_changes
    op.create_table(
        'regulatory_changes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('old_version_id', sa.UUID(), nullable=True),
        sa.Column('new_version_id', sa.UUID(), nullable=False),
        sa.Column('change_type', sa.String(length=64), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('affected_obligations', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='detected'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['document_id'], ['regulatory_documents.id']),
        sa.ForeignKeyConstraint(['old_version_id'], ['regulatory_versions.id']),
        sa.ForeignKeyConstraint(['new_version_id'], ['regulatory_versions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regulatory_changes_organization_id'), 'regulatory_changes', ['organization_id'], unique=False)
    op.create_index(op.f('ix_regulatory_changes_document_id'), 'regulatory_changes', ['document_id'], unique=False)

    # 11. impact_assessments
    op.create_table(
        'impact_assessments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('change_id', sa.UUID(), nullable=False),
        sa.Column('affected_controls', sa.Text(), nullable=True),
        sa.Column('affected_policies', sa.Text(), nullable=True),
        sa.Column('new_gaps_identified', sa.Text(), nullable=True),
        sa.Column('risk_delta', sa.Float(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['change_id'], ['regulatory_changes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_impact_assessments_organization_id'), 'impact_assessments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_impact_assessments_change_id'), 'impact_assessments', ['change_id'], unique=False)

    # 12. simulations
    op.create_table(
        'simulations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('scenario_description', sa.Text(), nullable=True),
        sa.Column('parameters', sa.Text(), nullable=True),
        sa.Column('results', sa.Text(), nullable=True),
        sa.Column('affected_obligations', sa.Text(), nullable=True),
        sa.Column('affected_controls', sa.Text(), nullable=True),
        sa.Column('projected_gaps', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='created'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_simulations_organization_id'), 'simulations', ['organization_id'], unique=False)

    # 13. agent_runs
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('triggered_by', sa.UUID(), nullable=True),
        sa.Column('workflow_type', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_runs_organization_id'), 'agent_runs', ['organization_id'], unique=False)

    # 14. agent_steps
    op.create_table(
        'agent_steps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('agent_name', sa.String(length=128), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('input_data', sa.Text(), nullable=True),
        sa.Column('output_data', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('token_usage', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_steps_run_id'), 'agent_steps', ['run_id'], unique=False)

    # 15. tool_calls
    op.create_table(
        'tool_calls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('step_id', sa.UUID(), nullable=False),
        sa.Column('tool_name', sa.String(length=256), nullable=False),
        sa.Column('input_args', sa.Text(), nullable=True),
        sa.Column('output_result', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['step_id'], ['agent_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tool_calls_step_id'), 'tool_calls', ['step_id'], unique=False)

    # 16. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=256), nullable=False),
        sa.Column('entity_type', sa.String(length=128), nullable=True),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)


def downgrade() -> None:
    # Drop in exact reverse order
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_organization_id'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index(op.f('ix_tool_calls_step_id'), table_name='tool_calls')
    op.drop_table('tool_calls')

    op.drop_index(op.f('ix_agent_steps_run_id'), table_name='agent_steps')
    op.drop_table('agent_steps')

    op.drop_index(op.f('ix_agent_runs_organization_id'), table_name='agent_runs')
    op.drop_table('agent_runs')

    op.drop_index(op.f('ix_simulations_organization_id'), table_name='simulations')
    op.drop_table('simulations')

    op.drop_index(op.f('ix_impact_assessments_change_id'), table_name='impact_assessments')
    op.drop_index(op.f('ix_impact_assessments_organization_id'), table_name='impact_assessments')
    op.drop_table('impact_assessments')

    op.drop_index(op.f('ix_regulatory_changes_document_id'), table_name='regulatory_changes')
    op.drop_index(op.f('ix_regulatory_changes_organization_id'), table_name='regulatory_changes')
    op.drop_table('regulatory_changes')

    op.drop_index(op.f('ix_remediation_plans_gap_id'), table_name='remediation_plans')
    op.drop_index(op.f('ix_remediation_plans_organization_id'), table_name='remediation_plans')
    op.drop_table('remediation_plans')

    op.drop_index(op.f('ix_risk_assessments_risk_level'), table_name='risk_assessments')
    op.drop_index(op.f('ix_risk_assessments_gap_id'), table_name='risk_assessments')
    op.drop_table('risk_assessments')

    op.drop_index(op.f('ix_gaps_control_id'), table_name='gaps')
    op.drop_index(op.f('ix_gaps_obligation_id'), table_name='gaps')
    op.drop_index(op.f('ix_gaps_organization_id'), table_name='gaps')
    op.drop_table('gaps')

    op.drop_index(op.f('ix_control_tests_control_id'), table_name='control_tests')
    op.drop_index(op.f('ix_control_tests_organization_id'), table_name='control_tests')
    op.drop_table('control_tests')

    op.drop_index(op.f('ix_evidence_control_id'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_organization_id'), table_name='evidence')
    op.drop_table('evidence')

    op.drop_index(op.f('ix_regulation_control_mappings_control_id'), table_name='regulation_control_mappings')
    op.drop_index(op.f('ix_regulation_control_mappings_obligation_id'), table_name='regulation_control_mappings')
    op.drop_index(op.f('ix_regulation_control_mappings_organization_id'), table_name='regulation_control_mappings')
    op.drop_table('regulation_control_mappings')

    op.drop_index(op.f('ix_controls_control_id_code'), table_name='controls')
    op.drop_index(op.f('ix_controls_policy_id'), table_name='controls')
    op.drop_index(op.f('ix_controls_organization_id'), table_name='controls')
    op.drop_table('controls')

    op.drop_index(op.f('ix_policies_title'), table_name='policies')
    op.drop_index(op.f('ix_policies_organization_id'), table_name='policies')
    op.drop_table('policies')

    op.drop_index(op.f('ix_regulatory_obligations_version_id'), table_name='regulatory_obligations')
    op.drop_index(op.f('ix_regulatory_obligations_organization_id'), table_name='regulatory_obligations')
    op.drop_table('regulatory_obligations')
