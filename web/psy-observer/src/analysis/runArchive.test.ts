import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  analyzeObserverData,
  buildLifecycle,
  createAnalysisState,
  ingestAnalysisInput,
  buildRunAnalysis,
  hasSufficientObservation,
  isMeaningfulExtrema,
  analysisToRunRecord,
  configFingerprint,
  makeRunId,
  upsertRun,
  evictOldest,
  loadRunArchive,
  saveRunArchive,
  selectRunThumbnail,
  DEFAULT_MAX_ARCHIVED_RUNS,
} from './index.ts';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; },
    clear() { m.clear(); },
    getItem(k: string) { return m.has(k) ? m.get(k)! : null; },
    setItem(k: string, v: string) { m.set(k, String(v)); },
    removeItem(k: string) { m.delete(k); },
    key(i: number) { return [...m.keys()][i] ?? null; },
  } as Storage;
}

function frame(tick: number, status: string, seed = 143, gen = 1, experimental = false) {
  return {
    header: {
      tick, seed, runtime_generation: gen, status,
      runtime_model: 'TwoAgentRuntime', agent_count: 2,
      experimental_overrides: experimental ? { experimental_physical_signal: true } : {},
      agent_body_mapping: [
        { agent_id: 'agent_0', body_id: 'body-0', agent_seed: seed },
        { agent_id: 'agent_1', body_id: 'body-1', agent_seed: seed + 1 },
      ],
    },
    world: { width: 12, height: 12 },
    agents_observer: [
      { observer_id: 'agent_0', agent_seed: seed, action_counts: { WAIT: tick } },
      { observer_id: 'agent_1', agent_seed: seed + 1, action_counts: { WAIT: tick } },
    ],
  };
}

function timeline(n: number, contactFrom = 9999) {
  const out = [];
  for (let t = 1; t <= n; t++) {
    out.push({
      tick: t,
      contact: t >= contactFrom,
      bodies: [
        { agent_id: 'agent_0', x: t * 0.1, y: 1, action: t < 5 ? 'WAIT' : 'MOVE:E' },
        { agent_id: 'agent_1', x: 2, y: 1, action: 'WAIT' },
      ],
    });
  }
  return out;
}

describe('analysis lifecycle + run archive', () => {
  it('A. LIVE status while runtime running', () => {
    const a = analyzeObserverData({
      frame: frame(20, 'RUNNING'),
      timeline: timeline(20),
      events: [],
      mode: 'LIVE',
    });
    assert.equal(a.lifecycle.phase, 'LIVE');
    assert.equal(a.lifecycle.banner, 'ANALYSIS: LIVE');
    assert.ok(['LIVE', 'INCREMENTAL', 'PARTIAL'].includes(a.lifecycle.coverage));
  });

  it('B. PAUSED status correct', () => {
    const a = analyzeObserverData({
      frame: frame(20, 'PAUSED'),
      timeline: timeline(20),
      events: [],
      mode: 'LIVE',
    });
    assert.equal(a.lifecycle.phase, 'PAUSED');
    assert.equal(a.lifecycle.banner, 'ANALYSIS: PAUSED');
  });

  it('C. completed run becomes archived run card', () => {
    const a = analyzeObserverData({
      frame: frame(30, 'STOPPED'),
      timeline: timeline(30, 10),
      events: [],
      mode: 'FINAL',
    });
    assert.equal(a.lifecycle.phase, 'COMPLETE');
    const rec = analysisToRunRecord(a, {
      run_id: 'run-test-1',
      run_number: 1,
      started_at: '2026-01-01T00:00:00Z',
      finished_at: '2026-01-01T00:01:00Z',
      status: 'STOPPED',
      config_fingerprint: 'cfg_x',
    });
    assert.equal(rec.run_number, 1);
    assert.equal(rec.status, 'STOPPED');
    assert.equal(rec.agents.length, 2);
  });

  it('D/E. reset-style new generation creates distinct run records; same seed OK', () => {
    let store = loadRunArchive(memStorage());
    const a1 = analyzeObserverData({ frame: frame(10, 'STOPPED', 143, 1), timeline: timeline(10), events: [], mode: 'FINAL' });
    const r1 = analysisToRunRecord(a1, {
      run_id: makeRunId(1, 143, 't1', 1), run_number: 1, started_at: 't1', finished_at: 't2', status: 'STOPPED',
      config_fingerprint: configFingerprint({
        seed: 143, runtime: 'TwoAgentRuntime', map_w: 12, map_h: 12, boundary: 'WRAP_PERIODIC',
        agent_count: 2, cognition_enabled: true, experimental_overrides: {}, active_mechanisms: [],
      }),
    });
    store = upsertRun(store, r1);
    store.next_run_number = 2;
    const a2 = analyzeObserverData({ frame: frame(8, 'STOPPED', 143, 2), timeline: timeline(8), events: [], mode: 'FINAL' });
    const r2 = analysisToRunRecord(a2, {
      run_id: makeRunId(2, 143, 't3', 2), run_number: 2, started_at: 't3', finished_at: 't4', status: 'STOPPED',
      config_fingerprint: r1.config_fingerprint,
    });
    store = upsertRun(store, r2);
    assert.equal(store.runs.length, 2);
    assert.notEqual(store.runs[0].run_id, store.runs[1].run_id);
    assert.equal(store.runs[0].base_seed, 143);
    assert.equal(store.runs[1].base_seed, 143);
  });

  it('F. canonical vs experimental fingerprints differ', () => {
    const can = configFingerprint({
      seed: 143, runtime: 'TwoAgentRuntime', map_w: 12, map_h: 12, boundary: 'WRAP_PERIODIC',
      agent_count: 2, cognition_enabled: true, experimental_overrides: {}, active_mechanisms: [],
    });
    const exp = configFingerprint({
      seed: 143, runtime: 'TwoAgentRuntime', map_w: 12, map_h: 12, boundary: 'WRAP_PERIODIC',
      agent_count: 2, cognition_enabled: true, experimental_overrides: { experimental_physical_signal: true }, active_mechanisms: [],
    });
    assert.notEqual(can, exp);
  });

  it('G/H. OPEN RUN identity isolation (detail uses archived analysis only)', () => {
    const a = analyzeObserverData({ frame: frame(15, 'PAUSED', 143, 5), timeline: timeline(15, 5), events: [], mode: 'LIVE' });
    const rec = analysisToRunRecord(a, {
      run_id: 'run-open', run_number: 9, started_at: 't', status: 'PAUSED', config_fingerprint: 'cfg',
    });
    assert.equal(rec.analysis.identity.generation, 5);
    assert.equal(rec.analysis.identity.seed, 143);
    assert.ok(rec.analysis.overview.every((c) => c.tick_start <= 15));
  });

  it('I/J. agent identities remain correct inside archived run', () => {
    const a = analyzeObserverData({ frame: frame(12, 'PAUSED'), timeline: timeline(12), events: [], mode: 'LIVE' });
    const rec = analysisToRunRecord(a, {
      run_id: 'r', run_number: 1, started_at: 't', status: 'PAUSED', config_fingerprint: 'c',
    });
    assert.deepEqual(rec.agents.map((x) => x.agent_id), ['agent_0', 'agent_1']);
    assert.equal(rec.agents[0].body_id, 'body-0');
    assert.equal(rec.agents[1].seed, 144);
  });

  it('K. bounded run eviction works', () => {
    let store = loadRunArchive(memStorage());
    store.max_runs = 3;
    for (let i = 1; i <= 5; i++) {
      const a = analyzeObserverData({ frame: frame(5, 'STOPPED', 10 + i, i), timeline: timeline(5), events: [], mode: 'FINAL' });
      const rec = analysisToRunRecord(a, {
        run_id: `run-${i}`, run_number: i, started_at: `t${i}`, finished_at: `f${i}`, status: 'STOPPED', config_fingerprint: `c${i}`,
      });
      store = upsertRun({ ...store, next_run_number: i + 1 }, rec);
    }
    assert.ok(store.runs.length <= 3);
    store = evictOldest(store, 2);
    assert.equal(store.runs.length, 2);
  });

  it('L/M. missing / partial coverage explicit', () => {
    const empty = analyzeObserverData({
      frame: frame(0, 'PAUSED'),
      timeline: [],
      events: [],
    });
    assert.equal(empty.lifecycle.phase, 'INSUFFICIENT_DATA');
    assert.equal(empty.coverage.level, 'INSUFFICIENT');

    const state = createAnalysisState();
    // Simulate long span with few unique ticks retained → PARTIAL
    state.start_tick = 0;
    state.end_tick = 5000;
    state.timeline_samples = 10;
    for (let t = 4990; t < 5000; t++) state.unique_simulation_ticks.add(t);
    state.status = 'STOPPED';
    state.event_samples = 5;
    const built = buildRunAnalysis(state, 'FINAL');
    assert.equal(built.coverage.level, 'PARTIAL');
    assert.match(built.coverage.reason, /earlier evidence/i);
  });

  it('N. tick-0 empty state does not create misleading extrema', () => {
    const state = createAnalysisState();
    state.start_tick = 0;
    state.end_tick = 0;
    state.extrema.max_velocity = { tick: 0, value: 0 };
    state.extrema.min_resource_A = { tick: 0, value: 0 };
    assert.equal(hasSufficientObservation(state), false);
    assert.equal(isMeaningfulExtrema('max_velocity', { tick: 0, value: 0 }, state), false);
    const a = analyzeObserverData({ frame: frame(0, 'PAUSED'), timeline: [], events: [] });
    assert.ok(!a.important_events.some((e) => e.kind.includes('MAX_VELOCITY')));
  });

  it('O. key-frame thumbnail corresponds to same run/tick', () => {
    const a = analyzeObserverData({
      frame: frame(25, 'PAUSED'),
      timeline: timeline(25, 8),
      events: [],
      mode: 'LIVE',
    });
    const thumb = selectRunThumbnail(a);
    if (thumb) {
      assert.ok(a.keyframes.some((k) => k.tick === thumb.tick));
      assert.ok(thumb.tick >= a.identity.start_tick && thumb.tick <= a.identity.end_tick);
    }
  });

  it('P. scientific runtime not modified (analysis is pure data transform)', () => {
    const tl = timeline(6);
    const fr = frame(6, 'RUNNING');
    const before = JSON.stringify({ fr, tl });
    analyzeObserverData({ frame: fr, timeline: tl, events: [] });
    assert.equal(JSON.stringify({ fr, tl }), before);
  });

  it('archive persists across load/save', () => {
    const storage = memStorage();
    let store = loadRunArchive(storage);
    const a = analyzeObserverData({ frame: frame(10, 'STOPPED'), timeline: timeline(10), events: [], mode: 'FINAL' });
    const rec = analysisToRunRecord(a, {
      run_id: 'persist-1', run_number: 1, started_at: 't', finished_at: 'f', status: 'COMPLETE', config_fingerprint: 'c',
    });
    store = upsertRun(store, rec);
    saveRunArchive(store, storage);
    const loaded = loadRunArchive(storage);
    assert.equal(loaded.runs.length, 1);
    assert.equal(loaded.runs[0].run_id, 'persist-1');
    assert.equal(DEFAULT_MAX_ARCHIVED_RUNS, 50);
  });
});
