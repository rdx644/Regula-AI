"use client";
import { useCallback, useEffect, useRef } from "react";
import { api } from "./api";

export function useWorkspaceRequest(token: string) {
  const lifecycle = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController(); lifecycle.current = controller;
    return () => controller.abort();
  }, []);
  const request = useCallback(<T,>(path: string, body?: object | FormData, method = "POST") =>
    api<T>(path, token, { method, signal: lifecycle.current?.signal,
      ...(body ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {}) }), [token]);
  const isActive = useCallback(() => !lifecycle.current?.signal.aborted, []);
  return { request, isActive };
}

export function exportReview(name: string, report: object) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = name;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
