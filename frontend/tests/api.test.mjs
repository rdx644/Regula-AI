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
    exports, process: { env: {} }, Headers, FormData, AbortSignal, AbortController, fetch,
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
    assert.equal(init.cache, "no-store");
    assert.equal(init.headers.get("X-CSRF-Token"), "test-csrf");
    calls++;
    return calls < 3 ? new Response("Service waking up", { status: calls === 1 ? 502 : 504 }) : json({ csrf_token: "ready" });
  });
  assert.equal((await client.api("/auth/session", "test-csrf")).csrf_token, "ready");
  assert.equal(calls, 3);
  assert.deepEqual(client.delays, [2_000, 4_000]);
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

test("a slow cold start can recover after more than five gateway responses", async () => {
  let calls = 0;
  const client = loadApi(async () => ++calls <= 6
    ? new Response("Unavailable", { status: 502 }) : json({ status: "ok" }));
  assert.equal((await client.api("/health")).status, "ok");
  assert.equal(calls, 7);
  assert.deepEqual(client.delays, [2_000, 4_000, 5_000, 5_000, 5_000, 5_000]);
});

test("continued gateway failures stop at the two-minute deadline", async () => {
  let calls = 0;
  let elapsed = 0;
  const deadline = new AbortController();
  const client = loadApi(async () => { calls++; return new Response("Unavailable", { status: 502 }); }, {
    AbortSignal: {
      any: AbortSignal.any.bind(AbortSignal),
      timeout: duration => duration === 120_000 ? deadline.signal : new AbortController().signal,
    },
    setTimeout: (callback, delay) => {
      elapsed += delay;
      queueMicrotask(() => elapsed >= 120_000
        ? deadline.abort(new DOMException("Deadline", "TimeoutError")) : callback());
      return 1;
    },
  });
  await assert.rejects(client.api("/health"), error => error instanceof client.ApiError && error.status === 0);
  assert.equal(calls, 25);
  assert.equal(elapsed, 121_000);
});

test("HTML hosting wake-up pages are retried even with HTTP 200", async () => {
  let calls = 0;
  const client = loadApi(async () => ++calls === 1
    ? new Response("<html>Starting</html>", { headers: { "content-type": "text/html; charset=utf-8" } })
    : json({ status: "ok" }));
  assert.equal((await client.api("/health")).status, "ok");
  assert.equal(calls, 2);
});

test("a hanging read is cancelled per attempt and then recovers", async () => {
  let calls = 0;
  const timeouts = [];
  const attempt = new AbortController();
  const client = loadApi(async (_url, init) => {
    if (++calls > 1) return json({ status: "ok" });
    return new Promise((_resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(init.signal.reason), { once: true });
      queueMicrotask(() => attempt.abort(new DOMException("Read timed out", "TimeoutError")));
    });
  }, {
    AbortSignal: {
      any: AbortSignal.any.bind(AbortSignal),
      timeout: duration => {
        timeouts.push(duration);
        return duration === 15_000 && calls === 0 ? attempt.signal : new AbortController().signal;
      },
    },
  });
  assert.equal((await client.api("/health")).status, "ok");
  assert.deepEqual(timeouts, [120_000, 15_000, 15_000]);
  assert.equal(calls, 2);
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
    for (const failure of ["gateway", "network", "html"]) {
      let calls = 0;
      const client = loadApi(async () => {
        calls++;
        if (failure === "network") throw new TypeError("Failed to fetch");
        if (failure === "html") return new Response("<html>Starting</html>", { headers: { "content-type": "text/html" } });
        return new Response("Unavailable", { status: 503 });
      });
      await assert.rejects(client.api("/organizations/", "csrf", { method }), error => error.status === (failure === "network" ? 0 : failure === "html" ? 200 : 503));
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

test("readiness and session start concurrently, but a missing session cannot bypass readiness", async () => {
  const calls = [];
  let ready;
  const health = new Promise(resolve => { ready = resolve; });
  const client = loadApi(async url => {
    calls.push(url);
    return url.endsWith("/health") ? health : json({ detail: "Not authenticated" }, 401);
  });
  let connected = false;
  const connection = client.connectSession(new AbortController().signal).then(result => {
    connected = true;
    return result;
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, ["/api/health", "/api/auth/session"]);
  assert.equal(connected, false);
  ready(json({ status: "ok" }));
  assert.equal(await connection, null);
});

test("concurrent connection preserves an existing session", async () => {
  const client = loadApi(async url => json(url.endsWith("/health")
    ? { status: "ok" } : { csrf_token: "existing-csrf" }));
  assert.equal((await client.connectSession(new AbortController().signal)).csrf_token, "existing-csrf");
});

test("only the session endpoint's 401 is treated as a signed-out visitor", async () => {
  const client = loadApi(async () => json({ detail: "Denied" }, 401));
  await assert.rejects(client.connectSession(new AbortController().signal), error => error.status === 401);
  const forbidden = loadApi(async url => url.endsWith("/health")
    ? json({ status: "ok" }) : json({ detail: "Forbidden" }, 403));
  await assert.rejects(forbidden.connectSession(new AbortController().signal), error => error.status === 403);
});

test("a failed readiness check cancels the sibling session read", async () => {
  let sessionSignal;
  const client = loadApi(async (url, init) => {
    if (url.endsWith("/health")) return json({ detail: "Rate limited" }, 429);
    sessionSignal = init.signal;
    return new Promise((_resolve, reject) => init.signal.addEventListener("abort", () => reject(init.signal.reason), { once: true }));
  });
  await assert.rejects(client.connectSession(new AbortController().signal), error => error.status === 429);
  assert.equal(sessionSignal.aborted, true);
});

test("a cancelled connection stops both reads", async () => {
  const signals = [];
  const client = loadApi(async (_url, init) => {
    signals.push(init.signal);
    return new Promise((_resolve, reject) => init.signal.addEventListener("abort", () => reject(init.signal.reason), { once: true }));
  });
  const controller = new AbortController();
  const connection = client.connectSession(controller.signal);
  controller.abort();
  await assert.rejects(connection, error => error.name === "AbortError");
  assert.equal(signals.length, 2);
  assert.ok(signals.every(signal => signal.aborted));
});
