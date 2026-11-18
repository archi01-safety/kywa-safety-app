/** Local mock only. Never forwards a request to Render. */
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../site');
const arg = (name, fallback) => process.argv.find((s) => s.startsWith(`--${name}=`))?.split('=')[1] || fallback;
const port = Number(arg('port', '8024')), mode = arg('mode', 'unready');
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.mjs': 'text/javascript', '.json': 'application/json', '.png': 'image/png' };
let probeCount = 0;
createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/__render/ready') {
    console.log(JSON.stringify({ mockProbe: ++probeCount, at: new Date().toISOString(), mode }));
    res.setHeader('Cache-Control', 'no-store');
    if (mode === 'hang') return;
    if (mode === 'html') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end('<title>Render loading example</title>'); return; }
    res.writeHead(mode === 'ready' ? 200 : 503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: mode === 'ready' ? 'ok' : 'starting' })); return;
  }
  const file = resolve(root, `.${decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname)}`);
  if (!file.startsWith(`${root}/`) && !file.startsWith(`${root}\\`)) { res.writeHead(403); res.end(); return; }
  try {
    const body = await readFile(file); res.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' }); res.end(body);
  } catch { res.writeHead(404); res.end('Not found'); }
}).listen(port, '127.0.0.1', () => console.log(`Local static mock: http://localhost:${port}/?preview=1 (no Render requests)`));
