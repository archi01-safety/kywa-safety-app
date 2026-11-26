import test from 'node:test';
import assert from 'node:assert/strict';
import { ResumeGate } from '../app/resume-gate.ts';

test('focus and viewport changes without an actual departure never refresh', () => {
  const gate = new ResumeGate();
  for (const now of [0, 1_000, 60_000, 3_600_000]) assert.equal(gate.resume(now), false);
});
test('short dialog, resize and application focus changes keep the current work', () => {
  const gate = new ResumeGate();
  gate.leave(100); gate.leave(150);
  assert.equal(gate.resume(200), false);
  gate.leave(1_000);
  assert.equal(gate.resume(30_999), false);
});
test('a return after thirty seconds refreshes once despite duplicate browser events', () => {
  const gate = new ResumeGate();
  gate.leave(1_000); gate.leave(2_000);
  assert.equal(gate.resume(31_000), true);
  assert.equal(gate.resume(31_001), false);
});
test('a real background return waits until the current write or analysis finishes', () => {
  const gate = new ResumeGate();
  gate.leave(0);
  assert.equal(gate.resume(40_000, true), false);
  assert.equal(gate.resume(45_000, true), false);
  assert.equal(gate.resume(46_000), true);
  assert.equal(gate.resume(46_001), false);
});
test('clock reversal cannot fabricate a long absence', () => {
  const gate = new ResumeGate(); gate.leave(100_000);
  assert.equal(gate.resume(1_000), false);
});
