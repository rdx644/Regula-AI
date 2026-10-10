"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import JobTracker from "./JobTracker";

import { API_URL, api, errorMessage, validateUpload } from "../lib/api";
import { useCapabilities } from "../lib/capabilities";
type RegulationSummary = { id: string; title: string; source?: string | null; jurisdiction?: string | null; status: string };
type JobStatus = { id: string; type: string; status: string; result?: { status?: string } | null };

const pause = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export default function RegulationIntake({
  token,
  organizationId,
  onComplete,
}: {
  token: string;
  organizationId: string;
  onComplete: () => Promise<void>;
}) {
  const capabilities = useCapabilities();
  const extractionEnabled = capabilities?.model_execution_enabled === true || capabilities?.synthetic_extraction_enabled === true;
  const maxBytes = capabilities?.max_upload_bytes ?? 10 * 1024 * 1024;
  const lifecycle = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => { const controller = new AbortController(); lifecycle.current = controller; return () => controller.abort(); }, []);
  const request = useCallback(<T,>(path: string, csrf: string, init?: RequestInit) =>
    api<T>(path, csrf, { ...init, signal: lifecycle.current?.signal }), []);
  const [items, setItems] = useState<RegulationSummary[]>([]);
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [jobId, setJobId] = useState("");

  const refresh = useCallback(async () => {
    if (!organizationId) return;
    const documents = await request<RegulationSummary[]>(
      `/regulations/?organization_id=${encodeURIComponent(organizationId)}`,
      token,
    );
    if (!lifecycle.current?.signal.aborted) setItems(documents);
  }, [organizationId, token, request]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      refresh().catch((reason: unknown) => {
        if (active && !lifecycle.current?.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load the regulatory library.");
      });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [refresh]);

  async function waitForJob(jobId: string, label: string): Promise<JobStatus> {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await pause(2500);
      if (lifecycle.current?.signal.aborted) throw new DOMException("Cancelled", "AbortError");
      const job = await request<JobStatus>(
        `/jobs/${encodeURIComponent(jobId)}?organization_id=${encodeURIComponent(organizationId)}`,
        token,
      );
      if (job.status === "succeeded") return job;
      if (job.status === "failed" || job.status === "cancelled") {
        throw new Error(`${label} did not complete. Check worker and model configuration, then retry from the library.`);
      }
      setMessage(`${label} — ${job.status}. This page will continue checking progress.`);
    }
    throw new Error(`${label} is still running. Job ${jobId} remains available for status checks.`);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!file) {
      setError("Choose a PDF, TXT, or Markdown source file.");
      return;
    }
    const invalid = validateUpload(file, maxBytes);
    if (invalid) { setError(invalid); return; }

    setBusy(true);
    try {
      setMessage("Creating a tenant-scoped source record…");
      const document = await request<{ id: string; versions: { id: string }[] }>("/regulations/", token, {
        method: "POST",
        body: JSON.stringify({
          organization_id: organizationId,
          title: title.trim(),
          source: source.trim() || null,
          jurisdiction: jurisdiction.trim() || null,
          document_type: "Regulation",
        }),
      });
      const version = document.versions[0];
      if (!version) throw new Error("The source record was created without an initial version.");

      const form = new FormData();
      form.append("file", file);
      await request(`/regulations/${document.id}/versions/${version.id}/file`, token, { method: "POST", body: form });
      const parseJob = await request<{ job_id: string }>(`/regulations/${document.id}/process`, token, {
        method: "POST",
        body: JSON.stringify({ version_id: version.id }),
      });
      setJobId(parseJob.job_id);
      setMessage(`Source secured. Parsing job ${parseJob.job_id} is queued…`);
      const parsed = await waitForJob(parseJob.job_id, "Document parsing");
      if (parsed.result?.status !== "parsed") throw new Error("The document parser did not produce a parsed version.");

      if (extractionEnabled) {
      const extraction = await request<{ job_id: string }>(`/regulations/${document.id}/extract-obligations`, token, {
        method: "POST",
        body: JSON.stringify({ version_id: version.id }),
      });
      setJobId(extraction.job_id);
      setMessage(`Extracting obligations (job ${extraction.job_id})…`);
      const extracted = await waitForJob(extraction.job_id, "Obligation extraction");
      if (extracted.result?.status !== "processed") {
        throw new Error("Obligation extraction finished without a successful result. Review the document and worker configuration before retrying.");
      }
      }
      await refresh();
      await onComplete();
      setTitle("");
      setSource("");
      setJurisdiction("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setMessage(extractionEnabled ? "Processing finished. Review extracted obligations in the compliance matrix before approving or mapping them." : "Source uploaded and parsed. AI extraction is paused; download the source here or use the demo scenario to explore the reviewed workflow.");
    } catch (reason) {
      if (lifecycle.current?.signal.aborted) return;
      setError(reason instanceof Error ? reason.message : "The regulatory document could not be processed.");
      await refresh().catch(() => undefined);
    } finally {
      if (!lifecycle.current?.signal.aborted) setBusy(false);
    }
  }

  async function download(item: RegulationSummary) {
    setError("");
    try {
      const record = await request<{ versions: { id: string; version_number: number }[] }>(`/regulations/${item.id}`, token);
      const version = [...record.versions].sort((a,b) => b.version_number - a.version_number)[0];
      if (!version) throw new Error("This record has no source version.");
      const response = await fetch(`${API_URL}/regulations/${item.id}/versions/${version.id}/file`, { credentials: "include", signal: lifecycle.current?.signal });
      if (!response.ok) throw new Error("This source is unavailable. Temporary demo files may be lost after a restart; upload a new source if needed.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = response.headers.get("content-type")?.includes("pdf") ? "regulation-source.pdf" : "regulation-source.txt";
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
      setMessage("Private source downloaded for review.");
    } catch (reason) { if (!lifecycle.current?.signal.aborted) setError(errorMessage(reason)); }
  }

  return (
    <div className="library-grid" aria-busy={busy}>
      <section className="panel-card intake-card">
        <div className="panel-heading"><div><h2>Ingest a regulation</h2><p>{extractionEnabled ? "Upload a source and follow parsing and extraction." : "Upload and parse a source. AI extraction is currently paused."}</p></div><span className="pill pill-neutral">Private · tenant scoped</span></div>
        <form className="intake-form" onSubmit={submit}>
          <label>Regulation title<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={1} maxLength={512} placeholder="e.g. RBI Master Direction" /></label>
          <div className="intake-fields"><label>Issuing authority<input value={source} onChange={(event) => setSource(event.target.value)} placeholder="RBI, OCC, EBA…" /></label><label>Jurisdiction<input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} placeholder="IN, US, EU…" /></label></div>
          <label>Source document<input ref={fileInput} type="file" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /></label>
          <p className="intake-hint">PDF, TXT, or Markdown · up to {Math.round(maxBytes / 1024 / 1024)} MB. Uploaded source documents are private; extracted obligations still require human review.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          {message && <p className="intake-progress" role="status">{message}</p>}
          <button className="button button-primary" disabled={busy || !organizationId}>{busy ? "Processing…" : extractionEnabled ? "Upload and extract obligations" : "Upload and parse source"}<span aria-hidden>↗</span></button>
        </form>
        {jobId && <JobTracker key={jobId} jobId={jobId} token={token} organizationId={organizationId} onComplete={async () => { await refresh(); await onComplete(); }} />}
      </section>
      <section className="panel-card library-list">
        <div className="panel-heading"><div><h2>Regulatory library</h2><p>Source records in the selected organization.</p></div><button className="link-button" onClick={() => refresh().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Refresh failed."))}>Refresh ↻</button></div>
        <div className="library-items">{items.map((item) => <article className="library-item" key={item.id}><span className="library-mark">§</span><div className="library-copy"><strong>{item.title}</strong><small>{[item.source, item.jurisdiction].filter(Boolean).join(" · ") || "Source details not set"}</small></div><span className={`pill pill-${item.status === "processed" ? "green" : item.status === "failed" ? "red" : "amber"}`}>{item.status}</span><button className="link-button" disabled={busy} onClick={() => download(item)} aria-label={`Download source for ${item.title}`}>Source ↗</button></article>)}{items.length === 0 && <div className="empty-state compact"><span>§</span><strong>No source records yet</strong><p>Use the form to create a privately stored regulation source.</p></div>}</div>
      </section>
    </div>
  );
}
