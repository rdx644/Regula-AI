"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import JobTracker from "./JobTracker";
import { errorMessage, validateUpload } from "../lib/api";
import { useCapabilities } from "../lib/capabilities";
import { exportReview, useWorkspaceRequest } from "../lib/workspace-review";

type Document = { id: string; title: string };
type Version = { id: string; version_number: number; status: string };
type Report = { method: string; old_version_id: string; new_version_id: string; old_version_number: number; new_version_number: number; scope_note: string;
  candidate_control_ids?: string[]; candidate_obligation_ids?: string[]; candidate_policy_ids?: string[];
  hunks: { kind: string; old_line_start: number; new_line_start: number; before: string; after: string }[] };
type Change = { id: string; change_type: string; summary: string; status: string };
type Comparison = { changed: boolean; report: Report; change_id?: string; impact_id?: string };
export default function ChangeWorkspace({ token, organizationId }: { token: string; organizationId: string }) {
  const { request, isActive } = useWorkspaceRequest(token);
  const capabilities = useCapabilities();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [jobId, setJobId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    const docs = await request<Document[]>(`/regulations/?organization_id=${organizationId}`, undefined, "GET");
    if (isActive()) setDocuments(docs);
    if (documentId) {
      const [document, records] = await Promise.all([
        request<{ versions: Version[] }>(`/regulations/${documentId}`, undefined, "GET"),
        request<Change[]>(`/changes/?organization_id=${organizationId}&document_id=${documentId}`, undefined, "GET"),
      ]);
      if (isActive()) { setVersions(document.versions); setChanges(records); }
    }
  }, [documentId, organizationId, request, isActive]);
  useEffect(() => { const timer = setTimeout(() => { void refresh().catch(reason => { if (isActive()) setError(errorMessage(reason)); }); }, 0); return () => clearTimeout(timer); }, [refresh, isActive]);
  async function perform(work: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await work(); if (isActive()) await refresh(); }
    catch (reason) { if (isActive()) setError(errorMessage(reason)); }
    finally { if (isActive()) setBusy(false); }
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const file = form.get("file");
    if (!(file instanceof File)) return;
    const invalid = validateUpload(file, capabilities?.max_upload_bytes ?? 10_485_760);
    if (invalid) { setError(invalid); return; }
    await perform(async () => {
      const version = await request<Version>(`/regulations/${documentId}/versions`, {});
      const data = new FormData(); data.set("file", file);
      await request(`/regulations/${documentId}/versions/${version.id}/file`, data);
      const job = await request<{ job_id: string }>(`/regulations/${documentId}/process`, { version_id: version.id });
      if (!isActive()) return;
      setJobId(job.job_id); setNotice(`Version ${version.version_number} uploaded. Wait for parsing before comparing.`);
    });
  }
  async function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    await perform(async () => {
      const result = await request<Comparison>("/changes/compare-text", { document_id: documentId, old_version_id: form.get("old"), new_version_id: form.get("new") });
      if (isActive()) { setComparison(result); setNotice(result.changed ? "Text comparison and candidate impact draft saved for human review." : "No literal text differences found."); }
    });
  }
  const ready = versions.filter(version => ["parsed", "processed"].includes(version.status));
  return <div className="review-workspace">
    <section className="panel-card"><h2>A change you can inspect</h2><p className="muted">Compare exact source text and retain a candidate impact draft. A reviewer must determine legal relevance; this workflow makes no semantic or AI claim.</p>
      <label className="review-select">Source document<select value={documentId} disabled={busy} onChange={event => { setDocumentId(event.target.value); setVersions([]); setChanges([]); setComparison(null); setJobId(""); setError(""); }}><option value="">Choose a source</option>{documents.map(document => <option key={document.id} value={document.id}>{document.title}</option>)}</select></label>
      {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="intake-progress" role="status">{notice}</p>}
    </section>
    {documentId && <><div className="library-grid">
      <section className="panel-card intake-card"><h2>Add a source version</h2><p className="muted">PDF, TXT or Markdown. Private uploads are temporary in this demo.</p><form className="intake-form" onSubmit={upload}><label>New version file<input name="file" type="file" accept=".pdf,.txt,.md" required /></label><button className="button button-primary" disabled={busy}>Upload new version</button></form>{versions.map(version => <p key={version.id}>Version {version.version_number} <span className="pill">{version.status}</span></p>)}</section>
      <section className="panel-card intake-card"><h2>Compare parsed versions</h2><form className="intake-form" onSubmit={compare}><label>Previous version<select name="old" required><option value="">Choose previous version</option>{ready.map(version => <option key={version.id} value={version.id}>Version {version.version_number}</option>)}</select></label><label>Updated version<select name="new" required><option value="">Choose updated version</option>{ready.map(version => <option key={version.id} value={version.id}>Version {version.version_number}</option>)}</select></label><button className="button button-primary" disabled={busy || ready.length < 2}>Compare text versions</button></form><p className="muted">Up to 50,000 characters and 500 lines per version. Same-version comparisons are rejected.</p></section>
    </div>{jobId && <JobTracker key={jobId} jobId={jobId} token={token} organizationId={organizationId} onComplete={refresh} />}</>}
    {comparison && <section className="panel-card"><h2>Version {comparison.report.old_version_number} to {comparison.report.new_version_number}</h2><p>{comparison.report.scope_note}</p><p>{comparison.report.candidate_obligation_ids?.length ?? 0} candidate obligations / {comparison.report.candidate_control_ids?.length ?? 0} candidate controls / {comparison.report.candidate_policy_ids?.length ?? 0} candidate policies</p>{comparison.impact_id && <p className="muted">Impact draft: {comparison.impact_id}. No new gaps or risk delta inferred.</p>}{comparison.report.hunks.map((hunk, index) => <article className="source-review" key={index}><h3>{hunk.kind} / source text lines</h3><div className="diff-grid"><div><strong>Before / line {hunk.old_line_start}</strong><pre tabIndex={0} role="region" aria-label={`Previous source text, change ${index + 1}`}>{hunk.before || "No text"}</pre></div><div><strong>After / line {hunk.new_line_start}</strong><pre tabIndex={0} role="region" aria-label={`Updated source text, change ${index + 1}`}>{hunk.after || "No text"}</pre></div></div></article>)}<button className="button button-secondary" onClick={() => exportReview("source-comparison.json", comparison)}>Export comparison</button></section>}
    <section className="panel-card"><h2>Saved comparisons</h2>{changes.length ? changes.map(change => <article className="source-review" key={change.id}><p>{change.change_type.replaceAll("_", " ")} / {change.status}</p>{change.change_type === "literal_text_diff" && <button className="button button-secondary" onClick={() => { try { setComparison({ changed: true, report: JSON.parse(change.summary), change_id: change.id }); } catch { setError("This saved comparison could not be read."); } }}>Open saved comparison</button>}</article>) : <p className="muted">Select a source and compare two parsed versions to retain the result here.</p>}</section>
  </div>;
}
