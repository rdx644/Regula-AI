import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// Run the browser helper with native fetch primitives and a controlled clock.
const compiled = ts.transpileModule(
  fs.readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
).outputText;

function loadApi(fetch, overrides = {}) {
  const exports = {};
  const delays = [];
  const context = vm.createContext({
    exports, process: { env: {} }, Headers, FormData, AbortSignal, fetch,
    setTimeout: (callback, delay) => { delays.push(delay); queueMicrotask(callback); return 1; },
    clearTimeout: () => {}, ...overrides,
  });
  vm.runInContext(compiled, context);
  return { ...exports, delays };
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

test("a read recovers from gateway errors while preserving cookies and CSRF", async () => {
  let calls = 0;
  const client = loadApi(async (url, init) => {
    assert.equal(url, "/api/auth/session");
    assert.equal(init.credentials, "include");
    assert.equal(init.headers.get("X-CSRF-Token"), "test-csrf");
    calls++;
    return calls < 3 ? new Response("Service waking up", { status: calls === 1 ? 502 : 504 }) : json({ csrf_token: "ready" });
  });
  assert.equal((await client.api("/auth/session", "test-csrf")).csrf_token, "ready");
  assert.equal(calls, 3);
  assert.deepEqual(client.delays, [5_000, 10_000]);
});

test("network failures recover on a read", async () => {
  let calls = 0;
  const client = loadApi(async () => {
    if (++calls === 1) throw new TypeError("Failed to fetch");
    return json({ status: "ok" });
  });
  assert.equal((await client.api("/health")).status, "ok");
  assert.equal(calls, 2);
});

test("continued gateway failure reaches a bounded retry limit", async () => {
  let calls = 0;
  const client = loadApi(async () => { calls++; return new Response("Unavailable", { status: 502 }); });
  await assert.rejects(client.api("/health"), error => error instanceof client.ApiError && error.status === 502);
  assert.equal(calls, 5);
  assert.deepEqual(client.delays, [5_000, 10_000, 20_000, 30_000]);
});

test("authorization, validation, and rate-limit failures return immediately", async () => {
  for (const status of [400, 401, 403, 429]) {
    let calls = 0;
    const client = loadApi(async () => { calls++; return json({ detail: "Denied" }, status); });
    await assert.rejects(client.api("/auth/session"), error => error.status === status && error.message === "Denied");
    assert.equal(calls, 1);
    assert.deepEqual(client.delays, []);
  }
});

test("writes are never replayed, including network failures", async () => {
  for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
    for (const failure of ["gateway", "network"]) {
      let calls = 0;
      const client = loadApi(async () => {
        calls++;
        if (failure === "network") throw new TypeError("Failed to fetch");
        return new Response("Unavailable", { status: 503 });
      });
      await assert.rejects(client.api("/organizations/", "csrf", { method }), error => error.status === (failure === "network" ? 0 : 503));
      assert.equal(calls, 1);
      assert.deepEqual(client.delays, []);
    }
  }
});

test("cancelling during retry backoff stops requests immediately", async () => {
  const controller = new AbortController();
  let calls = 0;
  const client = loadApi(async () => { calls++; return new Response("Unavailable", { status: 502 }); }, {
    setTimeout: () => { queueMicrotask(() => controller.abort()); return 1; },
  });
  await assert.rejects(client.api("/auth/session", undefined, { signal: controller.signal }), error => error.name === "AbortError");
  assert.equal(calls, 1);
});

test("the overall deadline stops retry backoff", async () => {
  const deadline = new AbortController();
  const timeouts = [];
  let calls = 0;
  const client = loadApi(async () => { calls++; return new Response("Unavailable", { status: 502 }); }, {
    AbortSignal: {
      any: AbortSignal.any.bind(AbortSignal),
      timeout: duration => { timeouts.push(duration); return deadline.signal; },
    },
    setTimeout: () => { queueMicrotask(() => deadline.abort(new DOMException("Deadline", "TimeoutError"))); return 1; },
  });
  await assert.rejects(client.api("/auth/session"), error => error instanceof client.ApiError && error.status === 0);
  assert.equal(calls, 1);
  assert.equal(timeouts[0], 120_000);
});
