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

export async function getSaveJob() {
  const r = await fetch(`${API}/api/control/save-job`);
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

/** LIVE ecology/mechanism mutation — does not rebuild runtime. */
export async function applyLiveIntervention(body: unknown) {
  const r = await fetch(`${API}/api/experiment/live`, {
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

export async function getInterventions() {
  const r = await fetch(`${API}/api/interventions`);
  if (!r.ok) throw new Error(await r.text());
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

export function connectLive(
  onFrame: (f: Frame) => void,
  onHeartbeat?: (hb: any) => void,
): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'frame') onFrame(msg.data);
      else if (msg.type === 'heartbeat' && onHeartbeat) onHeartbeat(msg.data);
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

export async function startAnalysisJob(opts: {
  source: 'current' | 'saved';
  run_id?: string | null;
  cutoff_tick?: number | null;
}) {
  const r = await fetch(`${API}/api/analysis/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source: opts.source,
      run_id: opts.run_id || undefined,
      cutoff_tick: opts.cutoff_tick ?? undefined,
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getAnalysisJob(jobId: string) {
  const r = await fetch(`${API}/api/analysis/jobs/${encodeURIComponent(jobId)}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function cancelAnalysisJob(jobId: string) {
  const r = await fetch(`${API}/api/analysis/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getAnalysisJobResult(jobId: string) {
  const r = await fetch(`${API}/api/analysis/jobs/${encodeURIComponent(jobId)}/result`);
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

export async function setGeometryAgentFilter(agent_filter: string) {
  const r = await fetch(`${API}/api/geometry/agent-filter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_filter }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getGeometryCell(ix: number, iy: number, agent_filter?: string) {
  const q = new URLSearchParams({ ix: String(ix), iy: String(iy) });
  if (agent_filter) q.set('agent_filter', agent_filter);
  const r = await fetch(`${API}/api/geometry/cell?${q}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getGeometryLive() {
  const r = await fetch(`${API}/api/geometry/live`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function hydrateGeometryRun(run_id: string, max_rows = 20000) {
  const r = await fetch(`${API}/api/geometry/hydrate/${encodeURIComponent(run_id)}?max_rows=${max_rows}`, {
    method: 'POST',
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function geometryUseLive() {
  const r = await fetch(`${API}/api/geometry/use-live`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function geometryClearSaved() {
  const r = await fetch(`${API}/api/geometry/clear-saved`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getSignalContextLive() {
  const r = await fetch(`${API}/api/signal-context/live`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getSignalContextEpisode(episode_id: string) {
  const r = await fetch(`${API}/api/signal-context/episode/${encodeURIComponent(episode_id)}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function analyzeSignalContextCurrent(opts?: {
  max_timeline_rows?: number;
  max_events?: number;
  max_episode_details?: number;
  cutoff_tick?: number | null;
}) {
  const q = new URLSearchParams();
  if (opts?.max_timeline_rows != null) q.set('max_timeline_rows', String(opts.max_timeline_rows));
  if (opts?.max_events != null) q.set('max_events', String(opts.max_events));
  if (opts?.max_episode_details != null) q.set('max_episode_details', String(opts.max_episode_details));
  if (opts?.cutoff_tick != null) q.set('cutoff_tick', String(opts.cutoff_tick));
  const qs = q.toString();
  const r = await fetch(`${API}/api/signal-context/current${qs ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function analyzeSignalContextRun(
  run_id: string,
  opts?: {
    max_timeline_rows?: number;
    max_events?: number;
    max_episode_details?: number;
    reference?: boolean;
  },
) {
  const q = new URLSearchParams();
  if (opts?.max_timeline_rows != null) q.set('max_timeline_rows', String(opts.max_timeline_rows));
  if (opts?.max_events != null) q.set('max_events', String(opts.max_events));
  if (opts?.max_episode_details != null) q.set('max_episode_details', String(opts.max_episode_details));
  if (opts?.reference) q.set('reference', 'true');
  const qs = q.toString();
  const r = await fetch(
    `${API}/api/signal-context/run/${encodeURIComponent(run_id)}${qs ? `?${qs}` : ''}`,
  );
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listSignalInterventions() {
  const r = await fetch(`${API}/api/signal-context/interventions`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getSignalIntervention(experiment_id: string) {
  const r = await fetch(
    `${API}/api/signal-context/interventions/${encodeURIComponent(experiment_id)}`,
  );
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listSignalSpecimens(opts?: { channel?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (opts?.channel) q.set('channel', opts.channel);
  if (opts?.limit != null) q.set('limit', String(opts.limit));
  const qs = q.toString();
  const r = await fetch(`${API}/api/signal-context/specimens${qs ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function saveSignalSpecimen(event: Record<string, unknown>) {
  const r = await fetch(`${API}/api/signal-context/specimens/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function replaySignalSpecimen(body: {
  specimen_id: string;
  target?: 'SELF' | 'PEER' | 'LOCATION';
  mode?: 'EXACT' | 'ALTER_AMPLITUDE' | 'ALTER_CHANNEL' | 'DELAY';
  amplitude_scale?: number;
}) {
  const r = await fetch(`${API}/api/signal-context/specimens/replay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listSignalRepertoire(opts?: { filter?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (opts?.filter) q.set('filter', opts.filter);
  if (opts?.limit != null) q.set('limit', String(opts.limit));
  const qs = q.toString();
  const r = await fetch(`${API}/api/signal-context/repertoire${qs ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listInteractionEpisodes(opts?: { limit?: number }) {
  const q = new URLSearchParams();
  if (opts?.limit != null) q.set('limit', String(opts.limit));
  const qs = q.toString();
  const r = await fetch(`${API}/api/signal-context/episodes${qs ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function replayInteractionEpisode(body: {
  episode: Record<string, unknown>;
  mode?: string;
}) {
  const r = await fetch(`${API}/api/signal-context/episodes/replay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listCognitiveForensics(opts?: { limit?: number }) {
  const q = new URLSearchParams();
  if (opts?.limit != null) q.set('limit', String(opts.limit));
  const qs = q.toString();
  const r = await fetch(`${API}/api/signal-context/forensics${qs ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterStatus() {
  const r = await fetch(`${API}/api/experimenter/status`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterSpawn(body: {
  x?: number; y?: number; theta?: number; near_agent?: number; run_id?: string;
} = {}) {
  const r = await fetch(`${API}/api/experimenter/spawn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterRemove() {
  const r = await fetch(`${API}/api/experimenter/remove`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterCommand(body: {
  kind: string;
  action?: string;
  amplitude?: number;
  specimen_id?: string;
  run_id?: string;
}) {
  const r = await fetch(`${API}/api/experimenter/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterSetTarget(agent_id: string | null) {
  const r = await fetch(`${API}/api/experimenter/target`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterCapture() {
  const r = await fetch(`${API}/api/experimenter/capture`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterListCaptures() {
  const r = await fetch(`${API}/api/experimenter/captures`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterTestCapture(capture_id: string, horizon = 40) {
  const r = await fetch(`${API}/api/experimenter/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capture_id, horizon }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getActionRealizationLive() {
  const r = await fetch(`${API}/api/action-realization/live`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getActionRealizationHistory(opts?: { agent_id?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (opts?.agent_id) q.set('agent_id', opts.agent_id);
  if (opts?.limit != null) q.set('limit', String(opts.limit));
  const qs = q.toString();
  const r = await fetch(`${API}/api/action-realization/history${qs ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getWorkEcologyLive() {
  const r = await fetch(`${API}/api/work-ecology/live`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function experimenterSetMobility(mode: 'ORDINARY_WORK' | 'RESEARCH_MOBILITY') {
  const r = await fetch(`${API}/api/experimenter/mobility`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
