"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { errorMessage } from "../lib/api";
import { exportReview, useWorkspaceRequest } from "../lib/workspace-review";
type Finding = { obligation: { id: string; text: string; source_page?: string; source_section?: string; source_text_snippet?: string; version_id: string; status: string }; control: { id?: string; code: string }; mapping: { status: string }; evidence: { id: string; title: string; status: string }[]; gaps: { id: string; type: string; severity: string; status: string }[] };
type Answer = { method: string; summary: string; total: number; truncated: boolean; findings: Finding[]; audit_id: string };
type Audit = { id: string; action: string; entity_type: string; created_at: string };
export default function InvestigationWorkspace({ token, organizationId }: { token: string; organizationId: string }) {
  const { request, isActive } = useWorkspaceRequest(token);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [logs, setLogs] = useState<Audit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const next = await request<Audit[]>(`/audit/logs?organization_id=${organizationId}&limit=20`, undefined, "GET");
    if (isActive()) setLogs(next);
  }, [organizationId, request, isActive]);
  useEffect(() => { const timer = setTimeout(() => { void refresh().catch(reason => { if (isActive()) setError(errorMessage(reason)); }); }, 0); return () => clearTimeout(timer); }, [refresh, isActive]);
  async function investigate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      const result = await request<Answer>("/intelligence/investigate", { organization_id: organizationId, question: form.get("question") });
      if (!isActive()) return;
      setAnswer(result); await refresh();
    } catch (reason) { if (isActive()) setError(errorMessage(reason)); }
    finally { if (isActive()) setBusy(false); }
  }
  return <div className="review-workspace"><section className="panel-card intake-card"><h2>Ask the workspace</h2><p className="muted">Guided questions query recorded links, retain source citations and add an audit event. No external model or legal interpretation is used.</p><form className="intake-form" onSubmit={investigate}><label>Investigation question<select name="question"><option value="open_gaps">Which obligation links have open gaps?</option><option value="unmapped_obligations">Which obligations have no mapped control?</option><option value="evidence_review">Which control links need evidence review?</option><option value="control_coverage">Which obligations link to controls?</option></select></label><button className="button button-primary" disabled={busy}>Run workspace investigation</button></form>{error && <p className="form-error" role="alert">{error}</p>}</section>
    {answer && <section className="panel-card"><h2>Recorded findings</h2><p role="status">{answer.summary}</p><p className="muted">Audit event: {answer.audit_id}{answer.truncated && " / showing the first 50 matching links"}</p>{answer.findings.map((finding, index) => <article className="source-review" key={`${finding.obligation.id}-${index}`}><h3>{finding.obligation.source_section ?? "Recorded obligation"}</h3><p>{finding.obligation.text}</p><p>Control: {finding.control.code} / mapping: {finding.mapping.status} / obligation: {finding.obligation.status}</p>{finding.obligation.source_text_snippet ? <blockquote>{finding.obligation.source_text_snippet}</blockquote> : <p className="muted">No source quote recorded. Review the source before relying on this finding.</p>}<p className="muted">Version {finding.obligation.version_id} / page {finding.obligation.source_page ?? "not recorded"}</p><p>{finding.evidence.length} evidence records / {finding.gaps.filter(gap => gap.status === "open").length} open gaps</p></article>)}<button className="button button-secondary" onClick={() => exportReview("workspace-investigation.json", answer)}>Export investigation</button></section>}
    <section className="panel-card"><div className="panel-heading"><h2>Recent audit trail</h2><button className="button button-secondary" disabled={busy} onClick={() => { void refresh().catch(reason => setError(errorMessage(reason))); }}>Refresh audit trail</button></div>{logs.length ? <ol className="audit-list">{logs.map(log => <li key={log.id}><strong>{log.action.replaceAll("_", " ")}</strong><span>{log.entity_type} / {new Date(log.created_at).toLocaleString()}</span></li>)}</ol> : <p className="muted">Recorded review and investigation events appear here.</p>}</section></div>;
}
