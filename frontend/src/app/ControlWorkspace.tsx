"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import JobTracker from "./JobTracker";
import { API_URL, api, errorMessage, validateUpload } from "../lib/api";
import { useCapabilities } from "../lib/capabilities";
type Control = { id: string; control_id_code: string; objective: string; procedure?: string; status: string };
type Evidence = { id: string; control_id: string; title: string; status: string; validation_result?: { reasoning: string } };
type Test = { id: string; control_id: string; result: string; review_status: string; findings?: string; proposed_result?: { result: string; findings: string } };
type Obligation = { id: string; obligation_text: string; status: string; applicability: string };
export default function ControlWorkspace({ token, organizationId, onComplete }: { token: string; organizationId: string; onComplete: () => Promise<void> }) {
  const [controls, setControls] = useState<Control[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [tests, setTests] = useState<Test[]>([]);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [jobId, setJobId] = useState("");
  const [source, setSource] = useState<{ id: string; text: string } | null>(null);
  const capabilities = useCapabilities();
  const modelEnabled = capabilities?.model_execution_enabled === true;
  const lifecycle = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController(); lifecycle.current = controller;
    return () => controller.abort();
  }, []);
  const request = useCallback(async <T,>(path: string, body?: object | FormData, method = "POST") =>
    api<T>(path, token, { method, signal: lifecycle.current?.signal,
      ...(body ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {}) }), [token]);
  const refresh = useCallback(async () => {
    if (!organizationId) return;
    const query = `?organization_id=${encodeURIComponent(organizationId)}`;
    const [nextControls, nextEvidence, nextTests, nextObligations] = await Promise.all([
      request<Control[]>(`/controls/${query}`, undefined, "GET"), request<Evidence[]>(`/evidence/${query}`, undefined, "GET"),
      request<Test[]>(`/evidence/tests${query}`, undefined, "GET"), request<Obligation[]>(`/obligations/${query}`, undefined, "GET"),
    ]);
    if (lifecycle.current?.signal.aborted) return;
    setControls(nextControls); setEvidence(nextEvidence); setTests(nextTests); setObligations(nextObligations);
  }, [organizationId, request]);
  useEffect(() => { const timer = setTimeout(() => { refresh().catch(reason => { if (!lifecycle.current?.signal.aborted) setError(errorMessage(reason)); }); }, 0); return () => clearTimeout(timer); }, [refresh]);
  async function perform(work: () => Promise<void>, refreshWorkspace = true) {
    setBusy(true); setError(""); setNotice("");
    try { await work(); if (lifecycle.current?.signal.aborted) return; if (refreshWorkspace) { await refresh(); await onComplete(); } }
    catch (reason) { if (!lifecycle.current?.signal.aborted) setError(errorMessage(reason)); }
    finally { if (!lifecycle.current?.signal.aborted) setBusy(false); }
  }
  async function queue(path: string, body: object) {
    if (!modelEnabled) { setError("AI assistance is paused. Use the manual review forms below."); return; }
    await perform(async () => { const result = await request<{ job_id: string }>(path, body); setJobId(result.job_id); setNotice("Assessment queued. Review its proposal after completion."); });
  }
  function values(event: FormEvent<HTMLFormElement>) { event.preventDefault(); return new FormData(event.currentTarget); }
  async function createControl(event: FormEvent<HTMLFormElement>) {
    const form = values(event);
    await perform(async () => { await request("/controls/", { organization_id: organizationId, control_id_code: String(form.get("code")).trim(), objective: String(form.get("objective")).trim(), procedure: String(form.get("procedure")).trim(), frequency: form.get("frequency") }); setNotice("Control proposed for reviewer approval."); });
  }
  async function uploadEvidence(event: FormEvent<HTMLFormElement>) {
    const form = values(event);
    const file = form.get("file");
    if (!(file instanceof File)) { setError("Choose an evidence source file."); return; }
    const invalid = validateUpload(file, capabilities?.max_upload_bytes ?? 10 * 1024 * 1024);
    if (invalid) { setError(invalid); return; }
    await perform(async () => {
      const record = await request<{ id: string }>("/evidence/", { organization_id: organizationId, control_id: form.get("control_id"), title: form.get("title"), evidence_date: new Date().toISOString() });
      const upload = new FormData(); upload.set("file", form.get("file") as File);
      await request(`/evidence/${record.id}/file`, upload); setNotice("Private evidence uploaded. Inspect its source before review.");
    });
  }
  async function inspectEvidence(record: Evidence) {
    await perform(async () => {
      const response = await fetch(`${API_URL}/evidence/${record.id}/file`, { credentials: "include", signal: lifecycle.current?.signal });
      if (!response.ok) throw new Error("Source download was denied.");
      const blob = await response.blob();
      const bytes = await blob.arrayBuffer();
      if (new TextDecoder().decode(bytes.slice(0, 5)) === "%PDF-") {
        const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "evidence-source.pdf"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
        setSource({ id: record.id, text: "Private PDF downloaded. Inspect the PDF before recording a decision." });
      } else { setSource({ id: record.id, text: new TextDecoder().decode(bytes) }); }
    }, false);
  }
  async function recordTest(event: FormEvent<HTMLFormElement>) {
    const form = values(event);
    await perform(async () => { await request("/evidence/tests", { organization_id: organizationId, control_id: form.get("control_id"), test_type: "manual", result: form.get("result"), effectiveness_score: Number(form.get("score")), findings: form.get("findings"), tested_at: new Date().toISOString() }); setNotice("Reviewed control test recorded."); });
  }
  async function createMapping(event: FormEvent<HTMLFormElement>) {
    const form = values(event);
    await perform(async () => { await request("/mappings/", { organization_id: organizationId, obligation_id: form.get("obligation_id"), control_id: form.get("control_id"), reasoning: form.get("reasoning"), confidence: 1 }); setNotice("Mapping proposed. Approve it in the compliance matrix after review."); });
  }
  return <div className="control-workspace" aria-busy={busy}>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="intake-progress" role="status">{notice}</p>}
    <button className="button button-secondary" disabled={busy} onClick={() => perform(async () => {})}>Refresh controls and evidence</button>
    {jobId && <JobTracker key={jobId} jobId={jobId} token={token} organizationId={organizationId} onComplete={async () => { await refresh(); await onComplete(); }} />}
    <div className="library-grid">
      <section className="panel-card intake-card"><h2>Propose a control</h2><form className="intake-form" onSubmit={createControl}>
        <label>Control code<input name="code" required maxLength={64} /></label><label>Control objective<input name="objective" required /></label><label>Control procedure<textarea name="procedure" required /></label><label>Control frequency<select name="frequency"><option>daily</option><option>monthly</option><option>quarterly</option><option>annual</option></select></label><button className="button button-primary" disabled={busy || !organizationId}>Create control proposal</button>
      </form></section>
      <section className="panel-card intake-card"><h2>Propose a mapping</h2><p className="intake-hint">Approve an applicable obligation in Compliance matrix and a control below before proposing a mapping.</p><form className="intake-form" onSubmit={createMapping}>
        <label>Reviewed obligation<select name="obligation_id" required><option value="">Choose an obligation</option>{obligations.filter(o => o.status === "approved" && ["applicable", "conditional"].includes(o.applicability)).map(o => <option key={o.id} value={o.id}>{o.obligation_text}</option>)}</select></label>
        <label>Reviewed control<select name="control_id" required><option value="">Choose a control</option>{controls.filter(c => ["approved", "active"].includes(c.status)).map(c => <option key={c.id} value={c.id}>{c.control_id_code}</option>)}</select></label><label>Mapping rationale<textarea name="reasoning" required /></label><button className="button button-primary" disabled={busy}>Propose mapping</button>
      </form></section>
    </div>
    <section className="panel-card review-panel"><h2>Reviewed controls</h2>{!controls.length && <p className="muted">No controls yet. Propose a control above, then approve it before mapping.</p>}{controls.map(control => <article className="review-item" key={control.id}><h3>{control.control_id_code}</h3><p>{control.objective}</p><p>{control.procedure}</p><span className="pill pill-neutral">{control.status}</span><div className="review-actions">{control.status === "pending_review" && <button className="button button-primary" disabled={busy} onClick={() => perform(async () => { await request(`/controls/${control.id}/approve`, { status: "approved" }); setNotice("Control approved."); })}>Approve control {control.control_id_code}</button>}<button className="button button-secondary" disabled={busy || !modelEnabled} title={!modelEnabled ? "AI assistance is paused; manual review remains available." : undefined} onClick={() => queue("/evidence/tests/run", { control_id: control.id })}>Request assisted test</button></div></article>)}</section>
    <div className="library-grid">
      <section className="panel-card intake-card"><h2>Upload evidence</h2><p className="intake-hint">PDF, TXT or Markdown, up to {Math.round((capabilities?.max_upload_bytes ?? 10 * 1024 * 1024) / 1024 / 1024)} MB. Inspect the source before review.</p><form className="intake-form" onSubmit={uploadEvidence}><label>Evidence control<select name="control_id" required><option value="">Choose a control</option>{controls.map(c => <option key={c.id} value={c.id}>{c.control_id_code}</option>)}</select></label><label>Evidence title<input name="title" required /></label><label>Evidence source<input type="file" name="file" required accept=".txt,.md,.pdf" /></label><button className="button button-primary" disabled={busy}>Upload private evidence</button></form></section>
      <section className="panel-card intake-card"><h2>Record a reviewed test</h2><p className="intake-hint">Record a human-reviewed result using the procedure and validated evidence.</p><form className="intake-form" onSubmit={recordTest}><label>Test control<select name="control_id" required><option value="">Choose a control</option>{controls.map(c => <option key={c.id} value={c.id}>{c.control_id_code}</option>)}</select></label><label>Test result<select name="result"><option>inconclusive</option><option>pass</option><option>partial</option><option>fail</option></select></label><label>Effectiveness score<input type="number" name="score" min={0} max={1} step={.01} required /></label><label>Test findings<textarea name="findings" required /></label><button className="button button-primary" disabled={busy}>Record reviewed test</button></form></section>
    </div>
    <section className="panel-card review-panel"><h2>Evidence review</h2>{!evidence.length && <p className="muted">Upload evidence to a control, then inspect its source here.</p>}{evidence.map(record => <article className="review-item" key={record.id}><h3>{record.title}</h3><span className="pill pill-neutral">{record.status}</span>{record.validation_result && <p>Assessment proposal: {record.validation_result.reasoning}</p>}<div className="review-actions"><button className="button button-secondary" disabled={busy} onClick={() => inspectEvidence(record)}>Inspect evidence source</button><button className="button button-secondary" disabled={busy || !modelEnabled} title={!modelEnabled ? "AI assistance is paused; manual review remains available." : undefined} onClick={() => queue("/evidence/validate", { evidence_id: record.id })}>Request assessment proposal</button></div>
      {source?.id === record.id && <div className="source-review"><pre>{source.text}</pre><form className="intake-form" onSubmit={event => { const form = values(event); void perform(async () => { await request(`/evidence/${record.id}/approve`, { status: form.get("status"), notes: form.get("notes") }); setNotice("Evidence review recorded."); }); }}><label>Evidence decision<select name="status"><option>insufficient</option><option>valid</option><option>invalid</option></select></label><label>Evidence review notes<textarea name="notes" required /></label><button className="button button-primary" disabled={busy}>Save evidence review</button></form></div>}
    </article>)}</section>
    <section className="panel-card review-panel"><h2>Control test results</h2>{!tests.length && <p className="muted">No tests recorded. Use the reviewed test form above.</p>}{tests.map(record => <article className="review-item" key={record.id}><p>{record.result} · {record.review_status}</p><p>{record.findings}</p>{record.proposed_result && <p>Proposal: {record.proposed_result.result} · {record.proposed_result.findings}</p>}{record.review_status === "pending_review" && <form className="intake-form" onSubmit={event => { const form = values(event); void perform(async () => { await request(`/evidence/tests/${record.id}/approve`, { result: form.get("result"), effectiveness_score: Number(form.get("score")), findings: form.get("findings") }); setNotice("Test review saved."); }); }}><label>Reviewed result<select name="result"><option>inconclusive</option><option>pass</option><option>partial</option><option>fail</option></select></label><label>Reviewed effectiveness<input name="score" type="number" min={0} max={1} step={.01} required /></label><label>Review findings<textarea name="findings" required /></label><button className="button button-primary" disabled={busy}>Save test review</button></form>}</article>)}</section>
  </div>;
}
