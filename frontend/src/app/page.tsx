"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import RegulationIntake from "./RegulationIntake";
import ComplianceReview, { ReviewRow } from "./ComplianceReview";
import ControlWorkspace from "./ControlWorkspace";
import GapWorkspace from "./GapWorkspace";
import ChangeWorkspace from "./ChangeWorkspace";
import ScenarioWorkspace from "./ScenarioWorkspace";
import InvestigationWorkspace from "./InvestigationWorkspace";
import { api, ApiError, errorMessage } from "../lib/api";
import { Capabilities, CapabilitiesContext } from "../lib/capabilities";
import TraceScene from "./TraceScene";

const ORG_KEY = "regulaai.organization-id";
type View = "overview" | "matrix" | "library" | "controls" | "gaps" | "changes" | "scenarios" | "investigation";
type User = { id: string; full_name: string; email: string };
type Organization = { id: string; name: string };
type MetricGroup = { total: number; approved?: number; valid?: number; open?: number; approval_rate?: number; validation_rate?: number };
type Metrics = { obligations: MetricGroup; controls: MetricGroup; mappings: MetricGroup; evidence: MetricGroup; gaps: MetricGroup; remediation: MetricGroup; overall_compliance_score: number };
type MatrixRow = ReviewRow & {
  obligation: { id: string; text: string; frequency?: string; confidence?: number; source_section?: string };
  control: { id?: string | null; code?: string; objective?: string; status?: string };
  mapping: { id?: string | null; status: string; confidence?: number; approved?: boolean };
  evidence: { id: string; title: string; status: string; coverage: string }[];
  tests: { id: string; result: string; effectiveness?: number }[];
};
const views: { id: View; label: string; symbol: string; description: string }[] = [
  { id: "overview", label: "Overview", symbol: "01", description: "Your compliance posture, at a glance." },
  { id: "library", label: "Regulatory library", symbol: "02", description: "Secure source documents. Keep their provenance close." },
  { id: "controls", label: "Control library", symbol: "03", description: "Build reviewed controls, link evidence and record tests." },
  { id: "matrix", label: "Compliance matrix", symbol: "04", description: "Follow each obligation through its control and evidence." },
  { id: "gaps", label: "Gap & remediation", symbol: "05", description: "Prioritize findings and move owned actions toward closure." },
  { id: "changes", label: "Version comparison", symbol: "06", description: "Inspect literal source changes and candidate impact drafts." },
  { id: "scenarios", label: "What-if scenarios", symbol: "07", description: "Explore a control outage without changing your baseline." },
  { id: "investigation", label: "Investigation & audit", symbol: "08", description: "Query recorded workspace facts and follow their audit trail." },
];
function Pill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "green" | "amber" | "red" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}
function percent(value?: number) { return typeof value === "number" ? `${value}%` : "—"; }

export default function Home() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [matrix, setMatrix] = useState<MatrixRow[]>([]);
  const [view, setView] = useState<View>("overview");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showOrganizationForm, setShowOrganizationForm] = useState(false);
  const [query, setQuery] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const revision = useRef(0);
  const pending = useRef<AbortController | null>(null);

  const clearSession = useCallback(() => {
    revision.current += 1;
    pending.current?.abort();
    setToken(""); setUser(null); setCapabilities(null); setOrganizations([]);
    setOrganizationId(""); setMetrics(null); setMatrix([]); setView("overview");
    setWorkspaceLoading(false); setShowOrganizationForm(false); setLastUpdated("");
    localStorage.removeItem(ORG_KEY);
  }, []);

  const loadWorkspace = useCallback(async (accessToken: string, preferredOrg?: string) => {
    const currentRevision = ++revision.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const options = { signal: controller.signal };
    setWorkspaceLoading(true);
    try {
      const [profile, orgs, features] = await Promise.all([
        api<User>("/users/me", accessToken, options),
        api<Organization[]>("/organizations/", accessToken, options),
        api<Capabilities>("/auth/capabilities", accessToken, options),
      ]);
      if (currentRevision !== revision.current) return;
      setUser(profile); setToken(accessToken); setOrganizations(orgs); setCapabilities(features);
      const savedOrg = preferredOrg ?? localStorage.getItem(ORG_KEY) ?? "";
      const activeOrg = orgs.find(org => org.id === savedOrg) ?? orgs[0];
      setOrganizationId(activeOrg?.id ?? "");
      if (!activeOrg) {
        setMetrics(null); setMatrix([]); setLastUpdated("");
        localStorage.removeItem(ORG_KEY);
        return;
      }
      localStorage.setItem(ORG_KEY, activeOrg.id);
      const params = `?organization_id=${encodeURIComponent(activeOrg.id)}`;
      const [nextMetrics, nextMatrix] = await Promise.all([
        api<Metrics>(`/evaluation/metrics/evaluation${params}`, accessToken, options),
        api<{ matrix: MatrixRow[] }>(`/evaluation/demo/compliance-matrix${params}`, accessToken, options),
      ]);
      if (currentRevision !== revision.current) return;
      setMetrics(nextMetrics); setMatrix(nextMatrix.matrix);
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (reason) {
      if (controller.signal.aborted || currentRevision !== revision.current) return;
      if (reason instanceof ApiError && reason.status === 401) clearSession();
      throw reason;
    } finally {
      if (currentRevision === revision.current) setWorkspaceLoading(false);
    }
  }, [clearSession]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api<{ csrf_token: string }>("/auth/session", undefined, { signal: controller.signal })
        .then(({ csrf_token }) => { if (active) return loadWorkspace(csrf_token); })
        .catch(reason => {
          if (active && !(reason instanceof ApiError && reason.status === 401)) setError(errorMessage(reason));
        }).finally(() => { if (active) setRestoring(false); });
    }, 0);
    return () => { active = false; clearTimeout(timer); controller.abort(); pending.current?.abort(); };
  }, [loadWorkspace]);

  const refresh = useCallback(() => loadWorkspace(token, organizationId), [loadWorkspace, token, organizationId]);
  const matchingRows = useMemo(() => matrix.filter(row =>
    `${row.obligation.text} ${row.obligation.source_section ?? ""} ${row.control.code ?? ""} ${row.control.objective ?? ""}`.toLowerCase().includes(query.toLowerCase())), [matrix, query]);
  const selectedView = views.find(item => item.id === view)!;
  const openGaps = metrics?.gaps.open ?? 0;
  const busy = loading || workspaceLoading;

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice(""); setLoading(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    try {
      if (mode === "register") {
        await api("/users/", undefined, { method: "POST", body: JSON.stringify({ email, password, full_name: String(form.get("full_name") ?? "").trim() }) });
        setMode("login");
        setNotice("Account created. You can sign in with these credentials if the connection is interrupted.");
      }
      const result = await api<{ csrf_token: string }>("/auth/login/access-token", undefined, {
        method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ username: email, password }),
      });
      await loadWorkspace(result.csrf_token);
      setNotice("Signed in. Choose a workspace or start with the demo.");
    } catch (reason) { setError(errorMessage(reason, "Could not sign in.")); }
    finally { setLoading(false); }
  }

  async function seedDemo() {
    setLoading(true); setError(""); setNotice("");
    try {
      const result = await api<{ organization_id: string }>("/evaluation/demo/seed", token, { method: "POST" });
      await loadWorkspace(token, result.organization_id);
      setShowOrganizationForm(false);
      setNotice("Synthetic Basel III scenario loaded. Explore the matrix and review the sample finding.");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }

  async function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = String(new FormData(event.currentTarget).get("organization_name") ?? "").trim();
    if (!name) { setError("Enter a workspace name."); return; }
    setLoading(true); setError("");
    try {
      const result = await api<Organization>("/organizations/", token, { method: "POST", body: JSON.stringify({ name }) });
      setMetrics(null); setMatrix([]);
      await loadWorkspace(token, result.id);
      setShowOrganizationForm(false); setNotice("Workspace created. Start by adding a regulation or control.");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }

  async function signOut() {
    setLoading(true); setError("");
    try {
      await api("/auth/logout", token, { method: "POST" });
      clearSession(); setNotice(""); setError("");
    } catch (reason) { setError(errorMessage(reason, "Could not end the server session.")); }
    finally { setLoading(false); }
  }

  function navigate(nextView: View) { setView(nextView); setQuery(""); }

  if (!token || !user) return <main className="auth-shell">
    <section className="auth-brand">
      <div className="auth-brand-head"><div className="brand-lockup">Regula<span className="brand-light">AI</span><span className="edition">COMPLIANCE / INTELLIGENCE</span></div><span className="brand-stamp" aria-hidden="true">SOURCE<br />TO ACTION ↗</span></div>
      <div className="auth-message">
        <p className="eyebrow">FROM REQUIREMENT TO RESOLUTION</p>
        <h1>Complex regulation.<br /><em>Clear decisions.</em></h1>
        <p>Connect obligations, controls and evidence. Make every decision traceable to its source.</p>
        <TraceScene />
      </div>
      <div className="auth-footnote"><span className="status-dot" /> Source linked <span className="foot-divider">/</span> Human reviewed</div>
    </section>
    <section className="auth-panel">
      <div className="auth-card">
        <div className="auth-card-top"><p className="eyebrow">YOUR NEXT CLEAR STEP</p><span className="auth-card-marker" aria-hidden="true">↗</span></div>
        <h2>{mode === "login" ? "Welcome back." : "Make room for clarity."}</h2>
        <p className="muted">{mode === "login" ? "Sign in to your compliance workspace." : "Create an account, then choose or create a workspace."}</p>
        <form className="auth-form" onSubmit={handleAuth} aria-busy={loading || restoring}>
          {mode === "register" && <label>Full name<input name="full_name" autoComplete="name" required minLength={2} maxLength={128} placeholder="Alex Morgan" /></label>}
          <label>Work email<input name="email" type="email" autoComplete="email" required placeholder="you@company.com" /></label>
          <label>Password<input name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={6} placeholder="At least 6 characters" /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          {notice && <p className="intake-progress" role="status">{notice}</p>}
          <button className="button button-primary button-wide" disabled={loading || restoring}>{loading ? "Signing in…" : restoring ? "Connecting…" : mode === "login" ? "Sign in" : "Create account"}<span aria-hidden="true">↗</span></button>
        </form>
        <p className="auth-switch">{mode === "login" ? "New to RegulaAI?" : "Already have an account?"}{" "}<button className="text-button" disabled={loading} onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setNotice(""); }}>{mode === "login" ? "Create account" : "Sign in"}</button></p>
        <div className="auth-security"><strong>Built around accountability.</strong><p>Private workspaces. Source context. Human decisions.</p></div>
        <p className="auth-demo-note">Hackathon edition · use synthetic data.</p>
      </div>
    </section>
  </main>;

  return <CapabilitiesContext.Provider value={capabilities}><main className="app-shell">
    <a className="skip-link" href="#workspace-content">Skip to workspace</a>
    <aside className="sidebar">
      <div className="brand-lockup">Regula<span className="brand-light">AI</span></div>
      <p className="side-label">CURRENT WORKSPACE</p>
      <div className="org-select-wrap"><select aria-label="Organization" value={organizationId} disabled={busy || organizations.length === 0} onChange={event => {
        const id = event.target.value; localStorage.setItem(ORG_KEY, id); setOrganizationId(id); setMetrics(null); setMatrix([]); setQuery(""); setError(""); setLastUpdated("");
        void loadWorkspace(token, id).catch(reason => setError(errorMessage(reason)));
      }}>{organizations.length === 0 && <option value="">Choose your first workspace</option>}{organizations.map(org => <option key={org.id} value={org.id}>{org.name.startsWith("Demo Bank ") ? "Demo Bank · Basel III" : org.name}</option>)}</select><span aria-hidden="true">⌄</span></div>
      <button className="new-workspace" disabled={busy} onClick={() => setShowOrganizationForm(!showOrganizationForm)}>+ New workspace</button>
      <p className="side-label nav-label">YOUR COMPLIANCE CHAIN</p>
      <nav className="side-nav" aria-label="Main navigation">{views.map(item => <button key={item.id} className={`nav-item${view === item.id ? " active" : ""}`} aria-current={view === item.id ? "page" : undefined} title={item.label} onClick={() => navigate(item.id)}><span className="nav-icon" aria-hidden="true">{item.symbol}</span>{item.label}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><strong>Start with a clear path.</strong><p>Source → Review → Control → Evidence → Action</p><button className="sidebar-link" onClick={() => { navigate("overview"); setNotice("Start with a workspace or load the synthetic demo. Add a source in Regulatory library; review decisions in Compliance matrix; manage controls, evidence and tests in Control library."); }}>Workflow guide <span aria-hidden="true">↗</span></button></div><div className="profile-row"><div className="profile-avatar" aria-hidden="true">{user.full_name.slice(0, 1).toUpperCase()}</div><div className="profile-copy"><strong>{user.full_name}</strong><small>{user.email}</small></div><button className="icon-button signout" disabled={loading} onClick={signOut} aria-label="Sign out" title="Sign out">↪</button></div></div>
    </aside>
    <section className="main-panel">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{selectedView.label}</strong></div><div className="top-actions"><span className="system-status"><span className="status-dot" />{workspaceLoading ? "Updating workspace" : lastUpdated ? `Updated ${lastUpdated}` : "Choose a workspace"}</span><button className="icon-button" disabled={busy} onClick={() => { setError(""); void refresh().catch(reason => setError(errorMessage(reason))); }} aria-label="Refresh data" title="Refresh data">↻</button></div></header>
      <div className="page-content" id="workspace-content" tabIndex={-1} aria-busy={workspaceLoading}>
        <div className="page-heading"><div><p className="eyebrow">THE COMPLIANCE WORKSPACE</p><h1>{view === "overview" ? <>Welcome, <em>{user.full_name.split(" ")[0]}.</em></> : selectedView.label}</h1><p className="muted">{selectedView.description}</p></div><button className="button button-primary" onClick={seedDemo} disabled={busy}>{loading ? "Please wait…" : "Load demo scenario"}<span aria-hidden="true">↗</span></button></div>
        {error && <div className="notice notice-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
        {notice && <div className="notice notice-success" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss notice">×</button></div>}
        {capabilities && <div className="edition-banner"><span className="edition-tag">HACKATHON EDITION</span><p>{capabilities.model_execution_enabled ? "Assisted workflows available; every proposal still needs review." : "Manual reviews, parsing and gap assessment are available. AI assistance is paused."}{capabilities.ephemeral_uploads && " Uploaded files are temporary; use synthetic data."}</p></div>}
        {(showOrganizationForm || !organizationId) && <section className="panel-card onboarding-card"><div><p className="eyebrow">{organizationId ? "A NEW WORKSPACE" : "BEGIN HERE"}</p><h2>{organizationId ? "Keep a team’s work together." : "Give your compliance work a home."}</h2><p className="muted">Create a workspace for your sources and decisions, or load the prepared demo above.</p></div><form className="intake-form" onSubmit={createOrganization}><label>Workspace name<input name="organization_name" required minLength={1} maxLength={256} placeholder="e.g. Capital review team" /></label><div className="review-actions"><button className="button button-primary" disabled={busy}>Create workspace</button>{organizationId && <button type="button" className="button button-secondary" onClick={() => setShowOrganizationForm(false)}>Cancel</button>}</div></form></section>}
        {organizationId && <>
          {view === "overview" && <>
            <div className="overview-grid">
              <article className="score-card"><div className="score-top"><span>COMPLIANCE POSTURE</span><span>01 / OVERVIEW</span></div><div className="score-value">{percent(metrics?.overall_compliance_score)}</div><div className="score-track" role="meter" aria-label="Compliance score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={metrics?.overall_compliance_score ?? 0}><i style={{ width: `${Math.max(0, Math.min(metrics?.overall_compliance_score ?? 0, 100))}%` }} /></div><p>Based on recorded approvals, mappings, evidence and test results.</p><button className="score-link" onClick={() => navigate("matrix")}>Explore the matrix <span aria-hidden="true">↗</span></button></article>
              {[{ label: "Regulatory obligations", value: metrics?.obligations.total, detail: `${metrics?.obligations.approved ?? 0} approved`, tag: "SOURCE" }, { label: "Internal controls", value: metrics?.controls.total, detail: `${metrics?.mappings.total ?? 0} mappings`, tag: "CONTROL" }, { label: "Validated evidence", value: metrics?.evidence.valid, detail: `${metrics?.evidence.total ?? 0} records`, tag: "EVIDENCE" }, { label: "Open compliance gaps", value: metrics?.gaps.open, detail: `${metrics?.remediation.total ?? 0} action plans`, tag: "ACTION" }].map((item, i) => <article className="metric-card" key={item.label}><div className="metric-card-head"><span className="metric-index">0{i + 2}</span><span className="trend neutral">{item.tag}</span></div><p className="metric-title">{item.label}</p><div className="metric-number">{item.value ?? "—"}</div><div className="metric-foot">{item.detail}</div></article>)}
            </div>
            <div className="content-grid"><section className="panel-card matrix-preview"><div className="panel-heading"><div><p className="eyebrow">EVERY LINK, IN CONTEXT</p><h2>Traceability overview</h2></div><button className="link-button" onClick={() => navigate("matrix")}>Full matrix ↗</button></div><div className="trace-steps">{["Obligation", "Control", "Evidence", "Action"].map((step, i) => <div className="trace-step" key={step}><span className="trace-num">0{i + 1}</span><strong>{step}</strong></div>)}</div><div className="preview-list">{matrix.slice(0, 3).map(row => <div className="preview-row" key={`${row.obligation.id}-${row.mapping.id ?? "none"}`}><div className="preview-doc" aria-hidden="true">§</div><div className="preview-copy"><strong>{row.obligation.source_section ?? "Regulatory clause"}</strong><small>{row.obligation.text}</small></div><Pill tone={row.gaps.some(gap => gap.status === "open") ? "amber" : "neutral"}>{row.gaps.some(gap => gap.status === "open") ? "Review needed" : "No open finding"}</Pill></div>)}{matrix.length === 0 && <div className="empty-state compact"><strong>Start with the source.</strong><p>Add your first regulation, or explore the synthetic demo.</p><button className="button button-secondary" onClick={() => navigate("library")}>Add a regulation</button></div>}</div></section>
            <section className="panel-card action-card"><div className="panel-heading"><div><p className="eyebrow">THE NEXT DECISION</p><h2>Attention queue</h2></div><span className="queue-count">{openGaps}</span></div><div className="attention-item"><span className="attention-mark" aria-hidden="true">!</span><div><strong>{openGaps ? `${openGaps} open finding${openGaps === 1 ? "" : "s"}` : "No open findings"}</strong><small>Review risk and assign a clear next action.</small></div><button className="icon-button" onClick={() => navigate("gaps")} aria-label="View findings">↗</button></div><div className="attention-item"><span className="attention-mark" aria-hidden="true">→</span><div><strong>{metrics?.remediation.total ?? 0} remediation plans</strong><small>Move reviewed plans toward completion.</small></div><button className="icon-button" onClick={() => navigate("gaps")} aria-label="View remediation">↗</button></div><div className="responsible-note"><p><strong>A decision you can explain.</strong><br />Keep source context and human review at every step.</p></div></section></div>
          </>}
          {view === "matrix" && <><section className="panel-card full-matrix"><div className="panel-heading"><div><h2>Obligation-to-evidence matrix</h2><p>Review each link and its recorded state.</p></div><label className="search-field"><span className="sr-only">Search matrix</span><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Find a clause or control…" /></label></div>{matrix.length > 0 ? <><p className="result-count">{matchingRows.length} of {matrix.length} links</p><div className="table-scroll" tabIndex={0} role="region" aria-label="Compliance matrix table"><table><caption className="sr-only">Regulatory requirements linked to controls, evidence, tests, gaps and remediation.</caption><thead><tr>{["Regulatory obligation", "Control", "Evidence", "Test", "Gap / risk", "Remediation"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{matchingRows.map(row => <tr key={`${row.obligation.id}-${row.mapping.id ?? "none"}`}><td><div className="cell-primary">{row.obligation.source_section ?? "Source clause"}</div><div className="cell-secondary">{row.obligation.text}</div><div className="cell-meta">{row.obligation.frequency ?? "Frequency not set"} · {Math.round((row.obligation.confidence ?? 0) * 100)}% confidence</div></td><td>{row.control.id ? <><div className="cell-primary">{row.control.code}</div><div className="cell-secondary">{row.control.objective}</div><Pill tone={row.mapping.approved ? "green" : "amber"}>{row.mapping.approved ? "Reviewed" : row.mapping.status}</Pill></> : <Pill tone="amber">Unmapped</Pill>}</td><td>{row.evidence.length ? row.evidence.map(item => <div className="evidence-item" key={item.id}><Pill tone={item.status === "valid" ? "green" : "amber"}>{item.status}</Pill><span>{item.title}</span></div>) : <span className="muted">No evidence linked</span>}</td><td>{row.tests.length ? row.tests.map(item => <Pill key={item.id} tone={item.result === "pass" ? "green" : "amber"}>{item.result}</Pill>) : <span className="muted">Not tested</span>}</td><td>{row.gaps.length ? row.gaps.map(item => <div className="gap-item" key={item.id}><Pill tone={["critical", "high"].includes(item.severity) ? "red" : "amber"}>{item.severity}</Pill><span>{item.type.replaceAll("_", " ")} · {item.status}</span></div>) : <Pill>No recorded gap</Pill>}</td><td>{row.remediation ? <><div className="cell-primary">{row.remediation.status}</div><div className="cell-secondary">{row.remediation.recommendation}</div></> : <span className="muted">No plan recorded</span>}</td></tr>)}</tbody></table></div>{!matchingRows.length && <div className="empty-state compact"><strong>No matching links.</strong><button className="link-button" onClick={() => setQuery("")}>Clear search</button></div>}</> : <div className="empty-state"><strong>No linked obligations yet.</strong><p>Add a regulation or load the demo scenario.</p><button className="button button-secondary" onClick={() => navigate("library")}>Open regulatory library</button></div>}</section><ComplianceReview key={organizationId} rows={matchingRows} token={token} organizationId={organizationId} refresh={refresh} /></>}
          {view === "library" && <RegulationIntake key={organizationId} token={token} organizationId={organizationId} onComplete={refresh} />}
          {view === "controls" && <ControlWorkspace key={organizationId} token={token} organizationId={organizationId} onComplete={refresh} />}
          {view === "gaps" && <GapWorkspace key={organizationId} token={token} organizationId={organizationId} onComplete={refresh} />}
          {view === "changes" && <ChangeWorkspace key={organizationId} token={token} organizationId={organizationId} />}
          {view === "scenarios" && <ScenarioWorkspace key={organizationId} token={token} organizationId={organizationId} />}
          {view === "investigation" && <InvestigationWorkspace key={organizationId} token={token} organizationId={organizationId} />}
        </>}
        <footer className="page-footer"><span>RegulaAI / Compliance intelligence</span><span>Source linked · Tenant scoped · Human governed</span></footer>
      </div>
    </section>
  </main></CapabilitiesContext.Provider>;
}
