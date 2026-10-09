"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import RegulationIntake from "./RegulationIntake";
import ComplianceReview, { ReviewRow } from "./ComplianceReview";
import ControlWorkspace from "./ControlWorkspace";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
const ORG_KEY = "regulaai.organization-id";

type User = { id: string; full_name: string; email: string };
type Organization = { id: string; name: string };
type MetricGroup = { total: number; approved?: number; valid?: number; open?: number; completed?: number; approval_rate?: number; validation_rate?: number; completion_rate?: number };
type Metrics = {
  obligations: MetricGroup;
  controls: MetricGroup;
  mappings: MetricGroup;
  evidence: MetricGroup;
  gaps: MetricGroup;
  remediation: MetricGroup;
  overall_compliance_score: number;
};
type MatrixRow = ReviewRow & {
  obligation: { id: string; text: string; frequency?: string; confidence?: number; source_section?: string };
  control: { id?: string | null; code?: string; objective?: string; status?: string };
  mapping: { id?: string | null; status: string; confidence?: number; approved?: boolean };
  evidence: { id: string; title: string; status: string; coverage: string }[];
  tests: { id: string; result: string; effectiveness?: number }[];
  gaps: { id: string; type: string; severity: string; status: string }[];
  remediation?: { id: string; recommendation: string; status: string; priority: string } | null;
};

async function api<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { "X-CSRF-Token": token } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      const detail = body.detail ?? body.error?.message;
      message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : message;
    } catch {
      // Use the HTTP status when the API does not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function metricLabel(value?: number) {
  return typeof value === "number" ? `${value}%` : "—";
}

function Pill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "green" | "amber" | "red" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export default function Home() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [matrix, setMatrix] = useState<MatrixRow[]>([]);
  const [view, setView] = useState<"overview" | "matrix" | "library" | "controls">("overview");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadWorkspace = useCallback(async (accessToken: string, preferredOrg?: string) => {
    const [profile, orgs] = await Promise.all([
      api<User>("/users/me", accessToken),
      api<Organization[]>("/organizations/", accessToken),
    ]);
    setUser(profile);
    setOrganizations(orgs);
    const savedOrg = preferredOrg ?? localStorage.getItem(ORG_KEY) ?? "";
    const activeOrg = orgs.find((org) => org.id === savedOrg) ?? orgs[0];
    if (!activeOrg) {
      setOrganizationId("");
      setMetrics(null);
      setMatrix([]);
      return;
    }
    setOrganizationId(activeOrg.id);
    localStorage.setItem(ORG_KEY, activeOrg.id);
    const query = `?organization_id=${encodeURIComponent(activeOrg.id)}`;
    const [nextMetrics, nextMatrix] = await Promise.all([
      api<Metrics>(`/evaluation/metrics/evaluation${query}`, accessToken),
      api<{ matrix: MatrixRow[] }>(`/evaluation/demo/compliance-matrix${query}`, accessToken),
    ]);
    setMetrics(nextMetrics);
    setMatrix(nextMatrix.matrix);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api<{ csrf_token: string }>("/auth/session")
        .then(({ csrf_token }) => loadWorkspace(csrf_token).then(() => setToken(csrf_token)))
        .catch(() => setToken(""));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadWorkspace]);

  const openGaps = useMemo(() => matrix.reduce((sum, row) => sum + row.gaps.filter((gap) => gap.status === "open").length, 0), [matrix]);

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const fullName = String(form.get("full_name") ?? "").trim();
    try {
      if (mode === "register") {
        await api("/users/", undefined, {
          method: "POST",
          body: JSON.stringify({ email, password, full_name: fullName }),
        });
      }
      const credentials = new URLSearchParams({ username: email, password });
      const result = await api<{ csrf_token: string }>("/auth/login/access-token", undefined, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: credentials,
      });
      setToken(result.csrf_token);
      await loadWorkspace(result.csrf_token);
      setNotice("Signed in. Your organization data is ready.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not sign in.");
    } finally {
      setLoading(false);
    }
  }

  async function seedDemo() {
    if (!token) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ organization_id: string }>("/evaluation/demo/seed", token, { method: "POST" });
      await loadWorkspace(token, result.organization_id);
      setNotice("Demo scenario loaded. The matrix now traces obligations through controls, evidence, tests, gaps, and remediation.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the demo scenario.");
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    try {
      await api("/auth/logout", token, { method: "POST" });
    } catch (reason) {
      setError(reason instanceof Error ? `Could not end the server session: ${reason.message}` : "Could not end the server session.");
      return;
    }
    localStorage.removeItem(ORG_KEY);
    setToken("");
    setUser(null);
    setOrganizations([]);
    setMetrics(null);
    setMatrix([]);
    setNotice("");
    setError("");
  }

  if (!token || !user) {
    return (
      <main className="auth-shell">
        <section className="auth-brand">
          <div className="brand-lockup"><span className="brand-mark">R</span><span>Regula<span className="brand-light">AI</span></span></div>
          <div className="auth-message">
            <p className="eyebrow">COMPLIANCE INTELLIGENCE</p>
            <h1>Regulations to evidence.<br /><span>One clear line of sight.</span></h1>
            <p>Turn requirements into accountable controls, verified evidence, and prioritized action.</p>
          </div>
          <div className="auth-footnote"><span className="status-dot" /> Traceable by design <span className="foot-divider">/</span> Human governed</div>
        </section>
        <section className="auth-panel">
          <div className="auth-card">
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
            <p className="muted">{mode === "login" ? "Sign in to continue to your compliance workspace." : "Start a private workspace for your team."}</p>
            <form className="auth-form" onSubmit={handleAuth}>
              {mode === "register" && <label>Full name<input name="full_name" autoComplete="name" required minLength={2} placeholder="Alex Morgan" /></label>}
              <label>Work email<input name="email" type="email" autoComplete="email" required placeholder="you@company.com" /></label>
              <label>Password<input name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={6} placeholder="At least 6 characters" /></label>
              {error && <p className="form-error" role="alert">{error}</p>}
              <button className="button button-primary button-wide" disabled={loading}>{loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}<span aria-hidden>↗</span></button>
            </form>
            <p className="auth-switch">{mode === "login" ? "New to RegulaAI?" : "Already have an account?"}{" "}<button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>{mode === "login" ? "Create account" : "Sign in"}</button></p>
            <p className="auth-security"><span aria-hidden>◈</span> Your organization’s data stays tenant scoped.</p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><span className="brand-mark">R</span><span>Regula<span className="brand-light">AI</span></span></div>
        <p className="side-label">WORKSPACE</p>
        <div className="org-select-wrap"><span className="org-avatar">{(organizations.find((org) => org.id === organizationId)?.name ?? "R").slice(0, 1)}</span><select aria-label="Organization" value={organizationId} onChange={(event) => { const orgId = event.target.value; setOrganizationId(orgId); localStorage.setItem(ORG_KEY, orgId); loadWorkspace(token, orgId).catch((reason) => setError(reason.message)); }}>
          {organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
        </select><span className="select-chevron">⌄</span></div>
        <p className="side-label nav-label">COMPLIANCE</p>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={view === "overview" ? "nav-item active" : "nav-item"} onClick={() => setView("overview")}><span className="nav-icon" aria-hidden="true">◫</span> Overview</button>
          <button className={view === "matrix" ? "nav-item active" : "nav-item"} onClick={() => setView("matrix")}><span className="nav-icon" aria-hidden="true">▦</span> Compliance matrix</button>
          <button className={view === "library" ? "nav-item active" : "nav-item"} onClick={() => setView("library")}><span className="nav-icon" aria-hidden="true">▤</span> Regulatory library</button>
          <button className={view === "controls" ? "nav-item active" : "nav-item"} onClick={() => setView("controls")}><span className="nav-icon" aria-hidden="true">⌘</span> Control library</button>
          <button className="nav-item" onClick={() => setView("matrix")}><span className="nav-icon" aria-hidden="true">◇</span> Gap & remediation</button>
        </nav>
        <div className="sidebar-bottom"><div className="help-card"><span className="help-icon">?</span><div><strong>Need a hand?</strong><small>Explore the linked workflow</small></div><span className="help-arrow">↗</span></div><div className="profile-row"><div className="profile-avatar">{user.full_name.slice(0, 1).toUpperCase()}</div><div className="profile-copy"><strong>{user.full_name}</strong><small>Compliance workspace</small></div><button className="icon-button signout" onClick={signOut} aria-label="Sign out" title="Sign out">↗</button></div></div>
      </aside>

      <section className="main-panel">
        <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{view === "overview" ? "Overview" : view === "matrix" ? "Compliance matrix" : view === "controls" ? "Control library" : "Regulatory library"}</strong></div><div className="top-actions"><span className="system-status"><span className="status-dot" /> Workspace connected</span><button className="icon-button" onClick={() => loadWorkspace(token, organizationId).catch((reason) => setError(reason.message))} aria-label="Refresh data" title="Refresh">↻</button><div className="profile-avatar small-avatar">{user.full_name.slice(0, 1).toUpperCase()}</div></div></header>
        <div className={view === "library" ? "page-content library-active" : "page-content"}>
          <div className="page-heading"><div><p className="eyebrow">REGULATORY CONTROL INTELLIGENCE</p><h1>{view === "overview" ? <>Good morning, <span>{user.full_name.split(" ")[0]}.</span></> : view === "matrix" ? "Compliance matrix" : view === "controls" ? "Control library" : "Regulatory library"}</h1><p className="muted">A connected view of obligations, controls, evidence, and action.</p></div><div className="heading-actions"><span className="updated-label"><span className="status-dot" /> Live workspace</span><button className="button button-primary" onClick={seedDemo} disabled={loading}>{loading ? "Loading…" : "Load demo scenario"}<span aria-hidden>＋</span></button></div></div>
          {error && <div className="notice notice-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss">×</button></div>}
          {notice && <div className="notice notice-success" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss">×</button></div>}

          {view === "overview" ? <>
            <div className="overview-grid">
              <article className="score-card"><div className="score-top"><span>COMPLIANCE HEALTH</span><span className="score-icon">◉</span></div><div className="score-value">{metricLabel(metrics?.overall_compliance_score)}<span> / 100</span></div><div className="score-track"><i style={{ width: `${Math.min(metrics?.overall_compliance_score ?? 0, 100)}%` }} /></div><p>{metrics ? "Based on current approvals, mappings, evidence, and test results." : "Load the demo scenario to populate your traceable workflow."}</p><button className="score-link" onClick={() => setView("matrix")}>View compliance matrix <span>↗</span></button></article>
              <article className="metric-card"><div className="metric-card-head"><span className="metric-icon violet">▤</span><span className="trend neutral">IN SCOPE</span></div><p className="metric-title">Regulatory obligations</p><div className="metric-number">{metrics?.obligations.total ?? "—"}</div><div className="metric-foot"><span>{metrics?.obligations.approved ?? 0} approved</span><span>{metricLabel(metrics?.obligations.approval_rate)}</span></div></article>
              <article className="metric-card"><div className="metric-card-head"><span className="metric-icon blue">⌘</span><span className="trend neutral">CONTROL LIBRARY</span></div><p className="metric-title">Mapped controls</p><div className="metric-number">{metrics?.controls.total ?? "—"}</div><div className="metric-foot"><span>{metrics?.mappings.total ?? 0} obligation mappings</span><span>{metricLabel(metrics?.mappings.approval_rate)}</span></div></article>
              <article className="metric-card"><div className="metric-card-head"><span className="metric-icon green">✓</span><span className="trend positive">EVIDENCE</span></div><p className="metric-title">Validated evidence</p><div className="metric-number">{metrics?.evidence.valid ?? "—"}<small> / {metrics?.evidence.total ?? "—"}</small></div><div className="metric-foot"><span>Verification records</span><span>{metricLabel(metrics?.evidence.validation_rate)}</span></div></article>
              <article className="metric-card"><div className="metric-card-head"><span className="metric-icon amber">△</span><span className="trend warning">NEEDS ATTENTION</span></div><p className="metric-title">Open compliance gaps</p><div className="metric-number">{metrics?.gaps.open ?? "—"}</div><div className="metric-foot"><span>Prioritized findings</span><span>{metrics?.remediation.total ?? 0} plans</span></div></article>
            </div>
            <div className="content-grid">
              <section className="panel-card matrix-preview"><div className="panel-heading"><div><h2>Traceability overview</h2><p>Follow regulatory requirements through to evidence and action.</p></div><button className="link-button" onClick={() => setView("matrix")}>Full matrix <span>↗</span></button></div>
                <div className="trace-steps"><div className="trace-step"><span className="trace-num">01</span><strong>Obligation</strong><small>Source grounded</small></div><span className="trace-connector" /><div className="trace-step"><span className="trace-num">02</span><strong>Control</strong><small>Mapped & reviewed</small></div><span className="trace-connector" /><div className="trace-step"><span className="trace-num">03</span><strong>Evidence</strong><small>Validated</small></div><span className="trace-connector" /><div className="trace-step"><span className="trace-num">04</span><strong>Action</strong><small>Owned & tracked</small></div></div>
                <div className="preview-list">{matrix.slice(0, 3).map((row) => <div className="preview-row" key={row.mapping.id ?? row.obligation.id}><div className="preview-doc">§</div><div className="preview-copy"><strong>{row.obligation.source_section ?? "Regulatory clause"}</strong><small>{row.obligation.text}</small></div><Pill tone={row.gaps.length ? "amber" : "green"}>{row.gaps.length ? "Review needed" : "No recorded finding"}</Pill></div>)}{matrix.length === 0 && <div className="empty-state compact"><span>▦</span><strong>Your traceability view is ready</strong><p>Load the prepared Basel III scenario to see each compliance link in context.</p><button className="button button-secondary" onClick={seedDemo} disabled={loading}>Load demo scenario</button></div>}</div>
              </section>
              <section className="panel-card action-card"><div className="panel-heading"><div><h2>Attention queue</h2><p>Items that may need a compliance decision.</p></div><span className="queue-count">{openGaps}</span></div><div className="attention-item"><span className="attention-mark amber-mark">!</span><div><strong>{openGaps ? `${openGaps} open finding${openGaps === 1 ? "" : "s"}` : "No open findings"}</strong><small>{openGaps ? "Review risk and remediation ownership" : "Load the demo to review a sample gap"}</small></div><button className="icon-button" onClick={() => setView("matrix")} aria-label="View findings">↗</button></div><div className="attention-item"><span className="attention-mark blue-mark">◷</span><div><strong>{metrics?.remediation.total ? `${metrics.remediation.total} remediation plan${metrics.remediation.total === 1 ? "" : "s"}` : "Remediation plans"}</strong><small>Human approval stays in the loop</small></div><button className="icon-button" onClick={() => setView("matrix")} aria-label="View remediation">↗</button></div><div className="responsible-note"><span>◇</span><p><strong>AI with accountability</strong><br />Critical decisions retain source context and human review.</p></div></section>
            </div>
          </> : view === "matrix" ? <section className="panel-card full-matrix"><div className="panel-heading"><div><h2>Obligation-to-evidence matrix</h2><p>Every row keeps the source requirement connected to the control and its proof.</p></div><button className="button button-secondary" onClick={() => loadWorkspace(token, organizationId).catch((reason) => setError(reason.message))}>Refresh data <span>↻</span></button></div>
            {matrix.length ? <div className="table-scroll"><table><thead><tr><th>REGULATORY OBLIGATION</th><th>CONTROL</th><th>EVIDENCE</th><th>TEST</th><th>GAP / RISK</th><th>REMEDIATION</th></tr></thead><tbody>{matrix.map((row) => <tr key={row.mapping.id ?? row.obligation.id}><td><div className="cell-primary">{row.obligation.source_section ?? "Source clause"}</div><div className="cell-secondary">{row.obligation.text}</div><div className="cell-meta">{row.obligation.frequency ?? "Frequency not set"} <span>·</span> {Math.round((row.obligation.confidence ?? 0) * 100)}% confidence</div></td><td>{row.control.id ? <><div className="cell-primary">{row.control.code}</div><div className="cell-secondary">{row.control.objective}</div><Pill tone={row.mapping.status === "mapped" ? "green" : "amber"}>{row.mapping.status}</Pill></> : <Pill tone="red">Unmapped</Pill>}</td><td>{row.evidence.length ? row.evidence.map((evidence) => <div className="evidence-item" key={evidence.id}><Pill tone={evidence.status === "valid" ? "green" : "amber"}>{evidence.status}</Pill><span>{evidence.title}</span></div>) : <span className="muted">No evidence linked</span>}</td><td>{row.tests.length ? row.tests.map((test) => <Pill key={test.id} tone={test.result === "pass" ? "green" : "amber"}>{test.result}</Pill>) : <span className="muted">Not tested</span>}</td><td>{row.gaps.length ? row.gaps.map((gap) => <div className="gap-item" key={gap.id}><Pill tone={gap.severity === "critical" || gap.severity === "high" ? "red" : "amber"}>{gap.severity}</Pill><span>{gap.type.replaceAll("_", " ")}</span></div>) : <Pill tone="green">No recorded gap</Pill>}</td><td>{row.remediation ? <><div className="cell-primary">{row.remediation.status}</div><div className="cell-secondary">{row.remediation.recommendation}</div><Pill tone="neutral">{row.remediation.priority}</Pill></> : <span className="muted">No action required</span>}</td></tr>)}</tbody></table></div> : <div className="empty-state"><span>▦</span><strong>No linked obligations yet</strong><p>Load the prepared demo scenario to explore a complete traceability path.</p><button className="button button-primary" onClick={seedDemo} disabled={loading}>Load demo scenario</button></div>}
          </section> : null}
          {view === "library" && <RegulationIntake token={token} organizationId={organizationId} onComplete={() => loadWorkspace(token, organizationId)} />}
          {view === "controls" && <ControlWorkspace key={organizationId} token={token} organizationId={organizationId} onComplete={() => loadWorkspace(token, organizationId)} />}
          {view === "matrix" && <ComplianceReview key={organizationId} rows={matrix} token={token} organizationId={organizationId} refresh={() => loadWorkspace(token, organizationId)} />}
          <footer className="page-footer"><span>RegulaAI <span className="foot-divider">/</span> Compliance workspace</span><span>Source linked <i>·</i> Tenant scoped <i>·</i> Human governed</span></footer>
        </div>
      </section>
    </main>
  );
}
