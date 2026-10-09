"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import JobTracker from "./JobTracker";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
type RegulationSummary = { id: string; title: string; source?: string | null; jurisdiction?: string | null; status: string };
type JobStatus = { id: string; type: string; status: string; result?: { status?: string } | null };

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      "X-CSRF-Token": token,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (typeof body.error?.message === "string") message = body.error.message;
    } catch {
      // Keep the status-based error when the API doesn't return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

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
    setItems(documents);
  }, [organizationId, token]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      refresh().catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Could not load the regulatory library.");
      });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [refresh]);

  async function waitForJob(jobId: string, label: string): Promise<JobStatus> {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await pause(1500);
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
    if (file.size > 25 * 1024 * 1024) {
      setError("The selected file exceeds the 25 MB upload limit.");
      return;
    }

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
      await refresh();
      await onComplete();
      setTitle("");
      setSource("");
      setJurisdiction("");
      setFile(null);
      setMessage("Processing finished. Review extracted obligations in the compliance matrix before approving or mapping them.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The regulatory document could not be processed.");
      await refresh().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="library-grid">
      <section className="panel-card intake-card">
        <div className="panel-heading"><div><h2>Ingest a regulation</h2><p>Upload a source and follow the parse and extraction jobs.</p></div><span className="pill pill-neutral">Private · tenant scoped</span></div>
        <form className="intake-form" onSubmit={submit}>
          <label>Regulation title<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={1} maxLength={512} placeholder="e.g. RBI Master Direction" /></label>
          <div className="intake-fields"><label>Issuing authority<input value={source} onChange={(event) => setSource(event.target.value)} placeholder="RBI, OCC, EBA…" /></label><label>Jurisdiction<input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} placeholder="IN, US, EU…" /></label></div>
          <label>Source document<input type="file" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /></label>
          <p className="intake-hint">PDF, TXT, or Markdown · up to 25 MB. Uploaded source documents are private; extracted obligations still require human review.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          {message && <p className="intake-progress" role="status">{message}</p>}
          <button className="button button-primary" disabled={busy || !organizationId}>{busy ? "Processing…" : "Upload and extract obligations"}<span aria-hidden>↗</span></button>
        </form>
        {jobId && <JobTracker key={jobId} jobId={jobId} token={token} organizationId={organizationId} />}
      </section>
      <section className="panel-card library-list">
        <div className="panel-heading"><div><h2>Regulatory library</h2><p>Source records in the selected organization.</p></div><button className="link-button" onClick={() => refresh().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Refresh failed."))}>Refresh ↻</button></div>
        <div className="library-items">{items.map((item) => <article className="library-item" key={item.id}><span className="library-mark">§</span><div className="library-copy"><strong>{item.title}</strong><small>{[item.source, item.jurisdiction].filter(Boolean).join(" · ") || "Source details not set"}</small></div><span className={`pill pill-${item.status === "processed" ? "green" : item.status === "failed" ? "red" : "amber"}`}>{item.status}</span></article>)}{items.length === 0 && <div className="empty-state compact"><span>§</span><strong>No source records yet</strong><p>Use the form to create a privately stored regulation source.</p></div>}</div>
      </section>
    </div>
  );
}
