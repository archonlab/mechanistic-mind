import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fmtDelta, fmtRaw, hasFakeDepth } from './tiktaalikEyeModel.ts';

test('absent vs zero', () => {
  assert.equal(fmtRaw({ present: false, raw: null, saturated: false, pe_bin: null, delta: null }), 'ABSENT');
  assert.equal(fmtRaw({ present: true, raw: 0, saturated: false, pe_bin: { index: 0, bins: 5, label: '0/5' }, delta: 0 }), '0.000');
});

test('delta format', () => {
  assert.equal(fmtDelta({ present: true, raw: 0.3, saturated: false, pe_bin: null, delta: 0.093 }), '+0.093');
});

test('eye payload must not invent depth fields', () => {
  assert.equal(hasFakeDepth({ agents: { agent_0: { accessible: { exo: {} } } } }), false);
  assert.equal(hasFakeDepth({ depth: 3 }), true);
});
