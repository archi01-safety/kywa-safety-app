import test from 'node:test';
import assert from 'node:assert/strict';
import {downloadName} from '../app/download-name.ts';

test('uses the Korean server filename, not the browser date or institution',()=>{
  const name='우주_위험성평가_20261102.pdf';
  assert.equal(downloadName(`attachment; filename*=UTF-8''${encodeURIComponent(name)}`),name);
  assert.equal(downloadName('attachment; filename="KYWA_위험성평가_20261102.xlsx"'),'KYWA_위험성평가_20261102.xlsx');
});
test('rejects missing, malformed or unsafe filenames',()=>{
  for(const h of [null,'attachment',"attachment; filename*=UTF-8''%ZZ",'attachment; filename="../file.pdf"','attachment; filename="file.exe"']) assert.throws(()=>downloadName(h));
});
