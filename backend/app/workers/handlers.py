import json
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from app.services.queue import Job, JobHandler, JobQueue
# Register ORM relationships without importing the AI workflows at startup.
from app.db import base as registered_models  # noqa: F401
from app.db.session import SessionLocal
from app.models.regulation import DocumentStatus, RegulatoryDocument, RegulatoryVersion
from app.services.storage import get_private_storage
from app.models.control import Policy, Control
from app.models.obligation import RegulatoryObligation
from app.models.evidence_model import Evidence
from app.models.gap import Gap
from app.models.change import RegulatoryChange, ImpactAssessment, Simulation


def _get_organization_record(db, model, record_id: UUID, organization_id: UUID):
    """Load a worker target only inside the organization carried by the trusted job envelope."""
    return db.query(model).filter(
        model.id == record_id,
        model.organization_id == organization_id,
    ).first()


class RegulationProcessHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.services.parser import parse_document_bytes, DocumentParser

        db = SessionLocal()
        try:
            version_id = UUID(job.payload["version_id"])

            version = db.query(RegulatoryVersion).join(RegulatoryDocument).filter(
                RegulatoryVersion.id == version_id,
                RegulatoryDocument.organization_id == UUID(job.organization_id),
            ).first()

            if not version:
                raise ValueError(f"Version {version_id} not found")

            if not version.file_reference and not version.raw_text:
                raise ValueError("Version has no source document (file_reference) or raw_text")

            if version.file_reference:
                expected_key_prefix = f"regulations/{job.organization_id}/{version.id}/"
                if not version.file_reference.startswith(expected_key_prefix):
                    raise ValueError("Stored document does not belong to this organization and version")
                storage = get_private_storage()
                file_type = Path(version.file_reference).suffix.lstrip(".")
                parsed = parse_document_bytes(storage.read(version.file_reference), file_type)
                version.raw_text = parsed.sanitized_text
            else:
                # raw_text is already set, just sanitize it
                parser = DocumentParser()
                parsed = parser.parse_text_content(version.raw_text)
                version.raw_text = parsed.sanitized_text

            version.source_pages = json.dumps([DocumentParser()._sanitize(page) for page in parsed.pages])
            version.status = DocumentStatus.PARSED.value
            version.document.status = DocumentStatus.PARSED.value
            db.commit()

            return {
                "version_id": str(version_id),
                "status": "parsed",
                "page_count": parsed.metadata.get("page_count", 0),
                "injection_warnings": parsed.injection_warnings,
                "next_step": "extract_obligations",
            }

        except Exception as e:
            db.rollback()
            version = db.query(RegulatoryVersion).join(RegulatoryDocument).filter(
                RegulatoryVersion.id == UUID(job.payload["version_id"]),
                RegulatoryDocument.organization_id == UUID(job.organization_id),
            ).first()
            if version:
                version.status = DocumentStatus.FAILED.value
                version.document.status = DocumentStatus.FAILED.value
                db.commit()
            raise
        finally:
            db.close()


class ObligationExtractionHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.services.parser import DocumentParser
        from app.agents.extraction import run_obligation_extraction

        db = SessionLocal()
        try:
            version_id = UUID(job.payload["version_id"])

            version = db.query(RegulatoryVersion).join(RegulatoryDocument).filter(
                RegulatoryVersion.id == version_id,
                RegulatoryDocument.organization_id == UUID(job.organization_id),
            ).first()

            if not version:
                raise ValueError(f"Version {version_id} not found")

            if not version.raw_text:
                raise ValueError("Version has no parsed text. Run process first.")

            version.status = DocumentStatus.PROCESSING.value
            version.document.status = DocumentStatus.PROCESSING.value
            db.commit()

            parser = DocumentParser()
            chunks = parser.chunk_document(
                type('ParsedDocument', (), {
                    'raw_text': version.raw_text,
                    'pages': json.loads(version.source_pages) if version.source_pages else [version.raw_text],
                    'metadata': {},
                    'injection_warnings': [],
                    'sanitized_text': version.raw_text,
                })()
            )

            result = await run_obligation_extraction(
                version_id=version_id,
                organization_id=UUID(job.organization_id),
                document_text=version.raw_text,
                chunks=chunks,
            )

            if result.success:
                version.status = DocumentStatus.PROCESSED.value
            else:
                version.status = DocumentStatus.FAILED.value
            version.document.status = version.status
            db.commit()

            return {
                "version_id": str(version_id),
                "status": version.status,
                "obligations_extracted": result.result.get("obligations_extracted", 0) if result.result else 0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            version = db.query(RegulatoryVersion).join(RegulatoryDocument).filter(
                RegulatoryVersion.id == UUID(job.payload["version_id"]),
                RegulatoryDocument.organization_id == UUID(job.organization_id),
            ).first()
            if version:
                version.status = DocumentStatus.FAILED.value
                version.document.status = DocumentStatus.FAILED.value
                db.commit()
            raise
        finally:
            db.close()


class PolicyProcessHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.services.parser import parse_document_bytes

        db = SessionLocal()
        try:
            policy_id = UUID(job.payload["policy_id"])
            policy = _get_organization_record(db, Policy, policy_id, UUID(job.organization_id))

            if not policy:
                raise ValueError(f"Policy {policy_id} not found")

            if not policy.file_reference:
                raise ValueError("Policy has no privately stored source document")
            expected_key_prefix = f"policies/{job.organization_id}/{policy.id}/"
            if not policy.file_reference.startswith(expected_key_prefix):
                raise ValueError("Stored document does not belong to this organization and policy")
            storage = get_private_storage()
            file_type = Path(policy.file_reference).suffix.lstrip(".")
            parsed = parse_document_bytes(storage.read(policy.file_reference), file_type)

            policy.raw_text = parsed.sanitized_text
            policy.status = "parsed"
            db.commit()

            return {
                "policy_id": str(policy_id),
                "status": "parsed",
                "page_count": parsed.metadata.get("page_count", 0),
                "injection_warnings": parsed.injection_warnings,
                "next_step": "extract_controls",
            }

        except Exception as e:
            db.rollback()
            policy = db.query(Policy).filter(
                Policy.id == UUID(job.payload["policy_id"]),
                Policy.organization_id == UUID(job.organization_id),
            ).first()
            if policy:
                policy.status = "failed"
                db.commit()
            raise
        finally:
            db.close()


class ControlExtractionHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.services.parser import DocumentParser
        from app.agents.control_extraction import run_control_extraction

        db = SessionLocal()
        try:
            policy_id = UUID(job.payload["policy_id"])

            policy = db.query(Policy).filter(
                Policy.id == policy_id,
                Policy.organization_id == UUID(job.organization_id),
            ).first()

            if not policy:
                raise ValueError(f"Policy {policy_id} not found")

            if not policy.raw_text:
                raise ValueError("Policy has no parsed text. Run process first.")

            policy.status = "processing"
            db.commit()

            parser = DocumentParser()
            chunks = parser.chunk_document(
                type('ParsedDocument', (), {
                    'raw_text': policy.raw_text,
                    'pages': [policy.raw_text],
                    'metadata': {},
                    'injection_warnings': [],
                    'sanitized_text': policy.raw_text,
                })()
            )

            result = await run_control_extraction(
                policy_id=policy_id,
                organization_id=UUID(job.organization_id),
                document_text=policy.raw_text,
                chunks=chunks,
            )

            if result.success:
                policy.status = "processed"
            else:
                policy.status = "failed"
            db.commit()

            return {
                "policy_id": str(policy_id),
                "status": policy.status,
                "controls_extracted": result.result.get("controls_extracted", 0) if result.result else 0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            policy = db.query(Policy).filter(
                Policy.id == UUID(job.payload["policy_id"]),
                Policy.organization_id == UUID(job.organization_id),
            ).first()
            if policy:
                policy.status = "failed"
                db.commit()
            raise
        finally:
            db.close()


class MappingHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.mapping import run_mapping

        db = SessionLocal()
        try:
            obligation_id = UUID(job.payload["obligation_id"])

            obligation = _get_organization_record(db, RegulatoryObligation, obligation_id, UUID(job.organization_id))

            if not obligation:
                raise ValueError(f"Obligation {obligation_id} not found")

            result = await run_mapping(
                obligation_id=obligation_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "obligation_id": str(obligation_id),
                "status": "completed" if result.success else "failed",
                "mapping_status": result.result.get("mapping_status") if result.result else "error",
                "confidence": result.result.get("confidence") if result.result else 0.0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class EvidenceValidationHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.evidence import run_evidence_validation

        db = SessionLocal()
        try:
            evidence_id = UUID(job.payload["evidence_id"])

            evidence = _get_organization_record(db, Evidence, evidence_id, UUID(job.organization_id))

            if not evidence:
                raise ValueError(f"Evidence {evidence_id} not found")

            result = await run_evidence_validation(
                evidence_id=evidence_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "evidence_id": str(evidence_id),
                "status": "completed" if result.success else "failed",
                "is_valid": result.result.get("is_valid") if result.result else False,
                "relevance_score": result.result.get("relevance_score") if result.result else 0.0,
                "coverage_score": result.result.get("coverage_score") if result.result else 0.0,
                "completeness_score": result.result.get("completeness_score") if result.result else 0.0,
                "evidence_status": result.result.get("evidence_status") if result.result else "unknown",
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class ControlTestingHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.testing import run_control_testing

        db = SessionLocal()
        try:
            control_id = UUID(job.payload["control_id"])

            control = _get_organization_record(db, Control, control_id, UUID(job.organization_id))

            if not control:
                raise ValueError(f"Control {control_id} not found")

            result = await run_control_testing(
                control_id=control_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "control_id": str(control_id),
                "status": "completed" if result.success else "failed",
                "test_result": result.result.get("test_result") if result.result else "error",
                "effectiveness_score": result.result.get("effectiveness_score") if result.result else 0.0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class GapIdentificationHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.gap import run_gap_identification

        db = SessionLocal()
        try:
            obligation_id = UUID(job.payload["obligation_id"])

            obligation = _get_organization_record(db, RegulatoryObligation, obligation_id, UUID(job.organization_id))

            if not obligation:
                raise ValueError(f"Obligation {obligation_id} not found")

            result = await run_gap_identification(
                obligation_id=obligation_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "obligation_id": str(obligation_id),
                "status": "completed" if result.success else "failed",
                "gap_created": result.result.get("gap_created") if result.result else False,
                "gap_type": result.result.get("gap_type") if result.result else "unknown",
                "severity": result.result.get("severity") if result.result else "unknown",
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class RemediationHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.remediation import run_remediation

        db = SessionLocal()
        try:
            gap_id = UUID(job.payload["gap_id"])

            gap = _get_organization_record(db, Gap, gap_id, UUID(job.organization_id))

            if not gap:
                raise ValueError(f"Gap {gap_id} not found")

            result = await run_remediation(
                gap_id=gap_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "gap_id": str(gap_id),
                "status": "completed" if result.success else "failed",
                "plan_created": result.result.get("plan_id") if result.result else False,
                "priority": result.result.get("priority") if result.result else "unknown",
                "owner": result.result.get("owner") if result.result else "unknown",
                "target_date": result.result.get("target_date") if result.result else None,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class ChangeDetectionHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.change import run_change_detection

        db = SessionLocal()
        try:
            document_id = UUID(job.payload["document_id"])
            old_version_id = UUID(job.payload["old_version_id"])
            new_version_id = UUID(job.payload["new_version_id"])
            organization_id = UUID(job.organization_id)
            document = db.query(RegulatoryDocument).filter(
                RegulatoryDocument.id == document_id,
                RegulatoryDocument.organization_id == organization_id,
            ).first()
            version_ids = {
                version.id for version in db.query(RegulatoryVersion).filter(
                    RegulatoryVersion.document_id == document_id,
                ).all()
            }
            if not document or old_version_id not in version_ids or new_version_id not in version_ids:
                raise ValueError("Regulatory change inputs are not in this organization and document")

            result = await run_change_detection(
                document_id=document_id,
                organization_id=UUID(job.organization_id),
                old_version_id=old_version_id,
                new_version_id=new_version_id,
            )

            return {
                "document_id": str(document_id),
                "status": "completed" if result.success else "failed",
                "changes_detected": result.result.get("changes_detected") if result.result else 0,
                "change_types": result.result.get("change_types") if result.result else [],
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class ImpactAnalysisHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.change import run_impact_analysis

        db = SessionLocal()
        try:
            change_id = UUID(job.payload["change_id"])
            change = _get_organization_record(db, RegulatoryChange, change_id, UUID(job.organization_id))
            if not change:
                raise ValueError(f"Regulatory change {change_id} not found")

            result = await run_impact_analysis(
                change_id=change_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "change_id": str(change_id),
                "status": "completed" if result.success else "failed",
                "affected_controls": result.result.get("affected_controls") if result.result else 0,
                "risk_delta": result.result.get("risk_delta") if result.result else 0.0,
                "new_gaps": result.result.get("new_gaps") if result.result else 0,
                "confidence": result.result.get("confidence") if result.result else 0.0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class SimulationHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.simulation import run_simulation_analysis

        db = SessionLocal()
        try:
            simulation = None
            simulation_id = UUID(job.payload["simulation_id"])

            simulation = _get_organization_record(db, Simulation, simulation_id, UUID(job.organization_id))

            if not simulation:
                raise ValueError(f"Simulation {simulation_id} not found")

            result = await run_simulation_analysis(
                simulation_id=simulation_id,
                organization_id=UUID(job.organization_id),
            )

            return {
                "simulation_id": str(simulation_id),
                "status": "completed" if result.success else "failed",
                "changed_obligations": result.result.get("changed_obligations") if result.result else 0,
                "affected_controls": result.result.get("affected_controls") if result.result else 0,
                "new_gaps": result.result.get("new_gaps") if result.result else 0,
                "risk_delta": result.result.get("risk_delta") if result.result else 0.0,
                "remediation_changes": result.result.get("remediation_changes") if result.result else 0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            if simulation:
                simulation.status = "failed"
                db.commit()
            raise
        finally:
            db.close()


class CrossRegulationHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.intelligence import run_cross_regulation_analysis

        db = SessionLocal()
        try:
            organization_id = UUID(job.organization_id)

            result = await run_cross_regulation_analysis(organization_id)

            return {
                "organization_id": str(organization_id),
                "status": "completed" if result.success else "failed",
                "common_obligations": result.result.get("common_obligations") if result.result else 0,
                "overlapping_controls": result.result.get("overlapping_controls") if result.result else 0,
                "duplicate_requirements": result.result.get("duplicate_requirements") if result.result else 0,
                "consolidation_opportunities": result.result.get("consolidation_opportunities") if result.result else 0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class ContradictionHandler(JobHandler):
    async def handle(self, job: Job) -> Dict[str, Any]:
        from app.agents.intelligence import run_contradiction_detection

        db = SessionLocal()
        try:
            organization_id = UUID(job.organization_id)

            result = await run_contradiction_detection(organization_id)

            return {
                "organization_id": str(organization_id),
                "status": "completed" if result.success else "failed",
                "total_contradictions": result.result.get("total_contradictions") if result.result else 0,
                "high_confidence": result.result.get("high_confidence") if result.result else 0,
                "errors": result.result.get("errors", []) if result.result else [],
                "tokens_used": result.tokens_used,
            }

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


def get_handlers() -> Dict[str, JobHandler]:
    return {
        "regulation_process": RegulationProcessHandler(),
        "obligation_extraction": ObligationExtractionHandler(),
        "policy_process": PolicyProcessHandler(),
        "control_extraction": ControlExtractionHandler(),
        "mapping": MappingHandler(),
        "evidence_validation": EvidenceValidationHandler(),
        "control_testing": ControlTestingHandler(),
        "gap_identification": GapIdentificationHandler(),
        "remediation": RemediationHandler(),
        "change_detection": ChangeDetectionHandler(),
        "impact_analysis": ImpactAnalysisHandler(),
        "simulation": SimulationHandler(),
        "cross_regulation": CrossRegulationHandler(),
        "contradiction": ContradictionHandler(),
    }
