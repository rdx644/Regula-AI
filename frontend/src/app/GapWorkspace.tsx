"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../lib/api";

type Gap = { id: string; gap_type: string; severity: string; status: string; description?: string; risk_assessment?: { risk_score: number; reasoning?: string } };
type Plan = { id: string; gap_id: string; recommendation: string; priority: string; status: string; assigned_to?: string; due_date?: string };

export default function GapWorkspace({ token, organizationId, onComplete }: { token: string; organizationId: string; onComplete: () => Promise<void> }) {
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lifecycle = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    const options = { signal: lifecycle.current?.signal };
    const params = `?organization_id=${encodeURIComponent(organizationId)}`;
    const [nextGaps, nextPlans] = await Promise.all([
      api<Gap[]>(`/gaps/${params}&limit=500`, token, options),
      api<Plan[]>(`/remediation/${params}&limit=500`, token, options),
    ]);
    if (options.signal?.aborted) return;
    setGaps(nextGaps); setPlans(nextPlans);
  }, [organizationId, token]);
  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    const timer = setTimeout(() => {
      refresh().catch(reason => { if (!controller.signal.aborted) setError(errorMessage(reason)); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);

  async function save(work: () => Promise<unknown>, message: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      await work();
      if (lifecycle.current?.signal.aborted) return;
      await refresh(); await onComplete(); setNotice(message);
    } catch (reason) { if (!lifecycle.current?.signal.aborted) setError(errorMessage(reason)); }
    finally { if (!lifecycle.current?.signal.aborted) setBusy(false); }
  }
  async function propose(event: FormEvent<HTMLFormElement>, gap: Gap) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await save(() => api("/remediation/", token, { method: "POST", signal: lifecycle.current?.signal, body: JSON.stringify({
      organization_id: organizationId, gap_id: gap.id,
      recommendation: String(form.get("recommendation")).trim(),
      assigned_to: String(form.get("assigned_to")).trim(), priority: form.get("priority"),
    }) }), "Remediation plan proposed. Review the plan before approving it.");
  }
  const visible = gaps.filter(gap => filter === "all" || gap.status === filter);
  return <section className="gap-workspace" aria-busy={loading || busy}>
    <div className="workspace-toolbar"><label>Finding status<select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All findings</option><option value="open">Open</option><option value="in_remediation">In remediation</option><option value="closed">Closed</option></select></label><button className="button button-secondary" disabled={busy || loading} onClick={() => save(refresh, "Findings refreshed.")}>Refresh findings</button></div>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="intake-progress" role="status">{notice}</p>}
    {loading && <p role="status" className="muted">Loading findings and plans…</p>}
    {visible.map(gap => {
      const plan = plans.find(item => item.gap_id === gap.id);
      const next = plan?.status === "proposed" ? "approved" : plan?.status === "approved" ? "in_progress" : plan?.status === "in_progress" ? "completed" : null;
      const label = next === "approved" ? "Approve remediation" : next === "in_progress" ? "Start remediation" : "Complete validated remediation";
      return <article className="panel-card gap-card" key={gap.id}>
        <div className="panel-heading"><div><p className="eyebrow">COMPLIANCE FINDING</p><h2>{gap.gap_type.replaceAll("_", " ")}</h2></div><span className={`pill pill-${["critical", "high"].includes(gap.severity) ? "red" : "amber"}`}>{gap.severity}</span></div>
        <p>{gap.description || "Review the linked obligation and control to understand this finding."}</p>
        <div className="gap-meta"><span className="pill pill-neutral">{gap.status.replaceAll("_", " ")}</span>{gap.risk_assessment && <span>Risk score {gap.risk_assessment.risk_score} / 100</span>}</div>
        {plan ? <div className="source-review"><h3>Remediation plan</h3><p>{plan.recommendation}</p><div className="gap-meta"><span className="pill pill-neutral">{plan.status.replaceAll("_", " ")}</span><span>Owner: {plan.assigned_to || "Not assigned"}</span><span>{plan.priority.replaceAll("_", " ")}</span></div>{next && <><p className="intake-hint">{next === "completed" ? "Completion requires valid evidence and a reviewed passing test recorded after remediation started. Record that test in Control library first." : "Approval and state changes require an authorized reviewer."}</p><button className="button button-primary" disabled={busy} onClick={() => save(() => api(`/remediation/${plan.id}`, token, { method: "PATCH", signal: lifecycle.current?.signal, body: JSON.stringify({ status: next }) }), "Remediation status updated.")}>{label}</button></>}</div>
          : gap.status === "open" && <details className="plan-details"><summary>Create a manual remediation plan</summary><form className="intake-form" onSubmit={event => propose(event, gap)}><label>Remediation recommendation<textarea name="recommendation" required minLength={10} placeholder="Describe the action needed and how it will be verified." /></label><div className="intake-fields"><label>Remediation owner<input name="assigned_to" required placeholder="Responsible person or team" /></label><label>Remediation priority<select name="priority"><option value="immediate">Immediate</option><option value="short_term">Short term</option><option value="medium_term">Medium term</option><option value="long_term">Long term</option></select></label></div><button className="button button-primary" disabled={busy}>Propose remediation plan</button></form></details>}
      </article>;
    })}
    {!loading && !visible.length && <div className="panel-card empty-state"><strong>{gaps.length ? "No findings match this filter." : "No findings recorded."}</strong><p>Use Assess gaps on a reviewed obligation in Compliance matrix, or load the synthetic demo to explore a sample plan.</p></div>}
  </section>;
}
