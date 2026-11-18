import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import assert from 'node:assert/strict';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const site = resolve(root, 'site');
const files = [];
function visit(dir) {
  for (const name of readdirSync(dir)) {
    const path = resolve(dir, name);
    if (statSync(path).isDirectory()) visit(path); else files.push(path);
  }
}
visit(site);
let bytes = 0, compressed = 0;
for (const file of files) {
  const data = readFileSync(file); bytes += data.length; compressed += gzipSync(data).length;
  assert(!/\.(pdf|mp4|env|pem|key|zip)$/i.test(file), `Unexpected public file: ${relative(site, file)}`);
  if (/\.(html|mjs|css|json)$/.test(file)) {
    const text = data.toString('utf8');
    assert(!/-----BEGIN (?:RSA )?PRIVATE KEY-----|AIza[\w-]{25,}|pbkdf2_sha256\$|gserviceaccount\.com/.test(text), 'Sensitive content');
  }
}
const html = readFileSync(resolve(site, 'index.html'), 'utf8');
for (const match of html.matchAll(/(?:src|href)="([^"#][^"]*)"/g)) {
  if (/^https:\/\//.test(match[1])) { assert(match[1] === 'https://kywa-safety.onrender.com/#inspect'); continue; }
  assert(files.includes(resolve(site, match[1])), `Missing asset ${match[1]}`);
}
assert.equal((html.match(/data-scene="/g) || []).length, 6);
assert.equal(readFileSync(resolve(site, '_redirects'), 'utf8').trim(), '/__render/ready https://kywa-safety.onrender.com/healthz 200!');
assert(bytes <= 500000, `Initial public files exceed 500KB: ${bytes}`);
const config = JSON.parse(readFileSync(resolve(site, 'config.json'), 'utf8'));
assert(config.storySeconds >= 6 && config.storySeconds <= 118);
console.log(JSON.stringify({ status: 'ok', files: files.length, uncompressedBytes: bytes, gzipBytes: compressed, storySeconds: config.storySeconds }, null, 2));
