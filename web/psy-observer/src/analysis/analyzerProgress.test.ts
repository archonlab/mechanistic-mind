import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  deriveUiState,
  formatLogLine,
  jobRestoreAllowed,
  loadActiveJobId,
  saveActiveJobId,
} from './analyzerJobProgress.ts';

const root = path.dirname(fileURLToPath(import.meta.url));

describe('analyzer progress UI contract', () => {
  it('exposes accessible progressbar, compact log, and cancel wiring', () => {
    const ar = fs.readFileSync(path.join(root, '../components/AnalyzeResultsPanel.tsx'), 'utf8');
    assert.ok(ar.includes('data-testid="analyzer-progress"'));
    assert.ok(ar.includes('data-testid="analyzer-progress-bar"') || ar.includes('analyzer-progress-bar-indeterminate'));
    assert.ok(ar.includes('role="progressbar"'));
    assert.ok(ar.includes('aria-valuemin'));
    assert.ok(ar.includes('aria-valuemax'));
    assert.ok(ar.includes('analysisProgressDetail'));
    assert.ok(ar.includes('control_availability'));
    assert.ok(ar.includes('data-testid="analyzer-compact-log"'));
    assert.ok(ar.includes('data-testid="analyzer-log-toggle"'));
    assert.ok(ar.includes('data-testid="analyzer-cancel"'));
    assert.ok(ar.includes('data-testid="analyzer-heartbeat"'));
    assert.ok(ar.includes('data-testid="analyzer-snapshot-bound"'));
    assert.ok(ar.includes('Analyzing frozen snapshot through tick'));
  });

  it('App polls structured progress, blocks duplicate analyze, reconnects job id', () => {
    const app = fs.readFileSync(path.join(root, '../App.tsx'), 'utf8');
    assert.ok(app.includes('setAnalysisProgressDetail'));
    assert.ok(app.includes('if (analyzing) return'));
    assert.ok(app.includes('phase_index'));
    assert.ok(app.includes('completed_units'));
    assert.ok(app.includes('jobRestoreAllowed'));
    assert.ok(app.includes('INTERRUPTED_BY_APPLICATION_EXIT'));
    assert.ok(app.includes('INTERRUPTED_USER_MESSAGE'));
    assert.ok(app.includes('listAnalysisJobs'));
    assert.ok(app.includes('cancelAnalysisJob'));
    assert.ok(app.includes('existing'));
    assert.ok(app.includes('worker_heartbeat_at'));
    assert.ok(app.includes('recent_log'));
    // Analyzer path must not call simulation mutate endpoints.
    const analyzeSlice = app.slice(app.indexOf('async function pollAnalysisJob'), app.indexOf('function handleAnalysisSourceChange'));
    assert.ok(!analyzeSlice.includes('postControl('));
    assert.ok(!analyzeSlice.includes('/api/control'));
    assert.ok(!analyzeSlice.includes('applyExperiment('));
  });

  it('deriveUiState distinguishes heartbeat vs progress wording', () => {
    const now = Date.parse('2026-10-03T20:00:20Z');
    const working = deriveUiState({
      state: 'RUNNING',
      worker_heartbeat_at: '2026-10-03T20:00:18Z',
      last_progress_at: '2026-10-03T20:00:00Z',
      alive: true,
    }, now);
    assert.equal(working.banner, 'ANALYSIS: WORKING');
    assert.ok(working.healthNote.includes('Worker responsive') || working.healthNote.includes('Heartbeat'));

    const noHb = deriveUiState({
      state: 'RUNNING',
      worker_heartbeat_at: '2026-10-03T19:59:00Z',
      last_progress_at: '2026-10-03T19:59:00Z',
      alive: true,
    }, now);
    assert.ok(noHb.banner.includes('HEARTBEAT') || noHb.healthNote.includes('No recent worker heartbeat'));

    assert.equal(deriveUiState({ state: 'COMPLETED', terminal: true }, now).banner, 'ANALYSIS: COMPLETED');
    assert.equal(deriveUiState({ state: 'FAILED', error_message: 'boom' }, now).banner, 'ANALYSIS: FAILED');
    assert.equal(formatLogLine({ ts: '2026-10-03T22:26:41Z', message: 'Snapshot frozen' }), '22:26:41  Snapshot frozen');
  });

  it('active job id helpers round-trip when localStorage exists', () => {
    const store = new Map<string, string>();
    (globalThis as any).localStorage = {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => { store.set(k, String(v)); },
      removeItem: (k: string) => { store.delete(k); },
    };
    saveActiveJobId('job-abc');
    assert.equal(loadActiveJobId(), 'job-abc');
    saveActiveJobId(null);
    assert.equal(loadActiveJobId(), null);
  });

  it('does not restore a localStorage job across instance or interrupted state', () => {
    const health = { instance_id: 'live', package_identity: '0.2.0:aaaa' };
    assert.equal(jobRestoreAllowed({
      job_id: 'ghost',
      state: 'CANCEL_REQUESTED',
      owner_instance_id: 'dead',
      owner_package_identity: '0.2.0:bbbb',
    } as any, health), false);
    assert.equal(jobRestoreAllowed({
      job_id: 'ghost',
      state: 'INTERRUPTED_BY_APPLICATION_EXIT',
      terminal: true,
      owner_instance_id: 'live',
      owner_package_identity: '0.2.0:aaaa',
    } as any, health), false);
    assert.equal(jobRestoreAllowed({
      job_id: 'ok',
      state: 'RUNNING',
      owner_instance_id: 'live',
      owner_package_identity: '0.2.0:aaaa',
    } as any, health), true);
    assert.equal(deriveUiState({ state: 'INTERRUPTED_BY_APPLICATION_EXIT', terminal: true }).healthNote,
      'Previous analysis was interrupted when MM Observer closed.');
  });
});
