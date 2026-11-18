/** Serve the generated site with a local health response. */
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import assert from 'node:assert/strict';
import { partnerIds } from './build.mjs';

const { values } = parseArgs({
  options: {
    org: { type: 'string' },
    port: { type: 'string', default: '8026' },
    mode: { type: 'string', default: 'unready' },
  },
});
const { org, mode } = values;
const port = Number(values.port);
assert(partnerIds.includes(org), 'Select a supported partner with --org.');
assert(Number.isInteger(port) && port > 1023 && port < 65536, 'Invalid port');
assert(['unready', 'ready', 'starting', 'html', 'hang'].includes(mode), 'Invalid mock mode');

const dist = fileURLToPath(new URL('../dist/', import.meta.url));
const manifest = JSON.parse(readFileSync(resolve(dist, `${org}.manifest.json`), 'utf8'));
const files = new Map(manifest.files.filter(({ path }) => !path.startsWith('_')).map(({ path }) => [
  `/${path}`, readFileSync(resolve(dist, org, path)),
]));
const mime = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.mjs': 'text/javascript',
  '.json': 'application/json', '.png': 'image/png',
};

let probeCount = 0;
createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET') { res.writeHead(405).end(); return; }
  if (url.pathname === '/__render/ready') {
    console.log(JSON.stringify({ mockProbe: ++probeCount, at: new Date().toISOString(), mode }));
    if (mode === 'hang') return;
    if (mode === 'html') {
      res.writeHead(200, { 'Content-Type': 'text/html' }).end('<title>Render loading example</title>');
      return;
    }
    const ready = mode === 'ready' || (mode === 'starting' && probeCount > 1);
    res.writeHead(ready ? 200 : 503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: ready ? 'ok' : 'starting' }));
    return;
  }
  const path = url.pathname === '/' ? '/index.html' : url.pathname;
  const file = files.get(path);
  if (!file) { res.writeHead(404).end('Not found'); return; }
  res.writeHead(200, { 'Content-Type': mime[extname(path)] }).end(file);
}).listen(port, '127.0.0.1', () => {
  console.log(`Local ${org} preview: http://localhost:${port}/?preview=1`);
});
