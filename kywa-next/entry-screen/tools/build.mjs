import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const root = fileURLToPath(new URL('../', import.meta.url));
const template = resolve(root, 'site');
const profiles = resolve(root, '../backend/organizations');
export const partnerIds = Object.freeze(['fowi', 'ayf', 'khidi', 'knps', 'knf', 'kohi', 'cayf']);
const commonFiles = ['_headers', 'app.mjs', 'controller.mjs', 'assets/icon.png'];
const storySeconds = 20.734;
const supportersName = '한국청소년활동진흥원';

function readTextTemplate(name) {
  return readFileSync(resolve(template, name), 'utf8').replace(/\r\n/g, '\n');
}

function readPartner(id) {
  assert(partnerIds.includes(id), 'Select a supported partner with --org.');
  const record = JSON.parse(readFileSync(resolve(profiles, `${id}.json`), 'utf8'));
  assert.equal(record.id, id);
  assert.equal(record.branding.technical_support, true);
  assert(typeof record.name === 'string' && record.name.trim());
  assert.match(record.short_name, /^[A-Za-z0-9]+$/);
  assert.match(record.branding.primary, /^#[\da-f]{6}$/i);
  assert.match(record.branding.secondary, /^#[\da-f]{6}$/i);
  assert(['required', 'optional', 'disabled'].includes(record.submitter_name.mode));

  const origin = `https://${id}-safety.onrender.com`;
  return {
    id,
    name: record.name,
    shortName: record.short_name,
    nameMode: record.submitter_name.mode,
    primary: record.branding.primary.toUpperCase(),
    secondary: record.branding.secondary.toUpperCase(),
    renderUrl: `${origin}/#inspect`,
    healthUrl: `${origin}/healthz`,
  };
}

const htmlEscapes = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const escape = (text) => text.replace(/[&<>"']/g, (character) => htmlEscapes[character]);

function renderHtml(organization) {
  const collectsName = organization.nameMode !== 'disabled';
  const privacyDescription = collectsName
    ? '분석 시 사진의 얼굴을 찾아 블러 처리하고,<br>성명 입력란은 초성으로 변환해 전송합니다.'
    : '분석 시 사진의 얼굴을 찾아 블러 처리합니다.<br>전송 전에 처리된 사진을 확인해 주세요.';
  const privacyCard = collectsName
    ? '<span>성명 입력란 변환 예시</span><div><del>홍길동</del><b>→</b><strong>홍㉠㉢</strong></div><p>제출 전 변환값을 미리 확인</p>'
    : '<span>개인정보 확인</span><div><strong>사진 확인</strong></div><p>제출 전 얼굴이나 민감정보가 남았는지 확인</p>';
  const values = {
    institutionName: escape(organization.name),
    shortName: escape(organization.shortName),
    supportingInstitution: escape(supportersName),
    renderUrl: escape(organization.renderUrl),
    privacyDescription,
    privacyCard,
  };
  return readTextTemplate('index.html').replace(/\{\{(\w+)\}\}/g, (_, key) => {
    assert(Object.hasOwn(values, key), `Unknown template field ${key}`);
    return values[key];
  });
}

const rgb = (color) => [1, 3, 5].map((offset) => Number.parseInt(color.slice(offset, offset + 2), 16));
const hex = (channels) => `#${channels.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;

function luminance(color) {
  const linear = rgb(color).map((channel) => {
    const srgb = channel / 255;
    return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

export function contrast(first, second) {
  const [low, high] = [luminance(first), luminance(second)].sort((a, b) => a - b);
  return (high + 0.05) / (low + 0.05);
}

function readableTone(base, background, target) {
  const from = rgb(base);
  const to = rgb(target);
  for (let step = 0; step <= 100; step++) {
    const candidate = hex(from.map((channel, i) => Math.round(channel + (to[i] - channel) * step / 100)));
    if (contrast(candidate, background) >= 4.5) return candidate;
  }
  throw new Error(`No readable tone for ${base} on ${background}`);
}

function renderStyles({ primary, secondary }) {
  const light = '#ffffff';
  const dark = '#000000';
  const darkestText = contrast(primary, dark) > contrast(primary, light) ? dark : light;
  // The shared accent also appears on the lighter charcoal panels.
  const panel = '#2d3949';
  const colors = `:root {
  --brand-primary: ${primary};
  --brand-secondary: ${secondary};
  --brand-primary-text: ${readableTone(primary, panel, light)};
  --brand-secondary-text: ${readableTone(secondary, panel, light)};
  --brand-primary-on-light: ${readableTone(primary, light, dark)};
  --brand-on-primary: ${darkestText};
}`;
  return readTextTemplate('style.css').replace('/* ORGANIZATION_THEME */', colors);
}

function validateSite(organization, files) {
  const html = files.get('index.html').toString('utf8');
  assert.equal([...html.matchAll(/data-scene="[0-5]"/g)].length, 6);
  assert.doesNotMatch(html, /\{\{\w+\}\}|class="direct-link"|kywa-safety\.onrender\.com/);
  for (const [, path] of html.matchAll(/(?:src|href)="([^"#][^"]*)"/g)) {
    assert(path === organization.renderUrl || files.has(path), `Unexpected link or missing asset ${path}`);
  }
  assert.equal(files.get('_redirects').toString('utf8').trim(), `/__render/ready ${organization.healthUrl} 200!`);

  let publicBytes = 0;
  for (const [path, bytes] of files) {
    publicBytes += bytes.length;
    if (/\.(html|css|json|mjs)$/.test(path)) {
      assert.doesNotMatch(bytes.toString('utf8'), /-----BEGIN (?:RSA )?PRIVATE KEY-----|AIza[\w-]{25,}|pbkdf2_sha256\$|gserviceaccount\.com/);
    }
  }
  assert(publicBytes <= 500_000, `Public files exceed 500 KB: ${publicBytes}`);
  return publicBytes;
}

export function generateSite(id) {
  const organization = readPartner(id);
  const files = new Map(commonFiles.map((name) => [
    name,
    name.endsWith('.png') ? readFileSync(resolve(template, name)) : Buffer.from(readTextTemplate(name)),
  ]));
  files.set('index.html', Buffer.from(renderHtml(organization)));
  files.set('style.css', Buffer.from(renderStyles(organization)));
  files.set('config.json', Buffer.from(`${JSON.stringify({ storySeconds })}\n`));
  files.set('_redirects', Buffer.from(`/__render/ready ${organization.healthUrl} 200!\n`));
  const publicBytes = validateSite(organization, files);
  return { organization, files, publicBytes };
}

function ensureOnlyPublicFiles(directory, files, prefix = '') {
  for (const item of readdirSync(directory, { withFileTypes: true })) {
    const name = prefix + item.name;
    if (item.isDirectory() && [...files.keys()].some((file) => file.startsWith(`${name}/`))) {
      ensureOnlyPublicFiles(resolve(directory, item.name), files, `${name}/`);
    } else {
      assert(item.isFile() && files.has(name), `Unexpected item in deploy directory: ${name}`);
    }
  }
}

function writeSite(id) {
  const { organization, files, publicBytes } = generateSite(id);
  const directory = resolve(root, 'dist', id);
  mkdirSync(directory, { recursive: true });
  ensureOnlyPublicFiles(directory, files);
  for (const [path, bytes] of files) {
    const destination = resolve(directory, path);
    mkdirSync(dirname(destination), { recursive: true });
    writeFileSync(destination, bytes);
  }
  const manifest = {
    organization: id,
    renderUrl: organization.renderUrl,
    storySeconds,
    publicBytes,
    files: [...files.keys()].sort().map((path) => ({
      path,
      bytes: files.get(path).length,
      sha256: createHash('sha256').update(files.get(path)).digest('hex'),
    })),
  };
  const manifestPath = resolve(root, 'dist', `${id}.manifest.json`);
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(JSON.stringify({ directory, manifest: manifestPath, files: files.size, publicBytes }, null, 2));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { values } = parseArgs({ options: { org: { type: 'string' } } });
  writeSite(values.org);
}
