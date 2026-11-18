import test from 'node:test';
import assert from 'node:assert/strict';
import { ReadinessController, isReady } from '../site/controller.mjs';

const flush = async () => { for (let i = 0; i < 14; i++) await Promise.resolve(); };
const response = (status = 200, body = { status: 'ok' }, type = 'application/json') => ({
  status, headers: { get: () => type }, json: async () => body,
});
function harness() {
  let time = 0, sequence = 0;
  const timers = new Map(), requests = [], states = [], navigations = [];
  const controller = new ReadinessController({
    now: () => time,
    setTimer(fn, ms) { const id = ++sequence; timers.set(id, { at: time + ms, fn }); return id; },
    clearTimer(id) { timers.delete(id); },
    fetcher(url, options) { return new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })); },
    onState: (state) => states.push(state), onReady: () => navigations.push('ready'),
  });
  async function advance(ms) {
    await flush(); const end = time + ms;
    for (;;) {
      const next = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
      if (!next || next[1].at > end) break;
      time = next[1].at; timers.delete(next[0]); next[1].fn(); await flush();
    }
    time = end; await flush();
  }
  return { controller, requests, states, navigations, timers, advance };
}

test('strict readiness rejects HTML, redirects, errors, and malformed bodies', async () => {
  for (const r of [response(200, null, 'text/html'), response(503), response(302), response(200, {}),
    response(200, { status: 'loading' }), response(200, [{ status: 'ok' }]), response(200, { status: 'ok', other: true })]) {
    assert.equal(await isReady(r), false);
  }
  assert.equal(await isReady(response(200, { status: 'ok' }, 'application/json; charset=utf-8')), true);
});
test('ready within 650ms skips story and signals navigation exactly once', async () => {
  const h = harness(); h.controller.start(); await h.advance(400);
  h.requests[0].resolve(response()); await flush(); await h.advance(20000);
  assert.deepEqual(h.states, ['checking', 'ready']); assert.deepEqual(h.navigations, ['ready']); assert.equal(h.timers.size, 0);
});
test('650ms shows story but readiness interrupts it without waiting for its duration', async () => {
  const h = harness(); h.controller.start(); await h.advance(649); assert.deepEqual(h.states, ['checking']);
  await h.advance(1); assert.equal(h.states.at(-1), 'waiting');
  h.requests[0].resolve(response()); await flush(); assert.equal(h.navigations.length, 1);
});
test('all probes are GET, no-store, same-origin, cookie-free, and non-redirecting', async () => {
  const h = harness(); h.controller.start(); await flush(); const { url, options } = h.requests[0];
  assert.match(url, /^\/__render\/ready\?_entry=/); assert.equal(options.method, 'GET');
  assert.equal(options.cache, 'no-store'); assert.equal(options.credentials, 'omit'); assert.equal(options.redirect, 'error');
  h.controller.dispose();
});
test('a failed response waits two seconds and does not overlap requests', async () => {
  const h = harness(); h.controller.start(); await flush(); h.requests[0].resolve(response(503)); await flush();
  await h.advance(1999); assert.equal(h.requests.length, 1); await h.advance(1); assert.equal(h.requests.length, 2);
  h.requests[1].resolve(response()); await flush(); assert.equal(h.navigations.length, 1);
});
test('a request times out at five seconds and aborts before another starts', async () => {
  const h = harness(); h.controller.start(); await h.advance(4999); assert.equal(h.requests[0].options.signal.aborted, false);
  await h.advance(1); assert.equal(h.requests[0].options.signal.aborted, true);
  await h.advance(2000); assert.equal(h.requests.length, 2); h.controller.dispose();
});
test('120-second deadline stops checks and ignores a late response', async () => {
  const h = harness(); h.controller.start(); await h.advance(120000); assert.equal(h.controller.state, 'delayed');
  const count = h.requests.length; h.requests.at(-1).resolve(response()); await h.advance(30000);
  assert.equal(h.requests.length, count); assert.equal(h.navigations.length, 0); assert.equal(h.timers.size, 0);
});
test('manual retry starts a new bounded attempt and ignores earlier requests', async () => {
  const h = harness(); h.controller.start(); await h.advance(120000); const old = h.requests[0];
  h.controller.start(); await flush(); old.resolve(response()); await flush(); assert.equal(h.navigations.length, 0);
  h.requests.at(-1).resolve(response()); await flush(); assert.equal(h.navigations.length, 1);
});
test('background cancels probes, freezes the active budget, and resumes with a fresh request', async () => {
  const h = harness(); h.controller.start(); await h.advance(300); h.controller.suspend();
  assert.equal(h.requests[0].options.signal.aborted, true); await h.advance(180000);
  assert.equal(h.requests.length, 1); h.requests[0].resolve(response()); await flush(); assert.equal(h.navigations.length, 0);
  h.controller.resume(); await flush(); assert.equal(h.requests.length, 2);
  await h.advance(349); assert.equal(h.states.includes('waiting'), false);
  await h.advance(1); assert.equal(h.states.at(-1), 'waiting');
  h.requests[1].resolve(response()); await flush(); assert.equal(h.navigations.length, 1);
});
test('background after story starts preserves waiting state and does not replay waiting event', async () => {
  const h = harness(); h.controller.start(); await h.advance(1000); h.controller.suspend(); await h.advance(50000);
  h.controller.resume(); await flush(); assert.equal(h.controller.state, 'waiting');
  assert.equal(h.states.filter((v) => v === 'waiting').length, 1); h.controller.dispose();
});
test('malformed JSON or a network error stays on the guide and can recover', async () => {
  const h = harness(); h.controller.start(); await flush();
  h.requests[0].resolve({ ...response(), json: async () => { throw new Error('invalid json'); } });
  await flush(); await h.advance(2000); h.requests[1].reject(new Error('network')); await flush();
  await h.advance(2000); h.requests[2].resolve(response()); await flush(); assert.equal(h.navigations.length, 1);
});
test('a stalled JSON body has the same five-second bound as connection establishment', async () => {
  const h = harness(); h.controller.start(); await flush();
  h.requests[0].resolve({ ...response(), json: () => new Promise(() => {}) }); await h.advance(7000);
  assert.equal(h.requests.length, 2); h.controller.dispose();
});
test('disposing a visit clears all timers and late navigation', async () => {
  const h = harness(); h.controller.start(); await flush(); h.controller.dispose(); h.requests[0].resolve(response());
  await h.advance(150000); assert.equal(h.navigations.length, 0); assert.equal(h.requests.length, 1); assert.equal(h.timers.size, 0);
});

test('default timer adapters preserve the browser Window receiver', async () => {
  const originalSet = globalThis.setTimeout, originalClear = globalThis.clearTimeout;
  let id = 0;
  try {
    globalThis.setTimeout = function () { assert.equal(this, globalThis); return ++id; };
    globalThis.clearTimeout = function () { assert.equal(this, globalThis); };
    const controller = new ReadinessController({ fetcher: () => new Promise(() => {}) });
    controller.start(); await flush(); controller.dispose(); assert(id >= 3);
  } finally { globalThis.setTimeout = originalSet; globalThis.clearTimeout = originalClear; }
});
