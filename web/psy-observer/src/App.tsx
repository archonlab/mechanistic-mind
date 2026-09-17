import { useEffect, useRef, useState } from 'react';
import './styles/app.css';
import type { ObserverFrame, ViewMode } from './types';
import {
  applyExperiment, connectLive, getSnapshot, getSnapshotMeta, getState, getTimeline,
  getStopInfo, inspectTick, postControl, replayTick,
} from './api/client';
import { WorldMap } from './components/WorldMap';
import { ActionDecisionInspector } from './components/ActionDecisionInspector';
import { MotionCausalInspector } from './components/MotionCausalInspector';
import { WhyDidItRotate } from './components/WhyDidItRotate';
import { WhyDidItsShapeChange } from './components/WhyDidItsShapeChange';
import { CausalChain } from './components/CausalChain';
import { ModelBanner } from './components/ModelBanner';
import {
  applyProjectionToFrame,
  canonicalBodyId,
  compareViewsSameFrame,
  requestedAgentId,
  shouldAcceptLiveFrame,
} from './observerProjection';
import {
  buildRunAnalysis,
  createAnalysisState,
  ingestAnalysisInput,
  shouldResetAnalysis,
  type AnalysisState,
  type RunAnalysis,
} from './analysis';
import {
  analysisToRunRecord,
  configFingerprint,
  loadRunArchive,
  makeRunId,
  saveRunArchive,
  statusFromRuntime,
  upsertRun,
  type RunArchiveStore,
} from './analysis/runArchive';
import type { ObserverRunRecord } from './analysis/types';
import { AnalyzeResultsPanel } from './components/AnalyzeResultsPanel';
import { OverviewPanel } from './components/OverviewPanel';
import { compressConsecutiveEvents, compressedEventSummary } from './eventCompression';

const TABS = ['WORLD', 'AGENT', 'MIND', 'TIMELINE', 'EXPERIMENT', 'DATA', 'ANALYZE RESULTS', 'OVERVIEW'] as const;
const SPEEDS = [0.25, 0.5, 1, 2, 5, 10, 50];
const EVENT_FILTERS = ['ALL', 'BODY', 'WORK', 'RESOURCE', 'ACTION', 'COGNITION', 'MATERIAL', 'SIGNAL'] as const;
const AGENT_EVENT_FILTERS = ['ALL AGENTS', 'AGENT_0', 'AGENT_1'] as const;
const PREFS_KEY = 'psy-observer-display';
const DEFAULT_LAYERS: Record<string, boolean> = {
  body: true, sites: true, trajectory: true, velocity: true, orientation: true,
  deformation: true, occupancy: false, force: false,
};
function loadPrefs(): any {
  try { return JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') || {}; }
  catch { return {}; }
}
function eventCategory(type: string) {
  const t = String(type || '');
  if (t.includes('SIGNAL') || t.includes('FIELD_')) return 'SIGNAL';
  if (t.startsWith('BODY_') || t.startsWith('SITE_')) return 'BODY';
  if (t.includes('RESOURCE') || t.includes('COMPLEMENTARY')) return 'RESOURCE';
  if (t.includes('MOTOR') || t.includes('ACTION') || t.includes('DISCRETE')) return 'ACTION';
  if (t.includes('DEFORM') || t.includes('WORK')) return 'WORK';
  if (t.includes('SCENARIO') || t.includes('PREDICTION') || t.includes('OBSERVATION')) return 'COGNITION';
  if (t.includes('MATERIAL') || t.includes('INTERNAL') || t.includes('ENVIRONMENT')) return 'MATERIAL';
  return 'OTHER';
}
const num = (v: any, digits = 4) => Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : '—';
const show = (v: any, digits = 4): string => {
  if (Array.isArray(v)) return `[${v.map(x => show(x, 3)).join(', ')}]`;
  if (typeof v === 'string') return v;
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (v && typeof v === 'object') {
    if ('dx' in v && 'dy' in v) return `[${show(v.dx, digits)}, ${show(v.dy, digits)}]`;
  }
  if (typeof v === 'number' && Number.isInteger(v)) return String(v);
  return num(v, digits);
};
const label = (s: string) => s.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());

function Card({ title, children, className = '' }: any) {
  return <section className={`panel science-card ${className}`}><h3>{title}</h3>{children}</section>;
}
function KV({ name, value, unit = '' }: any) {
  return <div className="metric"><span>{name}</span><strong>{show(value)}{unit}</strong></div>;
}
function Status({ value }: { value: string }) {
  return <span className={`badge ${String(value).toLowerCase().replaceAll(' ', '-')}`}>{value}</span>;
}

export default function App() {
  const prefs = loadPrefs();
  const [tab, setTab] = useState<(typeof TABS)[number]>(
    (TABS as readonly string[]).includes(prefs.tab) ? prefs.tab : 'WORLD',
  );
  const [liveFrame, setLiveFrame] = useState<ObserverFrame | null>(null);
  const [viewFrame, setViewFrame] = useState<ObserverFrame | null>(null);
  const [mode, setMode] = useState<ViewMode>('LIVE');
  const [connection, setConnection] = useState('CONNECTING');
  const [lastArrival, setLastArrival] = useState(0);
  const [now, setNow] = useState(0);
  const [events, setEvents] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [mechanisms, setMechanisms] = useState<any[]>([]);
  const [gearbox, setGearbox] = useState<any>(null);
  const [packs, setPacks] = useState<any[]>([]);
  const [snapshotMeta, setSnapshotMeta] = useState<any>(null);
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [selectedCell, setSelectedCell] = useState<any>(null);
  const [hoverCell, setHoverCell] = useState<any>(null);
  const [cellRaw, setCellRaw] = useState(false);
  const [layer, setLayer] = useState(prefs.layer || 'T');
  const [worldView, setWorldView] = useState(prefs.worldView || 'PHYSICAL');
  const [renderMode, setRenderMode] = useState(prefs.renderMode || 'COMPOSITE');
  const [opacity, setOpacity] = useState(Number.isFinite(prefs.opacity) ? prefs.opacity : .9);
  const [showGrid, setShowGrid] = useState(Boolean(prefs.showGrid));
  const [layers, setLayers] = useState<Record<string, boolean>>({ ...DEFAULT_LAYERS, ...(prefs.layers || {}) });
  const [trajectoryLength, setTrajectoryLength] = useState(Number.isFinite(prefs.trajectoryLength) ? prefs.trajectoryLength : 500);
  const [seed, setSeed] = useState('17');
  const [width, setWidth] = useState('32');
  const [height, setHeight] = useState('32');
  const [preset, setPreset] = useState('MM 1.0 — Tiktaalik');
  const [cognitionEnabled, setCognitionEnabled] = useState(true);
  const [twoAgentExperimental, setTwoAgentExperimental] = useState(false);
  const [targetTick, setTargetTick] = useState('');
  const [uiHz, setUiHz] = useState('10');
  const [bufferCapacity, setBufferCapacity] = useState('512');
  const [bodyMass, setBodyMass] = useState('2');
  const [bodyVMax, setBodyVMax] = useState('0.3');
  const [eventFilter, setEventFilter] = useState<(typeof EVENT_FILTERS)[number]>('ALL');
  const [agentEventFilter, setAgentEventFilter] = useState<(typeof AGENT_EVENT_FILTERS)[number]>('ALL AGENTS');
  const [compareMind, setCompareMind] = useState(false);
  const [appIdentity, setAppIdentity] = useState<any>(null);
  const [controlMessage, setControlMessage] = useState<any>(null);
  const [stopDialog, setStopDialog] = useState<any>(null);
  const [stopConfirmNoSave, setStopConfirmNoSave] = useState(false);
  const [finalizing, setFinalizing] = useState<string | null>(null);
  const [saveBanner, setSaveBanner] = useState<any>(null);
  const [rawOpen, setRawOpen] = useState(false);
  const [mechanismQuery, setMechanismQuery] = useState('');
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [mapKey, setMapKey] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const replayIndex = useRef(0);
  const modeRef = useRef<ViewMode>('LIVE');
  const desiredAgentIdRef = useRef<string | null>(null);
  const selectionSeqRef = useRef(0);
  const lastAcceptedSeqRef = useRef(0);
  const [desiredAgentId, setDesiredAgentId] = useState<string | null>(null);
  const analysisStateRef = useRef<AnalysisState>(createAnalysisState());
  const runArchiveRef = useRef<RunArchiveStore>(loadRunArchive());
  const currentRunMetaRef = useRef<{ run_id: string; run_number: number; started_at: string; fingerprint: string } | null>(null);
  const [runAnalysis, setRunAnalysis] = useState<RunAnalysis | null>(null);
  const [archivedRuns, setArchivedRuns] = useState<ObserverRunRecord[]>(() => loadRunArchive().runs);
  const [currentRunId, setCurrentRunId] = useState<string | null>(() => loadRunArchive().current_run_id);
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const [overviewFilter, setOverviewFilter] = useState('ALL');
  const [overviewAgentFilter, setOverviewAgentFilter] = useState('ALL AGENTS');
  const [analysisCopyMsg, setAnalysisCopyMsg] = useState<string | null>(null);
  useEffect(() => { modeRef.current = mode; }, [mode]);

  function persistArchive(store: RunArchiveStore) {
    runArchiveRef.current = store;
    saveRunArchive(store);
    setArchivedRuns([...store.runs]);
    setCurrentRunId(store.current_run_id);
  }

  function ensureCurrentRun(analysis: RunAnalysis, frame: any) {
    const id = analysis.identity;
    const fp = configFingerprint({
      seed: id.seed,
      runtime: id.runtime,
      map_w: id.map_width,
      map_h: id.map_height,
      boundary: id.boundary,
      agent_count: id.agent_count,
      cognition_enabled: id.cognition_enabled,
      experimental_overrides: id.experimental_overrides,
      active_mechanisms: id.active_mechanisms,
    });
    let meta = currentRunMetaRef.current;
    if (!meta) {
      const store = runArchiveRef.current;
      const n = store.next_run_number;
      const started = new Date().toISOString();
      meta = {
        run_id: makeRunId(id.generation, id.seed, started, n),
        run_number: n,
        started_at: started,
        fingerprint: fp,
      };
      currentRunMetaRef.current = meta;
      store.next_run_number = n + 1;
    }
    const st = statusFromRuntime(String(frame?.header?.status || id.status), analysis.identity.analysis_mode);
    const finished = st === 'COMPLETE' || st === 'STOPPED' ? new Date().toISOString() : null;
    const record = analysisToRunRecord(analysis, {
      run_id: meta.run_id,
      run_number: meta.run_number,
      started_at: meta.started_at,
      finished_at: finished,
      status: st,
      config_fingerprint: meta.fingerprint || fp,
    });
    persistArchive(upsertRun(runArchiveRef.current, record));
  }

  function finalizeCurrentRunBeforeReset(analysis: RunAnalysis | null, frame: any) {
    if (!analysis || analysis.lifecycle?.insufficient) {
      currentRunMetaRef.current = null;
      return;
    }
    ensureCurrentRun(analysis, frame);
    // Seal previous run as STOPPED/COMPLETE then clear current meta so next rebuild creates new run_id
    const meta = currentRunMetaRef.current;
    if (meta) {
      const existing = runArchiveRef.current.runs.find((r) => r.run_id === meta.run_id);
      if (existing && existing.status === 'RUNNING') {
        const sealed = {
          ...existing,
          status: 'STOPPED' as const,
          finished_at: existing.finished_at || new Date().toISOString(),
        };
        persistArchive(upsertRun(runArchiveRef.current, sealed));
      }
    }
    currentRunMetaRef.current = null;
  }

  function rebuildAnalysis(partial?: {
    frame?: any;
    timeline?: any[];
    events?: any[];
    mechanisms?: any[];
    mode?: 'LIVE' | 'FINAL';
  }) {
    const frame = partial?.frame ?? liveFrame ?? viewFrame;
    if (frame && shouldResetAnalysis(analysisStateRef.current, frame)) {
      const prev = runAnalysis;
      finalizeCurrentRunBeforeReset(prev, frame);
      analysisStateRef.current = createAnalysisState();
    }
    const status = String(frame?.header?.status || '');
    const analysisMode = partial?.mode
      || (status === 'STOPPED' || status === 'COMPLETE' ? 'FINAL' : 'LIVE');
    ingestAnalysisInput(analysisStateRef.current, {
      frame,
      timeline: partial?.timeline ?? timeline,
      events: partial?.events ?? events,
      telemetry: frame?.telemetry?.series,
      mechanisms: partial?.mechanisms ?? mechanisms,
      mode: analysisMode,
    });
    const built = buildRunAnalysis(analysisStateRef.current, analysisMode);
    setRunAnalysis(built);
    if (!built.lifecycle.insufficient) ensureCurrentRun(built, frame);
  }

  async function refreshAux() {
    const safe = (url: string): Promise<any> => fetch(url).then(r => r.ok ? r.json() : ({})).catch(() => ({}));
    const [tl, ev, me, ge, pa, meta] = await Promise.all([
      getTimeline(400).catch(() => ({ events: [] })),
      safe('/api/events?limit=200'), safe('/api/mechanisms'),
      safe('/api/evidence/gearbox'), safe('/api/results/packs'),
      getSnapshotMeta().catch(() => ({})),
    ]);
    const tlEvents = (tl as any).events || [];
    const evEvents = ev.events || [];
    const mechs = me.mechanisms || [];
    setTimeline(tlEvents); setEvents(evEvents);
    setMechanisms(mechs); setGearbox(ge); setPacks(pa.packs || []);
    setSnapshotMeta(meta);
    rebuildAnalysis({
      timeline: tlEvents,
      events: evEvents,
      mechanisms: mechs,
      frame: liveFrame ?? viewFrame ?? undefined,
    });
  }

  useEffect(() => {
    getState().then(f => {
      const agent = requestedAgentId(f);
      desiredAgentIdRef.current = agent;
      setDesiredAgentId(agent);
      const projected = applyProjectionToFrame(f, agent);
      setLiveFrame(projected); setViewFrame(projected); setSeed(String(f.header?.seed ?? 17));
      setWidth(String(f.world?.width ?? 32)); setHeight(String(f.world?.height ?? 32));
      setCognitionEnabled(Boolean(f.experiment?.runtime?.cognition_enabled ?? f.header?.cognition_enabled ?? true));
      if (f.header?.target_tick != null) setTargetTick(String(f.header.target_tick));
      const obs = f.experiment?.observer || {};
      if (obs.ui_hz != null) setUiHz(String(obs.ui_hz));
      if (obs.buffer_capacity != null) setBufferCapacity(String(obs.buffer_capacity));
      const bodyCfg = f.experiment?.agent_body || {};
      if (bodyCfg.mass != null) setBodyMass(String(bodyCfg.mass));
      if (bodyCfg.v_max != null) setBodyVMax(String(bodyCfg.v_max));
    });
    refreshAux().catch(() => undefined);
    fetch('/api/health').then(r => r.ok ? r.json() : null).then(h => {
      if (h) {
        setAppIdentity(h);
        document.title = `Psy Observer · local${h.version ? ' · v' + h.version : ''}`;
      }
    }).catch(() => undefined);
    let stopped = false, socket: WebSocket | null = null, timer: number;
    const open = () => {
      if (stopped) return;
      setConnection('CONNECTING');
      socket = connectLive(f => {
        setConnection('CONNECTED'); setLastArrival(Date.now());
        const desired = desiredAgentIdRef.current;
        const accept = shouldAcceptLiveFrame(f, {
          desiredAgentId: desired,
          selectionSeq: selectionSeqRef.current,
          lastAcceptedSeq: lastAcceptedSeqRef.current,
          mode: modeRef.current,
        });
        if (!accept) return;
        const agent = desired || requestedAgentId(f);
        const projected = applyProjectionToFrame(f, agent);
        if (desired && requestedAgentId(f) === desired) {
          lastAcceptedSeqRef.current = selectionSeqRef.current;
        }
        setLiveFrame(projected);
        setViewFrame(prev => modeRef.current === 'LIVE' ? projected : prev);
      });
      socket.onclose = () => {
        setConnection('DISCONNECTED');
        if (!stopped) timer = window.setTimeout(open, 1200);
      };
      socket.onerror = () => socket?.close();
    };
    open();
    return () => { stopped = true; clearTimeout(timer); socket?.close(); };
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  // Debounced aux refresh: avoid /api/results/packs storms when Step or an
  // external client advances many ticks while the SPA is open and not RUNNING.
  useEffect(() => {
    const running = liveFrame?.header?.status === 'RUNNING' && mode === 'LIVE';
    if (running) return;
    if (!liveFrame?.header?.tick && liveFrame?.header?.tick !== 0) return;
    const t = window.setTimeout(() => { refreshAux().catch(() => undefined); }, 350);
    return () => clearTimeout(t);
  }, [liveFrame?.header?.tick, liveFrame?.header?.status, mode]);
  useEffect(() => {
    if (!(liveFrame?.header?.status === 'RUNNING' && mode === 'LIVE')) return;
    const interval = Number(liveFrame?.header?.simulation_speed) >= 5 ? 1500 : 2000;
    const t = window.setInterval(() => { refreshAux().catch(() => undefined); }, interval);
    return () => clearInterval(t);
  }, [liveFrame?.header?.status, liveFrame?.header?.simulation_speed, mode]);
  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify({
        tab, layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength,
      }));
    } catch { /* display prefs only */ }
  }, [tab, layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength]);

  const rawFrame = mode === 'LIVE' ? liveFrame : viewFrame;
  if (!rawFrame) return <div className="loading">Connecting to MM 1.0 — Tiktaalik…</div>;
  const agentForProjection = desiredAgentId || requestedAgentId(rawFrame);
  // Atomic projection: identity + mind + body + seed always from the same agents_views entry
  const frame = applyProjectionToFrame(rawFrame, agentForProjection);
  const header = frame.header || {}, world = frame.world || {}, body = frame.body || {};
  const selectedAgentId = String(frame.observer?.selected_agent_id || header.selected_agent_id || agentForProjection);
  const selectedBodyId = String(header.selected_body_id || canonicalBodyId(selectedAgentId));
  const inspectedAgentSeed = header.inspected_agent_seed != null ? header.inspected_agent_seed : null;
  const mindSource = frame.mind?.source_agent_id || frame.mind?.agent_id || null;
  const projectionOk = frame.observer?.projection_ok !== false
    && mindSource === selectedAgentId
    && selectedBodyId === canonicalBodyId(selectedAgentId)
    && frame.mind?.status !== 'NOT AVAILABLE';
  const identityTuple = frame.observer?.identity_tuple || {
    runtime_generation: header.runtime_generation,
    inspected_tick: header.tick,
    selected_agent_id: selectedAgentId,
  };

  async function selectObserverAgent(index: number) {
    const agentId = `agent_${index}`;
    desiredAgentIdRef.current = agentId;
    selectionSeqRef.current += 1;
    const seq = selectionSeqRef.current;
    setDesiredAgentId(agentId);
    // Immediate optimistic re-projection of the current frame (same tick) — invalidates old agent data now
    if (mode === 'LIVE' && liveFrame) {
      setLiveFrame(applyProjectionToFrame(liveFrame, agentId));
      setViewFrame(applyProjectionToFrame(liveFrame, agentId));
    } else if (viewFrame) {
      setViewFrame(applyProjectionToFrame(viewFrame, agentId));
    }
    const f = await postControl('select-agent', { index });
    setControlMessage(f.control_receipt);
    if (!f.control_receipt?.accepted) return f;
    // Ignore stale responses if a newer selection happened
    if (selectionSeqRef.current !== seq) return f;
    const projected = applyProjectionToFrame(f, agentId);
    lastAcceptedSeqRef.current = seq;
    setLiveFrame(projected);
    if (mode === 'LIVE') {
      setViewFrame(projected);
    } else {
      // INSPECT: keep recorded tick; re-project from the inspected frame's agents_views
      setViewFrame(prev => applyProjectionToFrame(prev || projected, agentId));
    }
    await refreshAux();
    return f;
  }

  const physical = frame.physical || {}, action = physical.action || {};
  const motor = physical.motor || {};
  const resources = physical.resources || {}, allocation = physical.work_allocation || {};
  const fields = (world.fields_available || []).filter((f: any) => f.kind === 'scalar');
  const staleSeconds = Math.max(1, Number(liveFrame?.observation?.stale_after_seconds || 2));
  const stale = connection === 'CONNECTED' && now - lastArrival > staleSeconds * 1000 &&
    liveFrame?.header?.status === 'RUNNING';
  const displayStatus = connection === 'DISCONNECTED' ? 'DISCONNECTED' : stale ? 'STALE' : header.status || 'UNKNOWN';
  const tickMismatch = frame.observation && !frame.observation.tick_consistent;
  const historical = frame.historical_compatibility;
  const recordedTick = Number(timeline[timeline.length - 1]?.tick ?? liveFrame?.header?.tick ?? header.tick);
  const reservoir = Number(resources.reservoir || 0);
  const reservoirMax = Math.max(1e-9, Number(resources.reservoir_capacity || 1));

  async function control(op: string, payload?: any) {
    if (finalizing && op !== 'stop') return;
    const f = await postControl(op, payload);
    setControlMessage(f.control_receipt);
    const agent = desiredAgentIdRef.current || requestedAgentId(f);
    const projected = applyProjectionToFrame(f, agent);
    setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
    if (f.finalize?.accepted && f.finalize?.run_dir && f.finalize?.final_tick != null) {
      setSaveBanner({
        tick: f.finalize.final_tick,
        seed: f.finalize.seed,
        path: f.finalize.run_dir,
        reason: f.finalize.termination_reason,
        verified: true,
      });
    } else if (f.finalize && f.finalize.accepted === false) {
      setSaveBanner({
        failed: true,
        error: f.finalize.error || 'SAVE_FAILED',
        liveTick: f.finalize.live_tick,
        capturedTick: f.finalize.captured_tick ?? f.finalize.persisted_tick,
      });
    }
    await refreshAux();
    return f;
  }

  async function openStopDialog() {
    try {
      const info = await getStopInfo();
      setStopConfirmNoSave(false);
      setStopDialog(info);
    } catch (err) {
      setControlMessage({ operation: 'STOP', accepted: false, reason: String(err) });
    }
  }

  async function saveAndStop() {
    setStopDialog(null);
    setFinalizing('Finalizing run…');
    try {
      setFinalizing('Flushing telemetry…');
      setFinalizing('Saving snapshot…');
      const f = await postControl('stop', { save: true, reason: 'USER_STOP_SAVED' });
      setControlMessage(f.control_receipt);
      setLiveFrame(f);
      setViewFrame(f);
      setMode('LIVE');
      if (f.finalize?.accepted && f.finalize?.final_tick != null) {
        setFinalizing('Saving results…');
        const verifiedTick = f.finalize.final_tick;
        setSaveBanner({
          tick: verifiedTick,
          seed: f.finalize.seed,
          path: f.finalize.run_dir,
          reason: f.finalize.termination_reason,
          verified: true,
        });
        setControlMessage({
          ...(f.control_receipt || {}),
          accepted: true,
          operation: 'STOP',
          tick: verifiedTick,
          verified_final_tick: verifiedTick,
          reason: f.control_receipt?.reason || `SAVED · t${verifiedTick}`,
        });
        setFinalizing(null);
      } else {
        setFinalizing(null);
        const liveT = f.finalize?.live_tick;
        const capT = f.finalize?.captured_tick ?? f.finalize?.persisted_tick;
        const mismatch =
          f.finalize?.persistence_integrity_error && liveT != null && capT != null
            ? ` · live tick: ${liveT} · captured tick: ${capT} · reason: persistence integrity mismatch`
            : '';
        setControlMessage({
          ...(f.control_receipt || {}),
          accepted: false,
          operation: 'STOP',
          reason: (f.finalize?.error || f.control_receipt?.reason || 'SAVE_FAILED') + mismatch,
        });
        setSaveBanner({
          failed: true,
          error: (f.finalize?.error || 'Save failed — runtime preserved') + mismatch,
          liveTick: liveT,
          capturedTick: capT,
        });
      }
      await refreshAux();
    } catch (err) {
      setFinalizing(null);
      setControlMessage({ operation: 'STOP', accepted: false, reason: String(err) });
      setSaveBanner({ failed: true, error: String(err) });
    }
  }

  async function stopWithoutSaving() {
    if (!stopConfirmNoSave) {
      setStopConfirmNoSave(true);
      return;
    }
    setStopDialog(null);
    setStopConfirmNoSave(false);
    setFinalizing(null);
    await control('stop', { save: false, reason: 'USER_STOP_NO_SAVE' });
    setSaveBanner({ discarded: true, reason: 'USER_STOP_NO_SAVE' });
  }
  async function inspect(tick: number, replay = false) {
    try {
      const f = replay ? await replayTick(tick) : await inspectTick(tick);
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      setViewFrame(applyProjectionToFrame(f, agent));
      setMode(replay ? 'REPLAY' : 'INSPECT');
    } catch (err) {
      setControlMessage({ operation: replay ? 'REPLAY' : 'INSPECT', accepted: false, tick, reason: String(err) });
    }
  }
  async function toggleMechanism(m: any) {
    const f = await fetch(`/api/mechanisms/${m.id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !m.enabled }),
    }).then(r => r.json());
    setControlMessage(f.control_receipt);
    if (f.control_receipt?.accepted) {
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(f, agent);
      setLiveFrame(projected);
      setViewFrame(mode === 'LIVE' ? projected : viewFrame);
      setMechanisms(f.mechanism_result?.mechanisms || []);
    }
  }
  function inspectCell(info: any) {
    if (!info) return;
    const values: Record<string, any> = {};
    Object.entries(world.scalars || {}).forEach(([k, grid]: any) => {
      values[k] = grid?.[info.iy]?.[info.ix] ?? null;
    });
    const sites = (body.sites || []).filter((s: any) =>
      Math.floor(s.world?.[0]) === info.ix && Math.floor(s.world?.[1]) === info.iy);
    setSelectedCell({ position: [info.ix, info.iy], fields: values, body_sites: sites });
    setCellRaw(false);
  }

  const identity = <div className="model-banner">
    <ModelBanner banner={frame.model_banner} header={header} />
    <strong>Psy Observer · local</strong>
    <span>{header.model_display_name || frame.model_banner?.model || 'MM 1.0 — Tiktaalik'}</span>
    <span>{header.runtime_classification || (header.canonical ? 'CANONICAL' : 'TIKTAALIK + EXPERIMENTAL OVERRIDES')}</span>
    <span>v{appIdentity?.version || header.mm_version || '0.2.0'}</span>
    <span>Runtime {header.runtime_model}</span>
    <span>Seed {header.seed}</span>    <span>Tick {header.tick}{mode === 'INSPECT' ? ' inspected' : mode === 'REPLAY' ? ' replayed' : ''}{header.target_tick != null ? ` / ${header.target_tick}` : ''}</span>
    <span>Max {header.max_ticks ?? '∞'}</span>
    <span>Speed {header.simulation_speed === 50 ? 'MAX' : `${header.simulation_speed ?? 1}×`}</span>
    {header.sim_ticks_per_sec != null && <span title="Scientific ticks executed per wall-clock second. All ticks still run; Observer frames may be sampled.">SIM {header.sim_ticks_per_sec} t/s</span>}
    {header.observer_fps != null && <span title="Observer visual frames delivered per second (sampled).">OBS {header.observer_fps} fps</span>}
    <span title="Actual scientific runtime tick">LIVE TICK {header.live_runtime_tick ?? header.tick}</span>
    {(header.frame_tick != null && header.live_runtime_tick != null && Number(header.frame_tick) !== Number(header.live_runtime_tick)) && (
      <span className="warn" title="Displayed observer frame tick differs from live scientific tick">FRAME TICK {header.frame_tick}</span>
    )}
    {Number(header.visual_frames_dropped) > 0 && <span className="meta-extra" title="Superseded visual frames not pushed (backpressure)">drop {header.visual_frames_dropped}</span>}
    <span className="meta-extra">{world.width}×{world.height}</span>
    <span className="meta-extra">native {world.runtime_resolution?.width || world.width}×{world.runtime_resolution?.height || world.height}</span>
    <span className="meta-extra">transport {world.transported_resolution?.width || world.grid_shape_transported?.width}×{world.transported_resolution?.height || world.grid_shape_transported?.height}</span>
    <span>{header.boundary_topology}</span>
    <span className="badge on">INSPECTING: {String(selectedAgentId).toUpperCase()}</span><span>body {selectedBodyId}</span><span>agent seed {inspectedAgentSeed ?? '—'}</span><span className="meta-extra">gen {header.runtime_generation ?? identityTuple.runtime_generation ?? '—'}</span>{mindSource && mindSource !== selectedAgentId ? <span className="bad">MIND SOURCE MISMATCH {mindSource}</span> : null}
    {lastArrival > 0 && <span className="meta-extra">frame {((now - lastArrival) / 1000).toFixed(1)}s</span>}
    <Status value={mode}/><Status value={displayStatus}/>
    {mode !== 'LIVE' && <span className="warn">Live runtime t{header.live_runtime_tick ?? liveFrame?.header?.tick}</span>}
    {tickMismatch && <span className="bad">TICK MISMATCH</span>}
  </div>;

  const layerControls = <Card title="World layers">
    <label>View <select value={worldView} onChange={e => setWorldView(e.target.value)}>
      <option>PHYSICAL</option><option>AGENT_PERCEPTION</option>
      <option>PREDICTED</option><option>DIFFERENCE</option>
    </select></label>
    <div className="field-list">{fields.map((f: any) =>
      <button className={layer === f.id ? 'active' : ''} key={f.id} onClick={() => setLayer(f.id)}>{f.label || f.id}</button>)}
    </div>
    <label>Render <select value={renderMode} onChange={e => setRenderMode(e.target.value)}>
      {['COMPOSITE','SMOOTH','CELL','CONTOUR','VECTOR'].map(x => <option key={x}>{x}</option>)}
    </select></label>
    {Object.keys(layers).map(k => <label className="check" key={k}><input type="checkbox" checked={layers[k]}
      onChange={e => setLayers(x => ({ ...x, [k]: e.target.checked }))}/>{label(k)}</label>)}
    <label>Opacity <input type="range" min=".2" max="1" step=".05" value={opacity} onChange={e => setOpacity(+e.target.value)}/></label>
    <label className="check"><input type="checkbox" checked={showGrid} onChange={e => setShowGrid(e.target.checked)}/>Cell grid</label>
    <label>Trajectory <select value={trajectoryLength} onChange={e => setTrajectoryLength(+e.target.value)}>
      <option value="0">OFF</option><option value="100">SHORT</option><option value="500">MEDIUM</option><option value="2000">LONG</option>
    </select></label>
    <div className="toolbar-row">
      <button onClick={() => { setLayers({ ...DEFAULT_LAYERS }); setWorldView('PHYSICAL'); setRenderMode('COMPOSITE'); setMapKey(k => k + 1); }}>Reset layout</button>
      <button onClick={() => setFullscreen(f => !f)}>{fullscreen ? 'Exit fullscreen' : 'Fullscreen world'}</button>
    </div>
    <div className="availability">Predicted spatial layer: NOT_IMPLEMENTED (no predicted world field in Current MM)<br/>Perception map: NOT_IMPLEMENTED as spatial layer (perception evidence is on AGENT/MIND)<br/>Action-trace spatial overlay: NOT_IMPLEMENTED<br/>Occupancy overlay uses recorded trajectory only · NOT a live occupancy field</div>
  </Card>;

  const inspector = <div className="inspector-stack">
    <Card title="Cell / site inspector">
      {selectedCell ? <>
        <div className="toolbar-row">
          <button className={!cellRaw ? 'active' : ''} onClick={() => setCellRaw(false)}>Structured</button>
          <button className={cellRaw ? 'active' : ''} onClick={() => setCellRaw(true)}>Raw</button>
        </div>
        {cellRaw ? <pre className="cell-raw">{JSON.stringify(selectedCell, null, 2)}</pre> : <>
          <KV name="Cell" value={selectedCell.position}/>
          {Object.entries(selectedCell.fields).map(([k,v]) => <KV key={k} name={k} value={v}/>)}
          <div className="subtle">Body sites: {selectedCell.body_sites.length || 'none'}</div>
        </>}
      </> : <div className="empty">Click a world cell</div>}
    </Card>
    <Card title="Requested vs realized action">
      <div className="selected-action">{physical.selected_action || header.selected_action || '—'}</div>
      <KV name="Requested Δv" value={action.action_dv_requested}/>
      <KV name="Requested impulse" value={action.action_impulse_requested}/>
      <KV name="Positive work requested" value={action.action_work_requested}/>
      <KV name="Allocated" value={action.action_work_allocated}/>
      <KV name="Realized Δv" value={action.action_dv_realized}/>
      <KV name="Realized work" value={action.action_work_realized}/>
      <KV name="Unrealized" value={action.action_work_unrealized}/>
      <KV name="Limit" value={(action.action_work_limit_fraction ?? 0) * 100} unit="%"/>
    </Card>
    <Card title="Scientific honesty">
      <div className="subtle">Topology: WRAP_PERIODIC only</div>
      <div className="subtle">CLOSED / OPEN: UNSUPPORTED</div>
      <div className="subtle">Replay: bounded recorded frames</div>
      <div className="subtle">Physical EMIT: NOT AVAILABLE</div>
    </Card>
  </div>;

  const worldTab = <div className={`world-layout ${fullscreen ? 'fullscreen' : ''}`}>
    <aside className="left-rail resizable">{layerControls}</aside>
    <main className="world-center">
      <WorldMap key={mapKey} world={world} body={body} layer={layer} viewMode={worldView} perception={frame.perception}
        renderMode={renderMode} opacity={opacity} showGrid={showGrid} vectorDensity={.35} contourLevels={8}
        autoScale scaleMin={0} scaleMax={1} compositeLayers={[layer, 'flow_mag']}
        trajectory={(frame.trajectory?.points || []).slice(-trajectoryLength)} layers={layers}
        onHoverCell={setHoverCell} onSelectCell={inspectCell} />
      {hoverCell && <div className="cell-chip">{hoverCell.field}[{hoverCell.ix},{hoverCell.iy}] = {show(hoverCell.value, 3)}</div>}
      <div className="causal-strip">{['WORLD','PERCEPTION','BODY','INTERNAL','PREDICTION','ACTION','CONSEQUENCE'].map(k =>
        <div key={k}><b>{k}</b><Status value={frame.causal_chain?.stages?.[k]?.status || 'NOT AVAILABLE'}/></div>)}</div>
    </main>
    <aside className="right-rail resizable">{inspector}</aside>
  </div>;

  const worldWithInspector = <div className="world-click-wrapper">{worldTab}</div>;

  const agentCount = Number(frame.experiment?.runtime?.agent_count || frame.agents_observer?.length || 1);
  const agentTab = <div className="dashboard-grid">
    {agentCount >= 2 ? <Card title="Observer agent comparison" className="wide">
      <div className="subtle">Observer perspective only — selection does not change which agent runs cognition.</div>
      <div className="inspecting-banner" style={{marginBottom:8}}>
        <strong>INSPECTING: {String(selectedAgentId).toUpperCase()}</strong>
        <span> · seed {inspectedAgentSeed ?? '—'} · tick {header.tick} · gen {header.runtime_generation ?? '—'} · body {selectedBodyId}</span>
      </div>
      <div className="toolbar-row">
        {['AGENT A', 'AGENT B'].map((labelText, i) =>
          <button key={labelText} className={(selectedAgentId === `agent_${i}`) ? 'active' : ''}
            onClick={() => selectObserverAgent(i)}>{labelText} · agent_{i}</button>)}
      </div>
      <div className="dashboard-grid">
        {(frame.agents_observer || []).map((a: any) =>
          <div key={a.observer_id} className="science-card" style={{ padding: 8 }}>
            <b>{a.observer_id}</b> · seed {a.agent_seed ?? '—'}
            <KV name="Selected" value={a.selected_action}/>
            <KV name="Source" value={a.selection_source}/>
            <KV name="Reason" value={a.selection_reason}/>
            <KV name="WAIT / MOVE" value={`${a.wait_count ?? 0} / ${a.move_count ?? 0}`}/>
            <KV name="WAIT rate" value={(a.wait_rate ?? 0) * 100} unit="%"/>
            <KV name="Distance" value={a.distance_travelled}/>
            <KV name="Unique cells" value={a.unique_cells_visited}/>
            <KV name="Collisions" value={a.collision_count}/>
            <KV name="Prospections" value={a.prospective_compositions}/>
            <KV name="Supported" value={(a.supported_actions || []).join(', ') || '—'}/>
            <div className="subtle">pos ({Number(a.x).toFixed(2)}, {Number(a.y).toFixed(2)})</div>
          </div>)}
      </div>
    </Card> : null}
    <Card title="Why this action?" className="wide"><ActionDecisionInspector why={frame.causal_chain?.why_this_action}/></Card>
    <Card title="Causal chain" className="wide"><CausalChain chain={frame.causal_chain}/></Card>
    <Card title="Why did it move?"><MotionCausalInspector whyMove={frame.causal_chain?.why_did_it_move} physical={physical}/></Card>
    <Card title="Why did it rotate?"><WhyDidItRotate whyMove={frame.causal_chain?.why_did_it_move} physical={physical}/></Card>
    <Card title="Why did its shape change?"><WhyDidItsShapeChange whyMove={frame.causal_chain?.why_did_it_move} physical={physical}/></Card>
    <Card title="Physical channels">
      <KV name="Prior velocity" value={[body.vx, body.vy]}/><KV name="Environment" value={physical.force_contributions?.environmental_site}/>
      <KV name="Motor requested" value={motor.motor_delta_v_requested}/><KV name="Motor realized" value={motor.motor_delta_v_realized}/>
      <KV name="Action requested" value={action.action_dv_requested}/><KV name="Action realized" value={action.action_dv_realized}/>
    </Card>
    <Card title="Resource → work → realization">
      <KV name="ENV A" value={world.summary?.R_A_sum}/><KV name="ENV B" value={world.summary?.R_B_sum}/>
      <KV name="Body A" value={resources.complementary?.body_A}/><KV name="Body B" value={resources.complementary?.body_B}/>
      <KV name="Conversion input" value={resources.complementary?.work_credited}/><KV name="Reservoir" value={resources.reservoir}/>
      <div className="subtle">Reservoir fill {num((reservoir / reservoirMax) * 100, 1)}%</div>
      <div className="stack-bar"><i style={{ width: `${Math.min(100, (reservoir / reservoirMax) * 100)}%` }}/></div>
    </Card>
    <Card title="Prospection (read-only branches)">
      {(frame.prospection_view?.branches || []).length ? (frame.prospection_view?.branches || []).map((br: any) =>
        <div key={br.branch} className="prospection-branch">
          <div><b>BRANCH {br.branch}</b> {br.is_selected ? '· first action matches selected' : ''}</div>
          <KV name="Current" value={br.current}/><KV name="First action" value={br.first_action}/>
          <KV name="Predicted context" value={br.predicted_context}/><KV name="Future action" value={br.future_action}/>
          <KV name="Predicted consequence" value={br.predicted_consequence}/><KV name="Support" value={br.support}/>
          <div className="subtle">{br.note}</div>
        </div>) : <div className="subtle">No prospective branches at this tick.</div>}
      <div className="subtle">Selected now: {frame.prospection_view?.selected_action_now || physical.selected_action || '—'}</div>
    </Card>
    <Card title="Shared allocation">
      {['action','motor','deformation'].map(k => {
        const req = Number(allocation[`requested_${k}`] || 0);
        const alloc = Number(allocation[`allocated_${k}`] || 0);
        const denom = Math.max(req, alloc, 1e-9);
        return <div key={k} className="allocation-row"><span>{label(k)}</span>
          <span>req {num(req)}</span><strong>alloc {num(alloc)}</strong>
          <div className="stack-bar slim"><i className={k} style={{ width: `${Math.min(100, (alloc / denom) * 100)}%` }}/></div>
        </div>;
      })}
      <KV name="Available" value={allocation.available}/><div className="subtle">{allocation.policy || 'No receipt yet'}</div>
      <div className="subtle">Cross term: {allocation.cross_term_attribution || '—'}</div>
    </Card>
  </div>;

  const mindUnavailable = !projectionOk;
  const mindCross = Boolean(mindSource && mindSource !== selectedAgentId);
  const compareBundle = compareViewsSameFrame(rawFrame);
  const mindTab = <div className="dashboard-grid">
    <Card title="Inspection identity" className="wide">
      <div className="inspecting-banner">
        <strong>INSPECTING: {String(selectedAgentId).toUpperCase()}</strong>
        <div>SEED: {inspectedAgentSeed != null ? inspectedAgentSeed : '—'} · TICK: {header.tick} · GENERATION: {header.runtime_generation ?? '—'}</div>
        <div>MIND SOURCE: {projectionOk ? (mindSource || 'NOT AVAILABLE') : 'NOT AVAILABLE'} · BODY: {selectedBodyId}</div>
        <div className="subtle">identity ({identityTuple.runtime_generation ?? '—'}, {identityTuple.inspected_tick ?? header.tick}, {identityTuple.selected_agent_id || selectedAgentId})</div>
        {!projectionOk ? <div className="bad">{frame.mind?.reason || frame.observer?.projection_reason || 'Projection unavailable — refusing stale agent data'}</div> : null}
        {mindCross ? <div className="bad">REFUSING DISPLAY — mind source {mindSource} ≠ selected {selectedAgentId}</div> : null}
      </div>
      <div className="toolbar-row" style={{marginTop:8}}>
        {['AGENT A', 'AGENT B'].map((labelText, i) =>
          <button key={labelText} className={(selectedAgentId === `agent_${i}`) ? 'active' : ''}
            onClick={() => selectObserverAgent(i)}>{labelText}</button>)}
        <button className={compareMind ? 'active' : ''} onClick={() => setCompareMind(v => !v)}>COMPARE A | B</button>
      </div>
    </Card>
    {compareMind ? <Card title="COMPARE A | B (same tick, read-only)" className="wide">
      {!compareBundle.ok ? <div className="na">{compareBundle.reason || 'COMPARE unavailable for this frame'}</div> : (
      <div className="dashboard-grid">
        <div className="subtle">tick {compareBundle.tick} · generation {compareBundle.generation ?? '—'} · both sides from the same frozen frame</div>
        {(['agent_0','agent_1'] as const).map(aid => {
          const proj = aid === 'agent_0' ? compareBundle.agent_0 : compareBundle.agent_1;
          const m = proj.mind || {};
          return <div key={aid} className="science-card" style={{padding:8}}>
            <b>{aid}</b> · seed {proj.agent_seed ?? '—'} · tick {proj.tick} · body {proj.body_id}
            <div className="subtle">mind source {m.source_agent_id || 'NOT AVAILABLE'}</div>
            <KV name="Selected action" value={proj.physical?.selected_action || m.action?.selected}/>
            <KV name="Selection source" value={m.action?.source}/>
            <KV name="Prediction matches" value={(m.action?.prediction_matches || []).length}/>
            <KV name="Prospective compositions" value={m.metrics?.prospective_compositions}/>
            <KV name="Memory keys" value={Object.keys(m.memory || {}).length}/>
            <KV name="Prediction error" value={m.metrics?.prediction_error ?? m.metrics?.last_prediction_error}/>
            <KV name="Instrumental acquired" value={m.instrumental_observation?.acquired ?? m.metrics?.instrumental_acquired}/>
            <KV name="Instrumental later used" value={m.instrumental_observation?.later_used ?? m.metrics?.instrumental_later_used}/>
            <div className="subtle">Signals: see Signal forensics for selected agent (not communication).</div>
          </div>;
        })}
      </div>)}
    </Card> : null}
    {!mindUnavailable ? <>
    <Card title="Cognition pipeline" className="wide">
      <div className="pipeline-grid">{(frame.cognition_pipeline?.stages || []).map((s: any) =>
        <div key={s.stage}><b>{s.stage}</b><Status value={s.status}/>{s.experimental ? <small> EXPERIMENTAL</small> : null}</div>)}
      </div>
      <div className="subtle">{frame.cognition_pipeline?.note}</div>
    </Card>
    {['memory','predictive_organization','prospection','instrumental_observation','metrics','causal_trace'].map(k =>
      <Card title={label(k)} key={k}>{frame.mind?.[k] == null ? <div className="na">NOT AVAILABLE</div> : <EvidenceTree value={frame.mind?.[k]}/>}</Card>)}
    <Card title="Action receipt">{frame.mind?.action == null ? <div className="na">NOT AVAILABLE</div> : <EvidenceTree value={frame.mind?.action}/>}</Card>
    <Card title="Bridges">{frame.mind?.bridges == null ? <div className="na">BRIDGE MISSING / NOT AVAILABLE</div> : <EvidenceTree value={frame.mind?.bridges}/>}</Card>
    <Card title="Signal forensics (selected agent)" className="wide">
      <div className="subtle">{frame.signal_forensics?.note || 'Physical signals only — not communication.'}</div>
      <h4>SIGNALS EMITTED</h4>
      {(frame.signal_forensics?.signals_emitted || []).length ? ((frame.signal_forensics?.signals_emitted || []).map((r:any,i:number) =>
        <div key={i} className="subtle">t{r.tick} {r.agent} {r.channel} inten={show(r.intensity)} counterparty={r.counterparty || 'UNKNOWN'} · {r.pairing}</div>
      )) : <div className="na">NONE / NOT RECORDED</div>}
      <h4>SIGNALS RECEIVED</h4>
      {(frame.signal_forensics?.signals_received || []).length ? ((frame.signal_forensics?.signals_received || []).map((r:any,i:number) =>
        <div key={i} className="subtle">t{r.tick} {r.agent} {r.channel} inten={show(r.intensity)} source={r.counterparty || r.source || 'UNKNOWN'} · {r.pairing}</div>
      )) : <div className="na">NONE / NOT RECORDED</div>}
    </Card>
    <Card title="Active cognition mechanisms" className="wide">
      <div className="mechanism-grid">{mechanisms.filter(m => m.category === 'COGNITION').map(m =>
        <div key={m.id}><b>{m.label}</b><Status value={m.enabled ? 'ON' : 'ABLATED'}/><small>{m.scientific_status}</small></div>)}</div>
    </Card>
    </> : <Card title="Mind" className="wide"><div className="na">{frame.mind?.reason || frame.mind?.status || 'NOT AVAILABLE'}</div></Card>}
  </div>;

  const visibleEvents = events.filter((e) => {
    if (eventFilter !== 'ALL' && eventCategory(e.type || e.kind) !== eventFilter) return false;
    if (agentEventFilter === 'ALL AGENTS') return true;
    const want = agentEventFilter === 'AGENT_0' ? 'agent_0' : 'agent_1';
    const id = e.actor_agent_id || e.agent_id || e.emitter_agent_id || e.receiver_agent_id;
    return id === want;
  });
  const displayEvents = compressConsecutiveEvents(visibleEvents);
  const timelineTab = <div className="timeline-layout">
    <Card title={`Structured events (${displayEvents.length} shown / ${visibleEvents.length} matched / ${events.length} raw, bounded)`}>
      <div className="inspecting-banner" style={{marginBottom:8}}>
        <strong>INSPECTING: {String(selectedAgentId).toUpperCase()}</strong>
        <span> · tick {header.tick} · gen {header.runtime_generation ?? '—'}</span>
      </div>
      <div className="toolbar-row">
        {EVENT_FILTERS.map(f => <button key={f} className={eventFilter===f?'active':''} onClick={() => setEventFilter(f)}>{f}</button>)}
      </div>
      <div className="toolbar-row">
        {AGENT_EVENT_FILTERS.map(f => <button key={f} className={agentEventFilter===f?'active':''} onClick={() => setAgentEventFilter(f)}>{f}</button>)}
      </div>
      <div className="event-list">{displayEvents.map((e, i) => <button key={`${e._tick_start}-${e.type || e.kind}-${e.agent_id}-${i}`} onClick={() => {
        setSelectedEvent(e); inspect(Number(e._tick_end ?? e.tick));
      }}><span>t{e._count && e._count > 1 ? `${e._tick_start}–${e._tick_end}` : e.tick}</span><b>{label(e.type || e.kind || 'event')}</b>
        <small>{compressedEventSummary(e) || signalEventSummary(e)}</small>
      </button>)}</div>
    </Card>
    <Card title="Event details / evidence">
      {!selectedEvent ? <div className="empty">Select an event</div> : <>
        <KV name="Type" value={selectedEvent.type || selectedEvent.kind}/>
        <KV name="Tick" value={selectedEvent._count && selectedEvent._count > 1
          ? `${selectedEvent._tick_start}–${selectedEvent._tick_end} (${selectedEvent._count} consecutive)`
          : selectedEvent.tick}/>
        <KV name="Agent" value={selectedEvent.actor_agent_id || selectedEvent.agent_id || '—'}/>
        <KV name="Selected action" value={selectedEvent.evidence?.selected_action || selectedEvent.evidence?.action || '—'}/>
        <KV name="Selection source" value={selectedEvent.evidence?.selection_source || '—'}/>
        {(selectedEvent.evidence?.candidate_count != null) && (
          <KV name="Candidate count" value={selectedEvent.evidence.candidate_count}/>
        )}
        {(selectedEvent.evidence?.outcome_class != null) && (
          <KV name="Competition outcome" value={selectedEvent.evidence.outcome_class}/>
        )}
        <SignalEventDetails event={selectedEvent}/>
        <h4>Evidence payload</h4>
        <EvidenceTree value={selectedEvent.evidence != null ? selectedEvent.evidence : selectedEvent}/>
      </>}
    </Card>
    <Card title="Recorded frames">
      <div className="event-list">{timeline.map((e, i) => <button key={`${e.tick}-${i}`} onClick={() => inspect(Number(e.tick))}>
        <span>t{e.tick}</span><b>{e.action || '—'}</b><small>{e.agent_id || ''}</small></button>)}</div>
      <div className="toolbar-row">
        <button onClick={() => Number.isFinite(recordedTick) && inspect(recordedTick)}>Inspect newest</button>
        <button onClick={() => {
          replayIndex.current = Math.max(0, timeline.length - 1);
          if (timeline[replayIndex.current]) inspect(Number(timeline[replayIndex.current].tick), true);
        }}>Replay newest</button>
      </div>
    </Card>
  </div>;

  const filteredMechanisms = mechanisms.filter(m =>
    !mechanismQuery || `${m.id} ${m.label} ${m.category} ${m.description}`.toLowerCase().includes(mechanismQuery.toLowerCase()));

  const experiment = frame.experiment || {};
  const experimentTab = <div className="dashboard-grid">
    <Card title="Run setup">
      <label>Preset<select value={preset} onChange={e => setPreset(e.target.value)}>
        <option>MM 1.0 — Tiktaalik</option><option>CUSTOM</option>
      </select></label>
      <label>Seed<input value={seed} onChange={e => setSeed(e.target.value)}/></label>
      <label>Width<input value={width} onChange={e => setWidth(e.target.value)}/></label>
      <label>Height<input value={height} onChange={e => setHeight(e.target.value)}/></label>
      <label>Boundary<select><option>WRAP_PERIODIC</option><option disabled>CLOSED — UNSUPPORTED</option><option disabled>OPEN — UNSUPPORTED</option></select></label>
      <label>Target tick<input value={targetTick} onChange={e => setTargetTick(e.target.value)} placeholder="∞"/></label>
      <label>Observer Hz<input value={uiHz} onChange={e => setUiHz(e.target.value)}/></label>
      <label>History frames<input value={bufferCapacity} onChange={e => setBufferCapacity(e.target.value)}/></label>
      <label>Body mass<input value={bodyMass} onChange={e => { setBodyMass(e.target.value); setPreset('CUSTOM'); }}/></label>
      <label>Body v_max<input value={bodyVMax} onChange={e => { setBodyVMax(e.target.value); setPreset('CUSTOM'); }}/></label>
      <label className="check"><input type="checkbox" checked={cognitionEnabled} onChange={e => { setCognitionEnabled(e.target.checked); setPreset('CUSTOM'); }}/>Cognition enabled</label>
      <label className="check"><input type="checkbox" checked={twoAgentExperimental} onChange={e => { setTwoAgentExperimental(e.target.checked); setPreset('CUSTOM'); }}/>Experimental two-agent runtime (default OFF)</label>
      <div className="subtle">Apply rebuilds the live runtime. Two-agent is experimental and not Tiktaalik canonical default. Observer Hz/history frames are session capture bounds, not MM physics. Body mass/v_max require reset.</div>
      <button onClick={async () => {
        const payload: any = {
          seed: +seed,
          cognition_enabled: cognitionEnabled,
          world: { width: +width, height: +height, boundary_mode: 'WRAP_PERIODIC' },
          agent_body: { mass: +bodyMass, v_max: +bodyVMax },
        };
        if (twoAgentExperimental) payload.agent_count = 2;
        if (targetTick.trim() !== '' && Number.isFinite(+targetTick)) payload.target_tick = +targetTick;
        if (Number.isFinite(+uiHz)) payload.ui_hz = +uiHz;
        if (Number.isFinite(+bufferCapacity)) payload.buffer_capacity = Math.max(8, +bufferCapacity);
        const f = await applyExperiment(payload);
        setControlMessage(f.control_receipt);
        {
          const agent = desiredAgentIdRef.current || requestedAgentId(f);
          const projected = applyProjectionToFrame(f, agent);
          setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
        }
      }}>Apply & reset actual runtime</button>
    </Card>
    <Card title="Current experiment">
      <KV name="Runtime" value={experiment.runtime?.type}/>
      <KV name="Agent count" value={experiment.runtime?.agent_count}/>
      <KV name="Selected observer agent" value={experiment.runtime?.selected_agent}/>
      <KV name="Cognition" value={experiment.runtime?.cognition_enabled ? 'ON' : 'OFF'}/>
      <KV name="Seed" value={experiment.seed}/>
      <KV name="Observer Hz" value={experiment.observer?.ui_hz}/>
      <KV name="History frames" value={experiment.observer?.buffer_capacity}/>
      <KV name="Body mass" value={experiment.agent_body?.mass}/>
      <KV name="Body v_max" value={experiment.agent_body?.v_max}/>
      <div className="subtle">Available actions: {(experiment.actions_available || []).join(', ') || '—'}</div>
      <div className="availability">Bridge missing: {(experiment.actions_bridge_missing || []).join(', ') || 'none'}</div>
      <div className="subtle">{experiment.world?.supported_size_notes || experiment.note}</div>
    </Card>
    {experiment.observer_ground_truth?.enabled ? <Card title="OBSERVER GROUND TRUTH / EXPERIMENT">
      <div className="availability">Experimenter-only. Not present in agent observation or cognition.</div>
      <KV name="Climate ecology" value="ON"/>
      <KV name="Environmental cycle phase" value={Number(experiment.observer_ground_truth.environmental_cycle_phase).toFixed(3)}/>
      <KV name="Cycle index" value={experiment.observer_ground_truth.environmental_cycle_index}/>
      <KV name="Cycle period" value={experiment.observer_ground_truth.environmental_cycle_period}/>
      <KV name="Cycle mode" value={experiment.observer_ground_truth.environmental_cycle_mode}/>
      <KV name="Resource cycle phase" value={Number(experiment.observer_ground_truth.resource_cycle_phase).toFixed(3)}/>
      <KV name="T north / mid / south" value={`${Number(experiment.observer_ground_truth.T_north_mean).toFixed(3)} / ${Number(experiment.observer_ground_truth.T_mid_mean).toFixed(3)} / ${Number(experiment.observer_ground_truth.T_south_mean).toFixed(3)}`}/>
      <KV name="R_A max y" value={experiment.observer_ground_truth.R_A_max_y}/>
      <KV name="R_B max y" value={experiment.observer_ground_truth.R_B_max_y}/>
    </Card> : null}
    <Card title="Runtime mechanisms" className="wide">
      <label>Search<input value={mechanismQuery} onChange={e => setMechanismQuery(e.target.value)} placeholder="id, label, category"/></label>
      <div className="mechanism-list">{filteredMechanisms.map(m => <div key={m.id}>
        <div><b>{m.label}</b><small>{m.promotion_class || '—'} · {m.category} · {m.scientific_status} · {m.toggle_policy}</small></div>
        <button disabled={!m.ablatable} onClick={() => toggleMechanism(m)}>{m.ablatable ? (m.enabled ? 'ON' : 'OFF') : 'READ ONLY'}</button>
        <p>{m.description}</p><p>Dependencies: {m.dependencies?.join(', ') || 'none'}</p>
      </div>)}</div>
    </Card>
    <Card title="Snapshot">
      <KV name="Schema" value={snapshotMeta?.schema}/>
      <KV name="Tick" value={snapshotMeta?.tick}/>
      <KV name="Generation" value={snapshotMeta?.runtime_generation}/>
      <div className="subtle">Keys: {(snapshotMeta?.config_keys || []).join(', ') || '—'}</div>
      <div className="subtle">{snapshotMeta?.durable_path}</div>
      <button onClick={async () => {
        const snap = await getSnapshot();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([JSON.stringify(snap, null, 2)], {type:'application/json'}));
        a.download = `mm_snapshot_t${snap.tick}.json`; a.click();
        setSnapshotMeta(await getSnapshotMeta().catch(() => snapshotMeta));
      }}>Download v2 snapshot</button>
      <label className="file">Restore snapshot (replaces live runtime)
        <input type="file" accept=".json" onChange={async e => {
          const file = e.target.files?.[0]; if (!file || !confirm('Replace the current live runtime?')) return;
          const payload = JSON.parse(await file.text());
          if (payload?.schema !== 'mm.physical_system.snapshot.v2') {
            setControlMessage({ operation: 'RESTORE_SNAPSHOT', accepted: false, tick: header.tick, reason: 'unsupported or missing snapshot schema' });
            return;
          }
          const f = await fetch('/api/snapshot/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(r=>r.json());
          setControlMessage(f.control_receipt);
        {
          const agent = desiredAgentIdRef.current || requestedAgentId(f);
          const projected = applyProjectionToFrame(f, agent);
          setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
        }
        }}/>
      </label>
      <div className="subtle">{snapshotMeta?.historical_policy || 'Missing newer keys activate documented historical compatibility behavior.'}</div>
    </Card>
  </div>;

  const series = frame.telemetry?.series || [];
  const dataTab = <div className="dashboard-grid">
    <Card title="Mechanical work reservoir" className="wide">
      <Spark values={series.map((x:any)=>x.work_reservoir)}/>
      <div className="stack-bar"><i style={{ width: `${Math.min(100, (reservoir / reservoirMax) * 100)}%` }}/></div>
      <div className="subtle">Fill {num(reservoir, 4)} / {num(reservoirMax, 4)}</div>
    </Card>
    <Card title="Resource A/B stores"><Spark values={series.map((x:any)=>x.resource_A)}/><Spark values={series.map((x:any)=>x.resource_B)} second/></Card>
    <Card title="Velocity / omega"><Spark values={series.map((x:any)=>x.speed)}/><Spark values={series.map((x:any)=>x.omega)} second/></Card>
    <Card title="Retention">
      <KV name="Frames" value={timeline.length}/><KV name="Trajectory capacity" value={frame.trajectory?.capacity}/>
      <KV name="Telemetry capacity" value={frame.telemetry?.capacity}/><KV name="Events shown" value={events.length}/>
    </Card>
    <Card title="Result packs (catalog only)" className="wide">
      <div className="pack-grid">{packs.slice(-30).map(p => <div key={p.id}><b>{p.id}</b><span>{p.promoted === true ? 'PROMOTED' : p.promoted === false ? 'NOT PROMOTED' : 'NO PROMOTION RECORD'}</span></div>)}</div>
      <div className="availability">Analyzer: NOT YET INTEGRATED</div>
    </Card>
    <Card title="CURRENT causal gearbox" className="wide">
      <div className="structured">{(gearbox?.integrated?.edges || []).map((e:any,i:number) =>
        <button className={selectedEdge === e ? 'active edge-row' : 'edge-row'} key={i} onClick={() => setSelectedEdge(e)}>
          <span>{e.edge || `${e.from} → ${e.to}`}</span><strong>{e.level} · {e.provenance || e.type}</strong>
        </button>)}
      </div>
      {selectedEdge && <Structured value={selectedEdge}/>}
      {!gearbox?.integrated && <div className="empty">NOT AVAILABLE</div>}
    </Card>
  </div>;

  const content = frame.error ? <Card title="Recorded frame"><div className="availability">{frame.error}: {frame.reason || 'tick not in bounded buffer'}</div></Card>
    : tab === 'WORLD' ? worldWithInspector : tab === 'AGENT' ? agentTab : tab === 'MIND' ? mindTab :
    tab === 'TIMELINE' ? timelineTab : tab === 'EXPERIMENT' ? experimentTab
    : tab === 'ANALYZE RESULTS' ? <AnalyzeResultsPanel
        analysis={runAnalysis}
        onCopy={async () => {
          const text = runAnalysis?.analysis_log || '';
          try {
            await navigator.clipboard.writeText(text);
            setAnalysisCopyMsg('Analysis log copied to clipboard');
          } catch {
            setAnalysisCopyMsg('Clipboard unavailable — use Download');
          }
        }}
        onDownload={() => {
          const text = runAnalysis?.analysis_log || '';
          const a = document.createElement('a');
          a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
          a.download = `mm_run_analysis_t${runAnalysis?.generated_at_tick ?? 0}.txt`;
          a.click();
        }}
        onInspectTick={(t) => { inspect(t); setTab('TIMELINE'); }}
      />
    : tab === 'OVERVIEW' ? <OverviewPanel
        runs={archivedRuns}
        currentRunId={currentRunId}
        openRunId={openRunId}
        setOpenRunId={setOpenRunId}
        filter={overviewFilter}
        setFilter={setOverviewFilter}
        agentFilter={overviewAgentFilter}
        setAgentFilter={setOverviewAgentFilter}
        onInspectTick={(t) => { inspect(t); setTab('WORLD'); }}
        onViewEvidence={(card) => {
          setEventFilter(card.category === 'SIGNAL' ? 'SIGNAL'
            : card.category === 'ACTION' ? 'ACTION'
            : card.category === 'COGNITION' ? 'COGNITION'
            : card.category === 'RESOURCE' ? 'RESOURCE'
            : card.category === 'BODY' ? 'BODY'
            : 'ALL');
          inspect(card.evidence.frame_tick ?? card.tick_start);
          setTab('TIMELINE');
        }}
        onAnalysisLog={(run) => {
          const text = run.analysis.analysis_log || '';
          navigator.clipboard?.writeText(text).then(() => setAnalysisCopyMsg(`Run #${run.run_number} analysis log copied`)).catch(() => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
            a.download = `mm_run_${run.run_number}_analysis.txt`;
            a.click();
          });
        }}
      />
    : dataTab;

  return <div className="app">
    {identity}
    {historical?.active && <div className="control-receipt warn-banner">
      HISTORICAL COMPATIBILITY: missing { (historical.missing_mechanism_keys || []).join(', ') || 'newer keys' } restore documented OFF/free behavior
    </div>}
    <div className="nav">
      <div className="tabs">{TABS.map(t => <button key={t} className={tab===t?'active':''} onClick={()=>{
        setTab(t);
        if (t === 'ANALYZE RESULTS' || t === 'OVERVIEW') rebuildAnalysis({ frame: liveFrame ?? viewFrame ?? undefined });
      }}>{t}</button>)}</div>
      <div className="controls">
        <button className={mode==='LIVE'?'active':''} onClick={()=>{setMode('LIVE');setViewFrame(liveFrame)}}>LIVE</button>
        <button className={mode==='INSPECT'?'active':''} onClick={() => Number.isFinite(recordedTick) ? inspect(recordedTick) : undefined}>INSPECT</button>
        <button className={mode==='REPLAY'?'active':''} onClick={() => Number.isFinite(recordedTick) ? inspect(recordedTick, true) : undefined}>REPLAY</button>
        <button onClick={()=>control('play')} disabled={!!finalizing}>Play</button>
        <button onClick={()=>control('pause')} disabled={!!finalizing}>Pause</button>
        <button onClick={()=>control('step',{n:1})} disabled={!!finalizing}>Step</button>
        <button onClick={openStopDialog} disabled={!!finalizing}>Stop</button>
        <button onClick={()=>control('reset')} disabled={!!finalizing}>Reset</button>
        <select
          value={String(header.simulation_speed ?? 1)}
          title="Simulation speed controls wall-clock execution rate. All scientific ticks are still executed. Observer rendering may be sampled at high speeds."
          onChange={e=>control('speed',{speed:+e.target.value})}
        >{SPEEDS.map(s=><option key={s} value={s}>{s===50?'MAX':`${s}×`}</option>)}</select>
        {(header.sim_ticks_per_sec != null || header.observer_fps != null) && (
          <span className="meta-extra" style={{alignSelf:'center'}} title="SIM = scientific ticks/sec · OBS = observer frames/sec">
            {header.simulation_speed === 50 ? 'MAX' : `${header.simulation_speed ?? 1}×`}
            {header.sim_ticks_per_sec != null ? ` · SIM ${header.sim_ticks_per_sec} t/s` : ''}
            {header.observer_fps != null ? ` · OBS ${header.observer_fps} fps` : ''}
          </span>
        )}
        <button onClick={()=>setRawOpen(!rawOpen)}>Advanced / Raw</button>
      </div>
    </div>
    {finalizing && <div className="control-receipt warn-banner">{finalizing}</div>}
    {saveBanner && !saveBanner.failed && !saveBanner.discarded && <div className="control-receipt ok">
      SAVED · t{saveBanner.tick} · verified snapshot tick: {saveBanner.tick}
      {saveBanner.seed != null ? ` · Seed ${saveBanner.seed}` : ''}
      <div className="subtle">Path: {saveBanner.path}</div>
    </div>}
    {saveBanner?.failed && <div className="control-receipt bad">
      SAVE_FAILED — {saveBanner.error}. Live state preserved; try Save & Stop again.
    </div>}
    {saveBanner?.discarded && <div className="control-receipt warn-banner">
      Stopped without saving ({saveBanner.reason}). No completed run artifact was written.
    </div>}
    {stopDialog && <div className="stop-dialog-backdrop" style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div className="panel" style={{ minWidth: 360, maxWidth: 480, padding: 16 }}>
        <h3>Stop simulation?</h3>
        <div className="metric"><span>Current tick</span><strong>{stopDialog.tick}</strong></div>
        <div className="metric"><span>Seed</span><strong>{stopDialog.seed}</strong></div>
        <div className="metric"><span>Runtime</span><strong>{stopDialog.runtime}</strong></div>
        <div className="metric"><span>Agents</span><strong>{stopDialog.agent_count}</strong></div>
        {!stopConfirmNoSave ? (
          <div className="toolbar-row" style={{ marginTop: 12, gap: 8, flexWrap: 'wrap' }}>
            <button className="active" onClick={saveAndStop}>Save &amp; Stop</button>
            <button onClick={stopWithoutSaving}>Stop without saving</button>
            <button onClick={() => { setStopDialog(null); setStopConfirmNoSave(false); }}>Cancel</button>
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            <div className="availability">This discards the unsaved experiment. Confirm?</div>
            <div className="toolbar-row" style={{ marginTop: 8, gap: 8 }}>
              <button className="bad" onClick={stopWithoutSaving}>Confirm discard</button>
              <button onClick={() => setStopConfirmNoSave(false)}>Back</button>
              <button onClick={() => { setStopDialog(null); setStopConfirmNoSave(false); }}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>}
    {analysisCopyMsg && <div className="control-receipt ok">{analysisCopyMsg}</div>}
    {controlMessage && <div className={`control-receipt ${controlMessage.accepted?'ok':'bad'}`}>
      {controlMessage.operation}: {controlMessage.accepted?'ACCEPTED':'REJECTED'} · t{controlMessage.verified_final_tick ?? controlMessage.tick}
      {controlMessage.reason ? ` · ${controlMessage.reason}` : ''}
    </div>}
    <div className="main">{content}</div>
    {rawOpen && <div className="raw-drawer"><button onClick={()=>setRawOpen(false)}>Close</button><pre>{JSON.stringify(frame,null,2)}</pre></div>}
  </div>;
}

function signalEventSummary(e: any): string {
  const et = String(e?.type || e?.kind || '');
  const ev = e?.evidence || {};
  if (et.includes('SIGNAL_EMITTED')) {
    const body = e.emitter_body_id || ev.emitter_body_id || e.body_id || 'UNKNOWN';
    const ch = ev.channel || e.channel || '?';
    const field = String(ch).startsWith('FIELD_') ? ch : `FIELD_${ch}`;
    const a = ev.contact_entity_a_id;
    const b = ev.contact_entity_b_id;
    const contact = a && b ? ` · contact: ${a} × ${b}` : '';
    return `${body} → ${field}${contact}`;
  }
  if (et.includes('SIGNAL_RECEIVED')) {
    const body = e.receiver_body_id || ev.receiver_body_id || e.body_id || 'UNKNOWN';
    const chA = Number(ev['local.FIELD_A'] || 0) > 0;
    const chB = Number(ev['local.FIELD_B'] || 0) > 0;
    const field = chB && !chA ? 'FIELD_B' : chA && !chB ? 'FIELD_A' : 'FIELD_*';
    const attr = e.source_attribution || ev.source_attribution || 'UNKNOWN';
    const parents = (e.causal_parent_ids || ev.causal_parent_ids || []).length;
    return `${body} ← ${field} · source: ${attr}${parents ? ` · parents:${parents}` : ''}`;
  }
  const bits = [
    e.actor_agent_id || e.agent_id || '',
    e.receiver_agent_id ? `→ ${e.receiver_agent_id}` : '',
    e.source_agent_id ? `src=${e.source_agent_id}` : '',
  ].filter(Boolean);
  return bits.join(' ');
}

function SignalEventDetails({ event }: { event: any }) {
  const et = String(event?.type || event?.kind || '');
  const ev = event?.evidence || {};
  if (et.includes('SIGNAL_EMITTED')) {
    return <>
      <KV name="Channel" value={ev.channel || '—'}/>
      <KV name="Trigger" value={ev.trigger || '—'}/>
      <h4>PHYSICAL ORIGIN</h4>
      <KV name="Origin kind" value={ev.origin_kind || 'NOT_RECORDED'}/>
      <KV name="Origin id" value={ev.origin_id || 'NOT_RECORDED'}/>
      <h4>EMITTER</h4>
      <KV name="Agent" value={event.emitter_agent_id || ev.emitter_agent_id || 'UNKNOWN'}/>
      <KV name="Body" value={event.emitter_body_id || ev.emitter_body_id || ev.body_id || 'UNKNOWN'}/>
      <KV name="Component" value={ev.emitter_component_id || 'NOT_RECORDED'}/>
      {(ev.contact_entity_a_id || ev.contact_entity_b_id) ? <>
        <h4>CONTACT</h4>
        <KV name="Entity A" value={`${ev.contact_entity_a_kind || '?'} ${ev.contact_entity_a_id || '—'}`}/>
        <KV name="Entity B" value={`${ev.contact_entity_b_kind || '?'} ${ev.contact_entity_b_id || '—'}`}/>
        <KV name="Position" value={ev.x != null ? [ev.x, ev.y] : (ev.overlap_cells || '—')}/>
        <KV name="COM distance" value={ev.com_distance}/>
        <KV name="Realized amplitude" value={ev.realized}/>
        <KV name="Physical quantity" value={ev.physical_quantity ? `${ev.physical_quantity}=${ev.physical_quantity_value}` : '—'}/>
      </> : null}
      <h4>OBSERVATION</h4>
      <KV name="Observer source" value={event.observer_source_id || ev.observer_source_id || '—'}/>
      <h4>CAUSAL IDENTITY</h4>
      <KV name="Emission id" value={ev.emission_id || 'NOT_RECORDED'}/>
      <KV name="Parent event id" value={ev.parent_event_id || 'NOT_RECORDED'}/>
      <div className="subtle">Physical signal ≠ message. Observer source ≠ emitter.</div>
    </>;
  }
  if (et.includes('SIGNAL_RECEIVED')) {
    return <>
      <h4>RECEIVER</h4>
      <KV name="Agent" value={event.receiver_agent_id || ev.receiver_agent_id || '—'}/>
      <KV name="Body" value={event.receiver_body_id || ev.receiver_body_id || ev.body_id || '—'}/>
      <KV name="local.FIELD_A" value={ev['local.FIELD_A']}/>
      <KV name="local.FIELD_B" value={ev['local.FIELD_B']}/>
      <h4>SOURCE PROVENANCE</h4>
      <KV name="Source attribution" value={event.source_attribution || ev.source_attribution || 'NOT_RECORDED'}/>
      <KV name="Source agent" value={event.source_agent_id || ev.source_agent_id || 'UNKNOWN'}/>
      <KV name="Source body" value={ev.source_body_id || 'UNKNOWN'}/>
      <KV name="Origin kind" value={ev.source_origin_kind || 'NOT_RECORDED'}/>
      <KV name="Origin id" value={ev.source_origin_id || 'NOT_RECORDED'}/>
      <KV name="Emission/parent ids" value={(event.causal_parent_ids || ev.causal_parent_ids || []).join(', ') || 'NONE'}/>
      <KV name="Source note" value={ev.source || '—'}/>
      {(event.contributing_emissions_this_tick || ev.contributing_emissions_this_tick || []).length ? <>
        <h4>SAME-TICK CONTRIBUTING EMISSIONS</h4>
        <EvidenceTree value={event.contributing_emissions_this_tick || ev.contributing_emissions_this_tick}/>
      </> : null}
      <h4>OBSERVATION</h4>
      <KV name="Observer source" value={event.observer_source_id || ev.observer_source_id || '—'}/>
      <div className="subtle">Continuum field superposition — unique emitter not assumed.</div>
    </>;
  }
  return <>
    <KV name="Actor" value={event.actor_agent_id || event.agent_id}/>
    <KV name="Emitter" value={event.emitter_agent_id}/>
    <KV name="Receiver" value={event.receiver_agent_id}/>
    <KV name="Source" value={event.source_agent_id || event.evidence?.source_agent_id || event.evidence?.source || '—'}/>
    <KV name="Body" value={event.body_id || event.evidence?.body_id}/>
  </>;
}

function EvidenceTree({ value, depth = 0 }: { value: any; depth?: number }) {
  if (value === null) return <div className="kv">null</div>;
  if (value === undefined) return <div className="na">NOT AVAILABLE</div>;
  if (typeof value === 'boolean') return <div className="kv">{value ? 'true' : 'false'}</div>;
  if (typeof value === 'number' || typeof value === 'string') return <div className="kv">{String(value)}</div>;
  if (Array.isArray(value)) {
    if (!value.length) return <div className="na">[]</div>;
    return <div className="structured" style={{ marginLeft: depth ? 8 : 0 }}>
      {value.slice(0, 40).map((item, i) => (
        <div key={i}><span>[{i}]</span><EvidenceTree value={item} depth={depth + 1} /></div>
      ))}
      {value.length > 40 ? <div className="subtle">… {value.length - 40} more</div> : null}
    </div>;
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (!entries.length) return <div className="na">{'{}'}</div>;
    return <div className="structured" style={{ marginLeft: depth ? 8 : 0 }}>
      {entries.map(([k, v]) => (
        <div key={k} style={{ marginBottom: 4 }}>
          <span>{label(String(k))}</span>
          {v !== null && typeof v === 'object' ? <EvidenceTree value={v} depth={depth + 1} /> : <strong>{v === null ? 'null' : String(v)}</strong>}
        </div>
      ))}
    </div>;
  }
  return <div className="kv">{String(value)}</div>;
}
function Structured({ value }: { value: any }) {
  return <EvidenceTree value={value} />;
}
function Spark({ values, second=false }: { values:number[]; second?:boolean }) {
  const clean=values.map(Number).filter(Number.isFinite); if(!clean.length)return <div className="empty">No recorded samples</div>;
  const lo=Math.min(...clean), hi=Math.max(...clean), d=Math.max(1e-12,hi-lo);
  const pts=clean.map((v,i)=>`${(i/Math.max(1,clean.length-1))*300},${58-((v-lo)/d)*52}`).join(' ');
  return <svg className="spark" viewBox="0 0 300 64" preserveAspectRatio="none"><polyline className={second?'second':''} points={pts}/></svg>;
}
