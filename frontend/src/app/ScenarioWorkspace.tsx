"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import JobTracker from "./JobTracker";
import { errorMessage } from "../lib/api";
import { exportReview, useWorkspaceRequest } from "../lib/workspace-review";
type Control = { id: string; control_id_code: string; objective: string };
type Results = { risk_delta: number; changed_obligations: string[]; affected_controls: string[]; new_gaps: { obligation_id: string; gap_type: string; severity: string }[]; method: string };
type Scenario = { id: string; name: string; status: string; results?: Results; parameters?: object };
export default function ScenarioWorkspace({ token, organizationId }: { token: string; organizationId: string }) {
  const { request, isActive } = useWorkspaceRequest(token);
  const [controls, setControls] = useState<Control[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const query = `?organization_id=${organizationId}`;
    const [nextControls, nextScenarios, matrix] = await Promise.all([request<Control[]>(`/controls/${query}`, undefined, "GET"), request<Scenario[]>(`/simulations/${query}`, undefined, "GET"), request<{ matrix: { control: { id?: string } }[] }>(`/evaluation/demo/compliance-matrix${query}`, undefined, "GET")]);
    if (isActive()) { setControls(nextControls.filter(control => matrix.matrix.some(row => row.control.id === control.id))); setScenarios(nextScenarios); }
  }, [organizationId, request, isActive]);
  useEffect(() => { const timer = setTimeout(() => { void refresh().catch(reason => { if (isActive()) setError(errorMessage(reason)); }); }, 0); return () => clearTimeout(timer); }, [refresh, isActive]);
  async function run(id: string) {
    const job = await request<{ job_id: string }>("/simulations/run", { simulation_id: id });
    if (isActive()) setJobId(job.job_id);
  }
  async function perform(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); if (isActive()) await refresh(); }
    catch (reason) { if (isActive()) setError(errorMessage(reason)); }
    finally { if (isActive()) setBusy(false); }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    await perform(async () => {
      const scenario = await request<Scenario>("/simulations/", { organization_id: organizationId, name: form.get("name"), scenario_description: "Reviewer-defined control outage and bounded risk assumptions.",
        parameters: { disable_control_ids: [form.get("control")], likelihood_multiplier: Number(form.get("likelihood")), impact_multiplier: Number(form.get("impact")) } });
      await run(scenario.id);
    });
  }
  return <div className="review-workspace"><section className="panel-card intake-card"><h2>Test an assumption, preserve the baseline</h2><p className="muted">Clone recorded workspace links and simulate a control outage. Original controls, evidence and findings remain intact.</p><form className="intake-form" onSubmit={create}><label>Scenario name<input name="name" required minLength={1} maxLength={256} placeholder="Synthetic control outage" /></label><label>Control to disable in scenario<select name="control" required><option value="">Choose a mapped control</option>{controls.map(control => <option key={control.id} value={control.id}>{control.control_id_code} / {control.objective}</option>)}</select></label><div className="intake-fields"><label>Likelihood multiplier<input name="likelihood" type="number" min="0" max="2" step="0.1" defaultValue="1" required /></label><label>Impact multiplier<input name="impact" type="number" min="0" max="2" step="0.1" defaultValue="1" required /></label></div><button className="button button-primary" disabled={busy || !controls.length}>Run what-if scenario</button></form><p className="muted">Illustrative risk: open-gap links use likelihood 0.8 and impact 0.9; other links use 0.2 and 0.3. Risk is likelihood x impact x 100, summed per link. This is not a calibrated bank risk forecast.</p>{error && <p className="form-error" role="alert">{error}</p>}</section>
    {jobId && <JobTracker key={jobId} jobId={jobId} token={token} organizationId={organizationId} onComplete={refresh} />}
    <section className="panel-card"><div className="panel-heading"><h2>Saved scenarios</h2><button className="button button-secondary" disabled={busy} onClick={() => { void perform(refresh); }}>Refresh scenarios</button></div>{!scenarios.length && <p className="muted">Your saved baseline and scenario results will appear here.</p>}{scenarios.map(scenario => <article className="source-review" key={scenario.id}><h3>{scenario.name}</h3><p><span className="pill">{scenario.status}</span></p>{scenario.results && <><p>{scenario.results.changed_obligations.length} changed obligations / {scenario.results.affected_controls.length} affected controls / {scenario.results.new_gaps.length} projected gaps</p><p>Illustrative aggregate risk delta: {scenario.results.risk_delta}</p><ul>{scenario.results.new_gaps.map((gap, index) => <li key={index}>{gap.gap_type.replaceAll("_", " ")} / {gap.severity} / obligation {gap.obligation_id}</li>)}</ul><button className="button button-secondary" onClick={() => exportReview("what-if-scenario.json", scenario)}>Export scenario</button></>}{["created", "failed"].includes(scenario.status) && <button className="button button-secondary" disabled={busy} onClick={() => { void perform(() => run(scenario.id)); }}>Run saved scenario</button>}</article>)}</section></div>;
}
