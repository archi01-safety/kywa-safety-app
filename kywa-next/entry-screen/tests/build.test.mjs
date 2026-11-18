import assert from 'node:assert/strict';
import test from 'node:test';
import { contrast, generateSite, partnerIds } from '../tools/build.mjs';

test('FoWI uses the operating institution and KYWA partnership in the static page', () => {
  const { files } = generateSite('fowi');
  const html = files.get('index.html').toString();
  assert.match(html, /<strong>한국산림복지진흥원<\/strong>/);
  assert.match(html, /<span class="supporting-institution">한국청소년활동진흥원<\/span>/);
  assert.match(html, /FoWI · 결과보고서/);
  assert.match(html, /© 2026 한국산림복지진흥원 \(Powered by KYWA\)/);
  assert.match(html, /성명 입력란은 초성으로 변환/);
  assert.doesNotMatch(html, /<footer[^>]*>[^\n]*<a\s|assets\/kywa-logo\.png/);
});

test('every supported profile has one exact health route and matching app destination', () => {
  for (const id of partnerIds) {
    const { organization, files } = generateSite(id);
    const origin = `https://${id}-safety.onrender.com`;
    assert.equal(organization.renderUrl, `${origin}/#inspect`);
    assert.equal(files.get('_redirects').toString(), `/__render/ready ${origin}/healthz 200!\n`);
    const html = files.get('index.html').toString();
    const links = [...html.matchAll(/href="(https:[^"]+)"/g)].map((match) => match[1]);
    assert.deepEqual(links, Array(3).fill(organization.renderUrl));
    assert.match(html, /id="entry-target" href="https:/);
  }
});

test('AYF privacy example applies its disabled name field', () => {
  const html = generateSite('ayf').files.get('index.html').toString();
  assert.match(html, /제출 전 얼굴이나 민감정보가 남았는지 확인/);
  assert.doesNotMatch(html, /초성|성명 입력란|홍길동|부서/);
});

test('the original brand colors and readable text colors are emitted for each partner', () => {
  for (const id of partnerIds) {
    const { organization, files } = generateSite(id);
    const css = files.get('style.css').toString();
    const variables = new Map([...css.matchAll(/--brand-([\w-]+):\s*(#[0-9a-f]{6});/gi)]
      .map(([, name, value]) => [name, value]));
    const find = (role) => variables.get(role);
    assert.equal(find('primary'), organization.primary);
    assert.equal(find('secondary'), organization.secondary);
    assert(contrast(find('primary-text'), '#2d3949') >= 4.5);
    assert(contrast(find('secondary-text'), '#2d3949') >= 4.5);
    assert(contrast(find('primary-on-light'), '#ffffff') >= 4.5);
    assert(contrast(find('on-primary'), organization.primary) >= 4.5);
  }
});

test('builds require a supported partner and never fall back to KYWA', () => {
  for (const invalid of [undefined, 'kywa', 'example', '../fowi', 'FoWI']) {
    assert.throws(() => generateSite(invalid), /Select a supported partner/);
  }
});
