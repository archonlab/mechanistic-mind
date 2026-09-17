export type Frame = any;

const API = '';

export async function getState(): Promise<Frame> {
  const r = await fetch(`${API}/api/state`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postControl(path: string, body?: unknown): Promise<Frame> {
  const r = await fetch(`${API}/api/control/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getStopInfo() {
  const r = await fetch(`${API}/api/control/stop-info`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getTimeline(limit = 200) {
  const r = await fetch(`${API}/api/timeline?limit=${limit}`);
  return r.json();
}

export async function inspectTick(tick: number) {
  const r = await fetch(`${API}/api/inspect/${tick}`);
  return r.json();
}

export async function replayTick(tick: number) {
  const r = await fetch(`${API}/api/replay/${tick}`);
  return r.json();
}

export async function getData() {
  const r = await fetch(`${API}/api/data`);
  return r.json();
}

export async function applyExperiment(body: unknown) {
  const r = await fetch(`${API}/api/experiment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(detail || r.statusText);
  }
  return r.json();
}

export async function getSnapshot() {
  const r = await fetch(`${API}/api/snapshot`);
  return r.json();
}

export async function getSnapshotMeta() {
  const r = await fetch(`${API}/api/snapshot/meta`);
  return r.json();
}

export function connectLive(onFrame: (f: Frame) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'frame') onFrame(msg.data);
    } catch {
      /* ignore */
    }
  };
  return ws;
}

export async function getDiagnostics() {
  const r = await fetch(`${API}/api/diagnostics`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function setActionTrace(body: { enabled: boolean; mode?: string }) {
  const r = await fetch(`${API}/api/diagnostics/action-trace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listRuns() {
  const r = await fetch(`${API}/api/runs`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getAnalysisEvidence(opts: {
  source: 'current' | 'saved';
  run_id?: string | null;
  cutoff_tick?: number | null;
}) {
  const q = new URLSearchParams({ source: opts.source });
  if (opts.run_id) q.set('run_id', opts.run_id);
  if (opts.cutoff_tick != null) q.set('cutoff_tick', String(opts.cutoff_tick));
  const r = await fetch(`${API}/api/analysis/evidence?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function saveAnalysisReport(body: {
  run_id: string;
  report_text: string;
  report_json: Record<string, unknown>;
}) {
  const r = await fetch(`${API}/api/analysis/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
