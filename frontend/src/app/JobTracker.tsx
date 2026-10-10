"use client";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../lib/api";

type Job = { id: string; status: string; error?: string; retry_count: number; result?: { status?: string } };
export default function JobTracker({ jobId, token, organizationId, onComplete }: { jobId: string; token: string; organizationId: string; onComplete?: () => Promise<void> }) {
  const [job, setJob] = useState<Job | null>(null);
  const [currentId, setCurrentId] = useState(jobId);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const completion = useRef(onComplete);
  useEffect(() => { completion.current = onComplete; }, [onComplete]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      let terminal = false;
      try {
        const result = await api<Job>(`/jobs/${encodeURIComponent(currentId)}?organization_id=${encodeURIComponent(organizationId)}`, token, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setJob(result); setError("");
        if (["succeeded", "failed", "cancelled"].includes(result.status)) {
          terminal = true;
          if (result.status === "succeeded") await completion.current?.();
          return;
        }
      } catch (reason) {
        if (controller.signal.aborted) return;
        setError(errorMessage(reason, "Job status is unavailable."));
      }
      if (!controller.signal.aborted && !terminal) timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [currentId, organizationId, token]);
  async function retry() {
    setBusy(true); setError("");
    try {
      const result = await api<{ job_id: string }>(`/jobs/${encodeURIComponent(currentId)}/retry?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST" });
      setCurrentId(result.job_id); setJob(null);
    } catch (reason) { setError(errorMessage(reason, "Retry failed.")); }
    finally { setBusy(false); }
  }
  return <div className="source-review job-tracker" aria-label="Job progress">
    <div className="job-heading"><span className={`job-dot ${job?.status === "succeeded" ? "done" : ""}`} aria-hidden="true" /><p role="status">Job {currentId}: {job?.status ?? "Checking"}{job?.retry_count ? ` · ${job.retry_count} failed attempts` : ""}</p></div>
    {job?.error && <p className="form-error">{job.error}</p>}
    {job?.status === "succeeded" && <p>Processing finished. The workspace results are ready to review.</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {job?.status === "failed" && <button className="button button-secondary" disabled={busy} onClick={retry}>{busy ? "Retrying…" : "Retry failed job"}</button>}
  </div>;
}
