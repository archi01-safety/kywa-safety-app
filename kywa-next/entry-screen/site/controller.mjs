export const READY_PATH = '/__render/ready';

export async function isReady(response) {
  if (response.status !== 200 || !/application\/json/i.test(response.headers.get('content-type') || '')) return false;
  const body = await response.json();
  return body !== null && !Array.isArray(body) && body.status === 'ok' && Object.keys(body).length === 1;
}

/** One bounded visit; deliberately no persistent polling, cookies, or other APIs. */
export class ReadinessController {
  constructor({ fetcher = globalThis.fetch.bind(globalThis), now = () => performance.now(),
    setTimer = (fn, ms) => globalThis.setTimeout(fn, ms), clearTimer = (id) => globalThis.clearTimeout(id), onState = () => {}, onReady = () => {},
    introDelay = 650, requestTimeout = 5000, retryDelay = 2000, totalTimeout = 120000 } = {}) {
    Object.assign(this, { fetcher, now, setTimer, clearTimer, onState, onReady, introDelay, requestTimeout, retryDelay, totalTimeout });
    this.state = 'idle'; this.epoch = 0; this.activeElapsed = 0; this.timers = new Set(); this.waitingShown = false;
  }
  _timer(fn, ms) {
    const id = this.setTimer(() => { this.timers.delete(id); fn(); }, Math.max(0, ms));
    this.timers.add(id); return id;
  }
  _cancel() {
    this.epoch += 1;
    for (const id of this.timers) this.clearTimer(id);
    this.timers.clear(); this.abort?.abort(); this.abort = null;
  }
  _elapsed() { return this.activeElapsed + (this.startedAt === null ? 0 : this.now() - this.startedAt); }
  start() {
    this._cancel(); this.activeElapsed = 0; this.waitingShown = false;
    this.startedAt = this.now(); this.state = 'checking'; this.onState('checking'); this._arm();
  }
  _arm() {
    const elapsed = this._elapsed();
    this._timer(() => this._delayed(), this.totalTimeout - elapsed);
    if (!this.waitingShown) this._timer(() => {
      this.waitingShown = true; this.state = 'waiting'; this.onState('waiting');
    }, this.introDelay - elapsed);
    this._probe();
  }
  async _probe() {
    if (!['checking', 'waiting'].includes(this.state)) return;
    const epoch = this.epoch;
    const abort = this.abort = new AbortController();
    let timeout;
    try {
      const work = Promise.resolve().then(() => this.fetcher(`${READY_PATH}?_entry=${Math.floor(this.now())}-${epoch}`, {
        method: 'GET', cache: 'no-store', credentials: 'omit', redirect: 'error', signal: abort.signal,
        headers: { Accept: 'application/json' },
      })).then(isReady);
      const limit = new Promise((_, reject) => {
        timeout = this._timer(() => { abort.abort(); reject(new Error('probe-timeout')); },
          Math.min(this.requestTimeout, this.totalTimeout - this._elapsed()));
      });
      const ready = await Promise.race([work, limit]);
      if (epoch !== this.epoch) return;
      if (ready) {
        this._cancel(); this.startedAt = null; this.state = 'ready'; this.onState('ready'); this.onReady(); return;
      }
    } catch { /* A failed probe is retried without exposing infrastructure details. */ }
    finally { if (timeout !== undefined) { this.clearTimer(timeout); this.timers.delete(timeout); } }
    if (epoch !== this.epoch) return;
    this.abort = null;
    if (this._elapsed() >= this.totalTimeout) this._delayed();
    else this._timer(() => this._probe(), this.retryDelay);
  }
  _delayed() {
    if (!['checking', 'waiting'].includes(this.state)) return;
    this.activeElapsed = this._elapsed(); this.startedAt = null; this._cancel();
    this.state = 'delayed'; this.onState('delayed');
  }
  suspend() {
    if (!['checking', 'waiting'].includes(this.state)) return;
    this.activeElapsed = this._elapsed(); this.startedAt = null; this._cancel(); this.state = 'paused';
  }
  resume() {
    if (this.state !== 'paused') return;
    this.startedAt = this.now(); this.state = this.waitingShown ? 'waiting' : 'checking'; this._arm();
  }
  dispose() { this._cancel(); this.startedAt = null; this.state = 'disposed'; }
}
