"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
type Job = { id: string; status: string; error?: string; retry_count: number };
export default function JobTracker({ jobId, token, organizationId }: { jobId: string; token: string; organizationId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [currentId, setCurrentId] = useState(jobId);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const response = await fetch(`${API}/jobs/${currentId}?organization_id=${organizationId}`, { credentials: "include" });
        if (!response.ok) throw new Error(`Could not read job (${response.status})`);
        const result = await response.json();
        if (active) setJob(result);
      } catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "Job status unavailable"); }
    }
    void poll();
    const timer = window.setInterval(poll, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [currentId, organizationId]);
  async function retry() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${API}/jobs/${currentId}/retry?organization_id=${organizationId}`, { method: "POST", credentials: "include", headers: { "X-CSRF-Token": token } });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Retry failed");
      setCurrentId(result.job_id); setJob(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Retry failed"); }
    finally { setBusy(false); }
  }
  return <div className="source-review" aria-label="Job progress">
    <p role="status">Job {currentId}: {job?.status ?? "Checking"}{job?.retry_count ? ` · ${job.retry_count} failed attempts` : ""}</p>
    {job?.error && <p>{job.error}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {job?.status === "failed" && <button className="button button-secondary" disabled={busy} onClick={retry}>Retry failed job</button>}
  </div>;
}
