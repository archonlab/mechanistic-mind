import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  contributionFill,
  falseColorRgb,
  gridIndex,
  sampleMatchesLink,
  type FpvSample,
} from './tiktaalikFpvModel.ts';

const accepted: FpvSample = {
  fwd: 1,
  left: 0,
  status: 'accepted',
  sector: 'FORWARD',
  sector_index: 1,
  dist_f: 1,
  illumination: 1,
  final: 0.5,
  c0: 1,
  c1: 0,
  c2: 0,
};

test('false-color RICH maps C0/C1/C2 to display RGB only', () => {
  assert.equal(falseColorRgb(accepted, 'RICH'), 'rgb(255,0,0)');
});

test('LOW is monochrome from C0', () => {
  assert.equal(falseColorRgb({ ...accepted, c1: 1, c2: 1 }, 'LOW'), 'rgb(255,217,140)');
});

test('OFF uses intensity not invented channels', () => {
  const s = { ...accepted, surface_channels: 'ABSENT', composed: 0.2, c0: 1, c1: 1, c2: 1 };
  assert.equal(falseColorRgb(s, 'OFF'), 'rgb(44,44,44)');
});

test('agent-centered grid: forward is up, left is left', () => {
  const r3 = gridIndex(3, 0, 3);
  assert.equal(r3.row, 0);
  assert.equal(r3.col, 3);
  const left = gridIndex(0, 3, 3);
  assert.equal(left.row, 3);
  assert.equal(left.col, 0);
});

test('link matches exo sector names used in SENSOR SPACE', () => {
  assert.equal(sampleMatchesLink(accepted, { sector: 'FORWARD', channel: 'c1' }), true);
  assert.equal(sampleMatchesLink(accepted, { sector: 'LEFT', channel: 'exo' }), false);
});

test('contribution fill is sector-tinted by final, not renormalized to 1', () => {
  const weak = contributionFill({ ...accepted, final: 0.1 });
  const strong = contributionFill({ ...accepted, final: 0.9 });
  assert.notEqual(weak, strong);
});

test('non-LEGACY contribution fill uses A-bin index, occluded stays red', () => {
  const a0 = contributionFill({ ...accepted, spatial_sector_index: 0, sector: 'FORWARD', final: 0.5 }, 'ANGULAR');
  const a4 = contributionFill({ ...accepted, spatial_sector_index: 4, sector: 'FORWARD', final: 0.5 }, 'OCCLUSION');
  assert.notEqual(a0, a4);
  const occ = contributionFill({ ...accepted, status: 'occluded', spatial_sector_index: 2, final: 0.5 }, 'OCCLUSION');
  assert.match(occ, /248,113,113/);
});

test('LEGACY contribution fill ignores spatial_sector_index', () => {
  const withSpat = contributionFill({ ...accepted, spatial_sector_index: 4, sector: 'FORWARD', final: 0.5 }, 'LEGACY');
  const plain = contributionFill({ ...accepted, final: 0.5 });
  assert.equal(withSpat, plain);
});
