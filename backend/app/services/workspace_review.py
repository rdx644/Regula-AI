"""Literal source comparison and guided lookup; never call an external model."""
import difflib
import json
from fastapi import HTTPException
from app.models.change import RegulatoryChange, ImpactAssessment
from app.models.regulation import RegulatoryDocument, RegulatoryVersion
from app.models.audit_log import AuditLog
from app.models.control import Control
from app.services.compliance import compliance_matrix
from app.services.governance import audit, input_fingerprint


def literal_diff(before, after):
    # Bound SequenceMatcher's worst-case cost and report size before comparing.
    if any(len(text) > 50_000 or len(text.splitlines()) > 500 for text in [before, after]):
        raise HTTPException(413, "Text comparison supports up to 50,000 characters and 500 lines per version")
    left, right = before.splitlines(keepends=True), after.splitlines(keepends=True)
    changes = []
    for tag, a, b, c, d in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if tag != "equal":
            changes.append({"kind": {"insert": "added", "delete": "removed", "replace": "modified"}[tag],
                            "old_line_start": a + 1, "new_line_start": c + 1,
                            "before": "".join(left[a:b]), "after": "".join(right[c:d])})
    return changes


def compare_text(db, document, old_id, new_id, actor_id):
    # Serialize comparisons for this authorized source so simultaneous requests
    # reuse the persisted report rather than creating duplicate review drafts.
    db.query(RegulatoryDocument).filter(RegulatoryDocument.id == document.id,
        RegulatoryDocument.organization_id == document.organization_id).with_for_update().one()
    if old_id == new_id:
        raise HTTPException(422, "Choose two distinct versions")
    versions = []
    for version_id in [old_id, new_id]:
        version = db.query(RegulatoryVersion).filter(RegulatoryVersion.id == version_id,
            RegulatoryVersion.document_id == document.id).first()
        if not version:
            raise HTTPException(404, "Version not found")
        if not version.raw_text or version.status not in {"parsed", "processed"}:
            raise HTTPException(409, "Both versions must finish parsing before comparison")
        versions.append(version)
    before, after = versions
    hunks = literal_diff(before.raw_text, after.raw_text)
    fingerprint = input_fingerprint(old_id, new_id, before.raw_text, after.raw_text)
    report = {"method": "literal_text_diff", "fingerprint": fingerprint,
              "old_version_id": str(old_id), "new_version_id": str(new_id),
              "old_version_number": before.version_number, "new_version_number": after.version_number,
              "hunks": hunks,
              "scope_note": "All existing links to the old version are candidates for human review. Text differences do not establish legal impact."}
    if not hunks:
        return {"changed": False, "report": report}
    existing = db.query(RegulatoryChange).filter(RegulatoryChange.organization_id == document.organization_id,
        RegulatoryChange.document_id == document.id, RegulatoryChange.old_version_id == old_id,
        RegulatoryChange.new_version_id == new_id, RegulatoryChange.change_type == "literal_text_diff").all()
    for record in existing:
        try:
            saved = json.loads(record.summary or "{}")
        except (ValueError, TypeError):
            continue
        if isinstance(saved, dict) and saved.get("fingerprint") == fingerprint:
            impact = db.query(ImpactAssessment).filter(ImpactAssessment.organization_id == document.organization_id,
                ImpactAssessment.change_id == record.id).first()
            return {"changed": True, "report": saved, "change_id": record.id,
                    "impact_id": impact.id if impact else None}
    rows = [row for row in compliance_matrix(db, document.organization_id)
            if row["obligation"]["version_id"] == str(old_id)]
    obligations = sorted({row["obligation"]["id"] for row in rows})
    controls = sorted({row["control"]["id"] for row in rows if row["control"]["id"]})
    policies = [str(control.policy_id) for control in db.query(Control).filter(
        Control.organization_id == document.organization_id, Control.id.in_(controls)).all() if control.policy_id]
    report.update(candidate_obligation_ids=obligations, candidate_control_ids=controls,
                  candidate_policy_ids=sorted(set(policies)))
    change = RegulatoryChange(organization_id=document.organization_id, document_id=document.id,
        old_version_id=old_id, new_version_id=new_id, change_type="literal_text_diff", summary=json.dumps(report),
        affected_obligations=json.dumps(obligations), severity=None, status="detected")
    db.add(change)
    db.flush()
    impact = ImpactAssessment(organization_id=document.organization_id, change_id=change.id,
        affected_controls=json.dumps(controls), affected_policies=json.dumps(sorted(set(policies))),
        new_gaps_identified="[]", risk_delta=None, confidence=None, status="draft",
        recommendation="Review the cited text differences and candidate links. No semantic impact, new obligation or authoritative gap has been inferred.")
    db.add(impact)
    db.flush()
    audit(db, document.organization_id, actor_id, "text_change_compared", "regulatory_change", change.id,
          old_version_id=old_id, new_version_id=new_id, hunks=len(hunks), candidate_controls=len(controls))
    db.commit()
    return {"changed": True, "report": report, "change_id": change.id, "impact_id": impact.id}


def investigate(db, organization_id, actor_id, question):
    rows = compliance_matrix(db, organization_id)
    def matches(row):
        if question == "open_gaps":
            return any(gap["status"] == "open" for gap in row["gaps"])
        if question == "unmapped_obligations":
            return not row["control"]["id"]
        if question == "evidence_review":
            return bool(row["control"]["id"]) and (not row["evidence"] or any(e["status"] != "valid" for e in row["evidence"]))
        return bool(row["control"]["id"])
    findings = [row for row in rows if matches(row)]
    trace = AuditLog(organization_id=organization_id, user_id=actor_id, action="workspace_investigated",
        entity_type="organization", entity_id=organization_id,
        details=json.dumps({"question": question, "matched_links": len(findings), "method": "structured_workspace_lookup"}))
    db.add(trace)
    db.flush()
    trace_id = trace.id
    db.commit()
    return {"method": "structured_workspace_lookup", "question": question,
            "summary": f"{len(findings)} recorded obligation/control links match this question. These are workspace facts, not model or legal conclusions.",
            "total": len(findings), "truncated": len(findings) > 50, "findings": findings[:50], "audit_id": trace_id}
