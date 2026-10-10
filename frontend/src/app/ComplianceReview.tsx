"use client";
import { useEffect, useRef, useState } from "react";
import JobTracker from "./JobTracker";
import { api } from "../lib/api";
import { useCapabilities } from "../lib/capabilities";
export type ReviewRow = {
  obligation: { id: string; text: string; status: string; source_page?: number; source_section?: string };
  applicability: string;
  mapping: { id?: string | null; status: string; approved?: boolean };
  control: { id?: string | null; code?: string };
  gaps: { id: string; type: string; severity: string; status: string }[];
  remediation?: { id: string; recommendation: string; status: string; priority: string } | null;
};

export default function ComplianceReview({ rows, token, organizationId, refresh }: {
  rows: ReviewRow[]; token: string; organizationId: string; refresh: () => Promise<void>;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [source, setSource] = useState<{ text: string; citation?: string; page: number; section?: string } | null>(null);
  const [applicability, setApplicability] = useState("applicable");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [jobId, setJobId] = useState("");

  const capabilities = useCapabilities();
  const modelEnabled = capabilities?.model_execution_enabled === true;
  const lifecycle = useRef<AbortController | null>(null);
  useEffect(() => { const controller = new AbortController(); lifecycle.current = controller; return () => controller.abort(); }, []);
  async function request<T>(path: string, body?: object, method = "POST") {
    return api<T>(path, token, { method, signal: lifecycle.current?.signal, ...(body ? { body: JSON.stringify(body) } : {}) });
  }
  async function action(path: string, body: object, label: string, method = "POST") {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request<{ job_id?: string }>(path, body, method);
      if (lifecycle.current?.signal.aborted) return;
      if (result.job_id) setJobId(result.job_id);
      setNotice(result.job_id ? `${label} queued. Job ${result.job_id}. Results will refresh when it completes.` : `${label} saved.`);
      await refresh();
    } catch (reason) { if (!lifecycle.current?.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not save the decision."); }
    finally { if (!lifecycle.current?.signal.aborted) setBusy(false); }
  }
  async function review(id: string) {
    setBusy(true); setError(""); setNotice(""); setSelected(id); setSource(null); setApplicability("applicable");
    try { setSource(await request(`/obligations/${id}/source`, undefined, "GET")); }
    catch (reason) { if (!lifecycle.current?.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load the source."); }
    finally { if (!lifecycle.current?.signal.aborted) setBusy(false); }
  }
  return <section className="panel-card review-panel" aria-labelledby="review-heading">
    <div className="panel-heading"><div><h2 id="review-heading">Review and action</h2><p>Inspect the source, record applicability, and approve proposed compliance links.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="intake-progress" role="status">{notice}</p>}
    {jobId && <JobTracker key={jobId} jobId={jobId} token={token} organizationId={organizationId} onComplete={refresh} />}
    <div className="review-items">{rows.map((row) => <article className="review-item" key={`${row.obligation.id}-${row.mapping.id ?? "none"}`}>
      <div><strong>{row.obligation.source_section ?? "Regulatory obligation"}</strong><p>{row.obligation.text}</p><small>{row.obligation.status} · {row.applicability} · {row.mapping.approved ? "Mapping reviewed" : row.mapping.id ? "Mapping awaits review" : "No mapping proposed"}</small></div>
      <div className="review-actions">
        <button className="button button-secondary" disabled={busy} onClick={() => review(row.obligation.id)}>Review source</button>
        {row.obligation.status === "approved" && ["applicable", "conditional"].includes(row.applicability) && <button className="button button-secondary" disabled={busy || !modelEnabled} title={!modelEnabled ? "AI assistance is paused. Propose a manual mapping in Control library." : undefined} onClick={() => action("/mappings/run", { obligation_id: row.obligation.id }, "Control mapping")}>Suggest mapping</button>}
        {row.mapping.id && !row.mapping.approved && <button className="button button-primary" disabled={busy} onClick={() => action(`/mappings/${row.mapping.id}/approve`, { mapping_status: "mapped" }, "Mapping approval")}>Approve mapping</button>}
        {row.obligation.status === "approved" && ["applicable", "conditional"].includes(row.applicability) && <button className="button button-secondary" disabled={busy} onClick={() => action("/gaps/run", { obligation_id: row.obligation.id }, "Gap assessment")}>Assess gaps</button>}
        {row.gaps.filter(gap => gap.status === "open").map(gap => <button key={gap.id} className="button button-secondary" disabled={busy || !modelEnabled} title={!modelEnabled ? "AI assistance is paused. Create a manual plan in Gap & remediation." : undefined} onClick={() => action("/remediation/run", { gap_id: gap.id }, "Remediation proposal")}>Propose remediation</button>)}
        {row.remediation?.status === "proposed" && <button className="button button-primary" disabled={busy} onClick={() => action(`/remediation/${row.remediation?.id}`, { status: "approved" }, "Remediation approval", "PATCH")}>Approve remediation</button>}
        {row.remediation?.status === "approved" && <button className="button button-secondary" disabled={busy} onClick={() => action(`/remediation/${row.remediation?.id}`, { status: "in_progress" }, "Remediation start", "PATCH")}>Start remediation</button>}
        {row.remediation?.status === "in_progress" && <button className="button button-primary" disabled={busy} onClick={() => action(`/remediation/${row.remediation?.id}`, { status: "completed" }, "Validated remediation completion", "PATCH")}>Complete validated remediation</button>}
      </div>
      {selected === row.obligation.id && source && <div className="source-review">
        <h3>Source · page {source.page}{source.section ? ` · ${source.section}` : ""}</h3>
        {source.citation && <blockquote>{source.citation}</blockquote>}
        <details><summary>Read source page</summary><pre>{source.text || "Source text is unavailable for this record."}</pre></details>
        {row.obligation.status === "approved" && <><p className="intake-hint">Reopen this decision to review its applicability again. Gap assessment requires applicable or conditional obligations.</p><button className="button button-secondary" disabled={busy} onClick={() => action(`/obligations/${row.obligation.id}`, { status: "pending_review" }, "Obligation reopened for review", "PATCH")}>Reopen obligation review</button></>}
        {["pending_review", "rejected"].includes(row.obligation.status) && <>
          <label>Applicability decision<select value={applicability} onChange={event => setApplicability(event.target.value)}><option value="applicable">Applicable</option><option value="conditional">Conditional</option><option value="not_applicable">Not applicable</option><option value="uncertain">Requires further review</option></select></label>
          <div className="review-actions"><button className="button button-primary" disabled={busy || !source.text || !source.citation} onClick={() => action(`/obligations/${row.obligation.id}/approve`, { status: "approved", applicability }, "Obligation review")}>Approve obligation</button>
            <button className="button button-secondary" disabled={busy} onClick={() => action(`/obligations/${row.obligation.id}/approve`, { status: "rejected", applicability: "uncertain" }, "Obligation rejection")}>Reject obligation</button></div>
        </>}
        <button className="link-button" onClick={() => { setSelected(null); setSource(null); }}>Close source review</button>
      </div>}
    </article>)}{rows.length === 0 && <p className="muted">Upload a regulation to begin review.</p>}</div>
  </section>;
}
