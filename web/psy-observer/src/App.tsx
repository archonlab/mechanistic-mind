import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import './styles/app.css';
import type { ObserverFrame, ViewMode } from './types';
import { ObserverHeader } from './chrome/ObserverHeader';
import { LifecycleBanners } from './chrome/LifecycleBanners';
import { RunWorkspace } from './workspaces/RunWorkspace';
import { InspectWorkspace } from './workspaces/InspectWorkspace';
import { InspectorAccordion } from './inspectors/primitives';
import { AnalyzeWorkspace } from './workspaces/AnalyzeWorkspace';
import { AuxPollDriver, ClockDriver, InterestDriver } from './observer/drivers';
import {
  frameStore,
  lifecycleStore,
  inspectorUiStore,
  noteRender,
  slimStatusFromFrame,
  statusStore,
  workspaceStore,
} from './observer/stores';
import { applyRailDestination, railSelectedTool } from './observer/railNav';
import { useWorkspaceStore } from './observer/useExternalStore';
import {
  applyExperiment, applyLiveIntervention, connectLive, getSnapshot, getSnapshotMeta, getState, getTimeline,
  getStopInfo, getSaveJob, inspectTick, postControl, replayTick,
  listRuns, saveAnalysisReport,
  startAnalysisJob, getAnalysisJob, getAnalysisJobResult,
  setGeometryAgentFilter, getGeometryCell, hydrateGeometryRun,
  geometryUseLive, geometryClearSaved,
} from './api/client';
import { mergeMechanismWarmState } from './lifecycleReceipt';
import { WorldMap } from './components/WorldMap';
import { GeometryPanel } from './components/GeometryPanel';
import { SignalContextPanel } from './components/SignalContextPanel';
import { ObserveV2Panel } from './components/ObserveV2Panel';
import { InteractPanel } from './components/InteractPanel';
import { useExperimenterKeyboard } from './useExperimenterKeyboard';
import {
  fetchEmpiricalIfMissing,
  mergeGeoTransportIntoFrame,
  resetGeoEmpiricalCache,
} from './geoCache';
import { ActionDecisionInspector } from './components/ActionDecisionInspector';
import { MotionCausalInspector } from './components/MotionCausalInspector';
import { WhyDidItRotate } from './components/WhyDidItRotate';
import { NearFieldSensorPanel } from './components/NearFieldSensorPanel';
import {
  VisionExperimenterControl,
  visionRowFromIntegrity,
} from './components/VisionExperimenterControl';
import { VestibularProprioceptionPanel } from './components/VestibularProprioceptionPanel';
import { OscillatorySignalingPanel } from './components/OscillatorySignalingPanel';
import { SensorimotorConsequencePanel } from './components/SensorimotorConsequencePanel';
import { HistoricalSensorimotorSelectionPanel } from './components/HistoricalSensorimotorSelectionPanel';
import { SignalSensorimotorPanel } from './components/SignalSensorimotorPanel';
import { PscMotorResolutionControl } from './components/PscMotorResolutionControl';
import { ContextualProspectiveControlPanel } from './components/ContextualProspectiveControlPanel';
import { MechanismPreflightPanel } from './components/MechanismPreflightPanel';
import { WhyDidItsShapeChange } from './components/WhyDidItsShapeChange';
import { CausalChain } from './components/CausalChain';
import {
  applyProjectionToFrame,
  canonicalBodyId,
  compareViewsSameFrame,
  requestedAgentId,
  shouldAcceptLiveFrame,
} from './observerProjection';
import {
  LIVE_FE_EVENTS_DISPLAY_MAX,
  LIVE_FE_TIMELINE_DISPLAY_MAX,
  LIVE_FE_TRAJECTORY_DISPLAY_DEFAULT,
  projectLiveAuxState,
} from './liveBounds';
import { scalarGrid } from './rendererMath';
import {
  buildRunAnalysis,
  createAnalysisState,
  ingestAnalysisInput,
  shouldResetAnalysis,
  analyzeEvidencePackage,
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
import { AnalyzeResultsPanel, type AnalysisSourceMode, type RunCatalogEntry } from './components/AnalyzeResultsPanel';
import { OverviewPanel } from './components/OverviewPanel';
import { compressConsecutiveEvents, compressedEventSummary } from './eventCompression';
import { eventCategory as sharedEventCategory } from './observe/eventCategory';
import {
  invalidateEventsOnRunOrGeneration,
  observeBufferIdentityFromFrame,
  type ObserveBufferIdentity,
} from './observe/bufferIdentity';
import { ControlDevice } from './desktop/ControlDevice';
import {
  configPending, openOrFocusWindow,
} from './desktop/floatingWindows';
import { MechanismAwareSignals, VisionBars } from './desktop/liveWidgets';
import type { DeviceTool, ExperimentScreen, FloatingWindowId, FloatingWindowState } from './desktop/types';

const TABS = ['WORLD', 'INTERACT', 'AGENT', 'MIND', 'TIMELINE', 'EXPERIMENT', 'DATA', 'ANALYZE RESULTS', 'OVERVIEW'] as const;
const DESKTOP_PREFS_KEY = 'psy-observer-desktop';
const _SPEEDS = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 50];
void _SPEEDS;

function tabToExperimentScreen(tab: string): ExperimentScreen {
  if (tab === 'world') return 'set_world';
  if (tab === 'model' || tab === 'cognition') return 'set_model';
  if (tab === 'ecology') return 'set_ecology';
  if (tab === 'body') return 'set_resources';
  if (tab === 'predictive') return 'set_predictive';
  return 'experimental';
}
const EVENT_FILTERS = ['ALL', 'BODY', 'WORK', 'RESOURCE', 'ACTION', 'COGNITION', 'MATERIAL', 'SIGNAL'] as const;
const AGENT_EVENT_FILTERS = ['ALL AGENTS', 'AGENT_0', 'AGENT_1'] as const;
const PREFS_KEY = 'psy-observer-display';
const DEFAULT_LAYERS: Record<string, boolean> = {
  body: true, sites: true, trajectory: true, velocity: true, orientation: true,
  deformation: true, occupancy: false, force: false,
  // Observer-only terrain ground-truth overlays (independent of base field layer)
  terrain_potential: false, terrain_drag: false, terrain_grad: false,
  ambient_force: false, ambient_magnitude: false,
};
function loadPrefs(): any {
  try { return JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') || {}; }
  catch { return {}; }
}
function eventCategory(type: string) {
  return sharedEventCategory(type);
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
  noteRender('App');
  const prefs = loadPrefs();
  let desktopPrefs: any = {};
  try { desktopPrefs = JSON.parse(localStorage.getItem(DESKTOP_PREFS_KEY) || '{}') || {}; } catch { /* ignore */ }
  const [tab] = useState<(typeof TABS)[number]>(
    (TABS as readonly string[]).includes(prefs.tab) ? prefs.tab : 'WORLD',
  );
  const [deviceTool, setDeviceTool] = useState<DeviceTool>(desktopPrefs.tool || 'home');
  const [experimentScreen, setExperimentScreen] = useState<ExperimentScreen>('menu');
  const inspUi = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  const [deviceCollapsed, setDeviceCollapsed] = useState(
    desktopPrefs.collapsed === undefined ? true : Boolean(desktopPrefs.collapsed),
  );
  const [floatWindows, setFloatWindows] = useState<FloatingWindowState[]>([]);
  void floatWindows;
  const [simBounds, setSimBounds] = useState({ width: 800, height: 600 });
  const simWorkspaceRef = useRef<HTMLDivElement | null>(null);
  const [appliedConfig, setAppliedConfig] = useState<Record<string, string | boolean | number> | null>(null);
  const liveFrameRef = useRef<ObserverFrame | null>(null);
  const viewFrameRef = useRef<ObserverFrame | null>(null);
  const setLiveFrame = (f: ObserverFrame | null) => {
    liveFrameRef.current = f;
    if (f) {
      frameStore.setLive(f);
      const cur = statusStore.get();
      statusStore.replace(slimStatusFromFrame(f, {
        connection: cur.connection === 'CONNECTING' ? 'CONNECTED' : cur.connection,
        lastArrival: Date.now(),
        pendingApply: cur.pendingApply,
        heartbeat: cur.heartbeat,
      }));
    }
  };
  const setViewFrame = (f: ObserverFrame | null | ((prev: ObserverFrame | null) => ObserverFrame | null)) => {
    const next = typeof f === 'function' ? f(viewFrameRef.current) : f;
    viewFrameRef.current = next;
    if (next) frameStore.setView(next);
  };
  const liveFrame = liveFrameRef.current;
  const viewFrame = viewFrameRef.current;
  const [mode, setMode] = useState<ViewMode>('LIVE');
  const setConnection = (c: string) => statusStore.patch({ connection: c });
  const setLastArrival = (n: number) => statusStore.patch({ lastArrival: n });
  const setSimHeartbeat = (hb: any) => {
    if (!hb) {
      statusStore.patch({ lastArrival: Date.now() });
      return;
    }
    const patch: Record<string, unknown> = {
      heartbeat: hb,
      lastArrival: Date.now(),
    };
    if (hb.status) patch.status = String(hb.status);
    if (hb.tick != null) {
      patch.tick = hb.tick;
      patch.simTick = hb.tick;
    }
    if (hb.execution_mode != null) patch.executionMode = String(hb.execution_mode);
    if (Object.prototype.hasOwnProperty.call(hb, 'display_frozen')) {
      patch.displayFrozen = Boolean(hb.display_frozen);
    }
    if (hb.display_tick != null) patch.displayTick = hb.display_tick;
    if (hb.sim_ticks_per_sec != null) patch.simTps = hb.sim_ticks_per_sec;
    if (hb.observer_fps != null) patch.observerFps = hb.observer_fps;
    statusStore.patch(patch as any);
  };
  const setLiveApplyPending = (p: any) => statusStore.patch({ pendingApply: p });
  const connection = statusStore.get().connection;
  const lastArrival = statusStore.get().lastArrival;
  const simHeartbeat = statusStore.get().heartbeat;
  const liveApplyPending = statusStore.get().pendingApply;
  const now = 0;
  const mechanismCatalogGenRef = useRef<number | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const observeBufIdRef = useRef<ObserveBufferIdentity | null>(null);
  const [mechanisms, setMechanisms] = useState<any[]>([]);
  const [gearbox, setGearbox] = useState<any>(null);
  const [packs, setPacks] = useState<any[]>([]);
  const [snapshotMeta, setSnapshotMeta] = useState<any>(null);
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [selectedCell, setSelectedCell] = useState<any>(null);
  const [hoverCell, setHoverCell] = useState<any>(null);
  const [cellRaw, setCellRaw] = useState(false);
  const [arInspect, setArInspect] = useState<any | null>(null);
  const [geoAgentFilter, setGeoAgentFilter] = useState(prefs.geoAgentFilter || 'ALL');
  const [savedGeoRunId, setSavedGeoRunId] = useState('');
  const [selectedGeoEvent, setSelectedGeoEvent] = useState<any>(null);
  const [layer, setLayer] = useState(prefs.layer || 'T');
  const [worldView, setWorldView] = useState(prefs.worldView || 'PHYSICAL');
  const [renderMode, setRenderMode] = useState(prefs.renderMode || 'COMPOSITE');
  const [opacity, setOpacity] = useState(Number.isFinite(prefs.opacity) ? prefs.opacity : .9);
  const [showGrid, setShowGrid] = useState(Boolean(prefs.showGrid));
  const [layers, setLayers] = useState<Record<string, boolean>>({ ...DEFAULT_LAYERS, ...(prefs.layers || {}) });
  const [trajectoryLength, setTrajectoryLength] = useState(Number.isFinite(prefs.trajectoryLength) ? prefs.trajectoryLength : LIVE_FE_TRAJECTORY_DISPLAY_DEFAULT);
  const [seed, setSeed] = useState('17');
  const [width, setWidth] = useState('32');
  const [height, setHeight] = useState('32');
  const [preset, setPreset] = useState('MM 1.0 — Tiktaalik Public Beta 3');
  const [cognitionEnabled, setCognitionEnabled] = useState(true);
  const [twoAgentExperimental, setTwoAgentExperimental] = useState(true);
  const [ecologyPreset, setEcologyPreset] = useState<string>('BASELINE_CLIMATE_DEFAULT');
  const [terrainSeedOverride, setTerrainSeedOverride] = useState<string>('');
  const [targetTick, setTargetTick] = useState('');
  const [uiHz, setUiHz] = useState('10');
  const [bufferCapacity, setBufferCapacity] = useState('512');
  const [bodyMass, setBodyMass] = useState('2');
  const [bodyVMax, setBodyVMax] = useState('0.3');
  const [eventFilter, setEventFilter] = useState<(typeof EVENT_FILTERS)[number]>('ALL');
  const [agentEventFilter, setAgentEventFilter] = useState<(typeof AGENT_EVENT_FILTERS)[number]>('ALL AGENTS');
  const [compareMind, setCompareMind] = useState(false);
  const [appIdentity, setAppIdentity] = useState<any>(null);
  void appIdentity;
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
  const [analysisSource, setAnalysisSource] = useState<AnalysisSourceMode>('current');
  const [savedRunCatalog, setSavedRunCatalog] = useState<RunCatalogEntry[]>([]);
  const [selectedSavedRunId, setSelectedSavedRunId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState<string>('');
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => {
    try {
      localStorage.setItem(DESKTOP_PREFS_KEY, JSON.stringify({ tool: deviceTool, collapsed: deviceCollapsed }));
    } catch { /* ignore */ }
  }, [deviceTool, deviceCollapsed]);
  useEffect(() => {
    const el = simWorkspaceRef.current;
    if (!el) return;
    const measure = () => setSimBounds({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    ro?.observe(el);
    window.addEventListener('resize', measure);
    return () => { ro?.disconnect(); window.removeEventListener('resize', measure); };
  }, [deviceCollapsed]);

  function openFloat(id: FloatingWindowId) {
    setFloatWindows((prev) => openOrFocusWindow(prev, id, simBounds, prev.length));
  }

  // INT-01.1: single global experimenter keyboard listener (any Observer tab).
  const expKb = useExperimenterKeyboard({
    status: (liveFrame as any)?.experimenter_interaction?.status
      ?? (viewFrame as any)?.experimenter_interaction?.status,
  });

  async function refreshSavedRuns() {
    try {
      const data = await listRuns();
      setSavedRunCatalog((data.runs || []) as RunCatalogEntry[]);
    } catch {
      setSavedRunCatalog([]);
    }
  }

  async function pollAnalysisJob(jobId: string) {
    for (;;) {
      const st = await getAnalysisJob(jobId);
      const phase = String(st.phase || st.status || 'QUEUED');
      const ticks = st.ticks_reconstructed ?? st.records_processed ?? '';
      const last = st.last_tick_processed ?? '';
      setAnalysisProgress(`ANALYSIS: ${phase} · stories=${ticks} · last_tick=${last}`);
      if (phase === 'COMPLETE' || st.status === 'COMPLETE') return st;
      if (phase === 'FAILED' || st.status === 'FAILED') {
        throw new Error(String(st.error || 'analysis failed'));
      }
      if (phase === 'CANCELLED' || st.status === 'CANCELLED') {
        throw new Error('analysis cancelled');
      }
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  async function runHeavyAnalysis(source: 'current' | 'saved', runId: string | null) {
    const started = await startAnalysisJob({ source, run_id: runId });
    if (!started.accepted) {
      throw new Error(String(started.error || 'job not accepted'));
    }
    setAnalysisProgress(`ANALYSIS: QUEUED ${started.job_id}`);
    await pollAnalysisJob(started.job_id);
    const pkg = await getAnalysisJobResult(started.job_id);
    pkg.source = source;
    return pkg;
  }

  async function runExplicitAnalysis() {
    setAnalyzing(true);
    setAnalysisProgress('ANALYSIS: QUEUED');
    try {
      const pkg = await runHeavyAnalysis(
        analysisSource,
        analysisSource === 'saved' ? selectedSavedRunId : null,
      );
      if (pkg.error) {
        setAnalysisCopyMsg(String(pkg.error));
        return;
      }
      const built = analyzeEvidencePackage(pkg, {
        frame: analysisSource === 'current' ? (liveFrame ?? viewFrame ?? undefined) : undefined,
        mechanisms,
      });
      setRunAnalysis(built);
      if (analysisSource === 'saved' && selectedSavedRunId && built.analysis_log) {
        try {
          await saveAnalysisReport({
            run_id: selectedSavedRunId,
            report_text: built.analysis_log,
            report_json: {
              evidence_meta: built.evidence_meta,
              coverage: built.coverage,
              identity: built.identity,
              lifecycle: built.lifecycle,
            },
          });
        } catch {
          /* save is best-effort */
        }
      }
      if (!built.lifecycle.insufficient) {
        ensureCurrentRun(built, liveFrame ?? viewFrame ?? undefined);
      }
    } catch (err) {
      setAnalysisCopyMsg(String(err));
    } finally {
      setAnalyzing(false);
      setAnalysisProgress('');
    }
  }

  /**
   * Analyze Current — same evidence package path as explicit analysis for the
   * live/current run. Falls back to live-frame optical ticks only when
   * scientific_rows are absent (historical Visual Forensics → NOT_AVAILABLE).
   */
  async function runAnalyzeCurrent() {
    setAnalyzing(true);
    setAnalysisProgress('ANALYSIS: QUEUED');
    try {
      const frame = liveFrame ?? viewFrame ?? undefined;
      const pkg = await runHeavyAnalysis('current', null);
      const built = analyzeEvidencePackage(pkg, { frame, mechanisms });
      setRunAnalysis(built);
      if (!built.lifecycle.insufficient) ensureCurrentRun(built, frame);
    } catch (err) {
      setAnalysisCopyMsg(String(err));
      rebuildAnalysis({ frame: liveFrame ?? viewFrame ?? undefined, mode: 'LIVE' });
    } finally {
      setAnalyzing(false);
      setAnalysisProgress('');
    }
  }

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
    // Pass frame so Visual Forensics can fall back to live near_field when
    // scientific_rows are absent. Analyze Current prefers the evidence package.
    const built = buildRunAnalysis(analysisStateRef.current, analysisMode, { frame });
    setRunAnalysis(built);
    if (!built.lifecycle.insufficient) ensureCurrentRun(built, frame);
  }

  async function refreshAux() {
    const safe = (url: string): Promise<any> => fetch(url).then(r => r.ok ? r.json() : ({})).catch(() => ({}));
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
    const running = liveFrameRef.current?.header?.status === 'RUNNING' && modeRef.current === 'LIVE';
    const gen = Number(liveFrameRef.current?.header?.runtime_generation);
    const needCatalog = mechanismCatalogGenRef.current == null
      || (Number.isFinite(gen) && mechanismCatalogGenRef.current !== gen);
    const mechUrl = (!running || needCatalog) ? '/api/mechanisms' : '/api/mechanisms/state';
    // While RUNNING: skip packs catalog (disk scan) and gearbox — Analyzer isolation.
    // COLD mechanism catalog is fetched only on load / runtime generation change.
    const [tl, ev, me, ge, pa, meta] = await Promise.all([
      getTimeline(LIVE_FE_TIMELINE_DISPLAY_MAX).catch(() => ({ events: [] })),
      safe(`/api/events?limit=${LIVE_FE_EVENTS_DISPLAY_MAX}`), safe(mechUrl),
      running ? Promise.resolve({}) : safe('/api/evidence/gearbox'),
      running ? Promise.resolve({ packs: [] }) : safe('/api/results/packs'),
      getSnapshotMeta().catch(() => ({})),
    ]);
    const tlEvents = (tl as any).events || [];
    const evEvents = ev.events || [];
    const mechs = mergeMechanismWarmState(mechanisms, me);
    const projected = projectLiveAuxState({
      timeline: tlEvents,
      events: evEvents,
      world_interventions: liveFrameRef.current?.world_interventions,
      // Intentionally unused by LIVE — Analyzer loads evidence package separately.
      scientific_rows: undefined,
    });
    setTimeline(projected.timeline); setEvents(projected.events);
    setMechanisms(mechs);
    if (me.catalog_included !== false && Array.isArray(me.mechanisms) && me.mechanisms.length) {
      if (Number.isFinite(gen)) mechanismCatalogGenRef.current = gen;
    }
    if (!running) {
      setGearbox(ge); setPacks(pa.packs || []);
    }
    setSnapshotMeta(meta);
    // Do not continuously rebuild analysis on aux refresh — Analyze Current /
    // Run explicit analysis are button-triggered snapshots.
  }

  useEffect(() => {
    getState().then(f => {
      const agent = requestedAgentId(f);
      desiredAgentIdRef.current = agent;
      setDesiredAgentId(agent);
      const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
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
      const eco = String(
        f.experiment?.ecology_preset
        || f.experiment?.observer_ground_truth?.ecology_preset
        || f.header?.ecology_preset
        || 'BASELINE_CLIMATE_DEFAULT',
      );
      setEcologyPreset(eco);
      const twoA = Number(f.experiment?.runtime?.agent_count || 1) >= 2;
      setTwoAgentExperimental(twoA);
      setAppliedConfig({
        seed: String(f.header?.seed ?? 17),
        width: String(f.world?.width ?? 32),
        height: String(f.world?.height ?? 32),
        ecologyPreset: eco,
        cognitionEnabled: Boolean(f.experiment?.runtime?.cognition_enabled ?? f.header?.cognition_enabled ?? true),
        twoAgentExperimental: twoA,
        bodyMass: String(bodyCfg.mass ?? 2),
        bodyVMax: String(bodyCfg.v_max ?? 0.3),
        targetTick: f.header?.target_tick != null ? String(f.header.target_tick) : '',
        uiHz: String(obs.ui_hz ?? 10),
        bufferCapacity: String(obs.buffer_capacity ?? 512),
        terrainSeedOverride: '',
      });
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
        const withGeo = mergeGeoTransportIntoFrame(f);
        const projected = applyProjectionToFrame(withGeo, agent);
        if (desired && requestedAgentId(f) === desired) {
          lastAcceptedSeqRef.current = selectionSeqRef.current;
        }
        // Reconnect safety: if empirical grids missing from cache, fetch once.
        if (
          withGeo?.geometry_interpretation?.traversability?.status === 'CACHED' &&
          !withGeo?.geometry_interpretation?.traversability?.class_grid
        ) {
          fetchEmpiricalIfMissing(withGeo).then((filled) => {
            const p2 = applyProjectionToFrame(filled, agent);
            setLiveFrame(p2);
            setViewFrame(prev => modeRef.current === 'LIVE' ? p2 : prev);
          }).catch(() => undefined);
        }
        if (f?.pending_live_apply) setLiveApplyPending(f.pending_live_apply);
        else if (f?.toggle_runtime_applied === true || f?.pending_live_apply === null) {
          setLiveApplyPending(null);
        }
        if (f?.mechanism_result?.mechanisms) setMechanisms(f.mechanism_result.mechanisms);
        setLiveFrame(projected);
        setViewFrame(prev => modeRef.current === 'LIVE' ? projected : prev);
      }, (hb) => {
        setConnection('CONNECTED');
        setLastArrival(Date.now());
        setSimHeartbeat(hb);
        if (hb && Object.prototype.hasOwnProperty.call(hb, 'pending_live_apply')) {
          const pending = hb.pending_live_apply || null;
          setLiveApplyPending(pending);
          if (!pending) {
            setControlMessage((prev: any) => (
              prev?.reason === 'WAITING_FOR_TICK_BOUNDARY' ? null : prev
            ));
          }
        }
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

  const refreshAuxRef = useRef(refreshAux);
  refreshAuxRef.current = refreshAux;
  const refreshAuxStable = useCallback(() => { refreshAuxRef.current().catch(() => undefined); }, []);
  useEffect(() => {
    lifecycleStore.set({ controlMessage, saveBanner, finalizing });
  }, [controlMessage, saveBanner, finalizing]);
  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify({
        tab, layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength, geoAgentFilter,
      }));
    } catch { /* display prefs only */ }
  }, [tab, layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength, geoAgentFilter]);

  // Observe V2 buffer identity — MUST stay above any early return (Rules of Hooks).
  // Missing liveFrame must not crash the SPA into a blank #root.
  useEffect(() => {
    const raw = mode === 'LIVE' ? liveFrame : viewFrame;
    if (!raw) return;
    const agentId = desiredAgentId || requestedAgentId(raw);
    const projected = applyProjectionToFrame(raw, agentId);
    const sel = String(
      projected.observer?.selected_agent_id
      || projected.header?.selected_agent_id
      || agentId
      || '',
    );
    const next = observeBufferIdentityFromFrame(projected, {
      run_id: currentRunId,
      agent_id: sel,
    });
    const prev = observeBufIdRef.current;
    if (invalidateEventsOnRunOrGeneration(prev, next)) {
      setEvents([]);
      setTimeline([]);
      setSelectedEvent(null);
    } else if (prev && String(prev.agent_id) !== String(next.agent_id) && next.agent_id && prev.agent_id) {
      setSelectedEvent(null);
    }
    observeBufIdRef.current = next;
  }, [
    currentRunId,
    desiredAgentId,
    mode,
    liveFrame,
    viewFrame,
  ]);

  const lab = useWorkspaceStore();
  const worldPrefs = { layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength };

  const rawFrame = mode === 'LIVE' ? liveFrame : viewFrame;
  if (!rawFrame) {
    return (
      <div className="desktop app">
        <ClockDriver />
        <InterestDriver />
        <div className="loading">Connecting to MM 1.0 — Tiktaalik…</div>
      </div>
    );
  }
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
    setSelectedEvent(null);
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
  const visionMechOn = !!(mechanisms || []).find((m: any) => m.id === 'physical_near_field_vision')?.enabled;
  const nfSel = physical?.near_field_exteroception;
  const agentObservation =
    (frame as any).agent_observation
    || (frame as any)._projection?.agent_observation
    || (frame.perception as any)?.agent_observation
    || nfSel?.fragments
    || body?.observation
    || physical?.agent_observation
    || null;
  const visionAuthorityOn =
    visionMechOn
    || nfSel?.vision_contributes === true;
  // Do NOT treat perception_enabled alone as authority (inert while mode=OFF).
  // Terrain scalars are Observer GT overlays only — keep base field buttons on physics/ecology fields.
  const fields = (world.fields_available || []).filter((f: any) =>
    f.kind === 'scalar'
    && !String(f.id || '').startsWith('terrain_')
    && !String(f.id || '').startsWith('resource_geo_'));
  const staleSeconds = Math.max(1, Number(liveFrame?.observation?.stale_after_seconds || 2));
  const heartbeatFresh = simHeartbeat?.heartbeat_mono != null
    && (now - lastArrival) <= staleSeconds * 1000;
  const computingTick = Boolean(simHeartbeat?.tick_in_progress) && heartbeatFresh;
  const pendingApply = liveApplyPending || simHeartbeat?.pending_live_apply;
  // STALE only when RUNNING and we have neither frames nor heartbeats — not during a long tick.
  const stale = connection === 'CONNECTED'
    && liveFrame?.header?.status === 'RUNNING'
    && (now - lastArrival > staleSeconds * 1000)
    && !computingTick;
  const displayStatus = connection === 'DISCONNECTED'
    ? 'DISCONNECTED'
    : stale
      ? 'STALE'
      : computingTick
        ? 'RUNNING'
        : header.status || 'UNKNOWN';
  void displayStatus;
  const statusDetail = computingTick
    ? 'COMPUTING_TICK'
    : pendingApply
      ? 'PENDING — WAITING FOR TICK BOUNDARY'
      : (simHeartbeat?.status_detail || null);
  void statusDetail;
  const tickMismatch = frame.observation && !frame.observation.tick_consistent;
  const historical = frame.historical_compatibility;
  const identity = null; // desktop-top replaces legacy identity strip
  void identity;
  void historical;
  void tickMismatch;
  void rawOpen;
  void setRawOpen;
  const recordedTick = Number(timeline[timeline.length - 1]?.tick ?? liveFrame?.header?.tick ?? header.tick);
  const reservoir = Number(resources.reservoir || 0);
  const reservoirMax = Math.max(1e-9, Number(resources.reservoir_capacity || 1));

  async function control(op: string, payload?: any) {
    if (finalizing && op !== 'stop') return;
    if (op === 'reset' || op === 'apply' || op === 'restart') {
      resetGeoEmpiricalCache();
      setEvents([]);
      setTimeline([]);
      setSelectedEvent(null);
      observeBufIdRef.current = null;
    }
    const f = await postControl(op, payload);
    setControlMessage(f.control_receipt);
    const agent = desiredAgentIdRef.current || requestedAgentId(f);
    const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
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
    const applyFinalizeFrame = (f: any) => {
      if (f?.header && !f.header.compact_control) {
        setLiveFrame(f);
        setViewFrame(f);
        setMode('LIVE');
      }
      if (f?.control_receipt) setControlMessage(f.control_receipt);
    };
    const applySuccess = (fin: any, receipt?: any) => {
      const verifiedTick = fin.final_tick;
      setSaveBanner({
        tick: verifiedTick,
        seed: fin.seed,
        path: fin.run_dir,
        reason: fin.termination_reason,
        verified: true,
      });
      setControlMessage({
        ...(receipt || {}),
        accepted: true,
        operation: 'STOP',
        tick: verifiedTick,
        verified_final_tick: verifiedTick,
        reason: receipt?.reason || `SAVED · t${verifiedTick}`,
      });
      setFinalizing(null);
    };
    const applySaveFailed = (fin: any, receipt?: any) => {
      setFinalizing(null);
      const liveT = fin?.live_tick;
      const capT = fin?.captured_tick ?? fin?.persisted_tick;
      const mismatch =
        fin?.persistence_integrity_error && liveT != null && capT != null
          ? ` · live tick: ${liveT} · captured tick: ${capT} · reason: persistence integrity mismatch`
          : '';
      setControlMessage({
        ...(receipt || {}),
        accepted: false,
        operation: 'STOP',
        reason: (fin?.error || receipt?.reason || 'SAVE_FAILED') + mismatch,
        error: receipt?.error || { code: 'SAVE_FAILED', message: fin?.error || 'SAVE_FAILED', recoverable: true },
      });
      setSaveBanner({
        failed: true,
        layer: 'save',
        error: (fin?.error || 'Save failed — runtime preserved') + mismatch,
        liveTick: liveT,
        capturedTick: capT,
      });
    };
    const applyHttpFailure = (err: unknown) => {
      setControlMessage({
        operation: 'STOP',
        accepted: false,
        reason: String(err),
        error: { code: 'HTTP_FAILED', message: String(err), recoverable: true },
      });
      setSaveBanner({
        failed: true,
        layer: 'http',
        error:
          'HTTP/network failure during Save & Stop (connection closed or server died). '
          + 'This is not a confirmed disk serialization error. Check /api/control/save-job and live/tmp run dirs. '
          + String(err),
      });
    };
    try {
      setFinalizing('Requesting backend finalize…');
      const f = await postControl('stop', { save: true, reason: 'USER_STOP_SAVED', wait: false });
      applyFinalizeFrame(f);
      if (f.finalize?.accepted && f.finalize?.final_tick != null) {
        applySuccess(f.finalize, f.control_receipt);
        await refreshAux();
        return;
      }
      if (f.finalize && f.finalize.accepted === false) {
        applySaveFailed(f.finalize, f.control_receipt);
        await refreshAux();
        return;
      }
      setFinalizing('Backend owns finalize — polling status…');
      const deadline = Date.now() + 30 * 60 * 1000;
      let lastHttpErr: unknown = null;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 500));
        try {
          const job = await getSaveJob();
          lastHttpErr = null;
          const life = String(job.lifecycle || job.header?.status || '');
          setFinalizing(`Finalizing… ${life} · save=${job.save} · ${job.phases?.slice(-1)[0] || ''}`);
          if (life === 'STOPPED' && (job.save === 'succeeded' || job.finalize === 'succeeded')) {
            applySuccess({
              final_tick: job.final_tick,
              seed: job.seed,
              run_dir: job.run_dir,
              termination_reason: 'USER_STOP_SAVED',
            }, { operation: 'STOP', accepted: true });
            await refreshAux();
            return;
          }
          if (life === 'SAVE_FAILED' || job.save === 'failed' || job.finalize === 'failed') {
            applySaveFailed({
              accepted: false,
              error: job.error,
              live_tick: job.runtime?.tick,
            }, { operation: 'STOP', accepted: false, error: { code: 'SAVE_FAILED', message: job.error } });
            await refreshAux();
            return;
          }
        } catch (pollErr) {
          lastHttpErr = pollErr;
          setFinalizing('Polling interrupted — retrying save-job…');
        }
      }
      setFinalizing(null);
      applyHttpFailure(lastHttpErr || 'save-job poll timed out');
    } catch (err) {
      setFinalizing(null);
      applyHttpFailure(err);
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
  async function toggleMechanism(m: any, enabled?: boolean) {
    const next = typeof enabled === 'boolean' ? enabled : !m.enabled;
    setMechanisms((prev: any[]) => (prev || []).map((x: any) => (
      x.id === m.id ? { ...x, enabled: next } : x
    )));
    const f = await fetch(`/api/mechanisms/${m.id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: next }),
    }).then(r => r.json());
    setControlMessage(f.control_receipt);
    if (f.pending_live_apply || f.control_receipt?.reason === 'WAITING_FOR_TICK_BOUNDARY') {
      setLiveApplyPending(f.pending_live_apply || {
        mechanism_id: m.id,
        enabled: next,
        status: 'WAITING_FOR_TICK_BOUNDARY',
      });
      return;
    }
    if (f.control_receipt?.accepted) {
      setLiveApplyPending(null);
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(f, agent);
      setLiveFrame(projected);
      setViewFrame(mode === 'LIVE' ? projected : viewFrame);
      if (f.mechanism_result?.mechanisms) setMechanisms(f.mechanism_result.mechanisms);
    }
  }

  function mechanismHelp(m: any): string | null {
    if (m?.id === 'prospective_scenario_competition') {
      return 'Recommended: let the organism explore for a while before enabling PSC. This allows sensorimotor and predictive history to form first. PSC can be enabled during a running simulation without resetting the organism. (~1000 ticks is a reasonable experimental starting point.)';
    }
    if (m?.id === 'historical_sensorimotor_selection_bridge') {
      return 'Predicted sensory consequences of candidate actions are queried against accumulated history; continuation evidence can participate in prospective scenario competition.';
    }
    return null;
  }

  async function setVisionRadius(radius: number) {
    const f = await fetch('/api/vision/radius', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ radius }),
    }).then((r) => r.json());
    setControlMessage(f.control_receipt);
    if (f.control_receipt?.accepted !== false) {
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(f, agent);
      setLiveFrame(projected);
      setViewFrame(mode === 'LIVE' ? projected : viewFrame);
      if (f.mechanism_result?.mechanisms) setMechanisms(f.mechanism_result.mechanisms);
    }
  }
  async function inspectCell(info: any) {
    if (!info) return;
    const values: Record<string, any> = {};
    const ids = new Set<string>([
      ...Object.keys(world.scalars || {}),
      'terrain_potential', 'terrain_drag', 'terrain_grad_mag',
      'ambient_fx', 'ambient_fy', 'ambient_magnitude',
    ]);
    ids.forEach((k) => {
      const grid = scalarGrid(world, k);
      if (grid && grid[info.iy]) values[k] = grid[info.iy][info.ix] ?? null;
    });
    const sites = (body.sites || []).filter((s: any) =>
      Math.floor(s.world?.[0]) === info.ix && Math.floor(s.world?.[1]) === info.iy);
    let geometryDetail: any = null;
    try {
      geometryDetail = await getGeometryCell(info.ix, info.iy, geoAgentFilter);
    } catch {
      const key = `${info.ix},${info.iy}`;
      geometryDetail = {
        accepted: true,
        empirical: frame.geometry_interpretation?.traversability?.by_cell?.[key] || null,
        ground_truth: { status: 'NOT AVAILABLE', reason: 'api_fallback' },
      };
    }
    setSelectedCell({
      position: [info.ix, info.iy],
      fields: values,
      body_sites: sites,
      geometry: geometryDetail,
      terrain_observer_gt: {
        potential: values.terrain_potential ?? null,
        drag: values.terrain_drag ?? null,
        gradient_mag: values.terrain_grad_mag ?? null,
        note: 'OBSERVER GROUND TRUTH — not agent observation',
      },
      ambient_observer_gt: {
        fx: values.ambient_fx ?? null,
        fy: values.ambient_fy ?? null,
        magnitude: values.ambient_magnitude ?? null,
        note: 'OBSERVER GROUND TRUTH — ambient force; not WIND/CURRENT labels',
      },
    });
    setCellRaw(false);
    setSelectedGeoEvent(null);
  }

  async function changeGeoFilter(next: string) {
    setGeoAgentFilter(next);
    try {
      await setGeometryAgentFilter(next);
    } catch { /* filter is also applied on next capture via session state */ }
  }

  const layerControls = <Card title="World layers">
    <label>View <select value={worldView} onChange={e => setWorldView(e.target.value)}>
      <option>PHYSICAL</option>
      <option>TRAVERSABILITY</option>
      <option>DEFLECTION</option>
      <option>FLOW</option>
      <option>TRAJECTORY</option>
      <option>AGENT_PERCEPTION</option>
      <option>PREDICTED</option>
      <option>DIFFERENCE</option>
    </select></label>
    <div className="subtle">PHYSICAL=ground-truth fields · TRAVERSABILITY/DEFLECTION=empirical · FLOW=GT vectors · TRAJECTORY=realized path</div>
    <label>Empirical agents <select value={geoAgentFilter} onChange={e => changeGeoFilter(e.target.value)}>
      <option value="ALL">ALL AGENTS</option>
      <option value="agent_0">AGENT 0</option>
      <option value="agent_1">AGENT 1</option>
    </select></label>
    <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      <input
        style={{ minWidth: 220 }}
        value={savedGeoRunId}
        onChange={e => setSavedGeoRunId(e.target.value)}
        placeholder="saved run id (optional)"
        title="Leave blank to pick from recent runs list if available"
      />
      <button onClick={async () => {
        try {
          let rid = savedGeoRunId.trim();
          if (!rid) {
            const runs = await listRuns();
            const list = Array.isArray(runs?.runs) ? runs.runs : (Array.isArray(runs) ? runs : []);
            rid = String(list[0]?.run_id || list[0]?.id || '');
          }
          if (!rid) {
            alert('No saved run id. Enter a run id for LOAD SAVED GEO.');
            return;
          }
          const r = await hydrateGeometryRun(rid);
          if (!r?.accepted) {
            alert(`LOAD SAVED GEO failed: ${r?.error || 'unknown'}`);
            return;
          }
          resetGeoEmpiricalCache();
          const st = mergeGeoTransportIntoFrame(await getState());
          setLiveFrame(st);
          if (mode === 'LIVE') setViewFrame(st);
          setWorldView('TRAVERSABILITY');
          setSavedGeoRunId(rid);
        } catch (e) {
          alert(String(e));
        }
      }}>LOAD SAVED GEO</button>
      <button onClick={async () => {
        try {
          await geometryUseLive();
          resetGeoEmpiricalCache();
          const st = mergeGeoTransportIntoFrame(await getState());
          setLiveFrame(st);
          if (mode === 'LIVE') setViewFrame(st);
        } catch (e) { alert(String(e)); }
      }}>Use LIVE GEO</button>
      <button onClick={async () => {
        try {
          await geometryClearSaved();
          resetGeoEmpiricalCache();
          const st = mergeGeoTransportIntoFrame(await getState());
          setLiveFrame(st);
          if (mode === 'LIVE') setViewFrame(st);
        } catch (e) { alert(String(e)); }
      }}>Clear saved GEO</button>
    </div>
    {(() => {
      const trav = frame.geometry_interpretation?.traversability;
      const transport = frame.geo_transport || frame.geometry_interpretation?.geo_transport || {};
      const prov = trav?.provenance || transport.provenance || {};
      const src = String(trav?.geo_source || transport.geo_source || 'LIVE').toUpperCase();
      const liveUnavailable = trav?.status === 'LIVE_GEO_UNAVAILABLE'
        || (src === 'LIVE' && Number(trav?.n_observations || transport.n_observations || 0) <= 0 && !trav?.class_grid);
      const expBlock = frame.experiment || {};
      const terrainCs = expBlock.observer_ground_truth?.terrain?.checksum;
      const terrainMatch = terrainCs && prov.terrain_checksum
        ? (String(terrainCs) === String(prov.terrain_checksum) ? 'MATCH' : 'MISMATCH')
        : (src === 'SAVED' && terrainCs ? 'SAVED≠LIVE check' : '—');
      return (
        <div className="subtle" style={{ marginTop: 6 }}>
          {liveUnavailable && src === 'LIVE' ? (
            <div className="warn"><strong>LIVE GEO unavailable</strong> — no current-runtime empirical samples. Not showing older runs.</div>
          ) : null}
          {src === 'SAVED' ? (
            <div className="warn">
              <strong>SAVED GEO</strong> (not LIVE) · run {String(prov.run_id || savedGeoRunId || '—')}
              · seed {String(prov.experiment_seed ?? '—')}
              · gen {String(prov.runtime_generation ?? '—')}
              · tick {String(prov.tick ?? '—')}
              · terrain seed {String(prov.terrain_seed ?? '—')} / checksum {String(prov.terrain_checksum ?? '—')}
              · ambient seed {String(prov.ambient_seed ?? '—')} / checksum {String(prov.ambient_checksum ?? '—')}
            </div>
          ) : (
            <div>
              <strong>LIVE GEO</strong>
              · gen {String(prov.runtime_generation ?? transport.runtime_generation ?? header.runtime_generation ?? '—')}
              · seed {String(prov.experiment_seed ?? transport.experiment_seed ?? expBlock.seed ?? '—')}
              · terrain checksum {String(prov.terrain_checksum ?? transport.terrain_checksum ?? terrainCs ?? '—')}
              · ambient checksum {String(prov.ambient_checksum ?? transport.ambient_checksum ?? expBlock.observer_ground_truth?.ambient?.checksum ?? '—')}
              · terrain GT verify {terrainMatch}
              · n={(trav?.n_observations) ?? transport.n_observations ?? 0}
            </div>
          )}
        </div>
      );
    })()}
    <div className="field-list">{fields.map((f: any) =>
      <button className={layer === f.id ? 'active' : ''} key={f.id} onClick={() => setLayer(f.id)}>{f.label || f.id}</button>)}
    </div>
    <div className="section-label">Terrain overlays (Observer GT)</div>
    <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
      {([
        ['terrain_potential', 'TERRAIN POTENTIAL'],
        ['terrain_drag', 'TERRAIN DRAG'],
        ['terrain_grad', 'TERRAIN GRADIENT'],
        ['ambient_force', 'AMBIENT FORCE'],
        ['ambient_magnitude', 'AMBIENT MAGNITUDE'],
      ] as const).map(([k, lab]) => {
        const available = !!(
          world?.scalars?.terrain_potential || world?.scalars?.terrain_drag || world?.scalars?.terrain_grad_mag
          || world?.scalars?.ambient_fx || world?.scalars?.ambient_magnitude
        );
        return (
          <label className="check" key={k}>
            <input
              type="checkbox"
              checked={!!layers[k]}
              disabled={!available}
              onChange={e => setLayers(x => ({ ...x, [k]: e.target.checked }))}
            />{lab}
          </label>
        );
      })}
    </div>
    <div className="subtle">Overlays are independent of the base field button. OBSERVER GROUND TRUTH only — not cognition.</div>
    <label>Render <select value={renderMode} onChange={e => setRenderMode(e.target.value)}>
      {['COMPOSITE','SMOOTH','CELL','CONTOUR','VECTOR'].map(x => <option key={x}>{x}</option>)}
    </select></label>
    {Object.keys(layers).filter(k => !k.startsWith('terrain_')).map(k => <label className="check" key={k}><input type="checkbox" checked={layers[k]}
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
    <div className="availability">
      No hard walls (GEO-01). Difficult regions emerge from flow + soft contact.<br/>
      Low evidence ≠ easy. Empirical overlay is Observer-only — not agent cognition.<br/>
      Predicted spatial layer: NOT_IMPLEMENTED · Perception map: on AGENT/MIND
    </div>
  </Card>;

  const geoEmp = selectedCell?.geometry?.empirical;
  const geoGt = selectedCell?.geometry?.ground_truth;
  const dirs = geoEmp?.directions || {};
  const dirRow = (act: string) => {
    const d = dirs[act] || {};
    return `${act.replace('MOVE:', '')}: n=${d.attempts ?? 0} align=${d.mean_action_alignment == null ? '—' : Number(d.mean_action_alignment).toFixed(2)} opp=${d.opposing ?? 0} [${d.class_label || d.evidence_class || 'UNKNOWN'}]`;
  };

  const inspector = <div className="inspector-stack">
    <Card title="Cell / site inspector">
      {selectedCell ? <>
        <div className="toolbar-row">
          <button className={!cellRaw ? 'active' : ''} onClick={() => setCellRaw(false)}>Structured</button>
          <button className={cellRaw ? 'active' : ''} onClick={() => setCellRaw(true)}>Raw</button>
        </div>
        {cellRaw ? <pre className="cell-raw">{JSON.stringify(selectedCell, null, 2)}</pre> : <>
          <KV name="Location" value={selectedCell.position}/>
          <div className="section-label">Ground truth</div>
          {geoGt?.status === 'AVAILABLE' ? <>
            <KV name="local flow" value={`(${show(geoGt.local_flow_vx, 3)}, ${show(geoGt.local_flow_vy, 3)})`}/>
            <KV name="flow |v|" value={geoGt.local_flow_mag}/>
            <KV name="T" value={geoGt.local_T}/>
          </> : <div className="subtle">Flow GT: {geoGt?.status || 'NOT AVAILABLE'}{geoGt?.reason ? ` · ${geoGt.reason}` : ''}</div>}
          {(selectedCell.terrain_observer_gt?.potential != null
            || selectedCell.terrain_observer_gt?.drag != null
            || selectedCell.terrain_observer_gt?.gradient_mag != null) && <>
            <div className="section-label">Terrain (OBSERVER GROUND TRUTH)</div>
            <KV name="POTENTIAL" value={selectedCell.terrain_observer_gt.potential}/>
            <KV name="DRAG" value={selectedCell.terrain_observer_gt.drag}/>
            <KV name="GRADIENT |∇|" value={selectedCell.terrain_observer_gt.gradient_mag}/>
            <div className="subtle">{selectedCell.terrain_observer_gt.note}</div>
          </>}
          {(selectedCell.ambient_observer_gt?.fx != null
            || selectedCell.ambient_observer_gt?.fy != null) && <>
            <div className="section-label">Ambient (OBSERVER GROUND TRUTH)</div>
            <KV name="Fx" value={selectedCell.ambient_observer_gt.fx}/>
            <KV name="Fy" value={selectedCell.ambient_observer_gt.fy}/>
            <KV name="|F|" value={selectedCell.ambient_observer_gt.magnitude}/>
            <div className="subtle">{selectedCell.ambient_observer_gt.note}</div>
          </>}
          {Object.entries(selectedCell.fields || {}).slice(0, 8).map(([k, v]) => <KV key={k} name={k} value={v}/>)}
          <div className="section-label">Empirical traversability ({geoAgentFilter})</div>
          {geoEmp ? <>
            <KV name="class" value={geoEmp.class_label}/>
            <KV name="total attempts" value={geoEmp.total_attempts}/>
            <div className="dir-compass">
              <div className="dir-n">{dirRow('MOVE:N')}</div>
              <div className="dir-we"><span>{dirRow('MOVE:W')}</span><span>{dirRow('MOVE:E')}</span></div>
              <div className="dir-s">{dirRow('MOVE:S')}</div>
            </div>
            {geoEmp.by_agent && Object.keys(geoEmp.by_agent).length > 0 && <>
              <div className="section-label">Agent comparison</div>
              {Object.entries(geoEmp.by_agent).map(([aid, dmap]: any) => (
                <div key={aid} className="subtle">{aid}: {['MOVE:N','MOVE:E','MOVE:S','MOVE:W'].map(a => {
                  const d = dmap?.[a] || {};
                  return `${a.slice(-1)} n=${d.attempts ?? 0} ā=${d.mean_action_alignment == null ? '—' : Number(d.mean_action_alignment).toFixed(2)}`;
                }).join(' · ')}</div>
              ))}
            </>}
          </> : <div className="subtle">No empirical samples yet for this cell (UNKNOWN)</div>}
          <div className="subtle">Body sites: {selectedCell.body_sites?.length || 'none'}</div>
        </>}
      </> : <div className="empty">Click a world cell — primary geometry instrument</div>}
    </Card>
    <Card title="Requested vs realized">
      <div className="selected-action">{physical.selected_action || header.selected_action || '—'}</div>
      {frame.motor_control ? (() => {
        const mc = frame.motor_control;
        const out = mc.current_motor_output || {};
        const eff = mc.active_effectors || {};
        const sens = mc.passive_input || {};
        const osc = out.oscillator || {};
        return (
          <div className="motor-control-panel" style={{marginTop: 8}}>
            <div className="section-label">CURRENT MOTOR OUTPUT</div>
            <KV name="Locomotion" value={out.locomotion}/>
            <KV name="Neck" value={out.neck}/>
            <KV name="Osc freq Δ" value={osc.freq_delta}/>
            <KV name="Osc amp Δ" value={osc.amp_delta}/>
            <KV name="Emit trigger" value={osc.emit_trigger ? 'YES' : 'NO'}/>
            <KV name="Push" value={out.push ? 'YES' : 'NO'}/>
            <div className="subtle">{out.display || ''}</div>
            <div className="section-label" style={{marginTop: 8}}>ACTIVE EFFECTORS</div>
            <KV name="Locomotor force" value={eff.body_locomotor_force}/>
            <KV name="Neck torque" value={eff.neck_torque}/>
            <KV name="Head angle" value={eff.head_angle}/>
            <KV name="Head omega" value={eff.head_omega}/>
            <KV name="Oscillator" value={eff.oscillator}/>
            <KV name="Frequency" value={eff.osc_freq}/>
            <KV name="Amplitude" value={eff.osc_amp}/>
            <KV name="Remaining" value={eff.osc_remaining}/>
            <div className="section-label" style={{marginTop: 8}}>PASSIVE INPUT</div>
            <KV name="Vision" value={sens.vision}/>
            <KV name="Osc reception" value={sens.osc_reception}/>
            <KV name="Vestibular" value={sens.vestibular}/>
            <KV name="Neck proprioception" value={sens.neck_proprioception}/>
            <KV name="Legacy fields" value={sens.legacy_fields}/>
            <div className="subtle">{sens.note || 'Passive — not an action.'}</div>
          </div>
        );
      })() : null}
      {(frame.geometry_interpretation?.agents || []).filter((a: any) => a.agent_id === selectedAgentId).map((a: any) => {
        const s = a.since_prev_capture;
        return <div key={a.agent_id}>
          <KV name="Requested unit" value={a.requested_unit}/>
          <KV name="Realized Δ" value={s ? [s.dx, s.dy] : 'NOT AVAILABLE'}/>
          <KV name="|Δ|" value={s?.mag}/>
          <KV name="action_alignment" value={s?.action_alignment}/>
          <KV name="class" value={a.motion_class || s?.outcome || '—'}/>
          <KV name="local flow |v|" value={a.local_flow?.mag}/>
        </div>;
      })}
      <KV name="Requested Δv" value={action.action_dv_requested}/>
      <KV name="Realized Δv" value={action.action_dv_realized}/>
      <KV name="Work limit %" value={(action.action_work_limit_fraction ?? 0) * 100}/>
    </Card>
    <Card title="ACTION REALIZATION">
      {(() => {
        const ar = frame.action_realization || {};
        const latestMap = ar.latest_by_agent || {};
        const recent = (ar.recent || []) as any[];
          const forSelected = recent.filter((row: any) => row.agent_id === selectedAgentId);
          const forExp = recent.filter((row: any) => {
            const a = String(row.agent_id || '');
            return a === 'undercover' || a.includes('experimenter');
          });
          const pool = forSelected.length
            ? forSelected
            : (expKb.active && forExp.length ? forExp : recent.filter((row: any) =>
              row.agent_id === selectedAgentId
              || row.agent_id === 'undercover'
              || String(row.agent_id || '').includes('experimenter')
            ));
          const live = latestMap[selectedAgentId]
          || (expKb.active ? (latestMap['undercover'] || latestMap['experimenter-body-0']) : null)
          || latestMap['undercover']
          || latestMap['experimenter-body-0']
          || Object.values(latestMap)[0];
        const r = arInspect || live;
        if (!r) return <div className="subtle">No action realization receipt yet (step the sim).</div>;
        const hist = (pool.length ? pool : recent).slice(-24).reverse();
        return <>
          <div className="subtle">Observer forensic · not cognition · expected_free_progress NOT_AVAILABLE</div>
          <div className="section-label">REQUESTED</div>
          <div className="selected-action">{r.requested_action || '—'}</div>
          <div className="section-label">REALIZED</div>
          <KV name="Δ" value={r.realized_delta}/>
          <KV name="distance" value={r.realized_distance}/>
          <KV name="alignment" value={r.action_alignment}/>
          <KV name="effective progress" value={r.effective_progress}/>
          <div className="section-label">ACTION DRIVE</div>
          <KV name="work fraction" value={r.work_fraction}/>
          <KV name="work limited" value={r.work_limited ? 'YES' : 'no'}/>
          <div className="section-label">PHYSICAL CONTRIBUTIONS</div>
          <KV name="contact" value={r.contact_active ? 'active' : 'none'}/>
          <div className="section-label">OUTCOME</div>
          <KV name="class" value={r.outcome}/>
          <KV name="PRIMARY CONSTRAINT" value={r.primary_constraint}/>
          <KV name="secondary" value={(r.secondary_constraints || []).join(', ') || '—'}/>
          {arInspect ? (
            <button type="button" onClick={() => setArInspect(null)}>Back to live</button>
          ) : null}
          <div className="section-label">Recent history (click to inspect)</div>
          <div className="event-list" style={{ maxHeight: 140 }}>
            {hist.map((row: any, i: number) => (
              <button
                key={`${row.tick}-${row.agent_id}-${i}`}
                type="button"
                className="subtle"
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  padding: '2px 0',
                  opacity: arInspect && arInspect.tick === row.tick && arInspect.agent_id === row.agent_id ? 1 : 0.8,
                }}
                title="Observer receipt — physical description only"
                onClick={() => setArInspect(row)}
              >
                t{row.tick} {row.agent_id} {row.requested_action} → {row.outcome}
                {row.primary_constraint && row.primary_constraint !== 'NONE'
                  ? ` · ${row.primary_constraint}` : ''}
                {row.realized_distance != null ? ` · d=${Number(row.realized_distance).toFixed(3)}` : ''}
              </button>
            ))}
          </div>
        </>;
      })()}
    </Card>
    <Card title="Geometry event">
      {selectedGeoEvent ? <>
        <div className="selected-action">{selectedGeoEvent.kind}</div>
        <KV name="Agent" value={selectedGeoEvent.agent_id}/>
        <KV name="Tick" value={selectedGeoEvent.tick}/>
        <KV name="Position" value={[selectedGeoEvent.x, selectedGeoEvent.y]}/>
        <KV name="Requested" value={selectedGeoEvent.action}/>
        <KV name="Realized Δ" value={[selectedGeoEvent.dx, selectedGeoEvent.dy]}/>
        <KV name="Alignment" value={selectedGeoEvent.action_alignment}/>
        <KV name="Contact" value={selectedGeoEvent.contact == null ? 'NOT AVAILABLE' : selectedGeoEvent.contact}/>
        <div className="subtle">Physical descriptive label only — no intention inferred.</div>
      </> : <>
        <div className="subtle">Select a marker event from the list (TRAVERSABILITY / TRAJECTORY views).</div>
        <div className="event-list" style={{ maxHeight: 140 }}>
          {(frame.geometry_interpretation?.traversability?.events || []).slice(-12).reverse().map((ev: any, i: number) => (
            <button key={`${ev.tick}-${ev.agent_id}-${i}`} onClick={() => setSelectedGeoEvent(ev)}>
              <span>t{ev.tick}</span><b>{ev.kind} · {ev.agent_id} · {ev.action}</b>
            </button>
          ))}
        </div>
      </>}
    </Card>
    <Card title="WORK ECOLOGY">
      {(() => {
        const we = frame.work_ecology || {};
        const latestMap = we.latest_by_agent || {};
        const r = latestMap[selectedAgentId]
          || (expKb.active ? (latestMap['undercover'] || latestMap['experimenter-body-0']) : null)
          || latestMap['undercover']
          || latestMap['experimenter-body-0']
          || Object.values(latestMap)[0];
        if (!r) return <div className="subtle">No work budget receipt yet (step the sim).</div>;
        const spark = (we.reservoir_sparkline || {})[r.agent_id] || [];
        const ep = (we.episodes || {})[r.agent_id] || {};
        const income = r.income || {};
        const costs = r.costs || {};
        const wMax = Number(r.work_reservoir_max || 0);
        const wAfter = Number(r.work_reservoir_after || 0);
        return <>
          <div className="subtle">Observer physical budget · not hungry/tired · residual kept if unbalanced</div>
          <div className="section-label">WORK RESERVOIR</div>
          <div className="selected-action">
            {wAfter.toFixed(3)} / {wMax.toFixed(3)}
            {r.work_reservoir_fraction_after != null
              ? ` · ${(100 * Number(r.work_reservoir_fraction_after)).toFixed(1)}%`
              : ''}
          </div>
          {spark.length > 1 && (
            <div className="subtle" title="Recent reservoir after values">
              spark: {spark.slice(-12).map((v: number) => Number(v).toFixed(2)).join(' → ')}
            </div>
          )}
          <div className="section-label">RECENT INCOME</div>
          <KV name="resource conversion" value={
            (Number(income.complementary_conversion || 0) + Number(income.environmental_conversion || 0)).toFixed(4)
          }/>
          <KV name="research supply" value={Number(income.experimenter_research_supply || 0).toFixed(4)}/>
          <div className="section-label">RECENT COST</div>
          <KV name="MOVE" value={(-Number(costs.move || 0)).toFixed(4)}/>
          <KV name="DEFORMATION" value={(-Number(costs.deformation || 0)).toFixed(4)}/>
          <KV name="ENDOGENOUS" value={(-Number(costs.endogenous_motor || 0)).toFixed(4)}/>
          <div className="section-label">NET</div>
          <KV name="Δ reservoir" value={Number(r.work_reservoir_after) - Number(r.work_reservoir_before)}/>
          <KV name="unattributed" value={r.unattributed_work_delta}/>
          <div className="section-label">ACTION AUTHORITY</div>
          <KV name="constraint" value={r.action_realization_primary_constraint || (r.work_limited ? 'WORK_LIMITED' : '—')}/>
          <KV name="outcome" value={r.action_realization_outcome || '—'}/>
          <div className="section-label">LOW-WORK EPISODE</div>
          <KV name="state" value={r.episode_state || '—'}/>
          <KV name="ticks" value={r.low_work_episode_ticks ?? ep.ticks ?? 0}/>
          <KV name="local resource opportunity" value={(r.local_resource_opportunity || {}).status || 'NOT_AVAILABLE'}/>
        </>;
      })()}
    </Card>
    <Card title="LOCOMOTOR ECONOMY">
      {(() => {
        const le = frame.locomotor_economy || {};
        const latestMap = le.latest_by_agent || {};
        const r = latestMap[selectedAgentId]
          || (expKb.active ? (latestMap['undercover'] || latestMap['experimenter-body-0']) : null)
          || latestMap['undercover']
          || latestMap['experimenter-body-0']
          || Object.values(latestMap)[0];
        if (!r) return <div className="subtle">No locomotor economy receipt yet.</div>;
        const eff = r.work_per_realized_distance || {};
        const wMax = Number(r.work_reservoir_max || 0);
        const wAfter = Number(r.work_reservoir_after || 0);
        return <>
          <div className="subtle">Observer-only · DENOMINATOR_TOO_SMALL when |Δ| &lt; ε</div>
          <div className="section-label">RESERVOIR</div>
          <div className="selected-action">{wAfter.toFixed(3)} / {wMax.toFixed(3)}</div>
          <div className="section-label">MOVE WORK</div>
          <KV name="requested" value={r.move_work_requested}/>
          <KV name="allocated" value={r.move_work_allocated}/>
          <KV name="fraction" value={r.work_fraction}/>
          <div className="section-label">REALIZED</div>
          <KV name="distance" value={r.realized_distance}/>
          <KV name="alignment" value={r.alignment}/>
          <div className="section-label">EFFICIENCY</div>
          {eff.status === 'AVAILABLE'
            ? <KV name="work / distance" value={eff.value}/>
            : <div className="subtle">NOT AVAILABLE · {eff.status || 'displacement too small'}</div>}
          <div className="section-label">MOTOR AUTHORITY</div>
          <KV name="class" value={r.motor_authority_class}/>
          <KV name="PRIMARY CONSTRAINT" value={r.geo03_primary_constraint || '—'}/>
        </>;
      })()}
    </Card>
    <Card title="Landscape honesty">
      <div className="subtle">PHYSICAL FIELD = runtime ground truth</div>
      <div className="subtle">EMPIRICAL TRAVERSABILITY = observed movement outcomes</div>
      <div className="subtle">TRAJECTORY = realized agent motion</div>
      <div className="subtle">WRAP_PERIODIC · no hard walls · Observer-only</div>
    </Card>
    <GeometryPanel geometry={frame.geometry_interpretation} />
  </div>;

  const worldTab = <div className={`world-layout map-only ${fullscreen ? 'fullscreen' : ''}`}>
    <main className="world-center">
      <WorldMap key={mapKey} world={world} body={body} layer={layer} viewMode={worldView} perception={frame.perception}
        renderMode={renderMode} opacity={opacity} showGrid={showGrid} vectorDensity={.35} contourLevels={8}
        autoScale scaleMin={0} scaleMax={1} compositeLayers={[layer, 'flow_mag']}
        trajectory={(frame.trajectory?.points || []).slice(-trajectoryLength)} layers={layers}
        geometryInterpretation={frame.geometry_interpretation}
        agentsObserver={frame.agents_observer || []}
        interactionTargetId={frame.experimenter_interaction?.target?.agent_id || null}
        nearFieldSensor={
          deviceTool === 'sensors'
            ? (physical?.near_field_exteroception || null)
            : null
        }
        onHoverCell={setHoverCell} onSelectCell={inspectCell} />
      {hoverCell && <div className="cell-chip">{hoverCell.field}[{hoverCell.ix},{hoverCell.iy}] = {show(hoverCell.value, 3)}</div>}
    </main>
  </div>;

  const worldWithInspector = <div className="world-click-wrapper">{worldTab}</div>;
  void worldWithInspector;

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
    <Card title="Near-field exteroception" className="wide">
      <NearFieldSensorPanel
        physical={physical}
        agentObservation={agentObservation}
        mechanisms={mechanisms}
        onToggleMechanism={toggleMechanism}
        onSetVisionRadius={setVisionRadius}
      />
      <VestibularProprioceptionPanel
        physical={physical}
        agentObservation={agentObservation}
        mechanisms={mechanisms}
        onToggleMechanism={toggleMechanism}
      />
        <OscillatorySignalingPanel
          physical={physical}
          agentObservation={agentObservation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechanism}
        />
        <SensorimotorConsequencePanel />
        <HistoricalSensorimotorSelectionPanel />
        <SignalSensorimotorPanel />
        <ContextualProspectiveControlPanel
          frame={frame}
          agentId={desiredAgentId || requestedAgentId(frame)}
          detail={frame?.observer?.frame_detail}
        />

    </Card>
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
      <SignalContextPanel
        live={frame.signal_context_interpretation}
        selectedEvent={selectedEvent}
        sourceMeta={{
          run_id: currentRunId,
          generation: header.runtime_generation,
          tick: header.tick,
          telemetry_schema:
            frame.scientific_history?.telemetry_schema
            || frame.header?.telemetry_schema
            || 'SCIENTIFIC_TELEMETRY_V2',
          motor_schema: frame.motor_control?.schema || 'COMPOSITE_MOTOR_V1',
          coverage: Number(header.tick) > 0 ? 'LIVE CURRENT RUN' : 't0 — NO EVIDENCE YET',
        }}
      />
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
        <SignalContextPanel
        live={frame.signal_context_interpretation}
        selectedEvent={selectedEvent}
        sourceMeta={{
          run_id: currentRunId,
          generation: header.runtime_generation,
          tick: header.tick,
          telemetry_schema:
            frame.scientific_history?.telemetry_schema
            || frame.header?.telemetry_schema
            || 'SCIENTIFIC_TELEMETRY_V2',
          motor_schema: frame.motor_control?.schema || 'COMPOSITE_MOTOR_V1',
          coverage: Number(header.tick) > 0 ? 'LIVE CURRENT RUN' : 't0 — NO EVIDENCE YET',
        }}
      />
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
      <label>Preset<select value={preset} onChange={e => {
        const v = e.target.value;
        setPreset(v);
        if (v === 'MM 1.0 — Tiktaalik Public Beta 3') {
          setTwoAgentExperimental(true);
          setCognitionEnabled(true);
        }
      }}>
        <option>MM 1.0 — Tiktaalik Public Beta 3</option>
        <option>MM 1.0 — Tiktaalik</option>
        <option>CUSTOM</option>
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
      <label className="check"><input type="checkbox" checked={twoAgentExperimental} onChange={e => { setTwoAgentExperimental(e.target.checked); setPreset('CUSTOM'); }}/>Two-agent runtime (required for the recommended Beta 3 first run)</label>
      <div className="subtle" style={{ marginTop: 8, marginBottom: 8 }}>
        <strong>RECOMMENDED FIRST RUN:</strong> Apply the Public Beta 3 preset
        (two-agent, PSC off, Climate Control off). Before Play, open
        Experiment → Predictive and select <strong>OBSERVED_COMPOSITE</strong>.
        Run ~1000 ticks with PSC off, then enable PSC without resetting history.
      </div>
      <div style={{ marginTop: 8 }}>
      <div className="metric"><span>World ecology</span><strong>LIVE via Apply Live · structural via APPLY &amp; RESET WORLD</strong></div>
        <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_CLIMATE_DEFAULT' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_CLIMATE_DEFAULT'); setPreset('CUSTOM'); }}
          >Baseline Climate</button>
          <button
            type="button"
            className={ecologyPreset === 'CURRENT_LEGACY' ? 'active' : ''}
            onClick={() => { setEcologyPreset('CURRENT_LEGACY'); setPreset('CUSTOM'); }}
          >Current Legacy</button>
          <button
            type="button"
            className={ecologyPreset === 'GENTLE_FREE_MOVEMENT' ? 'active' : ''}
            onClick={() => { setEcologyPreset('GENTLE_FREE_MOVEMENT'); setPreset('CUSTOM'); }}
          >Gentle / Free Movement</button>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_A_STATIC_PATCHES' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_A_STATIC_PATCHES'); setPreset('CUSTOM'); }}
          >Static Patches</button>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_B_MIGRATING_RESOURCES' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_B_MIGRATING_RESOURCES'); setPreset('CUSTOM'); }}
          >Migrating</button>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_C_CHANGING_LANDSCAPE' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_C_CHANGING_LANDSCAPE'); setPreset('CUSTOM'); }}
          >Changing</button>
          <button
            type="button"
            className={ecologyPreset === 'STRUCTURED_TERRAIN_EXPERIMENTAL' ? 'active' : ''}
            onClick={() => { setEcologyPreset('STRUCTURED_TERRAIN_EXPERIMENTAL'); setPreset('CUSTOM'); }}
            title="Experimental: calibrated climate + spatial POTENTIAL/DRAG. Observer ground truth only."
          >Structured Terrain</button>
          <button
            type="button"
            className={ecologyPreset === 'STRUCTURED_WORLD_EXPERIMENTAL' ? 'active' : ''}
            onClick={() => { setEcologyPreset('STRUCTURED_WORLD_EXPERIMENTAL'); setPreset('CUSTOM'); }}
            title="Experimental: Structured Terrain + weak static ambient horizontal force. Observer GT only."
          >Structured World</button>
          <button
            className={ecologyPreset === 'CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL' ? 'active' : ''}
            onClick={() => { setEcologyPreset('CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL'); setPreset('CUSTOM'); }}
            title="Experimental: Structured World + season_period=800 + biased climate belt + soft F_fast weather (HABITABLE_WORLD_CALIBRATION_01). Not baseline."
          >Calibrated World</button>
        </div>
        <div className="subtle">
          Promoted default: BASELINE_CLIMATE_DEFAULT (env R_A/R_B, trickle=0).
          CURRENT_LEGACY preserves pre-promotion empty-resource physics.
          Structured Terrain enables spatial POTENTIAL/DRAG (experimental; not semantic obstacles).
          Structured World adds weak static ambient Fx/Fy on top of Structured Terrain.
          Calibrated World: season_period=800 + biased climate belt + soft local weather — experimental only.
          Observer may show R_A / R_B / terrain / ambient; cognition never receives food, terrain, or ambient GT labels.
        </div>
        {(ecologyPreset === 'STRUCTURED_TERRAIN_EXPERIMENTAL'
          || ecologyPreset === 'STRUCTURED_WORLD_EXPERIMENTAL'
          || ecologyPreset === 'CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL') && (
          <label style={{ marginTop: 6 }}>
            Terrain seed override (optional)
            <input
              value={terrainSeedOverride}
              onChange={e => setTerrainSeedOverride(e.target.value)}
              placeholder="blank = namespace from experiment seed"
            />
            <div className="subtle">Advanced matched-control: explicit terrain_seed. Leave blank for namespaced default.</div>
          </label>
        )}
      </div>
      <div className="subtle">APPLY &amp; RESET WORLD rebuilds the runtime. APPLY LIVE stamps ecology onto the current agents/history. Two-agent / body mass / v_max / map size are WORLD-STRUCTURAL.</div>
      <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
      <button type="button" onClick={async () => {
        try {
          const f = await applyLiveIntervention({ ecology_preset: ecologyPreset, category: 'ecology', source: 'observer_ui_legacy' });
          setControlMessage(f.control_receipt);
          if (f.control_receipt?.accepted) {
            setAppliedConfig((prev: any) => ({ ...(prev || {}), ecologyPreset }));
          }
          const agent = desiredAgentIdRef.current || requestedAgentId(f);
          const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
          setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
        } catch (err: any) {
          setControlMessage({ operation: 'LIVE_INTERVENTION', accepted: false, reason: String(err?.message || err) });
        }
      }}>APPLY LIVE ecology</button>
      <button type="button" className="active" onClick={async () => {
        const payload: any = {
          seed: +seed,
          cognition_enabled: cognitionEnabled,
          ecology_preset: ecologyPreset,
          world: { width: +width, height: +height, boundary_mode: 'WRAP_PERIODIC' },
          agent_body: { mass: +bodyMass, v_max: +bodyVMax },
        };
        if (preset === 'MM 1.0 — Tiktaalik Public Beta 3') {
          payload.public_preset = 'BETA3_RECOMMENDED';
          payload.psc_motor_resolution = 'OBSERVED_COMPOSITE';
          payload.agent_count = 2;
        } else {
          payload.mechanisms = Object.fromEntries(
            (mechanisms || [])
              .filter((m: any) => m && m.id && m.ablatable !== false)
              .map((m: any) => [m.id, !!m.enabled]),
          );
          if (twoAgentExperimental) payload.agent_count = 2;
        }
        if (targetTick.trim() !== '' && Number.isFinite(+targetTick)) payload.target_tick = +targetTick;
        if (Number.isFinite(+uiHz)) payload.ui_hz = +uiHz;
        if (Number.isFinite(+bufferCapacity)) payload.buffer_capacity = Math.max(8, +bufferCapacity);
        if (terrainSeedOverride.trim() !== '' && Number.isFinite(+terrainSeedOverride)) {
          payload.terrain_seed = +terrainSeedOverride;
          payload.world.terrain_seed = +terrainSeedOverride;
        }
        const f = await applyExperiment(payload);
        resetGeoEmpiricalCache();
        setControlMessage(f.control_receipt);
        if (Array.isArray(f.mechanism_result?.mechanisms)) {
          setMechanisms(f.mechanism_result.mechanisms);
        }
        await refreshAux().catch(() => undefined);
        setAppliedConfig({
          seed, width, height, ecologyPreset, cognitionEnabled, twoAgentExperimental,
          bodyMass, bodyVMax, targetTick, uiHz, bufferCapacity, terrainSeedOverride,
        });
        {
          const agent = desiredAgentIdRef.current || requestedAgentId(f);
          const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
          setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
        }
      }}>APPLY &amp; RESET WORLD</button>
      </div>
    </Card>
    <Card title="Current experiment">
      <KV name="Runtime" value={experiment.runtime?.type}/>
      <KV name="Agent count" value={experiment.runtime?.agent_count}/>
      <KV name="Selected observer agent" value={experiment.runtime?.selected_agent}/>
      <KV name="Cognition" value={experiment.runtime?.cognition_enabled ? 'ON' : 'OFF'}/>
      <KV name="Ecology preset" value={experiment.ecology_preset || experiment.runtime?.ecology_preset || header.ecology_preset || 'BASELINE_CLIMATE_DEFAULT'}/>
      <KV name="Seed" value={experiment.seed}/>
      <KV name="Observer Hz" value={experiment.observer?.ui_hz}/>
      <KV name="History frames" value={experiment.observer?.buffer_capacity}/>
      <KV name="Body mass" value={experiment.agent_body?.mass}/>
      <KV name="Body v_max" value={experiment.agent_body?.v_max}/>
      <div className="subtle">Available actions: {(experiment.actions_available || []).join(', ') || '—'}</div>
      <div className="availability">Bridge missing: {(experiment.actions_bridge_missing || []).join(', ') || 'none'}</div>
      <div className="subtle">{experiment.world?.supported_size_notes || experiment.note}</div>
    </Card>
    <Card title="OBSERVER GROUND TRUTH — Ecology">
      <div className="availability">Experimenter-only. Not present in agent observation or cognition.</div>
      <KV name="Ecology preset" value={
        experiment.observer_ground_truth?.ecology_preset
        || experiment.ecology_preset
        || header.ecology_preset
        || 'BASELINE_CLIMATE_DEFAULT'
      }/>
      <KV name="UI label" value={
        experiment.observer_ground_truth?.ecology_ui_label
        || experiment.ecology_ui_label
        || '—'
      }/>
      {experiment.observer_ground_truth?.action_authority?.coupling_label ? (
        <KV name="Action authority" value={experiment.observer_ground_truth.action_authority.coupling_label}/>
      ) : (
        <div className="subtle">Action authority: run locomotion audit / live GEO stats for measured coupling label.</div>
      )}
      {experiment.observer_ground_truth?.climate_ecology_enabled != null && (
        <KV name="Climate ecology" value={experiment.observer_ground_truth.climate_ecology_enabled ? 'ON' : 'OFF'}/>
      )}
      {experiment.observer_ground_truth?.effective_world && (
        <div className="science-card" style={{ padding: 8, marginTop: 8 }}>
          <b>EFFECTIVE WORLD</b>
          <div className="subtle">Observer GT — actual runtime subsystems (not cognition)</div>
          <KV name="Requested preset" value={experiment.observer_ground_truth.effective_world.requested_preset || '—'}/>
          <KV name="Climate package implies ON" value={experiment.observer_ground_truth.effective_world.climate_package_implies_climate ? 'YES' : 'NO'}/>
          <KV name="Climate ablated" value={experiment.observer_ground_truth.effective_world.climate_ablated ? 'YES' : 'NO'}/>
          <KV name="World fingerprint" value={experiment.observer_ground_truth.effective_world.world_fingerprint || '—'}/>
          {Array.isArray(experiment.observer_ground_truth.effective_world.overrides) && experiment.observer_ground_truth.effective_world.overrides.length > 0 && (
            <KV name="Overrides" value={experiment.observer_ground_truth.effective_world.overrides.join(', ')}/>
          )}
          {experiment.observer_ground_truth.effective_world.subsystems && (
            <div className="subtle" style={{ marginTop: 6 }}>
              T_eq {experiment.observer_ground_truth.effective_world.subsystems.climate_equilibrium_T_eq ? 'ON' : 'OFF'}
              · flow {experiment.observer_ground_truth.effective_world.subsystems.thermal_flow_vx_vy ? 'ON' : 'OFF'}
              · body←flow {experiment.observer_ground_truth.effective_world.subsystems.thermal_body_coupling ? 'ON' : 'OFF'}
              · wave←flow {experiment.observer_ground_truth.effective_world.subsystems.wave_flow_steering ? 'ON' : 'OFF'}
              · R_A/B {experiment.observer_ground_truth.effective_world.subsystems.resource_A_production ? 'ON' : 'OFF'}
              · terrain {experiment.observer_ground_truth.effective_world.subsystems.terrain ? 'ON' : 'OFF'}
              · ambient {experiment.observer_ground_truth.effective_world.subsystems.ambient_horizontal_force ? 'ON' : 'OFF'}
              · illum {experiment.observer_ground_truth.effective_world.subsystems.illumination ? 'ON' : 'OFF'}
            </div>
          )}
          <div className="availability">
            Legacy SPATIOTEMPORAL CLIMATE ECOLOGY toggle = ablation of climate_ecology.enabled.
            Preset stamps the package at Apply; Active mechanisms reflect the enabled bit.
          </div>
        </div>
      )}
      {(experiment.observer_ground_truth?.passive_reservoir_trickle != null
        || experiment.observer_ground_truth?.ecology?.passive_reservoir_trickle != null) && (
        <KV name="Passive reservoir trickle" value={
          experiment.observer_ground_truth?.passive_reservoir_trickle
          ?? experiment.observer_ground_truth?.ecology?.passive_reservoir_trickle
        }/>
      )}
      {(experiment.observer_ground_truth?.body_orientation_force_scale != null
        || experiment.observer_ground_truth?.ecology?.body_orientation_force_scale != null) && (
        <KV name="Body orientation force_scale" value={
          experiment.observer_ground_truth?.body_orientation_force_scale
          ?? experiment.observer_ground_truth?.ecology?.body_orientation_force_scale
        }/>
      )}
      {experiment.observer_ground_truth?.terrain && (
        <>
          <KV name="Terrain enabled" value={experiment.observer_ground_truth.terrain.enabled ? 'ON' : 'OFF'}/>
          {experiment.observer_ground_truth.terrain.enabled && (
            <>
              <KV name="Terrain mode" value={experiment.observer_ground_truth.terrain.mode || '—'}/>
              <KV name="Experiment seed" value={experiment.observer_ground_truth.terrain.experiment_seed ?? '—'}/>
              <KV name="Terrain seed" value={experiment.observer_ground_truth.terrain.terrain_seed ?? '—'}/>
              <KV name="Terrain seed source" value={experiment.observer_ground_truth.terrain.terrain_seed_source || '—'}/>
              <KV name="Terrain generator" value={experiment.observer_ground_truth.terrain.generator_version || '—'}/>
              <KV name="Generation attempt" value={experiment.observer_ground_truth.terrain.generation_attempt ?? '—'}/>
              <KV name="Generation fallback" value={experiment.observer_ground_truth.terrain.generation_fallback ? 'YES' : 'NO'}/>
              <KV name="Terrain checksum" value={experiment.observer_ground_truth.terrain.checksum || '—'}/>
              <KV name="Largest traversable frac" value={show(experiment.observer_ground_truth.terrain.largest_connected_traversable_frac, 3)}/>
              <KV name="Extreme gradient frac" value={show(experiment.observer_ground_truth.terrain.extreme_gradient_frac, 3)}/>
              <KV name="Potential min/max" value={`${show(experiment.observer_ground_truth.terrain.potential_min, 3)} / ${show(experiment.observer_ground_truth.terrain.potential_max, 3)}`}/>
              <KV name="Drag min/max" value={`${show(experiment.observer_ground_truth.terrain.drag_min, 3)} / ${show(experiment.observer_ground_truth.terrain.drag_max, 3)}`}/>
              <KV name="Gradient |∇| min/max" value={`${show(experiment.observer_ground_truth.terrain.gradient_mag_min, 3)} / ${show(experiment.observer_ground_truth.terrain.gradient_mag_max, 3)}`}/>
            </>
          )}
          <div className="subtle">
            OBSERVER GROUND TRUTH — POTENTIAL / DRAG / GRADIENT layers.
            Not agent observation. Not semantic obstacle / mountain / trap.
          </div>
        </>
      )}
      {experiment.observer_ground_truth?.ambient && (
        <>
          <KV name="Ambient enabled" value={experiment.observer_ground_truth.ambient.enabled ? 'ON' : 'OFF'}/>
          {experiment.observer_ground_truth.ambient.enabled && (
            <>
              <KV name="Ambient seed" value={experiment.observer_ground_truth.ambient.ambient_seed ?? '—'}/>
              <KV name="Ambient generator" value={experiment.observer_ground_truth.ambient.generator_version || '—'}/>
              <KV name="Ambient checksum" value={experiment.observer_ground_truth.ambient.checksum || '—'}/>
              <KV name="Fx min/max" value={`${show(experiment.observer_ground_truth.ambient.fx_min, 4)} / ${show(experiment.observer_ground_truth.ambient.fx_max, 4)}`}/>
              <KV name="Fy min/max" value={`${show(experiment.observer_ground_truth.ambient.fy_min, 4)} / ${show(experiment.observer_ground_truth.ambient.fy_max, 4)}`}/>
              <KV name="|F| mean" value={show(experiment.observer_ground_truth.ambient.magnitude_mean, 4)}/>
            </>
          )}
          <div className="subtle">OBSERVER GROUND TRUTH — AMBIENT FORCE. Not WIND/CURRENT labels. Not cognition.</div>
        </>
      )}
      <div className="subtle">
        Observer fields R_A / R_B / R_A_plus_R_B show ground-truth resource stocks.
        Not semantic food. Not agent observation.
      </div>
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
      <PscMotorResolutionControl
        pscEnabled={Boolean((mechanisms || []).find((m: any) => m.id === 'prospective_scenario_competition')?.enabled)}
        compact
        refreshKey={`rtmech-${header?.tick ?? ''}`}
      />
      <label>Search<input value={mechanismQuery} onChange={e => setMechanismQuery(e.target.value)} placeholder="id, label, category"/></label>
      <div className="mechanism-list">{filteredMechanisms.map(m => <div key={m.id}>
        <div><b>{m.label}</b><small>{m.promotion_class || '—'} · {m.category} · {m.scientific_status} · {m.toggle_policy}</small></div>
        <button disabled={!m.ablatable} onClick={() => toggleMechanism(m)}>{m.ablatable ? (m.enabled ? 'ON' : 'OFF') : 'READ ONLY'}</button>
        <p>{m.description}{mechanismHelp(m) ? (` — ` + mechanismHelp(m)) : ''}</p><p>Dependencies: {m.dependencies?.join(', ') || 'none'}</p>
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
  void experimentTab;

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

  const analyzePanel = <AnalyzeResultsPanel
        analysis={runAnalysis}
        analyzing={analyzing}
        analysisProgress={analysisProgress}
        analysisSource={analysisSource}
        onAnalysisSourceChange={setAnalysisSource}
        savedRuns={savedRunCatalog}
        selectedRunId={selectedSavedRunId}
        onSelectRunId={setSelectedSavedRunId}
        onRefreshRuns={refreshSavedRuns}
        onAnalyze={runExplicitAnalysis}
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
        onInspectTick={(t) => { inspect(t); openFloat('analysis'); }}
      />;

  const overviewPanel = <OverviewPanel
        runs={archivedRuns}
        currentRunId={currentRunId}
        openRunId={openRunId}
        setOpenRunId={setOpenRunId}
        filter={overviewFilter}
        setFilter={setOverviewFilter}
        agentFilter={overviewAgentFilter}
        setAgentFilter={setOverviewAgentFilter}
        onInspectTick={(t) => { inspect(t); }}
        onViewEvidence={(card) => {
          setEventFilter(card.category === 'SIGNAL' ? 'SIGNAL'
            : card.category === 'ACTION' ? 'ACTION'
            : card.category === 'COGNITION' ? 'COGNITION'
            : card.category === 'RESOURCE' ? 'RESOURCE'
            : card.category === 'BODY' ? 'BODY'
            : 'ALL');
          inspect(card.evidence.frame_tick ?? card.tick_start);
          setDeviceTool('signals');
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
      />;

  const editConfig = {
    seed, width, height, ecologyPreset, cognitionEnabled, twoAgentExperimental,
    bodyMass, bodyVMax, targetTick, uiHz, bufferCapacity, terrainSeedOverride,
  };
  const pending = configPending(editConfig, appliedConfig);
  const effWorld = experiment.observer_ground_truth?.effective_world;
  const overrideCount = Array.isArray(effWorld?.overrides) ? effWorld.overrides.length : 0;
  const undercoverIn = String(frame?.experimenter_interaction?.status || '') === 'CONTROL_ACTIVE';
  const agentsObs = frame.agents_observer || [];
  void agentsObs;

  const climateMechs = (mechanisms || []).filter((m: any) =>
    String(m.id || '').includes('spatiotemporal_climate')
    || (String(m.id || m.label || '').toLowerCase().includes('climate')
      && !String(m.id || '').includes('resource_ecology')),
  );
  const resourceEcoMechs = (mechanisms || []).filter((m: any) =>
    String(m.id || '').startsWith('resource_ecology_'),
  );
  const visionMechs = (mechanisms || []).filter((m: any) =>
    m.id === 'physical_near_field_vision'
    || m.id === 'illumination_cycle'
    || m.id === 'physical_body_optical_response',
  );
  const otherAblatable = (mechanisms || []).filter((m: any) =>
    m.ablatable && !climateMechs.includes(m) && !resourceEcoMechs.includes(m) && !visionMechs.includes(m),
  );
  const integrity = (frame as any)?.mechanism_integrity
    || (liveFrame as any)?.mechanism_integrity
    || null;

  function deviceBody(which: DeviceTool = deviceTool) {
    if (which === 'experiment') {
      const tabId = inspUi.tabs.EXPERIMENT || 'ecology';
      if (tabId === 'world') return (
        <div className="device-form">
          {pending && <div className="pending-banner">PENDING — APPLY &amp; RESET WORLD required</div>}
          <div className="section-gt subtle">WORLD-STRUCTURAL · creates new runtime generation</div>
          <label>Seed<input value={seed} onChange={e => setSeed(e.target.value)}/></label>
          <label>Width<input value={width} onChange={e => setWidth(e.target.value)}/></label>
          <label>Height<input value={height} onChange={e => setHeight(e.target.value)}/></label>
          <label>Boundary<select disabled><option>WRAP_PERIODIC</option></select></label>
          <div className="subtle">Terrain / ambient / illumination follow ecology preset on reset. Map size &amp; seed require world rebuild.</div>
          <button type="button" onClick={() => openFloat('effective_world')}>Open Effective World</button>
          <button type="button" onClick={() => openFloat('interventions')}>
            Interventions · {Number(frame?.world_intervention_summary?.n || frame?.world_interventions?.length || 0)}
          </button>
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button type="button" className="active" onClick={applyFromDevice} disabled={!!finalizing}>
              APPLY &amp; RESET WORLD
            </button>
            {pending && appliedConfig && (
              <button type="button" onClick={() => {
                setSeed(String(appliedConfig.seed));
                setWidth(String(appliedConfig.width));
                setHeight(String(appliedConfig.height));
                setEcologyPreset(String(appliedConfig.ecologyPreset));
                setCognitionEnabled(Boolean(appliedConfig.cognitionEnabled));
                setTwoAgentExperimental(Boolean(appliedConfig.twoAgentExperimental));
                setBodyMass(String(appliedConfig.bodyMass));
                setBodyVMax(String(appliedConfig.bodyVMax));
                setTargetTick(String(appliedConfig.targetTick ?? ''));
                setUiHz(String(appliedConfig.uiHz));
                setBufferCapacity(String(appliedConfig.bufferCapacity));
                setTerrainSeedOverride(String(appliedConfig.terrainSeedOverride ?? ''));
              }}>Discard pending</button>
            )}
          </div>
        </div>
      );
      if (tabId === 'model' || tabId === 'cognition') return (
        <div className="device-form">
          <div className="flag" style={{ alignSelf: 'flex-start' }}>LIVE</div>
          <div className="subtle">Cognition toggle applies LIVE. Agent count / body mass / v_max are WORLD-STRUCTURAL (use Set World).</div>
          <label>Preset<select value={preset} onChange={e => {
            const v = e.target.value;
            setPreset(v);
            if (v === 'MM 1.0 — Tiktaalik Public Beta 3') {
              setTwoAgentExperimental(true);
              setCognitionEnabled(true);
            }
          }}>
            <option>MM 1.0 — Tiktaalik Public Beta 3</option>
            <option>MM 1.0 — Tiktaalik</option>
            <option>CUSTOM</option>
          </select></label>
          <label className="check"><input type="checkbox" checked={cognitionEnabled} onChange={e => { setCognitionEnabled(e.target.checked); setPreset('CUSTOM'); }}/>Cognition enabled</label>
          <label className="check"><input type="checkbox" checked={twoAgentExperimental} onChange={e => { setTwoAgentExperimental(e.target.checked); setPreset('CUSTOM'); }}/>Two-agent runtime <span className="na">(requires world reset)</span></label>
          <label>Body mass<input value={bodyMass} onChange={e => { setBodyMass(e.target.value); setPreset('CUSTOM'); }}/> <span className="na">requires reset</span></label>
          <label>Body v_max<input value={bodyVMax} onChange={e => { setBodyVMax(e.target.value); setPreset('CUSTOM'); }}/> <span className="na">requires reset</span></label>
          <label>Target tick<input value={targetTick} onChange={e => setTargetTick(e.target.value)} placeholder="∞"/></label>
          <label>Observer Hz<input value={uiHz} onChange={e => setUiHz(e.target.value)}/></label>
          <label>History frames<input value={bufferCapacity} onChange={e => setBufferCapacity(e.target.value)}/></label>
          <div className="subtle">CURRENT RUNTIME: {experiment.runtime?.type || '—'} · agents {experiment.runtime?.agent_count ?? '—'}</div>
          <button type="button" onClick={() => openFloat('mechanisms')}>Mechanisms detail</button>
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button type="button" className="active" onClick={applyLiveFromDevice} disabled={!!finalizing}>
              APPLY LIVE
            </button>
            <div className="subtle">Does not rebuild agents · records WORLD_INTERVENTION when config changes. Body mass / v_max / two-agent require World tab reset.</div>
          </div>
        </div>
      );
      if (tabId === 'ecology') return (
        <div className="device-form">
          <div className="flag" style={{ alignSelf: 'flex-start' }}>LIVE INTERVENTION</div>
          <div className="subtle">Ecology preset stamps onto the current runtime — agents &amp; history continue.</div>
          <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
            {[
              ['BASELINE_CLIMATE_DEFAULT', 'Baseline Climate'],
              ['CURRENT_LEGACY', 'Current Legacy'],
              ['GENTLE_FREE_MOVEMENT', 'Gentle'],
              ['STRUCTURED_TERRAIN_EXPERIMENTAL', 'Structured Terrain'],
              ['STRUCTURED_WORLD_EXPERIMENTAL', 'Structured World'],
              ['CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL', 'Calibrated World'],
            ].map(([id, lab]) => (
              <button key={id} type="button" className={ecologyPreset === id ? 'active' : ''}
                onClick={() => { setEcologyPreset(id); setPreset('CUSTOM'); }}>{lab}</button>
            ))}
          </div>
          {(ecologyPreset.includes('STRUCTURED') || ecologyPreset.includes('CALIBRATED')) && (
            <label>Terrain seed override<input value={terrainSeedOverride} onChange={e => setTerrainSeedOverride(e.target.value)} placeholder="default"/>
              <span className="na"> seed override on live apply is ignored — use Set World</span>
            </label>
          )}
          <div className="metric"><span>Live preset</span><strong>{experiment.ecology_preset || header.ecology_preset || '—'}</strong></div>
          {overrideCount > 0 && <div className="flag overrides">Overrides: {overrideCount}</div>}
          <div className="section-label">Climate dynamics</div>
          <div className="subtle">Temporal thermal / insolation ecology (T_eq, seasonal cycle). Does not erase R_A/R_B. LIVE.</div>
          {climateMechs.map((m: any) => (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span>{m.label || m.id}</span>
              <button type="button" disabled={!m.ablatable} title={!m.ablatable ? 'NOT INDEPENDENTLY ABLATABLE' : 'LIVE mutable'} onClick={() => toggleMechanism(m)}>
                {m.ablatable ? (m.enabled ? 'ON' : 'OFF') : 'READ ONLY'}
              </button>
            </div>
          ))}
          {!climateMechs.length && <div className="na">Climate mechanism row not in registry snapshot</div>}
          <div className="section-label">R_A ecology</div>
          <div className="subtle">Environmental production, persistence and regeneration of R_A.</div>
          {resourceEcoMechs.filter((m: any) => String(m.id).includes('_A')).map((m: any) => (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span>{m.label || m.id}</span>
              <button type="button" onClick={() => toggleMechanism(m)}>{m.enabled ? 'ON' : 'OFF'}</button>
            </div>
          ))}
          <div className="section-label">R_B ecology</div>
          <div className="subtle">Environmental production, persistence and regeneration of R_B.</div>
          {resourceEcoMechs.filter((m: any) => String(m.id).includes('_B')).map((m: any) => (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span>{m.label || m.id}</span>
              <button type="button" onClick={() => toggleMechanism(m)}>{m.enabled ? 'ON' : 'OFF'}</button>
            </div>
          ))}
          {!resourceEcoMechs.length && <div className="na">Resource ecology mechanism rows not in registry</div>}
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button type="button" className="active" onClick={applyLiveFromDevice} disabled={!!finalizing}>
              APPLY LIVE
            </button>
            <div className="subtle">Does not rebuild agents · records WORLD_INTERVENTION when config changes.</div>
          </div>
        </div>
      );
      if (tabId === 'body') return (
        <div className="device-form section-gt">
          <div className="flag" style={{ alignSelf: 'flex-start' }}>LIVE</div>
          <div className="subtle">WORLD GT — R_A / R_B (anonymous environmental quantities). Ecology gated independently via Experimental (Climate / R_A / R_B).</div>
          <KV name="R_A mean" value={effWorld?.resources_now?.R_A?.mean ?? experiment.observer_ground_truth?.resources?.R_A_mean}/>
          <KV name="R_A max" value={effWorld?.resources_now?.R_A?.max}/>
          <KV name="R_B mean" value={effWorld?.resources_now?.R_B?.mean ?? experiment.observer_ground_truth?.resources?.R_B_mean}/>
          <KV name="R_B max" value={effWorld?.resources_now?.R_B?.max}/>
          <button type="button" onClick={() => openFloat('effective_world')}>Effective World</button>
        </div>
      );
      if (tabId === 'predictive') {
        const pscMech = (mechanisms || []).find((m: any) => m.id === 'prospective_scenario_competition');
        const smcMech = (mechanisms || []).find((m: any) => m.id === 'sensorimotor_consequence_model');
        const hssMech = (mechanisms || []).find((m: any) => m.id === 'historical_sensorimotor_selection_bridge');
        const cpoMech = (mechanisms || []).find((m: any) => m.id === 'contextual_predictive_organization');
        const cgpMech = (mechanisms || []).find((m: any) => m.id === 'context_grounded_prospection');
        const ppcMech = (mechanisms || []).find((m: any) => m.id === 'persistent_prospective_control');
        const pscOn = Boolean(pscMech?.enabled);
        const renderMech = (m: any, extraTitle?: string) => {
          if (!m) return null;
          const deps = (m.dependencies || []) as string[];
          const missing = deps.filter((d) => !(mechanisms || []).find((x: any) => x.id === d && x.enabled));
          return (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span title={(m.description || '') + (mechanismHelp(m) ? (' — ' + mechanismHelp(m)) : '') + (extraTitle ? (' — ' + extraTitle) : '')}>
                {m.label || m.id}
              </span>
              <button type="button" disabled={!m.ablatable} onClick={() => toggleMechanism(m)}>
                {m.enabled ? 'ON' : 'OFF'}
              </button>
              {missing.length > 0 && (
                <span className="subtle" title="Dependency-aware Observer hint — does not auto-enable">
                  requires {missing.join(', ')}
                </span>
              )}
            </div>
          );
        };
        return (
          <div className="device-form">
            <div className="flag" style={{ alignSelf: 'flex-start' }}>LIVE</div>
            <div className="subtle">
              Predictive / PSC controls. Motor resolution is a MODE, not an ON/OFF mechanism.
              Hot-toggle preserves history, SMC, and body.
            </div>
            <div className="section-label">PROSPECTIVE SCENARIO COMPETITION</div>
            {pscMech ? (
              <div className="metric" style={{ alignItems: 'center' }}>
                <span title={(pscMech.description || '') + (mechanismHelp(pscMech) ? (' — ' + mechanismHelp(pscMech)) : '')}>
                  {pscMech.label || pscMech.id}
                </span>
                <button type="button" disabled={!pscMech.ablatable} onClick={() => toggleMechanism(pscMech)}>
                  {pscMech.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
            ) : (
              <div className="na">PSC mechanism not in registry snapshot</div>
            )}
            <PscMotorResolutionControl
              pscEnabled={pscOn}
              refreshKey={`${header?.tick ?? ''}-${header?.run_id ?? ''}-${String(pscOn)}`}
            />
            <div className="section-label">4.26–4.28 Context → Prospection → Control</div>
            <div className="subtle">
              Experimental. Primary labels are scientific. “Intention-like” is Observer interpretation only — no INTENTION variable in cognition.
            </div>
            {renderMech(cpoMech, 'Reusable higher-order predictive organization formed from repeated relational experience.')}
            {renderMech(cgpMech, 'Prospective composition using learned higher-order contextual structures.')}
            {renderMech(ppcMech, 'Selected prospective continuation may remain causally relevant while predictive support persists. Observer interpretation: intention-like prospective control.')}
            <div className="section-label">Related predictive mechanisms</div>
            {[smcMech, hssMech].filter(Boolean).map((m: any) => (
              <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
                <span title={(m.description || '') + (mechanismHelp(m) ? (' — ' + mechanismHelp(m)) : '')}>
                  {m.label || m.id}
                </span>
                <button type="button" disabled={!m.ablatable} onClick={() => toggleMechanism(m)}>
                  {m.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
            ))}
          </div>
        );
      }
      if (tabId === 'perception' || tabId === 'ablations') return (
        <div className="device-form">
          <div className="flag" style={{ alignSelf: 'flex-start' }}>LIVE INTERVENTION</div>
          {tabId === 'perception' && (
            <>
              <div className="section-label">Vision / illumination</div>
              <div className="subtle">Physical near-field vision and illumination cycle — independent LIVE gates.</div>
              {visionMechs.map((m: any) => (
                <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
                  <span title={(m.description || '') + (mechanismHelp(m) ? (' — ' + mechanismHelp(m)) : '')}>{m.label || m.id}</span>
                  <button type="button" onClick={() => toggleMechanism(m)}>{m.enabled ? 'ON' : 'OFF'}</button>
                </div>
              ))}
              {(() => {
                const aso = String(
                  physical?.orientation?.ACTIVE_SENSOR_ORIENTATION
                  || physical?.near_field_exteroception?.ACTIVE_SENSOR_ORIENTATION
                  || 'NOT_AVAILABLE',
                );
                const headOn = Boolean(physical?.orientation?.articulated_head_enabled);
                const headHeading = physical?.orientation?.head_world_heading
                  ?? physical?.near_field_exteroception?.head_world_heading;
                const bodyTheta = physical?.orientation?.theta
                  ?? physical?.near_field_exteroception?.body_theta;
                return (
                  <>
                    <div className="metric">
                      <span>ACTIVE_SENSOR_ORIENTATION</span>
                      <strong>{aso}</strong>
                    </div>
                    {aso === 'AVAILABLE' ? (
                      <div className="metric">
                        <span>head_world_heading (Observer GT)</span>
                        <strong>{headHeading == null ? '—' : Number(headHeading).toFixed(4)}</strong>
                      </div>
                    ) : (
                      <div className="subtle">
                        NOT_AVAILABLE = articulated head OFF — no independent sensor DOF.
                        Vision FOV still uses body θ={bodyTheta == null ? '—' : Number(bodyTheta).toFixed(4)} (locomotion heading).
                        {headOn ? ' (config claims head ON — check runtime authority)' : ''}
                      </div>
                    )}
                  </>
                );
              })()}
            </>
          )}
          {tabId === 'ablations' && (
            <>
              <div className="section-label">Other ablatable mechanisms</div>
              {otherAblatable.slice(0, 40).map((m: any) => (
                <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
                  <span title={(m.description || '') + (mechanismHelp(m) ? (' — ' + mechanismHelp(m)) : '')}>{m.label || m.id}</span>
                  <button type="button" onClick={() => toggleMechanism(m)}>{m.enabled ? 'ON' : 'OFF'}</button>
                </div>
              ))}
              <div className="section-label">Flow channel ablations</div>
              <div className="na">Direct / wave thermal-body coupling — NOT independently available in runtime (see CLIMATE_AUTHORITY_AUDIT_01). No fake switches.</div>
              <button type="button" onClick={() => openFloat('effective_world')}>Effective World truth</button>
              <button type="button" onClick={() => openFloat('mechanisms')}>All mechanisms</button>
              <button type="button" onClick={() => openFloat('interventions')}>
                Interventions · {Number(frame?.world_intervention_summary?.n || 0)}
              </button>
            </>
          )}
        </div>
      );
    }
    if (which === 'intervention') return (
      <div className="device-form">
        <div className="metric"><span>UNDERCOVER</span><strong>{undercoverIn ? 'IN WORLD' : 'OUT'}</strong></div>
        <InteractPanel live={frame.experimenter_interaction} globalPressed={expKb.pressed} onRefresh={() => undefined} />
      </div>
    );
    if (which === 'observe') return null;
    if (which === 'sensors') {
      const visionMech = (mechanisms || []).find((m: any) => m.id === 'physical_near_field_vision');
      const vRow = visionRowFromIntegrity(integrity);
      const runtimeR = Math.max(
        1,
        Math.min(
          3,
          Number(
            physical?.near_field_exteroception?.vision_radius
            ?? physical?.near_field_exteroception?.radius
            ?? vRow?.runtime_radius
            ?? vRow?.radius
            ?? 3,
          ),
        ),
      );
      const configuredR = vRow?.configured_radius != null
        ? Number(vRow.configured_radius)
        : runtimeR;
      const visionMismatch = Boolean(
        vRow?.status && vRow.status !== 'READY',
      ) || (configuredR !== runtimeR);
      return (
      <div className="device-form section-agent">
        <MechanismPreflightPanel integrity={integrity} />
        <VisionExperimenterControl
          visionEnabled={visionAuthorityOn}
          runtimeRadius={runtimeR}
          configuredRadius={configuredR}
          mismatch={visionMismatch}
          visionMechanismPresent={!!visionMech}
          onToggleVision={visionMech ? () => toggleMechanism(visionMech) : undefined}
          onSetRadius={setVisionRadius}
        />
        <div className="section-label">Agent-accessible channels</div>
        <VisionBars
          observation={agentObservation}
          visionEnabled={visionAuthorityOn}
          agentLabel={String(selectedAgentId || 'agent_0').toUpperCase()}
        />
        <div className="subtle">AGENT-ACCESSIBLE exo_* · FOV overlay on map while Sensors is open (Observer GT only).</div>
        <div className="metric"><span>Illumination cycle</span><strong>{(mechanisms || []).find((m: any) => m.id === 'illumination_cycle')?.enabled ? 'ON' : 'OFF'}</strong></div>
        <div className="metric"><span>Illumination (GT)</span><strong>{physical?.near_field_exteroception?.illumination ?? '—'}</strong></div>
        {(() => {
          const aso = String(
            physical?.orientation?.ACTIVE_SENSOR_ORIENTATION
            || physical?.near_field_exteroception?.ACTIVE_SENSOR_ORIENTATION
            || 'NOT_AVAILABLE',
          );
          const fovAxis = physical?.near_field_exteroception?.sensor_forward_axis
            ?? physical?.near_field_exteroception?.head_world_heading
            ?? physical?.orientation?.theta;
          return (
            <>
              <div className="metric">
                <span>ACTIVE_SENSOR_ORIENTATION</span>
                <strong>{aso}</strong>
              </div>
              {aso === 'AVAILABLE' ? (
                <div className="metric">
                  <span>sensor FOV axis (Observer GT)</span>
                  <strong>{fovAxis == null ? '—' : Number(fovAxis).toFixed(4)}</strong>
                </div>
              ) : (
                <div className="subtle">
                  NOT_AVAILABLE = articulated head OFF — no independent sensor DOF.
                  Map FOV uses body θ={fovAxis == null ? '—' : Number(fovAxis).toFixed(4)}.
                  No LOOK_AT / TRACK / ATTENTION.
                </div>
              )}
            </>
          );
        })()}
        <button type="button" onClick={() => openFloat('sensor_inspector')}>Open Vision Inspector</button>
        <NearFieldSensorPanel
          physical={physical}
          agentObservation={agentObservation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechanism}
          onSetVisionRadius={setVisionRadius}
        />
        <VestibularProprioceptionPanel
          physical={physical}
          agentObservation={agentObservation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechanism}
          cognitionEnabled={
            !(
              String(selectedAgentId || '').toLowerCase().includes('undercover')
              && !(mechanisms || []).some((m: any) => m.id === 'cognition' && m.enabled)
            )
          }
        />
      </div>
      );
    }
    if (which === 'signals') return (
      <div className="device-form">
        <MechanismAwareSignals
          events={events}
          physical={physical}
          mechanisms={mechanisms}
          agentObservation={agentObservation}
          attribution={
            selectedEvent?.evidence?.source_attribution
            || selectedEvent?.evidence?.attribution
            || selectedEvent?.attribution
            || null
          }
        />
        <button type="button" onClick={() => openFloat('signal_forensics')}>Signal Forensics V2</button>
        <div className="subtle">Analyzer candidate relations open in forensics — not shown as meaning.</div>
      </div>
    );
    if (which === 'analyze') return (
      <div className="device-form section-analyzer">
        <div className="metric"><span>Current run</span><strong>{currentRunId || '—'}</strong></div>
        <div className="metric"><span>Archived</span><strong>{archivedRuns.length}</strong></div>
        {liveFrame?.header?.status === 'RUNNING' ? (
          <div className="pending-banner">
            LIVE SIMULATION PRIORITY — full Analyzer evidence package is not auto-run while RUNNING.
            Pause/Stop, then Analyze Current; or use Analyze snapshot explicitly (may compete for I/O).
          </div>
        ) : null}
        <button type="button" className="active" onClick={() => { void runAnalyzeCurrent(); openFloat('analysis'); }}>Analyze Current</button>
        <button type="button" onClick={() => { refreshSavedRuns(); openFloat('analysis'); }}>Open Analysis Window</button>
        <button type="button" onClick={() => runExplicitAnalysis()}>Run explicit analysis</button>
      </div>
    );
    if (which === 'runs') return (
      <div className="device-form">
        <button type="button" onClick={() => { refreshSavedRuns(); openFloat('run_details'); }}>Run catalog</button>
        <div className="subtle">Uses existing session/local archive — not a fake database.</div>
        {overviewPanel}
      </div>
    );
    if (which === 'world_status') return (
      <div className="device-form section-gt">
        <div className="metric"><span>Requested</span><strong>{effWorld?.requested_preset || experiment.ecology_preset || '—'}</strong></div>
        <div className="metric"><span>Fingerprint</span><strong>{String(effWorld?.world_fingerprint || '').slice(0, 8) || '—'}</strong></div>
        <div className="metric"><span>Overrides</span><strong>{overrideCount}</strong></div>
        <div className="metric"><span>Mechanisms</span><strong>{(mechanisms || []).filter((m: any) => m.enabled).length} active</strong></div>
        <div className="metric"><span>Config history</span><strong>{frame?.world_intervention_summary?.configuration_history || (Number(frame?.world_intervention_summary?.n || 0) > 0 ? 'MULTI_REGIME' : 'STATIC')}</strong></div>
        <button type="button" onClick={() => openFloat('interventions')}>
          INTERVENTIONS · {Number(frame?.world_intervention_summary?.n || frame?.world_interventions?.length || 0)}
        </button>
        <button type="button" onClick={() => openFloat('effective_world')}>Full Effective World</button>
        <button type="button" onClick={() => openFloat('mechanisms')}>Mechanism list</button>
      </div>
    );
    return null;
  }

  function floatBody(id: FloatingWindowId) {
    if (id === 'analysis') return <div className="section-analyzer">{analyzePanel}</div>;
    if (id === 'sensor_inspector') return (
      <div className="section-agent">
        <NearFieldSensorPanel
          physical={physical}
          agentObservation={agentObservation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechanism}
          onSetVisionRadius={setVisionRadius}
        />
        <VestibularProprioceptionPanel
          physical={physical}
          agentObservation={agentObservation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechanism}
        />
        <OscillatorySignalingPanel
          physical={physical}
          agentObservation={agentObservation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechanism}
        />
        <SensorimotorConsequencePanel />
        <HistoricalSensorimotorSelectionPanel />
        <SignalSensorimotorPanel />
        <ContextualProspectiveControlPanel
          frame={frame}
          agentId={desiredAgentId || requestedAgentId(frame)}
          detail={frame?.observer?.frame_detail}
        />

      </div>
    );
    if (id === 'signal_forensics') return (
      <div className="section-analyzer">
        <SignalContextPanel
          live={frame.signal_context_interpretation}
          selectedEvent={selectedEvent}
          sourceMeta={{
            run_id: currentRunId,
            generation: header.runtime_generation,
            tick: header.tick,
            telemetry_schema:
              frame.scientific_history?.telemetry_schema
              || frame.header?.telemetry_schema
              || 'SCIENTIFIC_TELEMETRY_V2',
            motor_schema: frame.motor_control?.schema || 'COMPOSITE_MOTOR_V1',
            coverage: Number(header.tick) > 0 ? 'LIVE CURRENT RUN' : 't0 — NO EVIDENCE YET',
          }}
        />
      </div>
    );
    if (id === 'effective_world') {
      const ew = effWorld || {};
      const sub = ew.subsystems || {};
      return (
        <div className="section-gt">
          <KV name="Requested preset" value={ew.requested_preset || '—'}/>
          <KV name="Climate package implies ON" value={ew.climate_package_implies_climate ? 'YES' : 'NO'}/>
          <KV name="Climate ablated" value={ew.climate_ablated ? 'YES' : 'NO'}/>
          <KV name="Climate dynamics" value={(ew.climate_ecology?.enabled || ew.subsystems?.climate_equilibrium_T_eq) ? 'ON' : 'OFF'}/>
          <KV name="R_A ecology" value={(ew.climate_ecology?.resource_ecology_A_enabled ?? ew.subsystems?.resource_A_production) ? 'ON' : 'OFF'}/>
          <KV name="R_B ecology" value={(ew.climate_ecology?.resource_ecology_B_enabled ?? ew.subsystems?.resource_B_production) ? 'ON' : 'OFF'}/>
          <KV name="Near-field vision" value={(ew.subsystems?.physical_near_field_vision ?? ew.subsystems?.near_field_perception) ? 'ON' : 'OFF'}/>
          <KV name="Illumination cycle" value={(ew.subsystems?.illumination_cycle ?? ew.subsystems?.illumination) ? 'ON' : 'OFF'}/>
          <KV name="ACTIVE_SENSOR_ORIENTATION" value={ew.near_field_exteroception?.ACTIVE_SENSOR_ORIENTATION || 'NOT_AVAILABLE'}/>
          <KV name="World fingerprint" value={ew.world_fingerprint || '—'}/>
          {Array.isArray(ew.overrides) && ew.overrides.length > 0 && <KV name="Overrides" value={ew.overrides.join(', ')}/>}
          <div className="subtle">
            T_eq {sub.climate_equilibrium_T_eq ? 'ON' : 'OFF'} · flow {sub.thermal_flow_vx_vy ? 'ON' : 'OFF'}
            · body←flow {sub.thermal_body_coupling ? 'ON' : 'OFF'} · wave←flow {sub.wave_flow_steering ? 'ON' : 'OFF'}
            · R_A/B {sub.resource_A_production ? 'ON' : 'OFF'} · terrain {sub.terrain ? 'ON' : 'OFF'}
            · ambient {sub.ambient_horizontal_force ? 'ON' : 'OFF'} · illum {sub.illumination ? 'ON' : 'OFF'}
          </div>
          <div className="availability">Observer GT only — never cognition.</div>
        </div>
      );
    }
    if (id === 'mechanisms') return (
      <div className="float-fill-list">
        <div className="metric"><span>Active</span><strong>{(mechanisms || []).filter((m: any) => m.enabled).length}</strong></div>
        <div className="float-fill-scroll">
          {(mechanisms || []).map((m: any) => (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span>{m.label || m.id}</span>
              <button type="button" disabled={!m.ablatable} onClick={() => toggleMechanism(m)}>
                {m.enabled ? 'ON' : 'OFF'}
              </button>
            </div>
          ))}
        </div>
      </div>
    );
    if (id === 'geometry') return <GeometryPanel geometry={frame.geometry_interpretation} />;
    if (id === 'interventions') {
      const items = Array.isArray(frame?.world_interventions) ? frame.world_interventions : [];
      return (
        <div className="section-gt">
          <div className="metric">
            <span>CONFIGURATION HISTORY</span>
            <strong>{items.length ? 'MULTI_REGIME' : 'STATIC'}</strong>
          </div>
          <div className="metric"><span>Interventions</span><strong>{items.length}</strong></div>
          <div className="subtle">Live mutations only — APPLY &amp; RESET WORLD clears this list for the new generation.</div>
          <div style={{ maxHeight: 280, overflow: 'auto', marginTop: 8 }}>
            {!items.length && <div className="na">No live WORLD_INTERVENTION events this generation.</div>}
            {items.map((ev: any) => {
              const ch = ev.changes || {};
              const keys = Object.keys(ch);
              return (
                <div key={ev.event_id || `${ev.simulation_tick}-${ev.category}`} style={{ marginBottom: 10, fontSize: 12 }}>
                  <div><b>t{ev.simulation_tick ?? ev.tick}</b> · {String(ev.intervention_category || ev.category || '—').toUpperCase()}</div>
                  {keys.map((k) => (
                    <div key={k} className="subtle">
                      {k}: {String(ch[k]?.old)} → {String(ch[k]?.new)}
                    </div>
                  ))}
                  <div className="na">
                    fp {String(ev.effective_world_fingerprint_before || '').slice(0, 8)} → {String(ev.effective_world_fingerprint_after || '').slice(0, 8)}
                    · reset={String(ev.history_reset)}/{String(ev.cognition_reset)}/{String(ev.body_reset)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }
    if (id === 'observe_overlays') return layerControls;
    if (id === 'observe_inspector') return inspector;
    if (id === 'agent_details') return agentTab;
    if (id === 'run_details') return overviewPanel;
    if (id === 'raw') return <pre style={{ fontSize: 10, whiteSpace: 'pre-wrap' }}>{JSON.stringify(frame, null, 2)}</pre>;
    return <div className="na">Empty</div>;
  }
  void floatBody;

  const applyFromDevice = async () => {
    const payload: any = {
      seed: +seed,
      cognition_enabled: cognitionEnabled,
      ecology_preset: ecologyPreset,
      world: { width: +width, height: +height, boundary_mode: 'WRAP_PERIODIC' },
      agent_body: { mass: +bodyMass, v_max: +bodyVMax },
    };
    if (preset === 'MM 1.0 — Tiktaalik Public Beta 3') {
      payload.public_preset = 'BETA3_RECOMMENDED';
      payload.psc_motor_resolution = 'OBSERVED_COMPOSITE';
      payload.agent_count = 2;
    } else {
      payload.mechanisms = Object.fromEntries(
        (mechanisms || [])
          .filter((m: any) => m && m.id && m.ablatable !== false)
          .map((m: any) => [m.id, !!m.enabled]),
      );
      if (twoAgentExperimental) payload.agent_count = 2;
    }
    if (targetTick.trim() !== '' && Number.isFinite(+targetTick)) payload.target_tick = +targetTick;
    if (Number.isFinite(+uiHz)) payload.ui_hz = +uiHz;
    if (Number.isFinite(+bufferCapacity)) payload.buffer_capacity = Math.max(8, +bufferCapacity);
    if (terrainSeedOverride.trim() !== '' && Number.isFinite(+terrainSeedOverride)) {
      payload.terrain_seed = +terrainSeedOverride;
      payload.world.terrain_seed = +terrainSeedOverride;
    }
    const f = await applyExperiment(payload);
    resetGeoEmpiricalCache();
    setControlMessage(f.control_receipt);
    if (Array.isArray(f.mechanism_result?.mechanisms)) {
      setMechanisms(f.mechanism_result.mechanisms);
    }
    await refreshAux().catch(() => undefined);
    setAppliedConfig({ ...editConfig });
    const agent = desiredAgentIdRef.current || requestedAgentId(f);
    const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
    setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
  };

  const applyLiveFromDevice = async () => {
    const screen = tabToExperimentScreen(inspUi.tabs.EXPERIMENT || 'ecology');
    const payload: any = {
      source: 'observer_ui',
      category: screen === 'set_model' ? 'model'
        : screen === 'set_ecology' ? 'ecology'
        : screen === 'set_resources' ? 'resources'
        : 'experimental',
    };
    if (screen === 'set_ecology') {
      payload.ecology_preset = ecologyPreset;
    } else if (screen === 'set_model') {
      payload.cognition_enabled = cognitionEnabled;
      if (targetTick.trim() !== '' && Number.isFinite(+targetTick)) payload.target_tick = +targetTick;
      if (Number.isFinite(+uiHz)) payload.ui_hz = +uiHz;
      if (Number.isFinite(+bufferCapacity)) payload.buffer_capacity = Math.max(8, +bufferCapacity);
    }
    try {
      const f = await applyLiveIntervention(payload);
      setControlMessage(f.control_receipt);
      if (f.control_receipt?.accepted) {
        setAppliedConfig((prev: any) => ({
          ...(prev || editConfig),
          ecologyPreset: screen === 'set_ecology' ? ecologyPreset : (prev?.ecologyPreset ?? ecologyPreset),
          cognitionEnabled: screen === 'set_model' ? cognitionEnabled : (prev?.cognitionEnabled ?? cognitionEnabled),
          targetTick: screen === 'set_model' ? targetTick : (prev?.targetTick ?? targetTick),
          uiHz: screen === 'set_model' ? uiHz : (prev?.uiHz ?? uiHz),
          bufferCapacity: screen === 'set_model' ? bufferCapacity : (prev?.bufferCapacity ?? bufferCapacity),
        }));
      }
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
      setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
    } catch (err: any) {
      setControlMessage({ operation: 'LIVE_INTERVENTION', accepted: false, reason: String(err?.message || err) });
    }
  };

  const observeAttribution =
    selectedEvent?.evidence?.source_attribution
    || selectedEvent?.evidence?.attribution
    || selectedEvent?.attribution
    || null;
  const observeSlice = (section: 'agent' | 'body' | 'environment' | 'cognition' | 'predictive') => (
    <ObserveV2Panel
      section={section}
      frame={frame}
      events={events}
      timeline={timeline}
      runId={currentRunId}
      agentId={selectedAgentId}
      agentObservation={agentObservation}
      attribution={observeAttribution}
      onSelectEvent={(e) => setSelectedEvent(e)}
      rawEvidenceSlot={section === 'cognition' ? timelineTab : undefined}
    />
  );
  const observeByTab = {
    agent: (
      <>
        {observeSlice('agent')}
        <InspectorAccordion id="observe-agent-details" title="Diagnostics · agent details" defaultOpen={false}>
          {agentTab}
        </InspectorAccordion>
      </>
    ),
    body: observeSlice('body'),
    environment: (
      <>
        {observeSlice('environment')}
        <InspectorAccordion id="observe-overlays" title="Overlays" defaultOpen={false}>
          {layerControls}
        </InspectorAccordion>
        <InspectorAccordion id="observe-geometry" title="Geometry" defaultOpen={false}>
          <GeometryPanel geometry={frame.geometry_interpretation} />
        </InspectorAccordion>
        <InspectorAccordion id="observe-cell-inspector" title="Diagnostics · cell / body inspector" defaultOpen={false}>
          {inspector}
        </InspectorAccordion>
      </>
    ),
    cognition: (
      <>
        {observeSlice('cognition')}
        <InspectorAccordion id="observe-mind" title="Diagnostics · mind" defaultOpen={false}>
          {mindTab}
        </InspectorAccordion>
        <InspectorAccordion id="observe-data" title="Diagnostics · data" defaultOpen={false}>
          {dataTab}
        </InspectorAccordion>
      </>
    ),
    predictive: (
      <>
        {observeSlice('predictive')}
        <InspectorAccordion id="observe-signal-forensics" title="Diagnostics · signal forensics" defaultOpen={false}>
          <SignalContextPanel
            live={frame.signal_context_interpretation}
            selectedEvent={selectedEvent}
            sourceMeta={{
              run_id: currentRunId,
              generation: header.runtime_generation,
              tick: header.tick,
              telemetry_schema:
                frame.scientific_history?.telemetry_schema
                || frame.header?.telemetry_schema
                || 'SCIENTIFIC_TELEMETRY_V2',
              motor_schema: frame.motor_control?.schema || 'COMPOSITE_MOTOR_V1',
              coverage: Number(header.tick) > 0 ? 'LIVE CURRENT RUN' : 't0 — NO EVIDENCE YET',
            }}
          />
        </InspectorAccordion>
      </>
    ),
  };

  return <div className="desktop app" data-observer-shell data-workspace={lab.workspace}>
    <ClockDriver />
    <InterestDriver />
    <AuxPollDriver refreshAux={refreshAuxStable} mode={mode} />
    <ObserverHeader
      onControl={control}
      onStop={openStopDialog}
      disabled={!!finalizing || connection === 'DISCONNECTED'}
    />

    {expKb.active && (
      <div className="subtle" style={{ padding: '3px 10px', borderBottom: '1px solid var(--line)', fontSize: 11 }}>
        YOU CONTROL EXPERIMENTER BODY · WASD · SPACE wait · Q/E FIELD {expKb.pressed ? `· ${expKb.pressed}` : ''}
      </div>
    )}
    <LifecycleBanners />
    {analysisCopyMsg && <div className="control-receipt ok">{analysisCopyMsg}</div>}
    {stopDialog && <div className="stop-dialog-backdrop" style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div className="panel" style={{ minWidth: 360, maxWidth: 480, padding: 16 }}>
        <h3>Stop simulation?</h3>
        <div className="metric"><span>Current tick</span><strong>{stopDialog.tick}</strong></div>
        {!stopConfirmNoSave ? (
          <div className="toolbar-row" style={{ marginTop: 12, gap: 8 }}>
            <button className="active" onClick={saveAndStop}>Save &amp; Stop</button>
            <button onClick={stopWithoutSaving}>Stop without saving</button>
            <button onClick={() => { setStopDialog(null); setStopConfirmNoSave(false); }}>Cancel</button>
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            <div className="availability">Discard unsaved experiment?</div>
            <button className="bad" onClick={stopWithoutSaving}>Confirm discard</button>
            <button onClick={() => setStopConfirmNoSave(false)}>Back</button>
          </div>
        )}
      </div>
    </div>}

    <div className="desktop-body">
      <div className={`control-workspace ${deviceCollapsed ? 'collapsed' : 'expanded'}`}>
        <ControlDevice
          collapsed={deviceCollapsed}
          onToggleCollapse={() => setDeviceCollapsed(v => !v)}
          tool={deviceTool}
          activeTool={railSelectedTool(lab, deviceTool, deviceCollapsed)}
          onTool={(t) => {
            const { dest, nextWorkspace } = applyRailDestination(t, workspaceStore.get());
            setDeviceTool(dest.deviceTool);
            setDeviceCollapsed(dest.deviceCollapsed);
            workspaceStore.set(nextWorkspace);
          }}
          experimentScreen={experimentScreen}
          onExperimentScreen={setExperimentScreen}
          pending={pending}
          overrideCount={overrideCount}
          undercoverInWorld={undercoverIn}
          selectedAgentLabel={String(selectedAgentId || 'agent_0').toUpperCase()}
        />
      </div>

      <main className="sim-workspace" ref={simWorkspaceRef}>
        {lab.workspace === 'ANALYZE' ? (
          <AnalyzeWorkspace
            analysis={runAnalysis}
            analyzing={analyzing}
            analysisProgress={analysisProgress}
            analysisSource={analysisSource}
            onAnalysisSourceChange={setAnalysisSource}
            savedRuns={savedRunCatalog}
            selectedRunId={selectedSavedRunId}
            onSelectRunId={setSelectedSavedRunId}
            onRefreshRuns={refreshSavedRuns}
            onAnalyze={runExplicitAnalysis}
            onAnalyzeCurrent={runAnalyzeCurrent}
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
            onInspectTick={(t) => { inspect(t); }}
            overview={overviewPanel}
          />
        ) : lab.workspace === 'INSPECT' ? (
          <InspectWorkspace
            prefs={worldPrefs}
            mechanisms={mechanisms}
            onToggleMechanism={(id, enabled) => {
              const m = (mechanisms || []).find((x: any) => x.id === id);
              if (m) void toggleMechanism(m, enabled);
            }}
            onSetVisionRadius={setVisionRadius}
            onSelectCell={inspectCell}
            expPressed={expKb.pressed}
            mapKey={mapKey}
            extras={{
              experiment: deviceBody('experiment'),
              observeByTab,
              runs: deviceBody('runs'),
              worldStatus: deviceBody('world_status'),
              sensors: (
                <>
                  <VisionBars
                    observation={agentObservation}
                    visionEnabled={visionAuthorityOn}
                    agentLabel={String(selectedAgentId || 'agent_0').toUpperCase()}
                  />
                  <button type="button" onClick={() => openFloat('sensor_inspector')}>Open Vision Inspector</button>
                </>
              ),
              signals: (
                <>
                  <MechanismAwareSignals
                    events={events}
                    physical={physical}
                    mechanisms={mechanisms}
                    agentObservation={agentObservation}
                    attribution={
                      selectedEvent?.evidence?.source_attribution
                      || selectedEvent?.evidence?.attribution
                      || selectedEvent?.attribution
                      || null
                    }
                  />
                  <button type="button" onClick={() => openFloat('signal_forensics')}>Signal Forensics V2</button>
                </>
              ),
            }}
            onSectionTab={(inspector, tabId) => {
              if (inspector === 'EXPERIMENT' || inspector === 'MECHANISMS' || inspector === 'PREDICTIVE') {
                setExperimentScreen(tabToExperimentScreen(
                  inspector === 'PREDICTIVE' ? 'predictive' : inspector === 'MECHANISMS' ? 'ablations' : tabId,
                ));
              }
            }}
          />
        ) : (
          <RunWorkspace
            prefs={worldPrefs}
            onSelectCell={inspectCell}
            onSelectAgent={selectObserverAgent}
            mapKey={mapKey}
          />
        )}
      </main>
    </div>
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
