import { ReadinessController } from './controller.mjs';

const $ = (id) => document.getElementById(id);
const scenes = [...document.querySelectorAll('.scene')];
const titles = ['작은 발견과 안전', '현장 사진과 설명', '분석 결과 검토', '개선조치와 재평가', '결과보고서', '개인정보 확인'];
const weights = [.10, .20, .20, .20, .20, .10];
const query = new URLSearchParams(location.search);
const preview = query.get('preview') === '1';
const renderUrl = $('entry-target').href;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let duration = 60000, scene = 0, elapsed = 0, lastFrame = null, running = false, paused = reducedMotion.matches;
let animationFrame = null, entrances = [];
const sceneWords = ['SAFETY', 'CAPTURE', 'REVIEW', 'ACTION', 'REPORT', 'TOGETHER'];

function finishEntrances() {
  for (const animation of entrances) { animation.finish(); animation.cancel(); }
  entrances = [];
}
function enterScene() {
  finishEntrances();
  if (reducedMotion.matches || paused || document.hidden) return;
  const element = scenes[scene], direction = scene % 2 ? 1 : -1;
  const play = (target, keyframes, delay = 0, length = 650) => {
    if (!target) return;
    entrances.push(target.animate(keyframes, { duration: length, delay, fill: 'backwards', easing: 'cubic-bezier(.16,.85,.24,1)' }));
  };
  [...element.querySelector('.copy').children].forEach((child, index) => {
    play(child, [{ opacity: 0, translate: `${direction * 38}px 12px` }, { opacity: 1, translate: '0 0' }], index * 85, 580);
  });
  play(element.querySelector('.art'), [{ opacity: 0, translate: `${-direction * 75}px 0`, scale: .90 }, { opacity: 1, translate: '0 0', scale: 1 }], 90, 800);
  const details = [
    ['.discovery', '.outcome'], ['.photo-front', '.input-note'], ['.focus-box', '.assessment-card'],
    ['.action-record', '.reevaluate'], ['.sheet-excel', '.sheet-main', '.report-badge'], ['.privacy-photo', '.name-card', '.ready-note'],
  ][scene];
  details.forEach((selector, index) => play(element.querySelector(selector),
    [{ opacity: 0, translate: `${(index % 2 ? 1 : -1) * 28}px 24px`, scale: .86 }, { opacity: 1, translate: '0 0', scale: 1 }], 240 + index * 170, 750));
}

const dots = titles.map((title, index) => {
  const button = document.createElement('button'); button.type = 'button';
  button.setAttribute('aria-label', `${index + 1}. ${title}`);
  button.addEventListener('click', () => selectScene(index, true));
  $('scene-nav').append(button); return button;
});
function sceneStart(index) { return weights.slice(0, index).reduce((a, b) => a + b, 0) * duration; }
function selectScene(index, manual = false) {
  scene = Math.min(scenes.length - 1, Math.max(0, index));
  $('story').classList.toggle('is-reversed', scene % 2 === 1);
  $('story').dataset.scene = String(scene);
  if ($('scene-word')) $('scene-word').textContent = sceneWords[scene];
  scenes.forEach((element, i) => {
    element.classList.toggle('is-active', i === scene); element.inert = i !== scene;
    element.setAttribute('aria-hidden', String(i !== scene));
    dots[i].setAttribute('aria-current', i === scene ? 'step' : 'false');
  });
  $('scene-count').textContent = `${String(scene + 1).padStart(2, '0')} / 06`;
  $('previous').disabled = scene === 0; $('next').disabled = scene === scenes.length - 1;
  if (manual) { elapsed = sceneStart(scene); lastFrame = null; }
  enterScene();
}
function tick(time) {
  animationFrame = null;
  if (!running || paused || document.hidden) { lastFrame = null; return; }
  if (lastFrame !== null) elapsed += Math.min(time - lastFrame, 250);
  lastFrame = time;
  let next = 0;
  while (next < scenes.length - 1 && elapsed >= sceneStart(next + 1)) next += 1;
  if (next !== scene) selectScene(next);
  if (elapsed < duration) animationFrame = requestAnimationFrame(tick);
}
function schedule() { if (!animationFrame && running && !paused && !document.hidden) animationFrame = requestAnimationFrame(tick); }
function updatePause() {
  document.body.classList.toggle('is-paused', paused || document.hidden);
  $('pause').setAttribute('aria-pressed', String(paused));
  $('pause').setAttribute('aria-label', paused ? '소개 재생' : '소개 일시정지');
  $('pause').textContent = paused ? '▶' : 'Ⅱ';
  if (paused || document.hidden) { finishEntrances(); if (animationFrame) cancelAnimationFrame(animationFrame); animationFrame = null; lastFrame = null; }
  else schedule();
}
function showStory() {
  $('checking').hidden = true; $('story').hidden = false; $('story-controls').hidden = false;
  if (!running) { running = true; selectScene(scene); }
  updatePause();
}
$('pause').addEventListener('click', () => { paused = !paused; updatePause(); });
$('previous').addEventListener('click', () => { selectScene(scene - 1, true); schedule(); });
$('next').addEventListener('click', () => { selectScene(scene + 1, true); schedule(); });
reducedMotion.addEventListener('change', () => { paused = reducedMotion.matches; updatePause(); });

const controller = preview ? null : new ReadinessController({
  onState(state) {
    document.documentElement.dataset.state = state;
    $('error-box').hidden = state !== 'delayed';
    if (state === 'checking') $('connection-label').textContent = '연결 확인 중';
    if (state === 'waiting') { $('connection-label').textContent = '서버 구동·연결 확인 중'; showStory(); }
    if (state === 'ready') $('connection-label').textContent = '연결 완료 · 시스템으로 이동합니다';
    if (state === 'delayed') { $('connection-label').textContent = '연결이 지연되고 있습니다'; showStory(); }
  },
  onReady() { location.replace(renderUrl); },
});
$('retry').addEventListener('click', () => { controller?.start(); if (document.hidden) controller?.suspend(); });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) controller?.suspend(); else controller?.resume();
  updatePause();
});
window.addEventListener('pagehide', () => controller?.dispose());
// A back/forward cache restoration must not reuse a readiness response from an earlier visit.
window.addEventListener('pageshow', (event) => { if (event.persisted && controller) { controller.start(); if (document.hidden) controller.suspend(); } });

// Preview is entirely static: it never probes or wakes the operating Render server.
if (preview) {
  document.documentElement.dataset.state = 'preview'; $('connection-label').textContent = '소개 화면 미리보기';
  const requested = Number(query.get('scene'));
  if (Number.isInteger(requested) && requested >= 1 && requested <= 6) { scene = requested - 1; elapsed = sceneStart(scene); paused = true; }
  showStory();
} else { controller.start(); if (document.hidden) controller.suspend(); }

// Timing is the only public configuration. Connection checks never wait for this file.
fetch('./config.json', { cache: 'no-store', credentials: 'omit' }).then((response) => response.ok ? response.json() : null).then((config) => {
  if (Number.isFinite(config?.storySeconds) && config.storySeconds >= 6 && config.storySeconds <= 118) {
    const ratio = elapsed / duration; duration = config.storySeconds * 1000; elapsed = ratio * duration;
  }
}).catch(() => {});
