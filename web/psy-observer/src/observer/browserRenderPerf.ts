/** P5 browser render performance telemetry — researcher display only.
 * Schema: OBSERVER_BROWSER_RENDER_PERFORMANCE_V1
 * Default OFF. Enable: localStorage PSY_OBSERVER_BROWSER_PERF=1 or ?browser_perf=1
 * Never mutates simulation / subscriptions / polling.
 */
export const SCHEMA = 'OBSERVER_BROWSER_RENDER_PERFORMANCE_V1';
export const CAPABILITY = 'browser_upload_render_profiling_and_optimization';
export const PROFILE = 'MAP_VOLUME_SURFACE_BROWSER_PIPELINE_P5_V1';
export const AUTHORITY = 'RESEARCHER_DISPLAY_PERFORMANCE_TELEMETRY_NO_PHYSICAL_EFFECT';

type Sample = { name: string; ms: number; t: number; meta?: Record<string, unknown> };

const MAX_SAMPLES = 400;
const samples: Sample[] = [];
let enabledCache: boolean | null = null;

function resolveEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const q = new URLSearchParams(window.location.search);
    if (q.get('browser_perf') === '1' || q.get('browser_perf') === 'true') return true;
    if (q.get('browser_perf') === '0' || q.get('browser_perf') === 'false') return false;
    const ls = window.localStorage?.getItem('PSY_OBSERVER_BROWSER_PERF');
    if (ls === '1' || ls === 'true') return true;
    if (ls === '0' || ls === 'false') return false;
  } catch {
    /* ignore */
  }
  return false;
}

export function browserPerfEnabled(): boolean {
  if (enabledCache === null) enabledCache = resolveEnabled();
  return enabledCache;
}

export function setBrowserPerfEnabled(flag: boolean): void {
  enabledCache = Boolean(flag);
  try {
    window.localStorage?.setItem('PSY_OBSERVER_BROWSER_PERF', flag ? '1' : '0');
  } catch {
    /* ignore */
  }
}

export function mark(name: string): void {
  if (!browserPerfEnabled()) return;
  try {
    performance.mark(`p5:${name}`);
  } catch {
    /* ignore */
  }
}

export function measure(name: string, startMark: string, endMark?: string): number | null {
  if (!browserPerfEnabled()) return null;
  try {
    const end = endMark || `p5:${name}:end`;
    if (!endMark) performance.mark(end);
    performance.measure(`p5:${name}`, `p5:${startMark}`, end);
    const entries = performance.getEntriesByName(`p5:${name}`, 'measure');
    const last = entries[entries.length - 1] as PerformanceMeasure | undefined;
    const ms = last ? last.duration : null;
    if (ms != null) record(name, ms);
    try {
      performance.clearMarks(`p5:${startMark}`);
      performance.clearMarks(end);
      performance.clearMeasures(`p5:${name}`);
    } catch {
      /* ignore */
    }
    return ms;
  } catch {
    return null;
  }
}

export function timeSync<T>(name: string, fn: () => T, meta?: Record<string, unknown>): T {
  if (!browserPerfEnabled()) return fn();
  const t0 = performance.now();
  try {
    return fn();
  } finally {
    record(name, performance.now() - t0, meta);
  }
}

export function record(name: string, ms: number, meta?: Record<string, unknown>): void {
  if (!browserPerfEnabled()) return;
  samples.push({ name, ms: Number(ms), t: performance.now(), meta });
  if (samples.length > MAX_SAMPLES) samples.splice(0, samples.length - MAX_SAMPLES);
  try {
    (window as any).__P5_BROWSER_PERF__ = snapshot();
  } catch {
    /* ignore */
  }
}

export function snapshot(): Record<string, unknown> {
  const by: Record<string, number[]> = {};
  for (const s of samples) {
    (by[s.name] ||= []).push(s.ms);
  }
  const stats: Record<string, unknown> = {};
  for (const [k, xs] of Object.entries(by)) {
    const ys = [...xs].sort((a, b) => a - b);
    const pct = (p: number) => ys[Math.min(ys.length - 1, Math.max(0, Math.round((p / 100) * (ys.length - 1))))];
    stats[k] = {
      n: ys.length,
      p50: pct(50),
      p95: pct(95),
      p99: pct(99),
      min: ys[0],
      max: ys[ys.length - 1],
      mean: ys.reduce((a, b) => a + b, 0) / ys.length,
    };
  }
  return {
    schema: SCHEMA,
    capability: CAPABILITY,
    profile: PROFILE,
    authority: AUTHORITY,
    enabled: browserPerfEnabled(),
    researcher_only: true,
    physical_mechanism: false,
    sample_count: samples.length,
    max_samples: MAX_SAMPLES,
    stats,
    viewport: typeof window !== 'undefined'
      ? { w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio }
      : null,
  };
}

export function resetSamples(): void {
  samples.length = 0;
  try {
    (window as any).__P5_BROWSER_PERF__ = snapshot();
  } catch {
    /* ignore */
  }
}

/** Expose for Playwright / CDP. */
export function installGlobal(): void {
  if (typeof window === 'undefined') return;
  (window as any).__P5_BROWSER_PERF_API__ = {
    enable: () => setBrowserPerfEnabled(true),
    disable: () => setBrowserPerfEnabled(false),
    snapshot,
    reset: resetSamples,
    schema: SCHEMA,
  };
  if (browserPerfEnabled()) {
    (window as any).__P5_BROWSER_PERF__ = snapshot();
  }
}
