/**
 * Bounded observer-side run archive (localStorage). Not scientific snapshots.
 */
import type { KeyFrameRef, ObserverRunRecord, RunAnalysis } from './types.ts';

export const RUN_ARCHIVE_KEY = 'psy-observer-run-archive-v1';
export const DEFAULT_MAX_ARCHIVED_RUNS = 50;

export type RunArchiveStore = {
  version: 1;
  max_runs: number;
  next_run_number: number;
  runs: ObserverRunRecord[];
  current_run_id: string | null;
};

function emptyStore(max = DEFAULT_MAX_ARCHIVED_RUNS): RunArchiveStore {
  return { version: 1, max_runs: max, next_run_number: 1, runs: [], current_run_id: null };
}

export function loadRunArchive(storage?: Storage | null): RunArchiveStore {
  try {
    const raw = (storage ?? (typeof localStorage !== 'undefined' ? localStorage : null))?.getItem(RUN_ARCHIVE_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.runs)) return emptyStore();
    return {
      version: 1,
      max_runs: Number(parsed.max_runs) || DEFAULT_MAX_ARCHIVED_RUNS,
      next_run_number: Number(parsed.next_run_number) || parsed.runs.length + 1,
      runs: parsed.runs,
      current_run_id: parsed.current_run_id ?? null,
    };
  } catch {
    return emptyStore();
  }
}

export function saveRunArchive(store: RunArchiveStore, storage?: Storage | null) {
  const s = storage ?? (typeof localStorage !== 'undefined' ? localStorage : null);
  if (!s) return;
  try {
    s.setItem(RUN_ARCHIVE_KEY, JSON.stringify(store));
  } catch {
    /* quota — drop oldest and retry once */
    store.runs = store.runs.slice(0, Math.max(1, store.max_runs - 5));
    try { s.setItem(RUN_ARCHIVE_KEY, JSON.stringify(store)); } catch { /* ignore */ }
  }
}

export function configFingerprint(parts: {
  seed: number | null;
  runtime: string;
  map_w: number | null;
  map_h: number | null;
  boundary: string;
  agent_count: number;
  cognition_enabled: any;
  experimental_overrides: Record<string, any>;
  active_mechanisms: string[];
}): string {
  const payload = JSON.stringify({
    seed: parts.seed,
    runtime: parts.runtime,
    map: [parts.map_w, parts.map_h, parts.boundary],
    agents: parts.agent_count,
    cognition: parts.cognition_enabled,
    experimental: parts.experimental_overrides || {},
    mechanisms: [...(parts.active_mechanisms || [])].sort(),
  });
  // FNV-1a 32-bit
  let h = 0x811c9dc5;
  for (let i = 0; i < payload.length; i++) {
    h ^= payload.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return `cfg_${(h >>> 0).toString(16)}`;
}

export function makeRunId(generation: number | null, seed: number | null, startedAt: string, n: number): string {
  return `run-g${generation ?? 'x'}-s${seed ?? 'x'}-n${n}-${startedAt.replace(/[:.]/g, '').slice(0, 20)}`;
}

export function selectRunThumbnail(analysis: RunAnalysis): KeyFrameRef | null {
  const kfs = analysis.keyframes || [];
  if (!kfs.length) return null;
  const contact = kfs.find((k) => /contact/i.test(k.reason) || k.contact);
  if (contact) return contact;
  const firstImp = analysis.important_events.find((e) => e.category === 'FIRST');
  if (firstImp) {
    const match = kfs.find((k) => k.tick === firstImp.tick);
    if (match) return match;
  }
  const ranked = analysis.important_events.find((e) => e.category === 'TRANSITION')
    || analysis.important_events[0];
  if (ranked) {
    const match = kfs.find((k) => k.tick === ranked.tick);
    if (match) return match;
  }
  return kfs[kfs.length - 1] || kfs[0] || null;
}

export function analysisToRunRecord(
  analysis: RunAnalysis,
  opts: {
    run_id: string;
    run_number: number;
    started_at: string;
    finished_at?: string | null;
    status: ObserverRunRecord['status'];
    config_fingerprint: string;
  },
): ObserverRunRecord {
  const id = analysis.identity;
  const experimental = Object.keys(id.experimental_overrides || {}).length > 0
    || /two.?agent/i.test(id.runtime);
  return {
    run_id: opts.run_id,
    run_number: opts.run_number,
    runtime_generation: id.generation,
    runtime_type: id.runtime,
    base_seed: id.seed,
    started_at: opts.started_at,
    finished_at: opts.finished_at ?? null,
    initial_tick: id.start_tick,
    final_tick: id.end_tick,
    map: { width: id.map_width, height: id.map_height, boundary: id.boundary },
    agents: id.agents.map((a) => ({ ...a })),
    config_fingerprint: opts.config_fingerprint,
    experimental,
    status: opts.status,
    summary: {
      first_contact_tick: analysis.interactions.first_contact_tick,
      signals_observed: analysis.agents.reduce(
        (s, a) => s + a.signals.emissions_A + a.signals.emissions_B + a.signals.receptions_A + a.signals.receptions_B,
        0,
      ),
      cross_agent_contributions: analysis.interactions.cross_agent_contributions,
      important_events: analysis.important_events.length,
      anomalies: analysis.important_events.filter((e) => e.category === 'ANOMALY').length,
      contact_ticks: analysis.interactions.contact_ticks,
    },
    thumbnail: selectRunThumbnail(analysis),
    analysis,
  };
}

export function upsertRun(store: RunArchiveStore, record: ObserverRunRecord): RunArchiveStore {
  const idx = store.runs.findIndex((r) => r.run_id === record.run_id);
  const runs = [...store.runs];
  if (idx >= 0) runs[idx] = record;
  else runs.unshift(record);
  // newest first; evict oldest when over cap
  runs.sort((a, b) => b.run_number - a.run_number);
  while (runs.length > store.max_runs) runs.pop();
  return { ...store, runs, current_run_id: record.run_id };
}

export function evictOldest(store: RunArchiveStore, max?: number): RunArchiveStore {
  const cap = max ?? store.max_runs;
  const runs = [...store.runs].sort((a, b) => b.run_number - a.run_number).slice(0, cap);
  return { ...store, max_runs: cap, runs };
}

export function statusFromRuntime(status: string, mode: string): ObserverRunRecord['status'] {
  const s = String(status || '').toUpperCase();
  if (s === 'STOPPED' || s === 'COMPLETE') return s === 'COMPLETE' ? 'COMPLETE' : 'STOPPED';
  if (s === 'PAUSED' || mode === 'FINAL') return 'PAUSED';
  if (s === 'RUNNING') return 'RUNNING';
  return 'PAUSED';
}
