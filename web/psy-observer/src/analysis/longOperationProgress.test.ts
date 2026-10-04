import assert from 'node:assert/strict';
import test from 'node:test';
import { deriveUiState } from './analyzerJobProgress.ts';

test('long operation UI distinguishes heartbeat from useful progress', () => {
  const now = Date.parse('2026-10-04T22:00:00.000Z');
  const base = {
    state: 'RUNNING',
    worker_heartbeat_at: '2026-10-04T21:59:55.000Z',
    last_progress_at: '2026-10-04T21:59:50.000Z',
    current_operation: 'contrasts_and_selection',
    alive: true,
  };
  const useful = deriveUiState(base, now);
  assert.match(useful.banner, /WORKING — useful progress observed/);

  const longOp = deriveUiState({
    ...base,
    last_progress_at: '2026-10-04T21:59:30.000Z',
  }, now);
  assert.match(longOp.banner, /long operation, heartbeat alive/);

  const stalled = deriveUiState({
    ...base,
    last_progress_at: '2026-10-04T21:40:00.000Z',
  }, now);
  assert.match(stalled.banner, /NO USEFUL PROGRESS FOR/);

  const lost = deriveUiState({
    ...base,
    worker_heartbeat_at: '2026-10-04T21:59:00.000Z',
  }, now);
  assert.equal(lost.banner, 'WORKER HEARTBEAT LOST');

  const failed = deriveUiState({ state: 'FAILED', error_message: 'x' }, now);
  assert.equal(failed.banner, 'ANALYSIS: FAILED');
});
