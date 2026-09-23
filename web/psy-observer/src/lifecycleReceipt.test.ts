import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { lifecycleErrorCode, mergeMechanismWarmState } from './lifecycleReceipt.ts';

describe('lifecycleReceipt', () => {
  it('preserves SAVE_FAILED from structured error', () => {
    assert.equal(lifecycleErrorCode({
      operation: 'STOP',
      accepted: false,
      error: { code: 'SAVE_FAILED', message: 'integrity', recoverable: true },
    }), 'SAVE_FAILED');
  });
  it('maps generic rejected STOP to STOP_REJECTED', () => {
    assert.equal(lifecycleErrorCode({
      operation: 'STOP',
      accepted: false,
      reason: 'not allowed now',
    }), 'STOP_REJECTED');
  });
  it('maps NetworkError STOP catch to HTTP_FAILED not SAVE_FAILED', () => {
    assert.equal(lifecycleErrorCode({
      operation: 'STOP',
      accepted: false,
      reason: 'TypeError: NetworkError when attempting to fetch resource.',
      error: { code: 'HTTP_FAILED', message: 'TypeError: NetworkError when attempting to fetch resource.' },
    }), 'HTTP_FAILED');
  });
  it('does not treat accepted STOP as failure', () => {
    assert.equal(lifecycleErrorCode({ operation: 'STOP', accepted: true }), null);
  });
});

describe('mergeMechanismWarmState', () => {
  it('merges enabled flags onto catalog rows', () => {
    const prev = [{ id: 'a', label: 'A', enabled: true, ablatable: true }];
    const next = mergeMechanismWarmState(prev, {
      catalog_included: false,
      mechanisms: [{ id: 'a', enabled: false, ablatable: true }],
    });
    assert.equal(next[0].label, 'A');
    assert.equal(next[0].enabled, false);
  });
  it('replaces when full catalog arrives', () => {
    const prev = [{ id: 'a', label: 'A', enabled: true }];
    const next = mergeMechanismWarmState(prev, {
      catalog_included: true,
      mechanisms: [{ id: 'a', label: 'Alpha', enabled: false, description: 'x' }],
    });
    assert.equal(next[0].label, 'Alpha');
  });
});
