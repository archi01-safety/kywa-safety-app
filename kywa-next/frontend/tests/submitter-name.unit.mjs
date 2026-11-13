import { test } from 'node:test';
import assert from 'node:assert/strict';
import { submissionName, composingNamePreview } from '../app/submitter-name.ts';

const cases = [
  ['홍', '홍'], ['김민', '김㉤'], ['홍길동', '홍㉠㉢'], ['남궁민', '남㉠㉤'],
  ['김하늘별', '김㉭㉡㉥'], ['홍까따빠싸짜', '홍ㄲㄸㅃㅆㅉ'],
  [' \t홍 길\n동　', '홍㉠㉢'], ['홍길동'.normalize('NFD'), '홍㉠㉢'],
  ['홍' + '가'.repeat(99), '홍' + '㉠'.repeat(99)],
];
cases.forEach(([raw, value], i) => test(`conversion case ${i+1}`, () => {
  assert.deepEqual(submissionName(raw, 'required'), {value, error:''});
}));
test('all nineteen initials are mapped in Hangul syllable order', () => {
  const syllables = Array.from({length:19}, (_, i) => String.fromCodePoint(0xac00 + i*588)).join('');
  assert.equal(submissionName('홍' + syllables, 'required').value, '홍㉠ㄲ㉡㉢ㄸ㉣㉤㉥ㅃ㉦ㅆ㉧㉨ㅉ㉩㉪㉫㉬㉭');
});
test('invalid inputs have no submission value and never appear in error messages', () => {
  for (const raw of ['홍A', '홍1', '홍!', '홍ㄱ', 'ㅎ', '홍😀', '홍㉠㉢', '홍\u200b길동', '홍'.repeat(101)]) {
    const result = submissionName(raw, 'required');
    assert.equal(result.value, ''); assert.ok(result.error); assert.ok(!result.error.includes(raw));
  }
});
test('institution modes', () => {
  assert.ok(submissionName(' \t', 'required').error);
  assert.deepEqual(submissionName(' \t', 'optional'), {value:'',error:''});
  assert.deepEqual(submissionName('ignored original', 'disabled'), {value:'',error:''});
  assert.ok(submissionName('Hong', 'optional').error);
});
test('composition preview uses completed syllables without unfinished jamo', () => {
  assert.equal(composingNamePreview('ㅎ'), '');
  assert.equal(composingNamePreview('홍ㄱ'), '홍');
  assert.equal(composingNamePreview('홍길ㄷ'), '홍㉠');
  assert.equal(composingNamePreview('홍길동'), '홍㉠㉢');
  assert.equal(composingNamePreview('홍길동'.normalize('NFD')), '홍㉠㉢');
});
