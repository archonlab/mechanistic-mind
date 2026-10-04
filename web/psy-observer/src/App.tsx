import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import './styles/app.css';
import type { ObserverFrame, ViewMode } from './types';
import { ObserverHeader } from './chrome/ObserverHeader';
import { LifecycleBanners } from './chrome/LifecycleBanners';
import { LeftSidebar } from './chrome/LeftSidebar';
import { BottomEvidencePanel, BottomDrawerAffordance } from './chrome/BottomEvidencePanel';
import { layoutShellClassName, layoutShellStore, useLayoutShell } from './chrome/layoutShellUi';
import type { ObservationDestination } from './observer/layoutShell';
import { RunWorkspace } from './workspaces/RunWorkspace';
import { InspectWorkspace } from './workspaces/InspectWorkspace';
import { FpvObservationWorkspace } from './components/FpvObservationWorkspace';
import { SettingInfoHelp } from './components/SettingInfoHelp';
import { currentRuntimePresentation, nextRunInitialLabel, nextRunScheduleLabel } from './components/pscUiAuthority';
import {
  EventsCentralWorkspace,
  HearingObservationWorkspace,
  OrganismCentralWorkspace,
  ScientificToolsLanding,
  SimulationInfoWorkspace,
} from './workspaces/ObservationCentralWorkspaces';
import { InspectorAccordion } from './inspectors/primitives';
import { AnalyzeWorkspace } from './workspaces/AnalyzeWorkspace';
import { AuxPollDriver, ClockDriver, DerivedViewportSubscriptionDriver, InterestDriver, TabVisibilityDriver } from './observer/drivers';
import {
  frameStore,
  lifecycleStore,
  inspectorUiStore,
  noteRender,
  openLeftHearingWorkspace,
  slimStatusFromFrame,
  statusStore,
  workspaceStore,
} from './observer/stores';
import { applyRailDestination } from './observer/railNav';
import {
  PUBLIC_MODEL_PRESETS,
  UI_PUBLIC_LABEL_TIKTAALIK_BETA31,
  UI_PRESET_CUSTOM,
  presetModifiedStatusLabel,
  publicPresetFromUi,
  uiPresetFromPublic,
  modelLineFromUiPreset,
  isNamedCanonicalUiPreset,
  isPublicModelSelectorEntry,
} from './observer/modelPreset';
import {
  applyStatusFor,
  applyStatusLabel,
  buildCanonicalApplyPayload,
  buildReviewRecipe,
  canonicalSourceFromApplyResponse,
  draftPresetModified,
  mergeCanonicalIntoSnapshot,
  mechanismMapFromCatalog,
  overlayMechanismEnabled,
  snapshotFromCanonical,
  snapshotFromEditors,
  snapshotFromRuntimeFrame,
  snapshotsEqual,
  uiFieldsFromSnapshot,
  visionDraftFromPhysical,
  type ApplyStatus,
  type ExperimentSnapshot,
  type VisionDraft,
} from './observer/experimentDraft';
import { useWorkspaceStore } from './observer/useExternalStore';
import {
  applyExperiment, applyLiveIntervention, connectLive, fetchCanonicalPreset, getSnapshot, getSnapshotMeta, getState, getTimeline,
  getStopInfo, getSaveJob, inspectTick, postControl, researcherForcedMotor, researcherLocalSignalEmission, replayTick,
  listRuns, saveAnalysisReport,
  startAnalysisJob, listAnalysisJobs, getAnalysisJob, getAnalysisJobResult, cancelAnalysisJob,
  setGeometryAgentFilter, getGeometryCell, hydrateGeometryRun,
  geometryUseLive, geometryClearSaved,
} from './api/client';
import { notifyC1Restore } from './acoustic/c1EngineBridge';
import { notifySav2Restore } from './acoustic/sav2EngineBridge';

// Mandatory researcher overlay labels for local physical signal transport (never agent-facing).
const LOCAL_SIGNAL_OVERLAY_LABELS = ['researcher-only', 'not agent-accessible', 'not a semantic message', 'finite range', 'finite propagation delay'];
import { mergeMechanismWarmState } from './lifecycleReceipt';
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
import {
  DEFAULT_VERTICAL_EXAGGERATION,
  elevationGridValid,
  readVerticalDisplay,
  TRAIL_LENGTH_SAMPLES,
  TRAIL_RESEARCHER_LABEL,
  type TerrainDisplayMode,
  type TrailDisplayMode,
  type TrailLengthMode,
  VERTICAL_EXAGGERATION_LABEL,
} from './observer/verticalDisplay';

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
import { PscOffTicksControl } from './components/PscOffTicksControl';
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
import {
  INTERRUPTED_BY_APPLICATION_EXIT,
  INTERRUPTED_USER_MESSAGE,
  jobRestoreAllowed,
  saveActiveJobId,
} from './analysis/analyzerJobProgress';
import { AnalyzeResultsPanel, type AnalysisSourceMode, type RunCatalogEntry } from './components/AnalyzeResultsPanel';
import { OverviewPanel } from './components/OverviewPanel';
import { compressConsecutiveEvents, compressedEventSummary } from './eventCompression';
import { eventCategory as sharedEventCategory } from './observe/eventCategory';
import {
  invalidateEventsOnRunOrGeneration,
  observeBufferIdentityFromFrame,
  type ObserveBufferIdentity,
} from './observe/bufferIdentity';
import { TiktaalikEyeDock } from './components/TiktaalikEyeDock';
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
  if (tab === 'model') return 'set_model';
  if (tab === 'ecology') return 'set_ecology';
  if (tab === 'body') return 'set_resources';
  if (tab === 'psc' || tab === 'predictive') return 'set_psc';
  if (tab === 'vision') return 'set_vision';
  if (tab === 'review') return 'menu';
  return 'experimental';
}

function peColdHistoryEvictionApplied(frame: any): boolean {
  const block = frame?.experiment?.pe_cold_history_eviction;
  if (block && typeof block.applied === 'boolean') return Boolean(block.applied);
  if (typeof frame?.experiment?.runtime?.pe_cold_history_eviction === 'boolean') {
    return Boolean(frame.experiment.runtime.pe_cold_history_eviction);
  }
  if (typeof frame?.header?.pe_cold_history_eviction === 'boolean') {
    return Boolean(frame.header.pe_cold_history_eviction);
  }
  return true;
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
  const [, setExperimentScreen] = useState<ExperimentScreen>('menu');
  const inspUi = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  const [deviceCollapsed, setDeviceCollapsed] = useState(
    // S7B: left observation sidebar open by default (legacy left rail defaulted collapsed).
    desktopPrefs.collapsed === undefined ? false : Boolean(desktopPrefs.collapsed),
  );
  const layoutShell = useLayoutShell();
  const [observationDest, setObservationDest] = useState<ObservationDestination>('WORLD');
  useEffect(() => {
    // Destination → right inspector section (display routing only; no Apply/reset).
    const cur = workspaceStore.get();
    if (observationDest === 'WORLD' || observationDest === 'MODEL') {
      workspaceStore.set({
        ...cur,
        workspace: 'INSPECT',
        inspector: 'EXPERIMENT',
        inspectorOpen: true,
      });
      const ui = inspectorUiStore.get();
      inspectorUiStore.set({
        ...ui,
        tabs: { ...ui.tabs, EXPERIMENT: observationDest === 'MODEL' ? 'model' : 'world' },
      });
    } else if (observationDest === 'ORGANISM') {
      const { nextWorkspace } = applyRailDestination('observe', cur);
      workspaceStore.set(nextWorkspace);
    } else if (observationDest === 'EVENTS') {
      const { nextWorkspace } = applyRailDestination('signals', cur);
      workspaceStore.set(nextWorkspace);
    } else if (observationDest === 'SIMULATION_INFO') {
      const { nextWorkspace } = applyRailDestination('world_status', cur);
      workspaceStore.set(nextWorkspace);
    } else if (observationDest === 'FPV_VISION' || observationDest === 'HEARING') {
      workspaceStore.set({ ...cur, workspace: 'INSPECT', inspectorOpen: true });
    } else if (observationDest === 'SCIENTIFIC_TOOLS') {
      workspaceStore.set({ ...cur, workspace: 'INSPECT' });
    }
  }, [observationDest]);
  useEffect(() => {
    // One-time alignment from legacy DESKTOP_PREFS → layout shell left track.
    layoutShellStore.patch({ leftOpen: !deviceCollapsed });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const leftOpen = layoutShell.leftOpen;
  const setLeftOpen = (open: boolean) => {
    layoutShellStore.patch({ leftOpen: open });
    setDeviceCollapsed(!open);
  };
  const [floatWindows, setFloatWindows] = useState<FloatingWindowState[]>([]);
  void floatWindows;
  const [simBounds, setSimBounds] = useState({ width: 800, height: 600 });
  const simWorkspaceRef = useRef<HTMLDivElement | null>(null);
  const [appliedConfig, setAppliedConfig] = useState<Record<string, string | boolean | number> | null>(null);
  const [activeExperiment, setActiveExperiment] = useState<ExperimentSnapshot | null>(null);
  const [canonicalBaseline, setCanonicalBaseline] = useState<ExperimentSnapshot | null>(null);
  const [mechanismDraft, setMechanismDraft] = useState<Record<string, boolean>>({});
  const [visionDraft, setVisionDraft] = useState<VisionDraft | null>(null);
  const [pscMotorDraft, setPscMotorDraft] = useState<string | null>(null);
  const [pscOffTicksDraft, setPscOffTicksDraft] = useState<number | null | undefined>(undefined);
  const [applyingExperiment, setApplyingExperiment] = useState(false);
  const [applyExperimentFailed, setApplyExperimentFailed] = useState(false);
  const appliedExperimentGenerationRef = useRef<number | null>(null);
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
  const [cellRaw, setCellRaw] = useState(false);
  const [arInspect, setArInspect] = useState<any | null>(null);
  const [geoAgentFilter, setGeoAgentFilter] = useState(prefs.geoAgentFilter || 'ALL');
  const [savedGeoRunId, setSavedGeoRunId] = useState('');
  const [selectedGeoEvent, setSelectedGeoEvent] = useState<any>(null);
  const [layer, setLayer] = useState(prefs.layer || 'T');
  const [worldView, setWorldView] = useState(prefs.worldView || 'PHYSICAL');
  const [volumeWorkspace, setVolumeWorkspace] = useState<'MAP' | 'VOLUME' | 'SURFACE'>('MAP');
  const [renderMode, setRenderMode] = useState(prefs.renderMode || 'COMPOSITE');
  const [terrainMode, setTerrainMode] = useState<TerrainDisplayMode>(
    (prefs.terrainMode as TerrainDisplayMode) || 'OPTICAL',
  );
  const [showClearanceStems, setShowClearanceStems] = useState(prefs.showClearanceStems !== false);
  const [showEventMarkers, setShowEventMarkers] = useState(prefs.showEventMarkers !== false);
  const [showElevationContours, setShowElevationContours] = useState(!!prefs.showElevationContours);
  const [verticalExaggeration, setVerticalExaggeration] = useState(
    Number(prefs.verticalExaggeration) > 0 ? Number(prefs.verticalExaggeration) : DEFAULT_VERTICAL_EXAGGERATION,
  );
  const [trailMode, setTrailMode] = useState<TrailDisplayMode>(
    (prefs.trailMode as TrailDisplayMode) || 'SELECTED',
  );
  const [trailLengthMode, setTrailLengthMode] = useState<TrailLengthMode>(
    (prefs.trailLengthMode as TrailLengthMode) || 'NORMAL',
  );
  const [opacity, setOpacity] = useState(Number.isFinite(prefs.opacity) ? prefs.opacity : .9);
  const [showGrid, setShowGrid] = useState(Boolean(prefs.showGrid));
  const [showManipulatorReach, setShowManipulatorReach] = useState(true);
  const [showObjectVelocity, setShowObjectVelocity] = useState(false);
  const [layers, setLayers] = useState<Record<string, boolean>>({ ...DEFAULT_LAYERS, ...(prefs.layers || {}) });
  const [trajectoryLength, setTrajectoryLength] = useState(Number.isFinite(prefs.trajectoryLength) ? prefs.trajectoryLength : LIVE_FE_TRAJECTORY_DISPLAY_DEFAULT);
  const [seed, setSeed] = useState('17');
  const [width, setWidth] = useState('32');
  const [height, setHeight] = useState('32');
  const [preset, setPreset] = useState(
    typeof prefs.preset === 'string' && prefs.preset ? prefs.preset : UI_PUBLIC_LABEL_TIKTAALIK_BETA31,
  );
  const [cognitionEnabled, setCognitionEnabled] = useState(true);
  const [peColdHistoryEviction, setPeColdHistoryEviction] = useState(true);
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
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisSource, setAnalysisSource] = useState<AnalysisSourceMode>('current');
  const [savedRunCatalog, setSavedRunCatalog] = useState<RunCatalogEntry[]>([]);
  const [selectedSavedRunId, setSelectedSavedRunId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState<string>('');
  const [analysisProgressDetail, setAnalysisProgressDetail] = useState<any>(null);
  const [activeAnalysisJobId, setActiveAnalysisJobId] = useState<string | null>(null);
  const analysisPollGenRef = useRef(0);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => {
    saveActiveJobId(activeAnalysisJobId, {
      instanceId: appIdentity?.instance_id,
      packageIdentity: appIdentity?.package_identity,
    });
  }, [activeAnalysisJobId, appIdentity?.instance_id, appIdentity?.package_identity]);
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

  function applyAnalysisProgressDetail(jobId: string, st: any) {
    const phase = String(st.phase || st.status || 'QUEUED');
    const ticks = st.ticks_reconstructed ?? st.records_processed ?? st.completed_units ?? '';
    const last = st.last_tick_processed ?? '';
    const pct = st.percent;
    const statusText = String(st.status_text || st.message || `ANALYSIS: ${phase} · stories=${ticks} · last_tick=${last}`);
    setAnalysisProgress(statusText);
    setAnalysisProgressDetail({
      job_id: jobId,
      schema: st.schema,
      state: String(st.state || st.status || phase),
      status: st.status,
      phase,
      phase_id: st.phase_id || phase,
      phase_label: st.phase_label,
      phase_index: st.phase_index,
      phase_count: st.phase_count,
      completed_units: st.completed_units ?? st.records_processed ?? null,
      total_units: st.total_units ?? null,
      phase_processed: st.phase_processed ?? st.completed_units ?? null,
      phase_total: st.phase_total ?? st.total_units ?? null,
      overall_processed: st.overall_processed ?? st.completed_units ?? null,
      overall_total: st.overall_total ?? st.total_units ?? null,
      percent: pct == null ? null : Number(pct),
      status_text: statusText,
      message: st.message || statusText,
      terminal: Boolean(st.terminal),
      error_code: st.error_code ?? null,
      error_message: st.error_message ?? st.error ?? null,
      started_at: st.started_at ?? null,
      updated_at: st.updated_at ?? null,
      last_progress_at: st.last_progress_at ?? null,
      worker_heartbeat_at: st.worker_heartbeat_at ?? st.heartbeat_at ?? null,
      heartbeat_at: st.heartbeat_at ?? st.worker_heartbeat_at ?? null,
      elapsed_seconds: st.elapsed_seconds ?? st.elapsed_s ?? null,
      elapsed_s: st.elapsed_s ?? st.elapsed_seconds ?? null,
      records_per_second: st.records_per_second ?? null,
      unit_label: st.unit_label ?? 'ticks',
      snapshot_terminal_tick: st.snapshot_terminal_tick ?? null,
      snapshot_record_count: st.snapshot_record_count ?? null,
      current_operation: st.current_operation ?? null,
      recent_log: Array.isArray(st.recent_log) ? st.recent_log.slice(-48) : [],
      alive: st.alive,
      ui_health: st.ui_health ?? null,
      cancel_requested: Boolean(st.cancel_requested),
    });
  }

  async function pollAnalysisJob(jobId: string) {
    const gen = ++analysisPollGenRef.current;
    for (;;) {
      if (gen !== analysisPollGenRef.current) return { aborted: true };
      const st = await getAnalysisJob(jobId);
      applyAnalysisProgressDetail(jobId, st);
      const phase = String(st.phase || st.status || 'QUEUED');
      const state = String(st.state || st.status || phase).toUpperCase();
      if (phase === 'COMPLETE' || st.status === 'COMPLETE' || state === 'COMPLETED') return st;
      if (phase === 'FAILED' || st.status === 'FAILED' || state === 'FAILED') {
        const code = st.error_code ? ` [${st.error_code}]` : '';
        const phaseFail = st.failed_phase ? ` phase=${st.failed_phase}` : '';
        throw new Error(`${String(st.error || st.error_message || 'analysis failed').slice(0, 500)}${code}${phaseFail}`);
      }
      if (phase === 'CANCELLED' || st.status === 'CANCELLED' || state === 'CANCELLED') {
        throw new Error('analysis cancelled');
      }
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  async function finishAnalysisPackage(jobId: string, source: 'current' | 'saved', runId: string | null) {
    const pkg = await getAnalysisJobResult(jobId);
    pkg.source = source;
    if (pkg.error) {
      setAnalysisError(String(pkg.error));
      setAnalysisCopyMsg(String(pkg.error));
      return null;
    }
    const built = analyzeEvidencePackage(pkg, {
      frame: source === 'current' ? (liveFrame ?? viewFrame ?? undefined) : undefined,
      mechanisms,
    });
    if (built.evidence_meta) {
      built.evidence_meta.source = source;
      if (source === 'saved' && runId) built.evidence_meta.run_id = runId;
      if (pkg.analysis_snapshot) {
        (built.evidence_meta as any).analysis_snapshot = pkg.analysis_snapshot;
        if (pkg.analysis_snapshot.snapshot_terminal_tick != null) {
          built.evidence_meta.analysis_cutoff_tick = pkg.analysis_snapshot.snapshot_terminal_tick;
        }
      }
    }
    setRunAnalysis(built);
    setAnalysisError(null);
    if (source === 'saved' && runId && built.analysis_log) {
      try {
        await saveAnalysisReport({
          run_id: runId,
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
    return built;
  }

  async function runHeavyAnalysis(source: 'current' | 'saved', runId: string | null) {
    const started = await startAnalysisJob({ source, run_id: runId });
    // Server duplicate guard: resume existing equivalent job instead of erroring hard.
    if (!started.accepted && started.existing && started.job_id) {
      setActiveAnalysisJobId(String(started.job_id));
      setAnalysisProgress(`ANALYSIS: RECONNECT ${started.job_id}`);
      await pollAnalysisJob(String(started.job_id));
      return finishAnalysisPackage(String(started.job_id), source, runId);
    }
    if (!started.accepted) {
      throw new Error(String(started.error || 'job not accepted'));
    }
    setActiveAnalysisJobId(String(started.job_id));
    setAnalysisProgress(`ANALYSIS: QUEUED ${started.job_id}`);
    setRunAnalysis(null); // new job started — clear prior completed output
    await pollAnalysisJob(started.job_id);
    return finishAnalysisPackage(started.job_id, source, runId);
  }

  async function runExplicitAnalysis() {
    if (analyzing) return;
    setAnalyzing(true);
    setAnalysisProgress('ANALYSIS: QUEUED');
    setAnalysisProgressDetail({
      phase: 'DISCOVER_EVIDENCE',
      phase_index: 0,
      percent: 0,
      status_text: 'ANALYSIS: QUEUED',
      terminal: false,
      state: 'QUEUED',
    });
    setAnalysisError(null);
    try {
      await runHeavyAnalysis(
        analysisSource,
        analysisSource === 'saved' ? selectedSavedRunId : null,
      );
    } catch (err) {
      const msg = String(err);
      setAnalysisError(msg);
      setAnalysisCopyMsg(msg);
    } finally {
      setAnalyzing(false);
      setAnalysisProgress('');
      setActiveAnalysisJobId(null);
    }
  }

  /**
   * Analyze Current — same evidence package path as explicit analysis for the
   * live/current run. Falls back to live-frame optical ticks only when
   * scientific_rows are absent (historical Visual Forensics → NOT_AVAILABLE).
   */
  async function runAnalyzeCurrent() {
    if (analyzing) return;
    setAnalyzing(true);
    setAnalysisProgress('ANALYSIS: QUEUED');
    setAnalysisError(null);
    setRunAnalysis(null);
    try {
      const frame = liveFrame ?? viewFrame ?? undefined;
      await runHeavyAnalysis('current', null);
      void frame;
    } catch (err) {
      const msg = String(err);
      setAnalysisError(msg);
      setAnalysisCopyMsg(msg);
      rebuildAnalysis({ frame: liveFrame ?? viewFrame ?? undefined, mode: 'LIVE' });
    } finally {
      setAnalyzing(false);
      setAnalysisProgress('');
      setActiveAnalysisJobId(null);
    }
  }

  async function cancelActiveAnalysis() {
    const jobId = activeAnalysisJobId || analysisProgressDetail?.job_id;
    if (!jobId) return;
    try {
      await cancelAnalysisJob(String(jobId));
      setAnalysisProgress('ANALYSIS: CANCEL REQUESTED');
    } catch (err) {
      setAnalysisCopyMsg(String(err));
    }
  }

  // Reconnect only to jobs owned by this live backend instance (never localStorage alone).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (analyzing) return;
      if (!appIdentity?.instance_id || !appIdentity?.package_identity) return;
      let storedOwner = { instanceId: null as string | null, packageIdentity: null as string | null };
      try {
        storedOwner = {
          instanceId: localStorage.getItem('mm.observer.analyzer.ownerInstanceId'),
          packageIdentity: localStorage.getItem('mm.observer.analyzer.ownerPackageIdentity'),
        };
      } catch { /* ignore */ }
      let jobId = activeAnalysisJobId;
      if (!jobId) {
        try {
          jobId = localStorage.getItem('mm.observer.analyzer.activeJobId');
        } catch {
          jobId = null;
        }
      }
      if (!jobId) {
        try {
          const listed = await listAnalysisJobs();
          const active = (listed.active || [])[0];
          if (active?.job_id && jobRestoreAllowed(active, appIdentity, storedOwner)) {
            jobId = String(active.job_id);
          }
        } catch {
          return;
        }
      }
      if (!jobId || cancelled) return;
      try {
        const st = await getAnalysisJob(jobId);
        if (cancelled) return;
        const state = String(st.state || st.status || st.phase || '').toUpperCase();
        if (state === INTERRUPTED_BY_APPLICATION_EXIT) {
          setAnalysisCopyMsg(INTERRUPTED_USER_MESSAGE);
          setActiveAnalysisJobId(null);
          saveActiveJobId(null);
          return;
        }
        if (!jobRestoreAllowed(st, appIdentity, storedOwner)) {
          setActiveAnalysisJobId(null);
          saveActiveJobId(null);
          return;
        }
        applyAnalysisProgressDetail(jobId, st);
        const terminal = Boolean(st.terminal) || ['COMPLETED', 'COMPLETE', 'FAILED', 'CANCELLED', INTERRUPTED_BY_APPLICATION_EXIT].includes(state);
        if (terminal) {
          if (state === 'COMPLETED' || state === 'COMPLETE') {
            setActiveAnalysisJobId(jobId);
            setAnalyzing(true);
            try {
              await finishAnalysisPackage(jobId, analysisSource, analysisSource === 'saved' ? selectedSavedRunId : null);
            } catch (err) {
              setAnalysisError(String(err));
            } finally {
              setAnalyzing(false);
              setActiveAnalysisJobId(null);
            }
          } else if (state === 'FAILED') {
            setAnalysisError(String(st.error_message || st.error || 'analysis failed').slice(0, 500));
            setActiveAnalysisJobId(null);
          } else {
            setActiveAnalysisJobId(null);
          }
          return;
        }
        setActiveAnalysisJobId(jobId);
        setAnalyzing(true);
        try {
          await pollAnalysisJob(jobId);
          await finishAnalysisPackage(jobId, analysisSource, analysisSource === 'saved' ? selectedSavedRunId : null);
        } catch (err) {
          setAnalysisError(String(err));
        } finally {
          if (!cancelled) {
            setAnalyzing(false);
            setActiveAnalysisJobId(null);
          }
        }
      } catch {
        saveActiveJobId(null);
      }
    })();
    return () => { cancelled = true; };
    // Wait for health identity so a stale localStorage job cannot restore across instances.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appIdentity?.instance_id, appIdentity?.package_identity]);

  function handleAnalysisSourceChange(s: AnalysisSourceMode) {
    setAnalysisSource(s);
    setRunAnalysis(null);
    setAnalysisError(null);
    setAnalysisCopyMsg(null);
  }

  function handleSelectSavedRunId(id: string | null) {
    setSelectedSavedRunId(id);
    setRunAnalysis(null);
    setAnalysisError(null);
  }

  async function copyAnalyzerReport() {
    if (!runAnalysis) return;
    const { formatMarkdownReport } = await import('./analysis/analyzerExport');
    const text = formatMarkdownReport(runAnalysis);
    try {
      await navigator.clipboard.writeText(text);
      setAnalysisCopyMsg('Report copied to clipboard');
    } catch {
      setAnalysisCopyMsg('Clipboard unavailable — use SAVE .MD');
    }
  }

  async function saveAnalyzerMarkdown() {
    if (!runAnalysis) return;
    const { formatMarkdownReport, exportFilenames, downloadBlob } = await import('./analysis/analyzerExport');
    const text = formatMarkdownReport(runAnalysis);
    const names = exportFilenames(runAnalysis);
    downloadBlob(names.md, 'text/markdown;charset=utf-8', text);
    setAnalysisCopyMsg(`Saved ${names.md}`);
  }

  async function saveAnalyzerJson() {
    if (!runAnalysis) return;
    const { formatJsonExport, exportFilenames, downloadBlob } = await import('./analysis/analyzerExport');
    const text = formatJsonExport(runAnalysis);
    const names = exportFilenames(runAnalysis);
    downloadBlob(names.json, 'application/json;charset=utf-8', text);
    setAnalysisCopyMsg(`Saved ${names.json}`);
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

  function adoptRuntimeExperiment(f: any, mechs?: any[]) {
    const catalog = Array.isArray(mechs) && mechs.length
      ? mechs
      : (Array.isArray(f?.mechanism_result?.mechanisms) ? f.mechanism_result.mechanisms : []);
    const canonical = canonicalSourceFromApplyResponse(f);
    const fromCanonical = snapshotFromCanonical(canonical);
    let snap = fromCanonical;
    if (!snap) {
      const visOn = Boolean((catalog || []).find((m: any) => m.id === 'physical_near_field_vision')?.enabled);
      const vis = visionDraftFromPhysical(f?.physical, visOn);
      const psc = String(
        f?.experiment?.runtime?.psc_motor_resolution
        || f?.header?.psc_motor_resolution
        || 'LOCO_FACTORIZED',
      );
      snap = snapshotFromRuntimeFrame(f, catalog, { vision: vis, pscMotorResolution: psc });
    }
    const mappedPreset = uiPresetFromPublic(snap.public_preset || f?.header?.public_preset);
    if (mappedPreset) setPreset(mappedPreset);
    if (snap.public_preset && canonical?.canonical === true) {
      setCanonicalBaseline(snap);
    } else if (snap.public_preset) {
      const pub = String(snap.public_preset);
      fetchCanonicalPreset(pub).then((j) => {
        const base = snapshotFromCanonical((j.canonical || {}) as Record<string, any>);
        if (base) setCanonicalBaseline(base);
      }).catch(() => undefined);
    }
    const fields = uiFieldsFromSnapshot(snap);
    setSeed(fields.seed);
    setWidth(fields.width);
    setHeight(fields.height);
    setEcologyPreset(fields.ecologyPreset);
    setCognitionEnabled(fields.cognitionEnabled);
    setPeColdHistoryEviction(fields.peColdHistoryEviction);
    setTwoAgentExperimental(fields.twoAgentExperimental);
    setBodyMass(fields.bodyMass);
    setBodyVMax(fields.bodyVMax);
    setTargetTick(fields.targetTick);
    setUiHz(fields.uiHz);
    setBufferCapacity(fields.bufferCapacity);
    setTerrainSeedOverride(fields.terrainSeedOverride);
    setMechanismDraft({ ...snap.mechanisms });
    setVisionDraft(snap.vision);
    setPscMotorDraft(String(snap.psc_motor_resolution || 'LOCO_FACTORIZED'));
    setPscOffTicksDraft(snap.psc_off_ticks);
    setActiveExperiment(snap);
    setApplyExperimentFailed(false);
    const gen = Number(f?.header?.runtime_generation);
    if (Number.isFinite(gen)) appliedExperimentGenerationRef.current = gen;
    setAppliedConfig({
      seed: fields.seed,
      width: fields.width,
      height: fields.height,
      ecologyPreset: fields.ecologyPreset,
      cognitionEnabled: fields.cognitionEnabled,
      peColdHistoryEviction: fields.peColdHistoryEviction,
      twoAgentExperimental: fields.twoAgentExperimental,
      bodyMass: fields.bodyMass,
      bodyVMax: fields.bodyVMax,
      targetTick: fields.targetTick,
      uiHz: fields.uiHz,
      bufferCapacity: fields.bufferCapacity,
      terrainSeedOverride: fields.terrainSeedOverride,
    });
  }

  useEffect(() => {
    if (!mechanisms.length) return;
    setActiveExperiment((prev) => {
      if (!prev) return prev;
      if (Object.keys(prev.mechanisms || {}).length) return prev;
      return { ...prev, mechanisms: mechanismMapFromCatalog(mechanisms) };
    });
  }, [mechanisms]);

  useEffect(() => {
    getState().then(f => {
      const agent = requestedAgentId(f);
      desiredAgentIdRef.current = agent;
      setDesiredAgentId(agent);
      const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
      setLiveFrame(projected); setViewFrame(projected);
      adoptRuntimeExperiment(f);
    });
    refreshAux().catch(() => undefined);
    fetch('/api/health').then(r => r.ok ? r.json() : null).then(h => {
      if (h) {
        setAppIdentity(h);
        document.title = `Mechanistic Mind Observer — Acanthostega Beta 4.0${h.version ? ' · v' + h.version : ''}`;
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
        const incomingGen = Number(f?.header?.runtime_generation);
        const appliedGenGate = appliedExperimentGenerationRef.current;
        if (
          appliedGenGate != null
          && Number.isFinite(incomingGen)
          && incomingGen < appliedGenGate
        ) {
          return;
        }
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
        if (f?.mechanism_result?.mechanisms) {
          const gen = Number(f?.header?.runtime_generation);
          const appliedGen = appliedExperimentGenerationRef.current;
          if (appliedGen == null || !Number.isFinite(gen) || gen >= appliedGen) {
            setMechanisms(f.mechanism_result.mechanisms);
          }
        }
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
        tab, layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength, geoAgentFilter, preset,
        terrainMode, showClearanceStems, showEventMarkers, showElevationContours, verticalExaggeration,
        trailMode, trailLengthMode,
      }));
    } catch { /* display prefs only */ }
  }, [tab, layer, worldView, renderMode, opacity, showGrid, layers, trajectoryLength, geoAgentFilter, preset,
    terrainMode, showClearanceStems, showEventMarkers, showElevationContours, verticalExaggeration,
    trailMode, trailLengthMode]);

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
        <TabVisibilityDriver />
        <DerivedViewportSubscriptionDriver mode={volumeWorkspace} />
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
    const body = op === 'reset'
      ? { ...(payload || {}), public_preset: publicPresetFromUi(preset) }
      : payload;
    const f = await postControl(op, body);
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
  async function setSurfaceDiscrimination(disc: 'OFF' | 'LOW' | 'RICH') {
    const f = await fetch('/api/vision/surface-discrimination', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: disc }),
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
  async function setOpticalMapping(mapping: 'INDEPENDENT' | 'CORRELATED' | 'SHUFFLED' | 'UNIFORM') {
    const f = await fetch('/api/vision/optical-mapping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: mapping }),
    }).then((r) => r.json());
    setControlMessage(f.control_receipt);
    if (f.control_receipt?.accepted !== false) {
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(f, agent);
      setLiveFrame(projected);
      setViewFrame(mode === 'LIVE' ? projected : viewFrame);
    }
  }
  async function setSpatialVision(sv: 'LEGACY' | 'ANGULAR' | 'OCCLUSION' | 'TEMPORAL_SPATIAL') {
    const f = await fetch('/api/vision/spatial-vision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: sv }),
    }).then((r) => r.json());
    setControlMessage(f.control_receipt);
    if (f.control_receipt?.accepted !== false) {
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(f, agent);
      setLiveFrame(projected);
      setViewFrame(mode === 'LIVE' ? projected : viewFrame);
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
      ix: info.ix,
      iy: info.iy,
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
    <label className="subtle">
      <input type="checkbox" checked={showManipulatorReach} onChange={e => setShowManipulatorReach(e.target.checked)} />
      {' '}effector reach overlay (researcher-only)
    </label>
    {Array.isArray(frame?.world?.manipulators) && frame.world.manipulators.length > 0 ? (
      <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
        {frame.world.manipulators.some((m: any) => m?.manipulator_id === 'LEFT' || m?.manipulator_id === 'RIGHT') ? (
          <>
            <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_left: 'GRASP' }); }}>LEFT GRASP</button>
            <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_left: 'RELEASE' }); }}>LEFT RELEASE</button>
            <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_right: 'GRASP' }); }}>RIGHT GRASP</button>
            <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_right: 'RELEASE' }); }}>RIGHT RELEASE</button>
            {frame.world.manipulators.some((m: any) => m?.kind === 'pair_state') ? (
              <>
                <button type="button" title="Researcher probe — not mixing" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_pair: 'BRING_TOGETHER' }); }}>BRING TOGETHER</button>
                <button type="button" title="Researcher probe — not mixing" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_pair: 'SEPARATE' }); }}>SEPARATE</button>
                {mechanisms.some((m: any) => m?.id === 'material_composition_merge' && m?.enabled) ? <button type="button" title="Researcher probe — explicit conserved composition merge" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator_pair: 'COMBINE' }); }}>COMBINE</button> : null}
                {mechanisms.some((m: any) => m?.id === 'explicit_surface_deposition' && m?.enabled) ? <button type="button" title="Researcher probe — motor command only, no cell or object id" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', apply_to_surface: true }); }}>APPLY TO SURFACE</button> : null}
              </>
            ) : null}
          </>
        ) : (
          <>
            <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator: 'GRASP' }); }}>GRASP probe</button>
            <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'WAIT', manipulator: 'RELEASE' }); }}>RELEASE probe</button>
          </>
        )}
        <button type="button" title="Researcher probe — not an organism policy" onClick={() => { void researcherForcedMotor({ locomotion: 'MOVE:E', manipulator: 'NONE' }); }}>MOVE:E probe</button>
        <span className="subtle">researcher motor probe · not a policy</span>
      </div>
    ) : null}
    {Array.isArray(frame?.world?.manipulators) && frame.world.manipulators.some((m: any) => m?.kind === 'pair_state') ? (
      <div className="subtle" data-testid="pair-state-readout">
        {frame.world.manipulators.filter((m: any) => m?.kind === 'pair_state').map((p: any, i: number) => (
          <span key={i}>
            aperture {Number(p.aperture).toFixed(3)} (open {Number(p.open_aperture).toFixed(3)} / min {Number(p.min_aperture).toFixed(3)})
            · state {String(p.pair_state)} · contact {p.contact ? 'yes' : 'no'}
            {p.surface_distance != null ? ` · surface ${Number(p.surface_distance).toFixed(3)}` : ''}
            {p.last_pair_receipt?.outcome ? ` · last ${p.last_pair_receipt.outcome}` : ''}
          </span>
        ))}
      </div>
    ) : null}
    {frame?.world?.local_signal_overlay ? (() => {
      const ov = frame.world.local_signal_overlay;
      const num = (v: any, d = 3) => (v == null ? '—' : Number(v).toFixed(d));
      return <div data-testid="local-signal-overlay" className="subtle" style={{ border: '1px dashed #888', padding: 6, marginTop: 6 }}>
        <div className="section-label">Local physical signal transport (researcher-only)</div>
        <div data-testid="local-signal-overlay-labels">{((ov.labels && ov.labels.length) ? ov.labels : LOCAL_SIGNAL_OVERLAY_LABELS).join(' · ')}</div>
        <KV name="medium" value={`${ov.medium?.medium_version} · v=${ov.medium?.propagation_speed} · k=${ov.medium?.attenuation_coefficient} · R=${ov.medium?.maximum_range} · thr=${ov.medium?.reception_threshold}`}/>
        <KV name="active / expired" value={`${ov.active_count} / ${ov.expired_total}`}/>
        <KV name="emissions / accepted receptions" value={`${ov.emissions_total} / ${ov.accepted_receptions_total}`}/>
        {frame?.world?.contact_acoustic_summary ? (() => {
          const ca = frame.world.contact_acoustic_summary;
          const c = ca.counters || {};
          return <div data-testid="contact-acoustic-overlay" title="Researcher-only: emissions derived from measured body-body contact impulse (not a sound class, not agent-accessible)">
            contact-impulse emissions {c.emissions ?? 0} · impulses measured {c.impulses_measured ?? 0} · silent (below ε {c.silent_below_epsilon ?? 0} / resting {c.silent_resting_contact ?? 0}) · researcher-only
          </div>;
        })() : null}
        {(ov.active || []).slice(0, 8).map((e: any) => (
          <div key={e.emission_id} data-testid="local-signal-emission-row" title={(() => {
            const src = (frame?.world?.contact_acoustic_summary?.recent_emissions || []).find((r: any) => r.emission_id === e.emission_id);
            return src ? `researcher-only · cause: measured contact impulse |J|=${num(src.new_impulse_magnitude, 4)} · energy ${num(src.emitted_energy)} · position ${src.position_derivation}` : `researcher-only · ${e.selection_provenance || ''}`;
          })()}>
            origin ◎ ({num(e.origin?.[0], 2)}, {num(e.origin?.[1], 2)}) · wavefront r={num(e.front_radius, 2)} / range {num(e.maximum_range, 1)} · energy {num(e.total_emitted_energy)} · {e.status} · local receivers {(e.receivers || []).length} · k={num(e.attenuation_coefficient, 3)}
          </div>
        ))}
        <button type="button" title="Researcher calibration emission (INTERVENTION_SETUP) — not an agent control, not a message" onClick={() => { void researcherLocalSignalEmission({}); }}>CALIBRATION EMISSION (researcher)</button>
      </div>;
    })() : null}
    {frame?.world?.free_object_kinematics ? (() => {
      const fk = frame.world.free_object_kinematics;
      const c = fk.counters || {};
      const num = (v: any, d = 3) => (v == null ? '—' : Number(v).toFixed(d));
      return <div data-testid="free-object-kinematics-overlay" className="subtle" style={{ border: '1px dashed #888', padding: 6, marginTop: 6 }}>
        <div className="section-label">Free resource object kinematics (researcher-only)</div>
        <div data-testid="free-object-collision-label">collision physics: not implemented · no gravity · objects pass through bodies and each other · researcher-only</div>
        <label className="subtle">
          <input type="checkbox" data-testid="free-object-velocity-toggle" checked={showObjectVelocity} onChange={e => setShowObjectVelocity(e.target.checked)} />
          {' '}velocity vectors on map (researcher overlay · arrow = 3 ticks × v, display scale)
        </label>
        <div data-testid="free-object-profile" className="subtle" style={{ whiteSpace: 'normal' }}>profile: transfer {fk.profile?.release_transfer} · damping {fk.profile?.damping_rate}/tick (exp) · rest &lt; {fk.profile?.rest_threshold} · max {fk.profile?.max_free_object_speed} cells/tick · material input {fk.profile?.material_property_input}</div>
        <KV name="releases moving / at rest" value={`${c.releases_moving ?? 0} / ${c.releases_at_rest ?? 0}`}/>
        <KV name="motion steps · rest transitions · wraps · clamps" value={`${c.motion_steps ?? 0} · ${c.rest_transitions ?? 0} · ${c.wrap_events ?? 0} · ${c.speed_clamps ?? 0}`}/>
        {(fk.objects || []).map((o: any) => (
          <div key={o.object_id} data-testid="free-object-row">
            {o.object_id} · {o.motion_status} · ({num(o.x, 2)}, {num(o.y, 2)}) · speed {num(o.speed)}{showObjectVelocity ? ` · v=(${num(o.vx)}, ${num(o.vy)})` : ''}
          </div>
        ))}
      </div>;
    })() : null}
    {frame?.world?.body_object_contact ? (() => {
      const bc = frame.world.body_object_contact;
      const ov = frame.world.body_object_contact_overlay || {};
      const c = bc.counters || {};
      const num = (v: any, d = 3) => (v == null ? '—' : Number(v).toFixed(d));
      const active = bc.active_episodes || ov.active?.active || [];
      return <div data-testid="body-object-contact-overlay" className="subtle" style={{ border: '1px dashed #c45', padding: 6, marginTop: 6 }}>
        <div className="section-label">Body / ResourceObject contact FACT (researcher-only)</div>
        <div data-testid="body-object-contact-banner"><strong>CONTACT FACT ONLY</strong> · NO IMPULSE · NO RESPONSE · NO SOUND</div>
        <div className="subtle">body radius {num(bc.body_contact_radius ?? ov.body_contact_radius)} · object collision_radius (not optical/glyph) · swept={String(bc.swept_contact ?? 'IMPLEMENTED')} · held={String(bc.held_object_body_contact ?? 'NOT_IMPLEMENTED')}</div>
        <KV name="BEGIN / PERSIST / END" value={`${c.begin ?? 0} / ${c.persist ?? 0} / ${c.end ?? 0}`}/>
        <KV name="broad / narrow / endpoint / swept" value={`${c.broad_candidates ?? 0} / ${c.narrow_checks ?? 0} / ${c.endpoint ?? 0} / ${c.swept ?? 0}`}/>
        {(Array.isArray(active) ? active : []).slice(0, 12).map((e: any) => (
          <div key={e.episode_id || e.pair_key} data-testid="body-object-contact-row">
            {e.episode_id} · {e.body_id}↔{e.object_id} · {e.status || e.detection_mode || 'ACTIVE'} · sep {num(e.separation)} · pen {num(e.penetration)}
          </div>
        ))}
      </div>;
    })() : null}
    {frame?.world?.body_object_impulse ? (() => {
      const bi = frame.world.body_object_impulse;
      const ov = frame.world.body_object_impulse_overlay || {};
      const c = bi.counters || ov.summary?.counters || {};
      const num = (v: any, d = 3) => (v == null ? '—' : Number(v).toFixed(d));
      const last = bi.last_step || ov.summary?.last_step || {};
      const rows = last.responses || last.applied || bi.recent_responses || [];
      return <div data-testid="body-object-impulse-overlay" className="subtle" style={{ border: '1px dashed #0ea5e9', padding: 6, marginTop: 6 }}>
        <div className="section-label">Body / ResourceObject contact RESPONSE (researcher-only)</div>
        <div data-testid="body-object-impulse-banner"><strong>MASS + COMPLIANCE NORMAL RESPONSE</strong> · NO FRICTION · NO SOUND</div>
        <KV name="applied / no-response" value={`${c.applied ?? c.impulses_applied ?? 0} / ${c.no_response ?? c.skipped ?? 0}`}/>
        <KV name="momentum residual max" value={num(c.momentum_residual_max ?? last.momentum_residual_max)}/>
        <KV name="energy creation violations" value={String(c.energy_creation_violations ?? 0)}/>
        {(Array.isArray(rows) ? rows : []).slice(0, 8).map((r: any, i: number) => (
          <div key={r.response_id || i} data-testid="body-object-impulse-row">
            {r.response_id || r.reason} · {r.body_id}↔{r.object_id} · {r.reason || r.response_reason} · j={num(r.clamped_impulse ?? r.impulse)} · e={num(r.effective_restitution ?? r.restitution)} · m={num(r.m_body)}/{num(r.m_object)}
          </div>
        ))}
      </div>;
    })() : null}
    {frame?.world?.body_object_impact_acoustics ? (() => {
      const ia = frame.world.body_object_impact_acoustics;
      const ov = frame.world.body_object_impact_acoustics_overlay || {};
      const c = ia.counters || ov.summary?.counters || {};
      const recent = ia.recent_emissions || ov.emissions || [];
      return <div data-testid="body-object-impact-acoustics-overlay" className="subtle" style={{ border: '1px dashed #a855f7', padding: 6, marginTop: 6 }}>
        <div className="section-label">Body / ResourceObject impact acoustics (researcher-only)</div>
        <div data-testid="body-object-impact-acoustics-banner"><strong>BODY/OBJECT IMPACT</strong><br/>PHYSICAL IMPULSE → DISSIPATED ENERGY → LOCAL SIGNAL<br/>NEUTRAL BROADBAND · NO MATERIAL TIMBRE</div>
        <KV name="emissions / silent-no-dissipation" value={`${c.emissions ?? 0} / ${c.silent_no_dissipation ?? 0}`}/>
        <KV name="eligible / below-epsilon" value={`${c.impulses_eligible ?? 0} / ${c.silent_below_epsilon ?? 0}`}/>
        {(Array.isArray(recent) ? recent : []).slice(0, 8).map((e: any, i: number) => (
          <div key={e.emission_id || i} data-testid="body-object-impact-acoustics-row">
            {e.emission_id} · {e.body_id}↔{e.object_id} · E={e.emitted_energy} · j={e.impulse_scalar_j}
          </div>
        ))}
      </div>;
    })() : null}

    {frame?.world?.resource_object_pair_contact_impulse ? (() => {
      const bi = frame.world.resource_object_pair_contact_impulse;
      const ov = frame.world.resource_object_pair_contact_impulse_overlay || {};
      const c = bi.counters || ov.summary?.counters || {};
      const num = (v: any, d = 3) => (v == null ? '—' : Number(v).toFixed(d));
      const last = bi.last_step || ov.summary?.last_step || {};
      const rows = last.responses || bi.recent_responses || ov.responses || [];
      return <div data-testid="resource-object-pair-contact-impulse-overlay" className="subtle" style={{ border: '1px dashed #14b8a6', padding: 6, marginTop: 6 }}>
        <div className="section-label">ResourceObject / ResourceObject contact RESPONSE (researcher-only)</div>
        <div data-testid="resource-object-pair-contact-impulse-banner"><strong>OBJECT/OBJECT MASS + COMPLIANCE NORMAL RESPONSE</strong> · NO FRICTION · NO SOUND · MULTI-CONTACT: ISOLATED PAIRS ONLY</div>
        <KV name="applied / multi-unresolved" value={`${c.impulses_applied ?? 0} / ${c.multi_contact_unresolved ?? 0}`}/>
        <KV name="isolated pairs / corrections" value={`${c.isolated_pairs_resolved ?? last.isolated_pairs_resolved ?? 0} / ${c.position_corrections ?? 0}`}/>
        {(Array.isArray(rows) ? rows : []).slice(0, 8).map((r: any, i: number) => (
          <div key={r.response_key || i} data-testid="resource-object-pair-contact-impulse-row">
            {r.response_key || r.reason} · {r.object_id_a}↔{r.object_id_b} · {r.reason} · j={num(r.impulse_scalar_j)} · e={num(r.restitution_e)} · c_eff={num(r.compliance_eff)}
          </div>
        ))}
      </div>;
    })() : null}
    {frame?.world?.resource_object_pair_contact ? (() => {
      const pc = frame.world.resource_object_pair_contact;
      const ov = frame.world.resource_object_pair_contact_overlay || {};
      const c = pc.counters || {};
      const active = pc.active_episodes || ov.active?.active_episodes || [];
      return <div data-testid="resource-object-pair-contact-overlay" className="subtle" style={{ border: '1px dashed #f59e0b', padding: 6, marginTop: 6 }}>
        <div className="section-label">ResourceObject / ResourceObject contact FACT (researcher-only)</div>
        <div data-testid="resource-object-pair-contact-banner"><strong>OBJECT/OBJECT CONTACT FACT ONLY</strong> · NO IMPULSE · NO RESPONSE · NO SOUND</div>
        <div className="subtle">broad={String(pc.broad_phase_strategy ?? 'BROAD_PHASE_ALL_PAIRS_V1')} · swept={String(pc.swept_contact ?? 'IMPLEMENTED')} · held+free={String(pc.held_free_object_pair_contact ?? 'NOT_IMPLEMENTED')}</div>
        <KV name="BEGIN / PERSIST / END" value={`${c.begin ?? 0} / ${c.persist ?? 0} / ${c.end ?? 0}`}/>
        <KV name="candidates / unique / endpoint / swept" value={`${c.broad_candidates ?? 0} / ${c.unique_pairs_checked ?? 0} / ${c.endpoint ?? 0} / ${c.swept ?? 0}`}/>
        <KV name="response flags" value="all false"/>
        {(Array.isArray(active) ? active : []).slice(0, 12).map((e: any) => (
          <div key={e.episode_id || e.pair_key} data-testid="resource-object-pair-contact-row">
            {e.episode_id} · {e.object_id_a}↔{e.object_id_b} · {e.status || e.detection_mode || 'ACTIVE'}
          </div>
        ))}
      </div>;
    })() : null}

    {frame?.world?.held_foreign_body_contact ? (() => {
      const hc = frame.world.held_foreign_body_contact;
      const ls = hc?.last_step || {};
      return (
        <div className="panel" data-testid="held-foreign-body-contact-panel" style={{marginTop:8}}>
        <div data-testid="held-foreign-body-contact-banner"><strong>HELD OBJECT ↔ FOREIGN BODY CONTACT FACT</strong> · NO IMPULSE · NO DAMAGE · NO RELEASE · NO SOUND</div>
        <div className="subtle">active={hc?.active_episodes?.length ?? 0} · begin={ls.begin_count ?? 0} · persist={ls.persist_count ?? 0} · end={ls.end_count ?? 0}</div>
        </div>
      );
    })() : null}

    {frame?.world?.held_resource_object_terrain_contact ? (() => {
      const ht = frame.world.held_resource_object_terrain_contact;
      const ls = ht?.last_step || {};
      const latest = ht?.latest_receipt || {};
      const banner = frame.world.held_resource_object_terrain_contact_banner
        || 'HELD OBJECT ↔ TERRAIN CONTACT GEOMETRY · RESEARCHER-ONLY · GEOMETRY FACT ONLY · NO WORK TRANSMISSION · NO TERRAIN FAILURE · NO IMPULSE · NO SOUND';
      return (
        <div className="panel" data-testid="held-resource-object-terrain-contact-panel" style={{marginTop:8}}>
        <div data-testid="held-resource-object-terrain-contact-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">active={ht?.active_episodes?.length ?? 0} · begin={ls.begin_count ?? 0} · persist={ls.persist_count ?? 0} · end={ls.end_count ?? 0} · mode={latest.detection_mode ?? '—'} · toi={latest.toi ?? '—'} · obj={latest.object_id ?? '—'} · hand={latest.manipulator_id ?? '—'} · penetration_unresolved={String(ht?.penetration_unresolved ?? true)}</div>
        </div>
      );
    })() : null}

    {frame?.world?.held_resource_object_terrain_mechanical_transmission ? (() => {
      const tx = frame.world.held_resource_object_terrain_mechanical_transmission;
      const ls = tx?.last_step || {};
      const banner = frame.world.held_resource_object_terrain_mechanical_transmission_banner
        || 'BETA4 · HELD OBJECT ↔ TERRAIN MECHANICAL TRANSMISSION · BOUNDED ACTUATOR WORK · NO TOOL CLASS · TRANSMISSION ONLY · TERRAIN FAILURE COUPLING NOT ACTIVE';
      return (
        <div className="panel" data-testid="held-resource-object-terrain-mechanical-transmission-panel" style={{marginTop:8}}>
        <div data-testid="held-resource-object-terrain-mechanical-transmission-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">blocks={tx?.counters?.held_blocks ?? 0} · transmissions={tx?.counters?.transmissions ?? 0} · work_used={ls.work_used ?? '—'} · transmitted={ls.work_transmitted_to_terrain ?? '—'} · residual={ls.work_partition_residual ?? '—'} · obj={ls.object_id ?? '—'} · setmr_routed={String(ls.setmr_routed ?? false)} · terrain_failure={String(ls.terrain_failure_coupling ?? false)}</div>
        </div>
      );
    })() : null}

    {frame?.world?.held_mediated_surface_exertion_integration ? (() => {
      const mi = frame.world.held_mediated_surface_exertion_integration;
      const ls = mi?.last_step || {};
      const banner = frame.world.held_mediated_surface_exertion_integration_banner
        || 'BETA4 · HELD-MEDIATED SURFACE EXERTION INTEGRATION · SAME SETMR ACCUMULATOR · SAME SEPARATION WMT · NO NEW RESISTANCE LAW · NO TOOL CLASS';
      return (
        <div className="panel" data-testid="held-mediated-surface-exertion-integration-panel" style={{marginTop:8}}>
        <div data-testid="held-mediated-surface-exertion-integration-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">held_routes={mi?.counters?.held_routes ?? 0} · setmr_invoked={mi?.counters?.setmr_invoked ?? 0} · transmitted={ls.work_transmitted_to_terrain ?? '—'} · setmr_routed={String(ls.setmr_routed ?? false)} · mat={ls.material_loading_status ?? '—'} · failure={String(ls.material_failure ?? false)} · wmt={String(ls.wmt_invoked ?? false)}</div>
        </div>
      );
    })() : null}

    {frame?.world?.detached_terrain_material_initial_placement ? (() => {
      const mi = frame.world.detached_terrain_material_initial_placement;
      const ls = mi?.last_step || {};
      const banner = frame.world.detached_terrain_material_initial_placement_banner
        || 'DETACHED TERRAIN MATERIAL INITIAL PLACEMENT · POST-MUTATION SUPPORT · BOUNDED DETERMINISTIC CANDIDATES · ZERO INITIAL VELOCITY · DYNAMICS BEGIN T+1';
      return (
        <div className="panel" data-testid="detached-terrain-material-initial-placement-panel" style={{marginTop:8}}>
        <div data-testid="detached-terrain-material-initial-placement-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">placed={mi?.counters?.placed ?? 0} · rejected={mi?.counters?.rejected_no_candidate ?? 0} · status={ls.status ?? '—'} · cand={ls.candidate_index ?? '—'} · cell={Array.isArray(ls.source_cell) ? ls.source_cell.join(',') : '—'} · support_z={ls.support_z ?? '—'} · z={ls.z ?? '—'} · dyn_tick={ls.dynamics_eligible_tick ?? '—'} · create_tick={ls.creation_tick ?? '—'}</div>
        </div>
      );
    })() : null}

    {frame?.world?.bnlt_move_breakaway_locomotion_repair ? (() => {
      const mi = frame.world.bnlt_move_breakaway_locomotion_repair;
      const ls = mi?.last_step || {};
      const banner = frame.world.bnlt_move_breakaway_locomotion_repair_banner
        || 'BETA4 · BNLT MOVE BREAKAWAY LOCOMOTION REPAIR · ACTIVE-DRIVE drive_accel FROM CAPACITY-LIMITED MOVE IMPULSE';
      return (
        <div className="panel" data-testid="bnlt-move-breakaway-locomotion-repair-panel" style={{marginTop:8}}>
        <div data-testid="bnlt-move-breakaway-locomotion-repair-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="bnlt-move-breakaway-locomotion-repair-budget">
          class={ls.classification ?? '—'} · drive_a={ls.repair_drive_accel ?? ls.drive_accel ?? '—'} · kinetic_a={ls.kinetic_a ?? '—'} · disp={ls.displacement_mag ?? '—'} · rest={String(ls.rest_transition ?? false)} · work_diss={ls.kinetic_dissipated ?? '—'} · translate={mi?.counters?.translation_ticks ?? 0} · blocked={mi?.counters?.blocked_insufficient_ticks ?? 0}
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.repeated_conservative_surface_column_separation ? (() => {
      const mi = frame.world.repeated_conservative_surface_column_separation;
      const ls = mi?.last_step || {};
      const banner = frame.world.repeated_conservative_surface_column_separation_banner
        || 'REPEATED CONSERVATIVE SURFACE-COLUMN SEPARATION · ONE SUCCESS PER CELL PER TICK';
      return (
        <div className="panel" data-testid="repeated-conservative-surface-column-separation-panel" style={{marginTop:8}}>
        <div data-testid="repeated-conservative-surface-column-separation-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="repeated-conservative-surface-column-separation-budget">
          class={ls.classification ?? '—'} · cell={ls.cell_x != null ? `${ls.cell_x},${ls.cell_y}` : '—'} · commits={mi?.counters?.commits ?? 0} · caps={mi?.counters?.cell_tick_caps ?? 0} · clears={mi?.counters?.accumulator_clears ?? 0} · surplus={ls.surplus_discarded ?? mi?.counters?.surplus_discards ?? '—'} · obj={ls.detached_object_id ?? '—'} · txn={ls.transaction_id ?? '—'} · deposit={mi?.deposit_coupling ?? 'NOT_ESTABLISHED'}
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.event_driven_crowded_placement_retry_contract ? (() => {
      const mi = frame.world.event_driven_crowded_placement_retry_contract;
      const ls = mi?.last_step || {};
      const cs = ls.candidate_summary || {};
      const banner = frame.world.event_driven_crowded_placement_retry_contract_banner
        || 'EVENT-DRIVEN CROWDED PLACEMENT RETRY CONTRACT V1\nNEW PHYSICAL EXERTION REQUIRED\nONE RETRY PER EVENT\nNO BACKGROUND RETRY\nK=16 UNCHANGED\nNO PENDING MATERIAL';
      const moved = mi?.blockers_moved_since_last_attempt_derived || {};
      return (
        <div className="panel" data-testid="event-driven-crowded-placement-retry-contract-panel" style={{marginTop:8}}>
        <div data-testid="event-driven-crowded-placement-retry-contract-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="event-driven-crowded-placement-retry-contract-budget">
          cell={ls.cell_x != null ? `${ls.cell_x},${ls.cell_y}` : '—'} · retained={ls.retained_work_before ?? '—'}→{ls.accumulated_work_after ?? '—'} · thr={ls.threshold ?? '—'} · exertion={ls.exertion_event_id ?? '—'} · retry={ls.retry_event_id ?? '—'} · trigger={mi?.retry_trigger ?? 'NEW_EXERTION'} · dedup={ls.result === 'DEDUPLICATED_SAME_EVENT' ? 'HIT' : (ls.dedup_key ? 'ok' : '—')} · K={mi?.placement_candidate_count ?? cs.candidate_count ?? 16} · reasons={JSON.stringify(cs.reason_counts || {})} · blockers={(cs.blocker_ids || []).join(',') || '—'} · blockers_moved_derived={String(moved.any_moved ?? '—')} · result={ls.result ?? '—'} · obj={ls.object_id ?? '—'} · accum={ls.accumulator_disposition ?? '—'} · placed={mi?.counters?.placed ?? 0} · crowded={mi?.counters?.rejected_crowded ?? 0} · deduped={mi?.counters?.deduplicated ?? 0}
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.detached_material_amount_scaled_collision_radius ? (() => {
      const mi = frame.world.detached_material_amount_scaled_collision_radius;
      const ls = mi?.last_step || {};
      const banner = frame.world.detached_material_amount_scaled_collision_radius_banner
        || 'DETACHED MATERIAL AMOUNT-SCALED COLLISION RADIUS V1\nCREATION-TIME ONLY\nr = clamp(0.25 × quantity^(1/3), 0.08, 0.25)\nSERIALIZED RADIUS\nNO POST-CREATION RESIZE\nOPTICAL / GRASP GEOMETRY UNCHANGED';
      return (
        <div className="panel" data-testid="detached-material-amount-scaled-collision-radius-panel" style={{marginTop:8}}>
        <div data-testid="detached-material-amount-scaled-collision-radius-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="detached-material-amount-scaled-collision-radius-budget">
          qty={ls.quantity ?? '—'} · r_raw={ls.raw_radius != null ? Number(ls.raw_radius).toFixed(4) : '—'} · r={ls.final_radius != null ? Number(ls.final_radius).toFixed(4) : '—'} · clamp={ls.clamp_status ?? '—'} · scope={ls.scope_classification ?? '—'} · vhe={ls.vertical_half_extent ?? '—'} · optical={ls.optical_radius ?? '—'} · obj={ls.object_id ?? '—'} · txn={ls.transaction_id ?? '—'} · profile={mi?.profile_version ?? ls.profile_version ?? '—'} · created={mi?.counters?.objects_created ?? 0} · scaled={mi?.counters?.scaled ?? 0} · clamp_min={mi?.counters?.clamped_min ?? 0} · resize=NO
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.held_combine_radius_resize_transaction ? (() => {
      const mi = frame.world.held_combine_radius_resize_transaction;
      const ls = mi?.last_step || {};
      const banner = frame.world.held_combine_radius_resize_transaction_banner
        || 'HELD COMBINE RADIUS RESIZE TRANSACTION V1\nEXPLICIT COMBINE ONLY\nPROFILE-STAMPED SURVIVOR ONLY\nHELD BASE ANCHOR\nm·g·Δr WORK DEBIT\nATOMIC GEOMETRY CONFLICT REJECT\nNO IMPACT SOUND\nNO DEPOSITION RESIZE';
      return (
        <div className="panel" data-testid="held-combine-radius-resize-transaction-panel" style={{marginTop:8}}>
        <div data-testid="held-combine-radius-resize-transaction-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="held-combine-radius-resize-transaction-budget">
          r_before={ls.radius_before != null ? Number(ls.radius_before).toFixed(4) : '—'} · r_after={ls.radius_after != null ? Number(ls.radius_after).toFixed(4) : '—'} · Δr={ls.delta_r != null ? Number(ls.delta_r).toFixed(4) : '—'} · work={ls.work_debited ?? '—'} · cls={ls.resize_classification ?? ls.result ?? '—'} · obj={ls.object_id ?? ls.survivor_id ?? '—'} · txn={ls.transaction_id ?? '—'} · profile={mi?.profile_version ?? ls.profile_version ?? '—'} · committed={mi?.counters?.committed ?? 0} · deposition=NO
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.held_deposition_radius_shrink_transaction ? (() => {
      const mi = frame.world.held_deposition_radius_shrink_transaction;
      const ls = mi?.last_step || {};
      const banner = frame.world.held_deposition_radius_shrink_transaction_banner
        || 'HELD DEPOSITION RADIUS SHRINK TRANSACTION V1\nEXPLICIT APPLY_TO_SURFACE ONLY\nPROFILE-STAMPED SOURCE ONLY\nHELD BASE ANCHOR\nPARTIAL SHRINK · FULL EXHAUSTION REMOVES\nPE DISSIPATED · NO AGENT CREDIT\nNO IMPULSE · NO IMPACT SOUND\nNO DEPOSIT COLLISION BODY';
      return (
        <div className="panel" data-testid="held-deposition-radius-shrink-transaction-panel" style={{marginTop:8}}>
        <div data-testid="held-deposition-radius-shrink-transaction-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="held-deposition-radius-shrink-transaction-budget">
          r_before={ls.radius_before != null ? Number(ls.radius_before).toFixed(4) : '—'} · r_after={ls.radius_after != null ? Number(ls.radius_after).toFixed(4) : '—'} · Δr={ls.delta_r != null ? Number(ls.delta_r).toFixed(4) : '—'} · released_pe={ls.released_pe_magnitude ?? '—'} · cls={ls.resize_classification ?? ls.result ?? '—'} · obj={ls.object_id ?? ls.source_id ?? '—'} · txn={ls.transaction_id ?? '—'} · profile={mi?.profile_version ?? ls.profile_version ?? '—'} · committed={mi?.counters?.committed ?? 0} · combine=NO
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.free_space_state_and_pe_authority_contract ? (() => {
      const mi = frame.world.free_space_state_and_pe_authority_contract;
      const ls = mi?.last_receipt || mi?.last_step || frame.world.last_free_space_support_state || {};
      const banner = frame.world.free_space_state_and_pe_authority_contract_banner
        || 'FREE-SPACE V1A · SUPPORT/PE AUTHORITY CONTRACT · EXISTING FGG FALLING · SUPPORTED REST GRAVITY GATED · NO LANDING IMPULSE · NO IMPACT SOUND';
      return (
        <div className="panel" data-testid="free-space-state-pe-authority-contract-panel" style={{marginTop:8}}>
        <div data-testid="free-space-state-pe-authority-contract-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="free-space-state-pe-authority-contract-inspector">
          id={ls.entity_id ?? '—'} · kind={ls.entity_kind ?? '—'} · state={ls.support_state ?? '—'} · prev={ls.previous_support_state ?? '—'} · reason={ls.transition_reason ?? '—'} · z={ls.base_z != null ? Number(ls.base_z).toFixed(4) : '—'} · centre_z={ls.centre_z != null ? Number(ls.centre_z).toFixed(4) : '—'} · vz={ls.vz_after != null ? Number(ls.vz_after).toFixed(4) : '—'} · support_h={ls.support_height != null ? Number(ls.support_height).toFixed(4) : '—'} · integ={String(ls.vertical_integration_eligible ?? '—')} · ground_force={String(ls.ground_force_eligibility ?? '—')} · pe={ls.active_pe_authority ?? '—'} · g={ls.gravity_applied === true ? 'applied' : (ls.gravity_skipped === true ? `skipped:${ls.gravity_skip_reason ?? ''}` : '—')} · double_pe={String(ls.double_pe_authority ?? false)} · clamp={String(ls.current_inelastic_clamp ?? false)} · landing=NO · impulse=NO · sound=NO · receipts={mi?.counters?.receipts ?? 0}
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.vertical_terrain_landing_contact_response ? (() => {
      const mi = frame.world.vertical_terrain_landing_contact_response;
      const ls = mi?.last_receipt || mi?.last_step || frame.world.last_vertical_terrain_landing || {};
      const banner = frame.world.vertical_terrain_landing_contact_response_banner
        || 'FREE-SPACE LANDING V1 · TERRAIN CONTACT + INELASTIC RESPONSE · e=0 · NO REBOUND · NO IMPACT SOUND · 2D BROAD PHASE';
      return (
        <div className="panel" data-testid="vertical-terrain-landing-contact-response-panel" style={{marginTop:8}}>
        <div data-testid="vertical-terrain-landing-contact-response-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="vertical-terrain-landing-contact-response-inspector">
          id={ls.entity_id ?? '—'} · kind={ls.entity_kind ?? '—'} · phase={ls.episode_phase ?? '—'} · episode={ls.episode_id ?? '—'} · cls={ls.intersection_class ?? ls.response_classification ?? '—'} · support={String(ls.support_acquired ?? false)} · pen={ls.penetration != null ? Number(ls.penetration).toFixed(6) : '—'} · toi={ls.toi != null ? Number(ls.toi).toFixed(6) : '—'} · impulse={ls.impulse_magnitude != null ? Number(ls.impulse_magnitude).toFixed(4) : '—'} · dissipated={ls.dissipated_energy != null ? Number(ls.dissipated_energy).toFixed(4) : '—'} · vz={ls.vz_post_response != null ? Number(ls.vz_post_response).toFixed(4) : '—'} · grounded={String(ls.grounded_after ?? '—')} · pe={ls.pe_authority_after ?? '—'} · rebound=NO · sound=NO · receipts={mi?.counters?.receipts ?? 0}
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.vertical_impact_acoustic_emission ? (() => {
      const mi = frame.world.vertical_impact_acoustic_emission;
      const ls = mi?.last_receipt || mi?.last_step || {};
      const banner = frame.world.vertical_impact_acoustic_emission_banner
        || 'VERTICAL IMPACT ACOUSTICS · LANDING RESPONSE ENERGY → LPS · NEUTRAL BANDS · PERSISTENT SUPPORT SILENT · NO HUMAN PLAYBACK YET';
      const cp = ls.contact_point;
      const cpStr = Array.isArray(cp) && cp.length >= 3
        ? `(${Number(cp[0]).toFixed(3)},${Number(cp[1]).toFixed(3)},${Number(cp[2]).toFixed(3)})`
        : '—';
      return (
        <div className="panel" data-testid="vertical-impact-acoustic-emission-panel" style={{marginTop:8}}>
        <div data-testid="vertical-impact-acoustic-emission-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="vertical-impact-acoustic-emission-inspector">
          id={ls.entity_id ?? '—'} · kind={ls.entity_kind ?? '—'} · episode={ls.episode_id ?? '—'} · response={ls.response_key ?? '—'} · tick={ls.emission_tick ?? '—'} · contact={cpStr} · impulse={ls.impulse_magnitude != null ? Number(ls.impulse_magnitude).toFixed(4) : '—'} · ke={ls.ke_before != null ? Number(ls.ke_before).toFixed(4) : '—'}→{ls.ke_after != null ? Number(ls.ke_after).toFixed(4) : '—'} · E_diss={ls.dissipated_energy != null ? Number(ls.dissipated_energy).toFixed(4) : '—'} · E_emit={ls.emitted_energy != null ? Number(ls.emitted_energy).toFixed(4) : (ls.selected_acoustic_energy != null ? Number(ls.selected_acoustic_energy).toFixed(4) : '—')} · source={ls.source_id ?? '—'} · emitted={String(ls.emitted ?? (ls.receipt_kind === 'VERTICAL_IMPACT_ACOUSTIC_EMISSION'))} · silent={ls.silence_reason ?? '—'} · lps={ls.lps_enqueue_status ?? '—'} · playback=NO · emissions={mi?.counters?.emissions ?? 0}
        </div>
        </div>
      );
    })() : null}

    {frame?.world?.authoritative_physical_acoustic_stream ? (() => {
      const s = frame.world.authoritative_physical_acoustic_stream;
      const banner = frame.world.authoritative_physical_acoustic_stream_banner
        || 'PHYSICAL ACOUSTIC EVENTS · RESEARCHER-ONLY · NO AUDIO PLAYBACK · NO HZ CALIBRATION';
      const recent = Array.isArray(s.recent_records) ? s.recent_records.slice(-8).reverse() : [];
      return (
        <div className="panel" data-testid="authoritative-physical-acoustic-stream-panel" style={{marginTop:8}}>
          <div data-testid="authoritative-physical-acoustic-stream-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
          <div className="subtle" data-testid="authoritative-physical-acoustic-stream-meta">
            schema={s.schema ?? '—'} · contract={s.contract ?? '—'} · capacity={s.history_capacity ?? '—'} · retained={s.retained_count ?? '—'} · evicted={s.evicted_count ?? '—'} · sync_tick={s.last_sync_tick ?? '—'} · playback=NO · hz=NOT_ESTABLISHED
          </div>
          {(() => {
            const cal = s.acoustic_calibration_status || frame?.world?.acoustic_calibration_status || s.acoustic_calibration || frame?.world?.acoustic_calibration;
            if (!cal) return null;
            const lines = Array.isArray(cal.status_lines) ? cal.status_lines : [
              `Calibration: ${cal.profile ?? 'ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1'}`,
              `Bands: ${cal.band_count ?? 6} anonymous`,
              'Time: scientific ticks',
              'Distance: XY cells',
              'Amplitude: anonymous band energy',
              'Hz: NOT ESTABLISHED',
              'SPL/dB: NOT ESTABLISHED',
              'Playback: NOT IMPLEMENTED',
              'Original / Human-Audible: NOT AVAILABLE',
              `Next honest listening mode: ${cal.next_honest_listening_mode ?? 'CANONICAL PHYSICAL-FIELD SONIFICATION'}`,
            ];
            return (
              <div className="subtle" data-testid="acoustic-calibration-status" style={{marginTop:4, borderTop:'1px dashed #666', paddingTop:4}}>
                {lines.map((ln: string) => <div key={ln}>{ln}</div>)}
              </div>
            );
          })()}
          <div className="subtle" data-testid="authoritative-physical-acoustic-stream-records" style={{maxHeight:160, overflow:'auto'}}>
            {recent.length === 0 ? <div>no retained physical acoustic records</div> : recent.map((r: any) => {
              const pos = r.position || {};
              const bands = Array.isArray(r.anonymous_band_energies)
                ? r.anonymous_band_energies.map((b: number) => Number(b).toFixed(3)).join(',')
                : String(r.anonymous_band_energies ?? '—');
              return (
                <div key={String(r.stream_record_id || r.stream_sequence)} style={{marginTop:2}}>
                  seq={r.stream_sequence ?? '—'} · tick={r.scientific_tick ?? '—'} · mech={r.source_mechanism_id ?? '—'} · id={r.stream_record_id ?? '—'} · E={r.emitted_energy != null && r.emitted_energy !== 'NOT_AVAILABLE_IN_LEGACY_RECORD' ? Number(r.emitted_energy).toFixed(4) : '—'} · xy=({pos.x != null && pos.x !== 'NOT_AVAILABLE_IN_LEGACY_RECORD' ? Number(pos.x).toFixed(2) : '—'},{pos.y != null && pos.y !== 'NOT_AVAILABLE_IN_LEGACY_RECORD' ? Number(pos.y).toFixed(2) : '—'}) · bands=[{bands}] · lps={r.lps_emission_id ?? '—'} · admitted={String(r.lps_admitted ?? '—')}
                </div>
              );
            })}
          </div>
        </div>
      );
    })() : null}

    {(frame?.world?.observer_acoustic_probe || frame?.world?.local_signal_summary || frame?.world?.canonical_physical_field_sonification || frame?.world?.selected_organism_auditory_view) ? (
      <div className="panel" data-testid="hearing-moved-notice" style={{ marginTop: 8 }}>
        <div className="observer-banner researcher-only">Audio controls moved to left HEARING workspace</div>
        <div className="subtle" style={{ marginTop: 4 }}>
          Configure C1 / SAV2 / passive probe in the left sensory dock. This World-layers location no longer mounts playback engines.
        </div>
        <button
          type="button"
          data-testid="open-left-hearing-workspace"
          style={{ marginTop: 6 }}
          onClick={() => openLeftHearingWorkspace()}
        >
          Open HEARING
        </button>
      </div>
    ) : null}

    {(frame?.world?.acanthostega_beta4_capability || frame?.world?.volumetric_world_vw7_cumulative) ? (() => {
      const vw = frame.world.acanthostega_beta4_capability || frame.world.volumetric_world_vw7_cumulative;
      const st = vw.stages || {};
      const banner = vw.banner || 'Acanthostega Beta 4.0';
      return (
        <div className="panel" data-testid="acanthostega-beta4-capability-panel" style={{marginTop:8}}>
          <div data-testid="acanthostega-beta4-capability-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
          <div className="subtle" data-testid="acanthostega-beta4-capability-status">
            preset={vw.public_preset || '—'} · model_line={vw.model_line || '—'} · occupancy={String(st.VW1_occupancy ?? st.volumetric_occupancy)} · free-space={String(st.free_space_v1d ?? st.V1D_release_excavation)} · support={String(st.VW2_support_contact)} · material_tx={String(st.VW3_separation)} · organism_vol={String(st.VW5_effector_bridge)} · xyz_vision={String(st.VW6_minimal_vision_3d)} · volume_view={String(st.VW7_observer_consumer)} · held→world={vw.held_to_world_physical_trigger || 'BLOCKED'}
          </div>
        </div>
      );
    })() : null}

    {frame?.world?.exposed_surface_optical_interaction_authority ? (() => {
      const o2 = frame.world.exposed_surface_optical_interaction_authority;
      const counts = o2.counts_by_face || {};
      return (
        <div className="panel" data-testid="o2-exposed-surface-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="o2-exposed-surface-banner">
            {o2.label || 'EXPOSED PHYSICAL BOUNDARIES · MATERIAL PROFILE ONLY · NO LIGHT/BRIGHTNESS'}
          </div>
          <div className="subtle" data-testid="o2-exposed-surface-status">
            facets={o2.facet_count ?? 0}
            {' '}· TOP={counts.TOP ?? 0} BOTTOM={counts.BOTTOM ?? 0}
            {' '}· N/S/E/W={(counts.NORTH ?? 0)}/{(counts.SOUTH ?? 0)}/{(counts.EAST ?? 0)}/{(counts.WEST ?? 0)}
            {' '}· checksum={o2.facet_checksum || '—'}
            {' '}· cache={o2.cache_key_digest || '—'}
            {' '}· hits={o2.cache_hits ?? 0}/miss={o2.cache_misses ?? 0}
            {' '}· O1 known={(o2.o1_status_counts && o2.o1_status_counts.PROFILE_RESOLVED) ?? 0}
            {' '}· unknown={(o2.o1_status_counts && o2.o1_status_counts.UNKNOWN_PROFILE) ?? 0}
          </div>
          <div className="subtle">researcher-only · no light/brightness · not agent vision · not VW7 authority</div>
        </div>
      );
    })() : null}

    {frame?.world?.abstract_spectral_light_source_and_direct_transport ? (() => {
      const o3 = frame.world.abstract_spectral_light_source_and_direct_transport;
      const src = o3.source || {};
      const counts = o3.state_counts || {};
      const bands = Array.isArray(src.source_spectrum) ? src.source_spectrum : [];
      const dir = Array.isArray(src.direction_toward_source) ? src.direction_toward_source : [];
      return (
        <div className="panel" data-testid="o3-abstract-spectral-light-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="o3-abstract-spectral-light-banner">
            {o3.label || 'ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB'}
          </div>
          <div className="subtle" data-testid="o3-abstract-spectral-light-status">
            source={src.source_id || '—'}
            {' '}· enabled={String(src.enabled ?? o3.capability_enabled ?? false)}
            {' '}· dir=({dir.map((v: number) => Number(v).toFixed(3)).join(',') || '—'})
            {' '}· bands=[{bands.map((v: number) => Number(v).toFixed(3)).join(', ') || '—'}]
            {' '}· evaluated={o3.evaluated_facet_count ?? 0}
            {' '}· lit={counts.DIRECT_ILLUMINATED ?? 0}
            {' '}· back={counts.BACK_FACING_ZERO ?? 0}
            {' '}· occluded={counts.OCCLUDED_ZERO ?? 0}
            {' '}· unknown={counts.UNKNOWN_MATERIAL_RESPONSE ?? 0}
            {' '}· checksum={o3.result_checksum || '—'}
            {' '}· cache={o3.cache_key_digest || '—'}
            {' '}· hits={o3.cache_hits ?? 0}/miss={o3.cache_misses ?? 0}/builds={o3.cache_builds ?? 0}
            {' '}· occ_q={o3.occlusion_queries ?? 0}
          </div>
          <div className="subtle">researcher-only · direct transport · not organism vision · not display RGB · O3A entity surfaces active</div>
        </div>
      );
    })() : null}

    {frame?.world?.object_body_held_optical_surfaces ? (() => {
      const o3a = frame.world.object_body_held_optical_surfaces;
      const classes = o3a.class_counts || {};
      const counts = o3a.state_counts || {};
      const o1 = o3a.o1_status_counts || {};
      return (
        <div className="panel" data-testid="o3a-object-body-held-optical-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="o3a-object-body-held-optical-banner">
            {o3a.label || 'ANALYTIC PHYSICAL SURFACE SAMPLES · DIRECT LIGHT ONLY · NOT ORGANISM VISION'}
          </div>
          <div className="subtle" data-testid="o3a-object-body-held-optical-status">
            samples={o3a.sample_count ?? 0}
            {' '}· body={classes.BODY ?? 0}
            {' '}· free={classes.FREE_RESOURCE_OBJECT ?? 0}
            {' '}· held={classes.HELD_RESOURCE_OBJECT ?? 0}
            {' '}· detached={classes.DETACHED_TERRAIN_RESOURCE_OBJECT ?? 0}
            {' '}· lit={counts.DIRECT_ILLUMINATED ?? 0}
            {' '}· back={counts.BACK_FACING_ZERO ?? 0}
            {' '}· occluded={counts.OCCLUDED_ZERO ?? 0}
            {' '}· o1_known={o1.PROFILE_RESOLVED ?? 0}
            {' '}· o1_unknown={(o1.UNKNOWN_PROFILE ?? 0) + (o1.LEGACY_FIXED_COMPATIBILITY ?? 0)}
            {' '}· entity_occ={o3a.entity_entity_light_occlusion || '—'}
            {' '}· checksum={o3a.result_checksum || '—'}
            {' '}· cache={o3a.cache_key_digest || '—'}
            {' '}· hits={o3a.cache_hits ?? 0}/miss={o3a.cache_misses ?? 0}
          </div>
          <div className="subtle">researcher-only · analytic samples · collision geometry · not organism vision · not optical_radius</div>
        </div>
      );
    })() : null}

    {frame?.world?.organism_physical_optical_reception ? (() => {
      const o4 = frame.world.organism_physical_optical_reception;
      const reasons = o4.reason_counts || {};
      return (
        <div className="panel" data-testid="o4-organism-physical-optical-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="o4-organism-physical-optical-banner">
            {(o4.labels && o4.labels.join(' · ')) || o4.label || 'ORGANISM PHYSICAL OPTICAL RECEPTION · ABSTRACT NON-SI BANDS · NOT HUMAN RGB · VW7/OBSERVER PIXELS NOT USED'}
          </div>
          <div className="subtle" data-testid="o4-organism-physical-optical-status">
            accepted={o4.accepted ?? '—'}
            {' '}· rejected={o4.rejected ?? '—'}
            {' '}· reached_receptor={String(o4.physical_signal_reached_receptor ?? false)}
            {' '}· delay={o4.visual_causal_delay_ticks ?? 0}
            {' '}· k_visual={o4.k_visual ?? '—'}
            {' '}· schema={o4.cognition_schema || '—'}
            {' '}· occluded_vw1={reasons.OCCLUDED_VW1 ?? 0}
            {' '}· occluded_entity={reasons.OCCLUDED_ENTITY ?? 0}
            {' '}· unknown={reasons.UNKNOWN_MATERIAL ?? 0}
          </div>
          <div className="subtle">physical optical receptor view · not conscious seeing · not display RGB · legacy illumination not used</div>
        </div>
      );
    })() : null}

    {frame?.world?.sensory_modality_temporal_alignment ? (() => {
      const o5 = frame.world.sensory_modality_temporal_alignment;
      const motor = o5.motor_links || {};
      return (
        <div className="panel" data-testid="o5-sensory-modality-temporal-alignment-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="o5-sensory-modality-temporal-alignment-banner">
            {(o5.labels && o5.labels.join(' · ')) || 'SCIENTIFIC TICKS · NOT WALL TIME · MODALITIES MAY REPRESENT DIFFERENT PHYSICAL EVENT TIMES · OATT DELAY IS RECEPTOR→OBSERVATION, NOT LPS TRANSPORT'}
          </div>
          <div className="subtle" data-testid="o5-sensory-modality-temporal-alignment-status">
            status={o5.alignment_status ?? '—'}
            {' '}· obs_tick={o5.organism_observation_tick ?? '—'}
            {' '}· agent={o5.agent_id ?? '—'}
            {' '}· vision_receptor={o5.vision_receptor_sample_tick ?? '—'}
            {' '}· vision_delay={o5.vision_causal_delay_ticks ?? '—'}
            {' '}· hearing_lps={o5.hearing_lps_reception_tick ?? '—'}
            {' '}· src→recv={o5.hearing_source_to_receptor_delay ?? '—'}
            {' '}· A3→obs={o5.hearing_receptor_to_observation_delay ?? '—'}
            {' '}· body={o5.body_support_tick ?? '—'}
            {' '}· decision={motor.motor_decision_tick ?? '—'}
            {' '}· actuate={motor.actuation_tick ?? '—'}
            {' '}· consequence={motor.physical_consequence_tick ?? '—'}
            {' '}· vision_avail={o5.vision_availability ?? '—'}
            {' '}· hearing_avail={o5.hearing_availability ?? '—'}
          </div>
          <div className="subtle" data-testid="o5-sensory-modality-temporal-alignment-note">
            same_observation ≠ same physical time · researcher-only · not synchronized badge · not cognition
          </div>
        </div>
      );
    })() : null}

    {frame?.world?.researcher_physical_optical_audit_view ? (() => {
      const o6 = frame.world.researcher_physical_optical_audit_view;
      return (
        <div className="panel" data-testid="o6-researcher-physical-optical-audit-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="o6-researcher-physical-optical-audit-banner">
            {(o6.labels && o6.labels.join(' · ')) || 'RESEARCHER TRANSFORM · ABSTRACT NON-SI OPTICAL BANDS · NOT HUMAN RGB · NOT ORGANISM VISION'}
          </div>
          <div className="subtle" data-testid="o6-researcher-physical-optical-audit-status">
            status={o6.status ?? '—'}
            {' '}· facets={o6.facet_count ?? '—'}
            {' '}· entities={o6.entity_sample_count ?? '—'}
            {' '}· illuminated={o6.state_counts?.DIRECT_ILLUMINATED ?? 0}
            {' '}· occluded={o6.state_counts?.OCCLUDED_ZERO ?? 0}
            {' '}· back={o6.state_counts?.BACK_FACING_ZERO ?? 0}
            {' '}· src={o6.source?.source_id ?? '—'}
            {' '}· org={o6.organism_comparison?.uses_exact_o4_trace ? 'EXACT_O4' : (o6.organism_comparison?.status ?? '—')}
            {' '}· o5={o6.o5_timing?.alignment_status ?? o6.o5_timing?.status ?? '—'}
          </div>
          <div className="subtle">SURFACE/LIGHT viewport · O2 facets · O3A analytic geometry · display-only · not VW7 pixels · not cognition</div>
        </div>
      );
    })() : null}

    {frame?.world?.release_and_excavation_support_loss_integration ? (() => {
      const mi = frame.world.release_and_excavation_support_loss_integration;
      const ls = mi?.last_receipt || frame.world.last_release_excavation_support_loss || {};
      const banner = frame.world.release_and_excavation_support_loss_integration_banner
        || 'FREE-SPACE ENTRY INTEGRATION · RELEASE + EXCAVATION SUPPORT LOSS · T+1 FALL · SHARED LANDING/SOUND · NO SNAP · NO SPECIAL-CASE IMPACT';
      return (
        <div className="panel" data-testid="release-excavation-support-loss-panel" style={{marginTop:8}}>
        <div data-testid="release-excavation-support-loss-banner" className="observer-banner researcher-only" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle" data-testid="release-excavation-support-loss-inspector">
          class={ls.event_class ?? '—'} · source={ls.source_kind ?? '—'} · id={ls.entity_id ?? '—'} · kind={ls.entity_kind ?? '—'} · tick={ls.tick ?? '—'} · release_tick={ls.release_tick ?? '—'} · eligible={ls.dynamics_eligible_tick ?? ls.next_vertical_eligibility ?? '—'} · pose=({ls.pose_x != null ? Number(ls.pose_x).toFixed(3) : '—'},{ls.pose_y != null ? Number(ls.pose_y).toFixed(3) : '—'},{ls.pose_z != null ? Number(ls.pose_z).toFixed(3) : '—'}) · vz={ls.inherited_vz != null ? Number(ls.inherited_vz).toFixed(4) : '—'} · support={ls.support_classification ?? ls.support_z_after ?? '—'} · z_unchanged={String(ls.entity_z_unchanged ?? true)} · impact={String(ls.creates_impact ?? false)} · sound={String(ls.creates_sound ?? false)} · shared_v1={String(ls.enters_shared_v1a ?? true)} · txn={ls.material_transaction_id ?? '—'} · cell={Array.isArray(ls.source_cell) ? ls.source_cell.join(',') : '—'} · dedup={ls.dedup_key ?? '—'} · entries={mi?.counters?.release_entries ?? 0} · lost={mi?.counters?.support_lost ?? 0}
        </div>
        </div>
      );
    })() : null}

    {(() => {
      const vd = readVerticalDisplay(frame?.world);
      if (!vd) return null;
      const ix = selectedCell?.ix ?? selectedCell?.position?.[0];
      const iy = selectedCell?.iy ?? selectedCell?.position?.[1];
      let cellInfo: any = null;
      if (Number.isFinite(Number(ix)) && Number.isFinite(Number(iy)) && Array.isArray(vd.cell_centre_elevation?.data)) {
        const x = Number(ix); const y = Number(iy);
        const cur = vd.cell_centre_elevation?.data?.[y]?.[x];
        const delta = (vd.sparse_deltas || []).find((d: any) => Number(d.cell_x) === x && Number(d.cell_y) === y);
        cellInfo = {
          x, y,
          current: cur,
          baseline: delta?.baseline_elevation,
          signed: delta?.signed_delta ?? (delta ? undefined : 0),
          revision: delta?.revision ?? 0,
        };
      }
      const ents = vd.entities_vertical || [];
      const events = vd.events_recent || [];
      return (
        <div className="panel" data-testid="physical-elevation-free-space-panel" style={{marginTop:8}}>
          <div className="observer-banner researcher-only" data-testid="physical-elevation-free-space-banner">
            PHYSICAL ELEVATION / FREE SPACE · RESEARCHER VIEW · NOT AGENT PERCEPTION · {vd.schema_version}
          </div>
          <div className="subtle">AUTHORITATIVE elev · RESEARCHER RECEIPT events · RENDER-DERIVED stems/false-color</div>
          {cellInfo ? (
            <div className="subtle" data-testid="physical-elevation-cell">
              cell ({cellInfo.x},{cellInfo.y}) · current={cellInfo.current != null ? Number(cellInfo.current).toFixed(4) : '—'}
              · baseline={cellInfo.baseline != null ? Number(cellInfo.baseline).toFixed(4) : '—'}
              · Δ={cellInfo.signed != null ? Number(cellInfo.signed).toFixed(4) : '—'}
              · rev={cellInfo.revision}
              · gen={vd.surface_generation ?? '—'} · checksum={vd.deltas_checksum ?? '—'}
              · AUTHORITATIVE
            </div>
          ) : (
            <div className="subtle">Select a terrain cell for elevation / baseline / delta.</div>
          )}
          <div className="subtle" data-testid="physical-elevation-entities">
            {ents.slice(0, 8).map((e: any) => (
              <div key={`${e.kind}-${e.id}`}>
                {e.kind}/{e.id} · xy=({Number(e.x).toFixed(2)},{Number(e.y).toFixed(2)})
                · base_z={e.base_z != null ? Number(e.base_z).toFixed(4) : '—'}
                · centre_z={e.centre_z != null ? Number(e.centre_z).toFixed(4) : '—'}
                · he={e.vertical_half_extent != null ? Number(e.vertical_half_extent).toFixed(3) : '—'}
                · support_z={e.support_z != null ? Number(e.support_z).toFixed(4) : '—'}
                · clearance={e.clearance != null ? Number(e.clearance).toFixed(4) : '—'}
                · vz={e.vz != null ? Number(e.vz).toFixed(4) : '—'}
                · state={e.support_state ?? '—'} · grounded={String(e.grounded ?? '—')}
                · phys={e.physical_state ?? '—'} · cr={e.collision_radius ?? '—'}
                · held={e.holder_body_id ? `${e.holder_body_id}/${e.manipulator_id}` : '—'}
                · elig={e.dynamics_eligible_tick ?? '—'}
                · AUTHORITATIVE{e.glyph_is_not_physics ? ' · glyph ≠ collision geometry' : ''}
              </div>
            ))}
          </div>
          <div className="subtle" data-testid="physical-elevation-events">
            events (bounded, RESEARCHER RECEIPT): {events.slice(-6).map((ev: any) =>
              `${ev.event_class}@${ev.tick}:${ev.entity_id || '?'}`
            ).join(' · ') || '—'}
          </div>
          <div className="subtle" data-testid="vertical-trajectory-section">
            <strong>VERTICAL TRAJECTORY</strong> · AUTHORITATIVE SAMPLES · DISPLAY-SPACE HEIGHT
            {(vd.trail_segments || []).slice(0, 4).map((seg: any) => (
              <div key={seg.segment_id || `${seg.entity_id}-${seg.start_tick}`}>
                {seg.entity_kind}/{seg.entity_id} · start={seg.start_reason}@{seg.start_tick}
                · end={seg.end_reason || 'active'}@{seg.end_tick ?? '—'}
                · n={seg.sample_count ?? (seg.samples || []).length}
                · policy={seg.sample_policy ?? '—'}
                · z=[{seg.z_min != null ? Number(seg.z_min).toFixed(3) : '—'},{seg.z_max != null ? Number(seg.z_max).toFixed(3) : '—'}]
                · clr=[{seg.clearance_min != null ? Number(seg.clearance_min).toFixed(3) : '—'},{seg.clearance_max != null ? Number(seg.clearance_max).toFixed(3) : '—'}]
                · vz=[{seg.vz_min != null ? Number(seg.vz_min).toFixed(3) : '—'},{seg.vz_max != null ? Number(seg.vz_max).toFixed(3) : '—'}]
                · release={seg.release_tick ?? '—'} · loss={seg.support_loss_tick ?? '—'}
                · land={seg.landing_tick ?? '—'} · sound={seg.acoustic_tick ?? '—'}
                · disc={seg.discontinuity_reason ?? '—'}
                · {seg.authority || 'DERIVED_OBSERVER_CACHE_NON_AUTHORITATIVE'}
              </div>
            ))}
            {!(vd.trail_segments || []).length ? (
              <div>no active/recent trail segments · INTERPOLATION OFF · {vd.display_profile || 'trails'}</div>
            ) : null}
          </div>
          <div className="subtle" data-testid="elevation-free-space-story">
            ELEVATION / EXCAVATION / FREE-SPACE STORY · VERTICAL TRAJECTORIES ·
            missing elevation/trail payload ⇒ FULL VERTICAL TRAIL NOT AVAILABLE FOR THIS RUN ·
            ANALYZER_PROGRESS_BAR_STATUS=TEXT_STATUS_ONLY
          </div>
        </div>
      );
    })()}

    {frame?.world?.held_translational_impulse ? (() => {
      const hi = frame.world.held_translational_impulse;
      const ls = hi?.last_step || {};
      return (
        <div className="panel" data-testid="held-translational-impulse-panel" style={{marginTop:8}}>
        <div data-testid="held-translational-impulse-banner"><strong>HELD OBJECT TRANSLATIONAL IMPULSE MEDIATION V1</strong> · CONSTRAINED OBJECT → HOLDER BODY · NO SWING WORK · NO DAMAGE · NO RELEASE · NO SOUND</div>
        <div className="subtle">responses={ls.responses ?? 0} · impulses={ls.impulses_applied ?? 0} · eligible={ls.translationally_eligible ?? 0} · effector_unresolved={ls.effector_work_unresolved ?? 0} · multi={ls.multi_constraint_unresolved ?? 0}</div>
        </div>
      );
    })() : null}

    {frame?.world?.effector_work_held_load ? (() => {
      const ew = frame.world.effector_work_held_load;
      const ls = ew || {};
      return (
        <div className="panel" data-testid="effector-work-held-load-panel" style={{marginTop:8}}>
        <div data-testid="effector-work-held-load-banner"><strong>EFFECTOR WORK + HELD-LOAD INERTIA ACCOUNTING V1</strong> · NO ARM MASS · NO SWING IMPULSE · NO DAMAGE</div>
        <div className="subtle">work_debit={ls.last_work_debit ?? 0} · admission_scale={ls.last_admission_scale ?? 1} · limited={String(ls.last_work_limited ?? false)} · rotational={ls.ROTATIONAL_WORK_STATUS || 'ROTATIONAL_WORK_NOT_ESTABLISHED'}</div>
        </div>
      );
    })() : null}

        {frame?.world?.surface_elevation_support ? (() => {
      const banner = frame.world.surface_elevation_support_banner
        || 'PHASE C · SURFACE ELEVATION SUPPORT V1 · ENERGY-ACCOUNTED MICRORELIEF · NO FREE PE';
      return (
        <div className="observer-banner researcher-only" data-mechanism="surface_elevation_support">
          {banner}
        </div>
      );
    })() : null}

        {frame?.world?.ses_decomposition_contract ? (() => {
      // G2C1: researcher-only metadata. Taxonomy/authority are never agent-visible.
      const sdc = frame.world.ses_decomposition_contract;
      const banner = frame.world.ses_decomposition_contract_banner
        || 'SES DECOMPOSITION CONTRACT G2C1\nPE AUTHORITY: SES DDA\nTRANSITION TAXONOMY ACTIVE\nPHYSICS OUTPUTS IDENTICAL TO PARENT\nNORMAL/TANGENT GRAVITY OFF · NO RADIUS-FACE SWEEP';
      const c = sdc.counters || {};
      const last = sdc.last_receipt || {};
      return (
        <div className="panel" data-testid="ses-decomposition-contract-panel" style={{marginTop:8}}>
        <div className="observer-banner researcher-only" data-mechanism="ses_decomposition_contract" data-testid="ses-decomposition-contract-banner" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">researcher-only · authority={sdc.pe_authority ?? 'PE_AUTHORITY_SES_DDA'} · receipts={c.receipts_emitted ?? 0} · last={last.transition_class ?? '—'} · decision={last.ses_legacy_decision ?? '—'} · support={last.support_class ?? '—'}</div>
        </div>
      );
    })() : null}

        {frame?.world?.ses_runtime_transition_classifier ? (() => {
      const srtc = frame.world.ses_runtime_transition_classifier;
      const banner = frame.world.ses_runtime_transition_classifier_banner
        || 'SES RUNTIME CLASSIFIER · RESEARCHER-ONLY · PE AUTHORITY: SES DDA · CLASSIFICATION DOES NOT CONTROL PHYSICS';
      const c = srtc.counters || {};
      const origin = Array.isArray(srtc.latest_origin) ? srtc.latest_origin.map((n: number) => Number(n).toFixed(2)).join(',') : '—';
      const proposed = Array.isArray(srtc.latest_proposed_destination) ? srtc.latest_proposed_destination.map((n: number) => Number(n).toFixed(2)).join(',') : '—';
      const realized = Array.isArray(srtc.latest_realized_destination) ? srtc.latest_realized_destination.map((n: number) => Number(n).toFixed(2)).join(',') : '—';
      const acc = srtc.latest_accepted === true ? 'accepted' : (srtc.latest_blocked === true ? 'blocked' : '—');
      return (
        <div className="panel" data-testid="ses-runtime-transition-classifier-panel" style={{marginTop:8}}>
        <div className="observer-banner researcher-only" data-mechanism="ses_runtime_transition_classifier" data-testid="ses-runtime-transition-classifier-banner" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">researcher-only · class={srtc.latest_transition_class ?? '—'} · {acc} · {origin} → prop {proposed} / real {realized} · PE={srtc.pe_authority ?? 'PE_AUTHORITY_SES_DDA'} · ver={srtc.classifier_version ?? '—'} · receipts={c.receipts_emitted ?? 0} · classification does not control physics</div>
        </div>
      );
    })() : null}

        {frame?.world?.radius_aware_face_sweep ? (() => {
      const fs = frame.world.radius_aware_face_sweep;
      const banner = frame.world.radius_aware_face_sweep_banner
        || 'RADIUS-AWARE FACE SWEEP · SES PLAN EVIDENCE · PE AUTHORITY: SES DDA · NO RADIUS PE';
      const c = fs.counters || {};
      const last = fs.last_receipt || {};
      const origin = Array.isArray(last.origin) ? last.origin.map((n: number) => Number(n).toFixed(2)).join(',') : '—';
      const proposed = Array.isArray(last.proposed_destination) ? last.proposed_destination.map((n: number) => Number(n).toFixed(2)).join(',') : '—';
      const realized = Array.isArray(last.realized_destination) ? last.realized_destination.map((n: number) => Number(n).toFixed(2)).join(',') : '—';
      const result = last.ses_accepted === true ? 'accepted' : (last.ses_block_reason ? `blocked:${last.ses_block_reason}` : '—');
      const pen = last.starting_penetration?.disposition ?? '—';
      return (
        <div className="panel" data-testid="radius-aware-face-sweep-panel" style={{marginTop:8}}>
        <div className="observer-banner researcher-only" data-mechanism="radius_aware_face_sweep" data-testid="radius-aware-face-sweep-banner" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">researcher-only · entity={last.entity_kind ?? '—'}:{last.entity_id ?? '—'} · R={last.physical_radius ?? '—'} · {origin} → prop {proposed} / real {realized} · {result} · hit_t={last.earliest_hit_t ?? '—'} · candidates={last.candidate_count ?? c.evaluations ?? 0} · pen={pen} · work/PE=0 · ver={fs.profile_version ?? '—'}</div>
        </div>
      );
    })() : null}


        {frame?.world?.continuous_gravitational_pe_diagnostic_shadow ? (() => {
      const pe = frame.world.continuous_gravitational_pe_diagnostic_shadow;
      const banner = frame.world.continuous_gravitational_pe_diagnostic_shadow_banner
        || 'CONTINUOUS GRAVITATIONAL PE\nDIAGNOSTIC SHADOW\nPHYSICAL AUTHORITY: SES_DDA\nCANDIDATE: ENDPOINT ΔU\nPHYSICS: UNCHANGED';
      const c = pe.counters || {};
      const last = pe.last_receipt || {};
      return (
        <div className="panel" data-testid="continuous-gravitational-pe-diagnostic-shadow-panel" style={{marginTop:8}}>
        <div className="observer-banner researcher-only" data-mechanism="continuous_gravitational_pe_diagnostic_shadow" data-testid="continuous-gravitational-pe-diagnostic-shadow-banner" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">researcher-only · SHADOW · authority=SES_DDA · candidate=endpoint ΔU · status={last.status ?? '—'} · cmp={last.comparison_class ?? '—'} · ΔU={last.candidate_endpoint_delta_u ?? '—'} · ses={last.current_ses_gravitational_delta ?? '—'} · queries={c.queries ?? 0} · cand_only={c.cmp_candidate_only ?? 0} · physics_effect=NONE</div>
        </div>
      );
    })() : null}

        {frame?.world?.diagnostic_normal_load_shadow ? (() => {
      const dn = frame.world.diagnostic_normal_load_shadow;
      const banner = frame.world.diagnostic_normal_load_shadow_banner
        || 'CONTINUOUS NORMAL LOAD · DIAGNOSTIC SHADOW · PHYSICAL N = m·g · CANDIDATE N = m·g·n_z · PHYSICS EFFECT = NONE';
      const c = dn.counters || {};
      const last = dn.last_receipt || {};
      return (
        <div className="panel" data-testid="diagnostic-normal-load-shadow-panel" style={{marginTop:8}}>
        <div className="observer-banner researcher-only" data-mechanism="diagnostic_normal_load_shadow" data-testid="diagnostic-normal-load-shadow-banner" style={{whiteSpace:'pre-line'}}>{banner}</div>
        <div className="subtle">researcher-only · SHADOW · physical N=m·g · candidate N=m·g·n_z · source={last.normal_source ?? 'CENTRE_ANALYTIC_CSG_N_HAT'} · status={last.status ?? '—'} · n_z={last.n_z ?? '—'} · N_flat={last.N_flat ?? '—'} · N_proj={last.N_projected ?? '—'} · queries={c.queries ?? 0} · dup={c.duplicate_suppressed ?? 0} · physics_effect=NONE</div>
        </div>
      );
    })() : null}

        {frame?.world?.body_normal_load_traction ? (() => {
      const bn = frame.world.body_normal_load_traction;
      const banner = frame.world.body_normal_load_traction_banner
        || 'BODY NORMAL-LOAD TRACTION + PASSIVE SLIDING V1 · N=m_eff g · μ(affinity) · GENTLE DAMP BYPASS · NO AIR TRACTION';
      const c = bn.counters || {};
      return (
        <div className="panel" data-testid="body-normal-load-traction-panel" style={{marginTop:8}}>
        <div className="observer-banner researcher-only" data-mechanism="body_normal_load_traction" data-testid="body-normal-load-traction-banner">{banner}</div>
        <div className="subtle">grounded_steps={c.grounded_friction_steps ?? 0} · airborne={c.airborne_conserve_steps ?? 0} · rest={c.rest_transitions ?? 0} · gentle_bypass={c.gentle_velocity_damp_bypassed ?? 0}</div>
        </div>
      );
    })() : null}
{frame?.world?.free_resource_object_ground_friction ? (() => {
      const fr = frame.world.free_resource_object_ground_friction;
      const c = fr.counters || {};
      return (
        <div className="panel" data-testid="free-object-ground-friction-panel" style={{marginTop:8}}>
        <div data-testid="free-object-ground-friction-banner"><strong>FREE OBJECT FLAT-GROUND FRICTION V1</strong> · F=μN · MATERIAL-DERIVED SURFACE COUPLING · BODIES UNCHANGED · NO AIR DRAG · NO SLOPES</div>
        <div className="subtle">grounded_steps={c.grounded_friction_steps ?? 0} · airborne_conserve={c.airborne_conserve_steps ?? 0} · rest={c.rest_transitions ?? 0} · damping_bypassed={c.legacy_damping_bypassed ?? 0}</div>
        </div>
      );
    })() : null}

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
    <div className="section-label">Terrain relief (researcher display)</div>
    <div className="subtle" data-testid="terrain-researcher-only-label">RESEARCHER VIEW · NOT AGENT PERCEPTION</div>
    <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }} data-testid="terrain-display-modes">
      {([
        ['OPTICAL', 'TERRAIN: OPTICAL'],
        ['ELEVATION', 'TERRAIN: ELEVATION'],
        ['DELTA', 'TERRAIN: DELTA'],
      ] as Array<[TerrainDisplayMode, string]>).map(([mode, lab]) => {
        const vd = readVerticalDisplay(world);
        const elevOk = elevationGridValid(vd);
        const deltaOk = Array.isArray(vd?.sparse_deltas);
        const available = mode === 'OPTICAL' || (mode === 'ELEVATION' && elevOk) || (mode === 'DELTA' && (elevOk || deltaOk));
        return (
          <button
            key={mode}
            type="button"
            className={terrainMode === mode ? 'active' : ''}
            disabled={!available}
            data-testid={`terrain-mode-${mode.toLowerCase()}`}
            onClick={() => setTerrainMode(mode)}
          >{lab}</button>
        );
      })}
    </div>
    <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
      <label className="check">
        <input type="checkbox" checked={showClearanceStems} onChange={e => setShowClearanceStems(e.target.checked)} />
        CLEARANCE STEMS
      </label>
      <label className="check">
        <input type="checkbox" checked={showEventMarkers} onChange={e => setShowEventMarkers(e.target.checked)} />
        EVENT MARKERS
      </label>
      <label className="check">
        <input type="checkbox" checked={showElevationContours} onChange={e => setShowElevationContours(e.target.checked)} />
        CONTOURS (render-derived)
      </label>
      <label>
        {VERTICAL_EXAGGERATION_LABEL}
        <select
          value={verticalExaggeration}
          onChange={e => setVerticalExaggeration(Number(e.target.value))}
          data-testid="vertical-exaggeration"
        >
          {[2, 3, 4].map(v => <option key={v} value={v}>{v}× stems</option>)}
        </select>
      </label>
    </div>
    <div className="subtle">Elevation false-color uses physical 1× semantics. Stem length may use labelled display exaggeration. Never agent perception.</div>
    <div className="section-label">Vertical trails (researcher display)</div>
    <div className="subtle" data-testid="trail-researcher-only-label">{TRAIL_RESEARCHER_LABEL}</div>
    <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }} data-testid="trail-display-modes">
      {([
        ['OFF', 'TRAILS: OFF'],
        ['SELECTED', 'TRAILS: SELECTED'],
        ['UNSUPPORTED', 'TRAILS: UNSUPPORTED'],
      ] as Array<[TrailDisplayMode, string]>).map(([mode, lab]) => (
        <button
          key={mode}
          type="button"
          className={trailMode === mode ? 'active' : ''}
          data-testid={`trail-mode-${mode.toLowerCase()}`}
          onClick={() => setTrailMode(mode)}
        >{lab}</button>
      ))}
    </div>
    <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
      <label>
        Trail length
        <select
          value={trailLengthMode}
          onChange={e => setTrailLengthMode(e.target.value as TrailLengthMode)}
          data-testid="trail-length-mode"
        >
          {([
            ['SHORT', TRAIL_LENGTH_SAMPLES.SHORT],
            ['NORMAL', TRAIL_LENGTH_SAMPLES.NORMAL],
            ['LONG', TRAIL_LENGTH_SAMPLES.LONG],
          ] as const).map(([k, n]) => (
            <option key={k} value={k}>{k} ({n})</option>
          ))}
        </select>
      </label>
    </div>
    <div className="subtle">Default SELECTED · INTERPOLATION OFF · samples are scientific-tick authoritative when Observer serializes</div>
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
      <button data-testid="world-view-map" className={volumeWorkspace === 'MAP' ? 'active' : ''} onClick={() => setVolumeWorkspace('MAP')}>MAP / 2D</button>
      <button data-testid="world-view-volume" className={volumeWorkspace === 'VOLUME' ? 'active' : ''} onClick={() => setVolumeWorkspace('VOLUME')}>VOLUME / X-RAY</button>
      <button data-testid="world-view-surface" className={volumeWorkspace === 'SURFACE' ? 'active' : ''} onClick={() => setVolumeWorkspace('SURFACE')}>SURFACE / LIGHT</button>
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
          {selectedCell.geometry?.surface_column ? (() => {
            const col = selectedCell.geometry.surface_column;
            return <div data-testid="surface-column-inspector">
              <div className="section-label">Surface column (researcher-only · authoritative world state)</div>
              <KV name="surface elevation" value={col.surface_elevation}/>
              <KV name="modelled depth" value={col.modelled_depth}/>
              <KV name="layer count" value={col.layer_count}/>
              <KV name="persistent delta" value={col.persistent_delta ? `yes (rev ${col.delta_revision})` : 'no'}/>
              <KV name="generator" value={col.generator_version}/>
              {(col.layers || []).map((layer: any, i: number) => (
                <div key={i} className="subtle">
                  L{i} [{Number(layer.top_depth).toFixed(3)}, {Number(layer.bottom_depth).toFixed(3)}) · ρ {Number(layer.density).toFixed(3)} · {(layer.composition || []).map((c: any) => `${c.component_id} ${Number(c.quantity_per_area).toFixed(3)}`).join(' · ')}
                </div>
              ))}
              <div className="subtle">researcher-only · not agent-accessible · geometry metadata only · no support/gravity effect · procedural baseline + sparse delta</div>
              {col.column_transfer ? (() => {
                const tr = col.column_transfer;
                const num = (v: any) => (v == null ? '—' : Number(v).toFixed(4));
                return <div data-testid="surface-column-transfer-inspector">
                  <div className="section-label">Column transfer (researcher-only)</div>
                  <KV name="surface elevation" value={num(tr.surface_elevation)}/>
                  <KV name="baseline elevation" value={num(tr.baseline_surface_elevation)}/>
                  <KV name="elevation delta" value={num(tr.elevation_delta)}/>
                  <KV name="resolved depth" value={num(tr.resolved_modelled_depth)}/>
                  <KV name="column revision" value={tr.column_revision}/>
                  <KV name="last transfer id" value={tr.last_transfer_id || '—'}/>
                  <KV name="transfer role" value={tr.transfer_role || '—'}/>
                  <div className="subtle" data-testid="surface-column-transfer-labels">{(tr.labels || []).join(' · ')}</div>
                </div>;
              })() : null}
            </div>;
          })() : null}
          {selectedCell.geometry?.volumetric_occupancy ? (() => {
            const vo = selectedCell.geometry.volumetric_occupancy;
            const intervals = vo.occupied_intervals || [];
            const gaps = vo.free_gaps || [];
            const zVals = [
              ...intervals.flatMap((it: any) => [Number(it.z_min), Number(it.z_max)]),
              ...gaps.flatMap((g: any) => [Number(g.z_lo), Number(g.z_hi)]),
            ].filter((z) => Number.isFinite(z));
            const zLo = zVals.length ? Math.min(...zVals) : 0;
            const zHi = zVals.length ? Math.max(...zVals) : 1;
            const span = Math.max(zHi - zLo, 1e-9);
            const pct = (z: number) => `${((Number(z) - zLo) / span) * 100}%`;
            const hPct = (a: number, b: number) => `${(Math.abs(Number(b) - Number(a)) / span) * 100}%`;
            return <div data-testid="volumetric-occupancy-inspector">
              <div className="section-label">AUTHORITATIVE VOLUMETRIC OCCUPANCY (VW1 · absolute Z)</div>
              <KV name="authority" value={vo.authority || 'AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z'}/>
              <KV name="source" value={vo.source}/>
              <KV name="endpoint semantics" value={vo.interval_endpoint_semantics}/>
              <KV name="legacy projected surface" value={vo.derived_surface_elevation == null ? '—' : Number(vo.derived_surface_elevation).toFixed(4)}/>
              <div className="subtle" data-testid="volumetric-occupancy-authority-label">
                AUTHORITATIVE VOLUMETRIC OCCUPANCY · not LEGACY / DERIVED SURFACE PROJECTION · VW2 support/contact consumes this occupancy
              </div>
              <div data-testid="volumetric-occupancy-column-strip" style={{position: 'relative', height: 160, margin: '8px 0', border: '1px solid #555', background: '#1a1a1a'}}>
                {gaps.map((g: any, i: number) => (
                  <div key={`gap-${i}`} data-testid="volumetric-free-gap" title={`FREE (${Number(g.z_lo).toFixed(3)}, ${Number(g.z_hi).toFixed(3)}]`}
                    style={{position: 'absolute', left: 0, right: 0, bottom: pct(g.z_lo), height: hPct(g.z_lo, g.z_hi), background: 'rgba(80,120,200,0.25)', borderTop: '1px dashed #6af'}}/>
                ))}
                {intervals.map((it: any, i: number) => (
                  <div key={`occ-${i}`} data-testid="volumetric-occupied-interval" title={`OCC (${Number(it.z_min).toFixed(3)}, ${Number(it.z_max).toFixed(3)}]`}
                    style={{position: 'absolute', left: 0, right: 0, bottom: pct(it.z_min), height: hPct(it.z_min, it.z_max), background: 'rgba(160,110,60,0.7)', borderTop: '1px solid #c96'}}/>
                ))}
              </div>
              {(intervals || []).map((it: any, i: number) => (
                <div key={i} className="subtle" data-testid="volumetric-interval-row">
                  OCC [{Number(it.z_min).toFixed(3)}, {Number(it.z_max).toFixed(3)}] · ρ {Number(it.density).toFixed(3)} · {(it.composition || []).map((c: any) => `${c.component_id} ${Number(c.quantity_per_area).toFixed(3)}`).join(' · ') || '—'}
                  {it.physical_optical_material_profile ? (
                    <div data-testid="o1-material-optical-profile" style={{marginTop: 4}}>
                      <div className="subtle">{it.physical_optical_material_profile_label || 'MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB'}</div>
                      <div>O1 status: {it.physical_optical_material_profile.status} · schema {it.physical_optical_material_profile.schema}</div>
                      <div>
                        R[{(it.physical_optical_material_profile.optical_band_identifiers || []).join(',')}] ={' '}
                        {Array.isArray(it.physical_optical_material_profile.spectral_reflectance)
                          ? it.physical_optical_material_profile.spectral_reflectance.map((v: number) => Number(v).toFixed(3)).join(', ')
                          : '—'}
                      </div>
                      <div className="subtle">no color swatch · not display RGB · no light transport</div>
                    </div>
                  ) : null}
                </div>
              ))}
              {(gaps || []).map((g: any, i: number) => (
                <div key={`g-${i}`} className="subtle" data-testid="volumetric-gap-row">
                  FREE gap ({Number(g.z_lo).toFixed(3)}, {Number(g.z_hi).toFixed(3)}]
                </div>
              ))}
              <div className="subtle">researcher-only · not agent-accessible · VW1 occupancy authority · free = complement of occupied</div>
            </div>;
          })() : null}
          {selectedCell.geometry?.occupancy_support_contact ? (() => {
            const sc = selectedCell.geometry.occupancy_support_contact;
            const num = (v: any) => (v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(4));
            return <div data-testid="occupancy-support-contact-inspector">
              <div className="section-label">VW2 SUPPORT / CONTACT (from volumetric occupancy)</div>
              <div className="subtle" data-testid="vw2-authority-label">{sc.authority_label || 'AUTHORITATIVE VW2 SUPPORT/CONTACT FROM VOLUMETRIC OCCUPANCY'}</div>
              <div className="subtle" data-testid="vw2-legacy-label">{sc.legacy_label || 'LEGACY / DERIVED SURFACE PROJECTION (not support authority when VW2 active)'}</div>
              <KV name="body query_z (lower extent)" value={num(sc.query_z)}/>
              <KV name="VW2 boundary_z" value={num(sc.boundary_z)}/>
              <KV name="legacy projected surface" value={num(sc.legacy_projected_surface)}/>
              <KV name="clearance" value={num(sc.clearance)}/>
              <KV name="penetration" value={num(sc.penetration)}/>
              <KV name="relation" value={sc.relation}/>
              <KV name="contact_exists" value={sc.contact_exists ? 'YES' : 'NO'}/>
              <KV name="support_capable" value={sc.support_capable ? 'YES' : 'NO'}/>
              <KV name="contradicts legacy surface" value={sc.contradicts_legacy_projected_surface ? 'YES' : 'NO'}/>
              {sc.source_interval ? <div className="subtle" data-testid="vw2-source-interval">
                source interval ({Number(sc.source_interval.z_min).toFixed(3)}, {Number(sc.source_interval.z_max).toFixed(3)}] · ρ {Number(sc.source_interval.density).toFixed(3)}
              </div> : <div className="subtle" data-testid="vw2-source-interval">source interval: NONE</div>}
              <div className="subtle">researcher-only · physics follows VW2 occupancy boundary, not legacy max surface · gravity/PE/landing ownership unchanged</div>
            </div>;
          })() : null}
          {selectedCell.geometry?.volumetric_material_separation ? (() => {
            const sep = selectedCell.geometry.volumetric_material_separation;
            const rec = sep.receipt || {};
            const before = rec.before?.occupied_intervals || [];
            const after = rec.after?.occupied_intervals || [];
            const removed = rec.removed_pieces || [];
            return <div data-testid="volumetric-material-separation-inspector">
              <div className="section-label">VW3 VOLUMETRIC SEPARATION (WMT)</div>
              <div className="subtle" data-testid="vw3-authority-label">{sep.authority_label || 'AUTHORITATIVE VW3 VOLUMETRIC SEPARATION VIA WMT'}</div>
              <KV name="status" value={rec.status}/>
              <KV name="transaction_id" value={rec.transaction_id || '—'}/>
              <KV name="object_id" value={rec.object_id || '—'}/>
              <KV name="cell" value={(rec.cell || []).join(', ')}/>
              <KV name="removed Z" value={rec.removal ? `(${Number(rec.removal.z_lo).toFixed(3)}, ${Number(rec.removal.z_hi).toFixed(3)}]` : '—'}/>
              <div className="subtle" data-testid="vw3-before-intervals">BEFORE: {(before || []).map((it: any) => `(${Number(it.z_min).toFixed(2)}, ${Number(it.z_max).toFixed(2)}]`).join(' · ') || '—'}</div>
              <div className="subtle" data-testid="vw3-removed-region">REMOVED: {(removed || []).map((it: any) => `(${Number(it.z_min).toFixed(2)}, ${Number(it.z_max).toFixed(2)}]`).join(' · ') || '—'}</div>
              <div className="subtle" data-testid="vw3-after-intervals">AFTER: {(after || []).map((it: any) => `(${Number(it.z_min).toFixed(2)}, ${Number(it.z_max).toFixed(2)}]`).join(' · ') || '—'}</div>
              <div className="subtle">researcher-only · occupancy mutated · ResourceObject conserved · no DIG verb · reintegration = VW4</div>
            </div>;
          })() : null}
          {selectedCell.geometry?.volumetric_material_reintegration ? (() => {
            const rein = selectedCell.geometry.volumetric_material_reintegration;
            const rec = rein.receipt || {};
            const before = rec.before?.occupied_intervals || [];
            const after = rec.after?.occupied_intervals || [];
            const inserted = rec.after?.inserted || rec.deposition || {};
            const cons = rec.conservation || {};
            const prov = rec.provenance || {};
            return <div data-testid="volumetric-material-reintegration-inspector">
              <div className="section-label">VW4 VOLUMETRIC REINTEGRATION (WMT)</div>
              <div className="subtle" data-testid="vw4-authority-label">{rein.authority_label || 'AUTHORITATIVE VW4 VOLUMETRIC REINTEGRATION VIA WMT'}</div>
              <div className="subtle" data-testid="vw4-legacy-label">{rein.legacy_label || 'LEGACY / DERIVED SURFACE PROJECTION (not deposition destination truth)'}</div>
              <KV name="status" value={rec.status}/>
              <KV name="transaction_id" value={rec.transaction_id || '—'}/>
              <KV name="source object_id" value={rec.object_id || '—'}/>
              <KV name="source consumed" value={rec.source_consumed ? 'YES' : 'NO'}/>
              <KV name="qty consumed" value={rec.source_quantity_consumed != null ? Number(rec.source_quantity_consumed).toFixed(4) : '—'}/>
              <KV name="qty remaining" value={rec.source_remaining_quantity != null ? Number(rec.source_remaining_quantity).toFixed(4) : '—'}/>
              <KV name="cell" value={(rec.cell || []).join(', ')}/>
              <KV name="deposit Z" value={inserted.z_lo != null ? `(${Number(inserted.z_lo).toFixed(3)}, ${Number(inserted.z_hi).toFixed(3)}]` : '—'}/>
              <KV name="world qty added" value={cons.world_quantity_added != null ? Number(cons.world_quantity_added).toFixed(4) : '—'}/>
              <KV name="prior VW3 tx" value={prov.separation_transaction_id || '—'}/>
              <div className="subtle" data-testid="vw4-before-intervals">BEFORE: {(before || []).map((it: any) => `(${Number(it.z_min).toFixed(2)}, ${Number(it.z_max).toFixed(2)}]`).join(' · ') || '—'}</div>
              <div className="subtle" data-testid="vw4-deposited-region">DEPOSITED: {inserted.z_lo != null ? `(${Number(inserted.z_lo).toFixed(2)}, ${Number(inserted.z_hi).toFixed(2)}]` : '—'}</div>
              <div className="subtle" data-testid="vw4-after-intervals">AFTER: {(after || []).map((it: any) => `(${Number(it.z_min).toFixed(2)}, ${Number(it.z_max).toFixed(2)}]`).join(' · ') || '—'}</div>
              <div className="subtle">researcher-only · occupancy mutated · ResourceObject consumed · no BUILD verb · VW2 support follows occupancy · passive inspection</div>
            </div>;
          })() : null}
          {selectedCell.geometry?.effector_held_occupancy_exertion_bridge ? (() => {
            const br = selectedCell.geometry.effector_held_occupancy_exertion_bridge;
            const probe = br.last_probe || {};
            const exb = br.last_exertion_bridge || {};
            const vw3 = exb.vw3_receipt || {};
            const num = (v: any) => (v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(4));
            return <div data-testid="vw5-effector-occupancy-bridge-inspector">
              <div className="section-label">VW5 EFFECTOR / HELD OCCUPANCY EXERTION BRIDGE</div>
              <div className="subtle" data-testid="vw5-authority-label">{br.authority_label || 'AUTHORITATIVE VW5 EFFECTOR/HELD OCCUPANCY EXERTION BRIDGE'}</div>
              <div className="subtle" data-testid="vw5-legacy-label">{br.legacy_label || 'LEGACY / DERIVED SURFACE PROJECTION (not contact/exertion authority)'}</div>
              <KV name="probe clearance" value={probe.clearance_infinite ? '+∞ (no floor)' : num(probe.clearance)}/>
              <KV name="boundary_z" value={num(probe.boundary_z)}/>
              <KV name="in_contact" value={probe.in_contact ? 'YES' : 'NO'}/>
              <KV name="relation" value={probe.relation || '—'}/>
              <KV name="legacy projected surface" value={num(probe.legacy_projected_surface)}/>
              <KV name="contradicts legacy" value={probe.contradicts_legacy_projected_surface ? 'YES' : 'NO'}/>
              <KV name="false HF contact prevented" value={probe.false_heightfield_contact_prevented ? 'YES' : 'NO'}/>
              {probe.source_interval ? <div className="subtle" data-testid="vw5-contact-interval">
                contacted ({Number(probe.source_interval.z_min).toFixed(3)}, {Number(probe.source_interval.z_max).toFixed(3)}] · ρ {Number(probe.source_interval.density).toFixed(3)}
              </div> : <div className="subtle" data-testid="vw5-contact-interval">contacted interval: NONE</div>}
              <KV name="VW3 status" value={vw3.status || '—'}/>
              <KV name="VW3 transaction" value={vw3.transaction_id || '—'}/>
              <KV name="detached object" value={vw3.object_id || '—'}/>
              <div className="subtle" data-testid="vw5-reintegration-blocker">VW4 physical trigger: BLOCKED — {br.reintegration_blocker || '—'}</div>
              <div className="subtle">researcher-only · occupancy clearance/contact · resistance from contacted interval · failure→VW3 · no DIG/BUILD/PLACE · passive</div>
            </div>;
          })() : null}
          {selectedCell.geometry?.minimal_vision_3d_geometric_interface ? (() => {
            const v6 = selectedCell.geometry.minimal_vision_3d_geometric_interface;
            const live = v6.live || {};
            const rel = live.relative || {};
            const los = live.occupancy_los || {};
            const blocker = los.blocker || null;
            const receptor = live.phenotype_receptor || null;
            const num = (v: any) => (v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(4));
            const xyz = (a: any) => Array.isArray(a) && a.length >= 3
              ? `(${num(a[0])}, ${num(a[1])}, ${num(a[2])})` : '—';
            return <div data-testid="vw6-vision-3d-inspector">
              <div className="section-label">VW6 MINIMAL VISION 3D GEOMETRIC INTERFACE</div>
              <div className="subtle" data-testid="vw6-authority-label">{v6.authority_label || 'AUTHORITATIVE VW6 MINIMAL VISION 3D GEOMETRIC INTERFACE'}</div>
              <div className="subtle" data-testid="vw6-legacy-label">{v6.legacy_label || 'LEGACY XY / MAX-SURFACE GEOMETRY (not LOS authority when VW6 active)'}</div>
              <KV name="eye XYZ" value={xyz(live.eye_xyz)}/>
              <KV name="target XYZ" value={xyz(live.target_xyz)}/>
              <KV name="relative XYZ" value={`Δ(${num(rel.dx)}, ${num(rel.dy)}, ${num(rel.dz)})`}/>
              <KV name="distance 3D" value={num(live.distance_3d ?? rel.distance_3d)}/>
              <KV name="elevation deg" value={num(live.elevation_deg ?? rel.elevation_deg)}/>
              <KV name="vertical acceptance" value={live.vertical_acceptance ? 'YES' : 'NO'}/>
              <KV name="occupancy LOS" value={los.visible ? 'CLEAR' : (los.occluded ? 'OCCLUDED' : '—')}/>
              <KV name="legacy max-surface would block" value={los.legacy_max_surface_would_block ? 'YES' : 'NO'}/>
              <KV name="physical visibility" value={live.physical_visibility ? 'YES' : 'NO'}/>
              {blocker ? <div className="subtle" data-testid="vw6-blocker-interval">
                blocker cell=({blocker.cell_x},{blocker.cell_y}) interval=({num(blocker.interval?.z_min)}, {num(blocker.interval?.z_max)}] z_hit={num(blocker.z_hit)}
              </div> : <div className="subtle" data-testid="vw6-blocker-interval">blocker: NONE</div>}
              {receptor ? <div className="subtle" data-testid="vw6-phenotype-boundary">
                phenotype: visibility={receptor.visibility || '—'} detectable={receptor.detectable ? 'YES' : 'NO'} final={num(receptor.final_contribution)} fov={receptor.inside_fov ? 'IN' : 'OUT'}
              </div> : <div className="subtle" data-testid="vw6-phenotype-boundary">phenotype: (no matching neighbor row)</div>}
              <div className="subtle" data-testid="vw6-cognition-boundary">{live.cognition_abstraction || 'cognition: exo_*/surface_*/spatial_* only'}</div>
              <div className="subtle">researcher-only · XYZ + occupancy LOS · no cave/above/below semantics · no renderer · passive</div>
            </div>;
          })() : null}
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
            <KV name="LEFT effector Z" value={
              Number(out.effector_z_left) > 0 ? 'UP' : Number(out.effector_z_left) < 0 ? 'DOWN' : 'NONE'
            }/>
            <KV name="RIGHT effector Z" value={
              Number(out.effector_z_right) > 0 ? 'UP' : Number(out.effector_z_right) < 0 ? 'DOWN' : 'NONE'
            }/>
            <div className="subtle">{out.display || ''}</div>
            {mc.effector_relative_z ? (() => {
              const ez = mc.effector_relative_z;
              const L = ez.LEFT || {};
              const R = ez.RIGHT || {};
              return (
                <div style={{marginTop: 8}}>
                  <div className="section-label">EFFECTOR RELATIVE Z (researcher)</div>
                  <KV name="Available" value={ez.available ? 'YES' : 'NO'}/>
                  <KV name="LEFT selected" value={L.selected}/>
                  <KV name="LEFT relative_z" value={L.relative_z}/>
                  <KV name="LEFT requested Δ" value={L.requested_delta}/>
                  <KV name="LEFT realized Δ" value={L.realized_delta}/>
                  <KV name="LEFT work used" value={L.work_used}/>
                  <KV name="RIGHT selected" value={R.selected}/>
                  <KV name="RIGHT relative_z" value={R.relative_z}/>
                  <KV name="RIGHT requested Δ" value={R.requested_delta}/>
                  <KV name="RIGHT realized Δ" value={R.realized_delta}/>
                  <KV name="RIGHT work used" value={R.work_used}/>
                  <div className="subtle">{ez.note || 'Researcher diagnostics — not cognition.'}</div>
                </div>
              );
            })() : null}
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
        if (isNamedCanonicalUiPreset(v)) {
          setTwoAgentExperimental(true);
          setCognitionEnabled(true);
        }
      }}>
        {PUBLIC_MODEL_PRESETS.map(option => <option key={option}>{option}</option>)}
      </select></label>
      <button type="button" onClick={() => { void loadCanonicalPresetIntoDraft(preset); }} disabled>Load preset into draft</button>
      <label>Seed<input value={seed} onChange={e => setSeed(e.target.value)}/></label>
      <label>Width<input value={width} onChange={e => setWidth(e.target.value)}/></label>
      <label>Height<input value={height} onChange={e => setHeight(e.target.value)}/></label>
      <label>Boundary<select><option>WRAP_PERIODIC</option><option disabled>CLOSED — UNSUPPORTED</option><option disabled>OPEN — UNSUPPORTED</option></select></label>
      <label>Target tick<input value={targetTick} onChange={e => setTargetTick(e.target.value)} placeholder="∞"/></label>
      <label>Observer Hz<input value={uiHz} onChange={e => setUiHz(e.target.value)}/></label>
      <label>History frames<input value={bufferCapacity} onChange={e => setBufferCapacity(e.target.value)}/></label>
      <label>Body mass<input value={bodyMass} onChange={e => { setBodyMass(e.target.value); }}/></label>
      <label>Body v_max<input value={bodyVMax} onChange={e => { setBodyVMax(e.target.value); }}/></label>
      <label className="check"><input type="checkbox" checked={cognitionEnabled} onChange={e => { setCognitionEnabled(e.target.checked); }}/>Cognition enabled</label>
      <label className="check"><input type="checkbox" checked={twoAgentExperimental} onChange={e => { setTwoAgentExperimental(e.target.checked); }}/>Two-agent runtime (required for the recommended Beta 3 first run)</label>
      <div className="subtle" style={{ marginTop: 8, marginBottom: 8 }}>
        <strong>CANONICAL FIRST RUN:</strong> Choose Tiktaalik Beta 3.1 or Acanthostega Phase 0, edit any EXPERIMENT tabs, then APPLY EXPERIMENT.
      </div>
      <div style={{ marginTop: 8 }}>
      <div className="metric"><span>World ecology</span><strong>draft until APPLY EXPERIMENT</strong></div>
        <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_CLIMATE_DEFAULT' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_CLIMATE_DEFAULT'); }}
          >Baseline Climate</button>
          <button
            type="button"
            className={ecologyPreset === 'CURRENT_LEGACY' ? 'active' : ''}
            onClick={() => { setEcologyPreset('CURRENT_LEGACY'); }}
          >Current Legacy</button>
          <button
            type="button"
            className={ecologyPreset === 'GENTLE_FREE_MOVEMENT' ? 'active' : ''}
            onClick={() => { setEcologyPreset('GENTLE_FREE_MOVEMENT'); }}
          >Gentle / Free Movement</button>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_A_STATIC_PATCHES' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_A_STATIC_PATCHES'); }}
          >Static Patches</button>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_B_MIGRATING_RESOURCES' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_B_MIGRATING_RESOURCES'); }}
          >Migrating</button>
          <button
            type="button"
            className={ecologyPreset === 'BASELINE_C_CHANGING_LANDSCAPE' ? 'active' : ''}
            onClick={() => { setEcologyPreset('BASELINE_C_CHANGING_LANDSCAPE'); }}
          >Changing</button>
          <button
            type="button"
            className={ecologyPreset === 'STRUCTURED_TERRAIN_EXPERIMENTAL' ? 'active' : ''}
            onClick={() => { setEcologyPreset('STRUCTURED_TERRAIN_EXPERIMENTAL'); }}
            title="Experimental: calibrated climate + spatial POTENTIAL/DRAG. Observer ground truth only."
          >Structured Terrain</button>
          <button
            type="button"
            className={ecologyPreset === 'STRUCTURED_WORLD_EXPERIMENTAL' ? 'active' : ''}
            onClick={() => { setEcologyPreset('STRUCTURED_WORLD_EXPERIMENTAL'); }}
            title="Experimental: Structured Terrain + weak static ambient horizontal force. Observer GT only."
          >Structured World</button>
          <button
            className={ecologyPreset === 'CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL' ? 'active' : ''}
            onClick={() => { setEcologyPreset('CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL'); }}
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
      <div className="subtle">Shared experiment draft. Use Experiment → Review / Apply to apply configuration and start a new run at tick 0.</div>
    </Card>
    <Card title="Current experiment">
      <KV name="Runtime" value={experiment.runtime?.type}/>
      <KV name="Agent count" value={experiment.runtime?.agent_count}/>
      <KV name="Selected observer agent" value={experiment.runtime?.selected_agent}/>
      <KV name="Cognition" value={experiment.runtime?.cognition_enabled ? 'ON' : 'OFF'}/>
      <KV name="PE Cold History Eviction" value={experiment.pe_cold_history_eviction?.label || (experiment.runtime?.pe_cold_history_eviction ? 'ON' : 'OFF')}/>
      <KV name="Ecology preset" value={experiment.ecology_preset || experiment.runtime?.ecology_preset || header.ecology_preset || 'BASELINE_CLIMATE_DEFAULT'}/>
      <KV name="Seed" value={experiment.seed}/>
      <KV name="Observer Hz" value={experiment.observer?.ui_hz}/>
      <KV name="History frames" value={experiment.observer?.buffer_capacity}/>
      <KV name="Body mass" value={experiment.agent_body?.mass}/>
      <KV name="Body v_max" value={experiment.agent_body?.v_max}/>
      {experiment.applied_configuration && (
        <>
          <div className="section-label">APPLIED CONFIGURATION</div>
          <KV name="CONFIGURED fingerprint" value={experiment.applied_configuration.configured?.fingerprint}/>
          <KV name="REQUESTED fingerprint" value={experiment.applied_configuration.requested?.fingerprint}/>
          <KV name="RUNTIME fingerprint" value={experiment.applied_configuration.runtime?.fingerprint}/>
          <KV name="REQUESTED == RUNTIME" value={experiment.applied_configuration.match ? 'YES' : 'NO'}/>
          <div className="subtle">CONFIGURED = canonical draft · REQUESTED = last Apply snapshot · RUNTIME = constructed organism readback</div>
        </>
      )}
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
          notifyC1Restore();
          notifySav2Restore();
          setControlMessage(f.control_receipt);
        {
          const agent = desiredAgentIdRef.current || requestedAgentId(f);
          const projected = applyProjectionToFrame(f, agent);
          setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
          if (Array.isArray(f.mechanism_result?.mechanisms)) setMechanisms(f.mechanism_result.mechanisms);
          adoptRuntimeExperiment(f, f.mechanism_result?.mechanisms);
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
            analysisProgressDetail={analysisProgressDetail}
        analysisError={analysisError}
        analysisSource={analysisSource}
        onAnalysisSourceChange={handleAnalysisSourceChange}
        savedRuns={savedRunCatalog}
        selectedRunId={selectedSavedRunId}
        onSelectRunId={handleSelectSavedRunId}
        onRefreshRuns={refreshSavedRuns}
        onAnalyze={runExplicitAnalysis}
        onCancelAnalysis={() => { void cancelActiveAnalysis(); }}
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
        onCopyReport={() => { void copyAnalyzerReport(); }}
        onSaveMarkdown={() => { void saveAnalyzerMarkdown(); }}
        onSaveJson={() => { void saveAnalyzerJson(); }}
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
    seed, width, height, ecologyPreset, cognitionEnabled, peColdHistoryEviction, twoAgentExperimental,
    bodyMass, bodyVMax, targetTick, uiHz, bufferCapacity, terrainSeedOverride,
  };
  void editConfig;
  void configPending;
  const effWorld = experiment.observer_ground_truth?.effective_world;
  const overrideCount = Array.isArray(effWorld?.overrides) ? effWorld.overrides.length : 0;
  const undercoverIn = String(frame?.experimenter_interaction?.status || '') === 'CONTROL_ACTIVE';
  const agentsObs = frame.agents_observer || [];
  void agentsObs;

  const experimentMechanisms = overlayMechanismEnabled(mechanisms || [], mechanismDraft)
    .filter((m: any) => m?.model_line !== 'ACANTHOSTEGA' || modelLineFromUiPreset(preset) === 'ACANTHOSTEGA');
  const climateMechs = (experimentMechanisms || []).filter((m: any) =>
    String(m.id || '').includes('spatiotemporal_climate')
    || (String(m.id || m.label || '').toLowerCase().includes('climate')
      && !String(m.id || '').includes('resource_ecology')),
  );
  const resourceEcoMechs = (experimentMechanisms || []).filter((m: any) =>
    String(m.id || '').startsWith('resource_ecology_'),
  );
  const visionMechs = (experimentMechanisms || []).filter((m: any) =>
    m.id === 'physical_near_field_vision'
    || m.id === 'illumination_cycle'
    || m.id === 'physical_body_optical_response',
  );
  const otherAblatable = (experimentMechanisms || []).filter((m: any) =>
    m.ablatable && !climateMechs.includes(m) && !resourceEcoMechs.includes(m) && !visionMechs.includes(m),
  );
  const integrity = (frame as any)?.mechanism_integrity
    || (liveFrame as any)?.mechanism_integrity
    || null;
  const visionMech = (experimentMechanisms || []).find((m: any) => m.id === 'physical_near_field_vision');
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
  const configuredR = vRow?.configured_radius != null ? Number(vRow.configured_radius) : runtimeR;
  const visionEffective: VisionDraft = visionDraft || visionDraftFromPhysical(
    physical,
    Boolean(visionMech?.enabled),
    runtimeR,
  );
  const visionMismatch = Boolean(vRow?.status && vRow.status !== 'READY')
    || (configuredR !== runtimeR)
    || (visionEffective.radius !== runtimeR)
    || (Boolean(visionEffective.enabled) !== Boolean(visionMech?.enabled));

  function currentExperimentDraft(): ExperimentSnapshot {
    return snapshotFromEditors({
      seed,
      width,
      height,
      ecologyPreset,
      cognitionEnabled,
      peColdHistoryEviction,
      twoAgentExperimental,
      bodyMass,
      bodyVMax,
      publicPreset: publicPresetFromUi(preset),
      pscMotorResolution: pscMotorDraft || 'LOCO_FACTORIZED',
      pscOffTicks: pscOffTicksDraft,
      mechanisms: { ...mechanismMapFromCatalog(mechanisms || []), ...mechanismDraft },
      vision: visionEffective,
      terrainSeedOverride,
      targetTick,
      uiHz,
      bufferCapacity,
    });
  }

  function buildCompleteApplyPayload(opts?: { loadPreset?: boolean }) {
    const payload: any = buildCanonicalApplyPayload(currentExperimentDraft());
    if (opts?.loadPreset) payload.load_preset = true;
    return payload;
  }

  async function loadCanonicalPresetIntoDraft(v: string) {
    setPreset(v);
    if (isNamedCanonicalUiPreset(v)) {
      setTwoAgentExperimental(true);
      setCognitionEnabled(true);
    }
    const pub = publicPresetFromUi(v);
    if (!pub) {
      setCanonicalBaseline(null);
      return;
    }
    try {
      const j = await fetchCanonicalPreset(pub);
      const merged = mergeCanonicalIntoSnapshot(currentExperimentDraft(), (j.canonical || {}) as Record<string, any>);
      const fields = uiFieldsFromSnapshot(merged);
      setSeed(fields.seed);
      setWidth(fields.width);
      setHeight(fields.height);
      setEcologyPreset(fields.ecologyPreset);
      setCognitionEnabled(fields.cognitionEnabled);
      setPeColdHistoryEviction(fields.peColdHistoryEviction);
      setTwoAgentExperimental(fields.twoAgentExperimental);
      setBodyMass(fields.bodyMass);
      setBodyVMax(fields.bodyVMax);
      setTargetTick(fields.targetTick);
      setUiHz(fields.uiHz);
      setBufferCapacity(fields.bufferCapacity);
      setTerrainSeedOverride(fields.terrainSeedOverride);
      setMechanismDraft(merged.mechanisms || {});
      setVisionDraft(merged.vision);
      setPscMotorDraft(String(merged.psc_motor_resolution || 'LOCO_FACTORIZED'));
      setPscOffTicksDraft(merged.psc_off_ticks);
      setCanonicalBaseline(merged);
    } catch {
      /* selector still updates; canonical fetch is best-effort */
    }
  }

  function restoreModelDefaultsIntoDraft() {
    if (!canonicalBaseline) return;
    const fields = uiFieldsFromSnapshot(canonicalBaseline);
    setSeed(fields.seed);
    setWidth(fields.width);
    setHeight(fields.height);
    setEcologyPreset(fields.ecologyPreset);
    setCognitionEnabled(fields.cognitionEnabled);
    setPeColdHistoryEviction(fields.peColdHistoryEviction);
    setTwoAgentExperimental(fields.twoAgentExperimental);
    setBodyMass(fields.bodyMass);
    setBodyVMax(fields.bodyVMax);
    setTargetTick(fields.targetTick);
    setUiHz(fields.uiHz);
    setBufferCapacity(fields.bufferCapacity);
    setTerrainSeedOverride(fields.terrainSeedOverride);
    setMechanismDraft({ ...(canonicalBaseline.mechanisms || {}) });
    setVisionDraft(canonicalBaseline.vision);
    setPscMotorDraft(String(canonicalBaseline.psc_motor_resolution || 'LOCO_FACTORIZED'));
    setPscOffTicksDraft(canonicalBaseline.psc_off_ticks);
    const mapped = uiPresetFromPublic(canonicalBaseline.public_preset);
    if (mapped) setPreset(mapped);
    setApplyExperimentFailed(false);
  }

  function toggleExperimentMechanism(m: any, enabled?: boolean) {
    if (!m?.id) return;
    const next = typeof enabled === 'boolean' ? enabled : !m.enabled;
    setMechanismDraft((prev) => ({ ...prev, [m.id]: next }));
  }

  function discardPendingExperiment() {
    if (!activeExperiment) return;
    const fields = uiFieldsFromSnapshot(activeExperiment);
    setSeed(fields.seed);
    setWidth(fields.width);
    setHeight(fields.height);
    setEcologyPreset(fields.ecologyPreset);
    setCognitionEnabled(fields.cognitionEnabled);
    setPeColdHistoryEviction(fields.peColdHistoryEviction);
    setTwoAgentExperimental(fields.twoAgentExperimental);
    setBodyMass(fields.bodyMass);
    setBodyVMax(fields.bodyVMax);
    setTargetTick(fields.targetTick);
    setUiHz(fields.uiHz);
    setBufferCapacity(fields.bufferCapacity);
    setTerrainSeedOverride(fields.terrainSeedOverride);
    setMechanismDraft({ ...(activeExperiment.mechanisms || {}) });
    setVisionDraft(activeExperiment.vision);
    setPscMotorDraft(String(activeExperiment.psc_motor_resolution || 'LOCO_FACTORIZED'));
    setPscOffTicksDraft(activeExperiment.psc_off_ticks);
    const mapped = uiPresetFromPublic(activeExperiment.public_preset);
    if (mapped) setPreset(mapped);
    setApplyExperimentFailed(false);
  }

  const experimentDraftSnap = currentExperimentDraft();
  const draftPresetIsModified = draftPresetModified(experimentDraftSnap, canonicalBaseline);
  const experimentApplyStatus: ApplyStatus = applyStatusFor(
    experimentDraftSnap,
    activeExperiment,
    applyingExperiment,
    applyExperimentFailed,
  );
  const pending = experimentApplyStatus !== 'SAVED';
  void snapshotsEqual;
  void peColdHistoryEvictionApplied;

  function deviceBody(which: DeviceTool = deviceTool) {
    if (which === 'experiment') {
      const tabId = inspUi.tabs.EXPERIMENT || 'world';
      if (tabId === 'review') {
        const recipe = buildReviewRecipe(experimentDraftSnap, {
          baseline: canonicalBaseline,
          liveInterventionNote: 'Live PSC Auto-enable interventions are not included unless mirrored in draft psc_off_ticks',
        });
        const pscInitial = experimentDraftSnap.mechanisms?.prospective_scenario_competition ? 'ON' : 'OFF';
        return (
          <div className="device-form" data-testid="experiment-review-apply">
            <div className="section-gt subtle">SIMULATION RECIPE · SINGLE GLOBAL APPLY · STARTS NEW RUN AT TICK 0</div>
            {pending ? (
              <div className="pending-banner" data-testid="experiment-draft-hint">
                Changes saved to experiment draft — current run unchanged
              </div>
            ) : (
              <div className="subtle">Draft matches active applied configuration.</div>
            )}
            <div className="section-label">WORLD</div>
            <div className="metric"><span>Seed</span><strong>{seed || '—'}</strong></div>
            <div className="metric"><span>Size</span><strong>{width}×{height}</strong></div>
            <div className="metric"><span>Topology / boundary</span><strong>WRAP_PERIODIC</strong></div>
            <div className="metric"><span>Target tick</span><strong>{targetTick || '∞'}</strong></div>
            <div className="metric"><span>Observer Hz / buffer</span><strong>{uiHz} / {bufferCapacity}</strong></div>
            <div className="section-label">ECOLOGY</div>
            <div className="metric"><span>Selected preset</span><strong>{ecologyPreset}</strong></div>
            <div className="section-label">MODEL</div>
            <div className="metric"><span>Public model</span><strong>{preset}</strong></div>
            <div className="metric"><span>Agent count</span><strong>{twoAgentExperimental ? 2 : 1}</strong></div>
            <div className="metric"><span>Canonical-profile status</span><strong>{draftPresetIsModified ? 'OVERRIDDEN' : 'CANONICAL'}</strong></div>
            <div className="section-label">BODY</div>
            <div className="metric"><span>Mass</span><strong>{bodyMass}</strong></div>
            <div className="metric"><span>V_max</span><strong>{bodyVMax}</strong></div>
            <div className="section-label">PSC</div>
            <div className="metric"><span>Initial state</span><strong>{pscInitial}</strong></div>
            <div className="metric"><span>Auto-enable tick</span><strong>{pscOffTicksDraft == null ? 'MANUAL' : String(pscOffTicksDraft)}</strong></div>
            <div className="metric"><span>Motor resolution</span><strong>{pscMotorDraft || 'LOCO_FACTORIZED'}</strong></div>
            <div className="section-label">SIGNALING AND MECHANISMS</div>
            <div className="metric"><span>Experimental physical signal</span><strong>{experimentDraftSnap.mechanisms?.experimental_physical_signal ? 'ON' : 'OFF'}</strong></div>
            <div className="metric"><span>Physical oscillatory signaling</span><strong>{experimentDraftSnap.mechanisms?.oscillatory_signaling ? 'ON' : 'OFF'}</strong></div>
            <div className="metric"><span>Cognition enabled</span><strong>{cognitionEnabled ? 'ON' : 'OFF'}</strong></div>
            <div className="section-label">VISION</div>
            <div className="metric"><span>Enabled / range</span><strong>{visionEffective.enabled ? 'ON' : 'OFF'} / R{visionEffective.radius}</strong></div>
            <div className="metric"><span>Surface / optical / spatial</span><strong>{visionEffective.visual_surface_discrimination} / {visionEffective.optical_mapping} / {visionEffective.spatial_vision}</strong></div>
            <div className="section-label">APPLY CONSEQUENCE</div>
            <div className="subtle">Starts a new runtime at tick 0. Cancel preserves the active runtime and the draft.</div>
            <div className="metric"><span>Apply status</span><strong>{applyStatusLabel(experimentApplyStatus)}</strong></div>
            <div className="metric"><span>Current tick</span><strong>{statusStore.get().simTick ?? statusStore.get().tick ?? header.tick ?? '—'}</strong></div>
            <details className="phenomenon-category">
              <summary className="phenomenon-category-summary">
                <span className="phenomenon-category-title">Canonical defaults · overrides · live interventions</span>
              </summary>
              <pre className="phenomenon-pre" style={{ fontSize: 10 }}>{JSON.stringify(recipe, null, 2)}</pre>
            </details>
            {pending && appliedConfig && (
              <button type="button" data-testid="experiment-cancel-draft" onClick={discardPendingExperiment}>
                Cancel — keep current run and restore applied draft
              </button>
            )}
          </div>
        );
      }
      if (tabId === 'world') return (
        <div className="device-form">
          {pending && <div className="pending-banner">UNAPPLIED CHANGES — use Review / Apply (starts new run at tick 0)</div>}
          <div className="section-gt subtle">WORLD-STRUCTURAL · draft only until Review / Apply</div>
          <label className="setting-label-row">
            World Seed
            <SettingInfoHelp
              label="World Seed"
              brief="Deterministic experiment seed. Draft only until global Apply."
              detail={<p>Changing seed does not reset the active run until Review / Apply confirms a new run at tick 0.</p>}
              testId="info-world-seed"
            />
            <input value={seed} onChange={e => setSeed(e.target.value)}/>
          </label>
          <label className="setting-label-row">
            World Size (W×H)
            <SettingInfoHelp
              label="World Size"
              brief="Supported map dimensions for the next prepared run."
              detail={<p>Draft only. Apply rebuilds the world at tick 0.</p>}
              testId="info-world-size"
            />
            <span className="toolbar-row" style={{ gap: 6 }}>
              <input value={width} onChange={e => setWidth(e.target.value)} aria-label="Width"/>
              <input value={height} onChange={e => setHeight(e.target.value)} aria-label="Height"/>
            </span>
          </label>
          <label>Boundary<select disabled><option>WRAP_PERIODIC</option></select></label>
          <label>Target tick<input value={targetTick} onChange={e => setTargetTick(e.target.value)} placeholder="∞"/></label>
          <label>Observer Hz<input value={uiHz} onChange={e => setUiHz(e.target.value)}/></label>
          <label>History frames<input value={bufferCapacity} onChange={e => setBufferCapacity(e.target.value)}/></label>
          <div className="subtle">Terrain / ambient / illumination follow ecology preset. Map size &amp; seed apply with the shared experiment draft.</div>
          <div className="subtle">
            resource-* objects are DEVELOPMENT_FIXTURE entities (contact / transfer / work / ecology exercise).
            They are not canonical food, rewards, or goals. Replacement requires a new public-model fingerprint.
          </div>
          <button type="button" onClick={() => openFloat('effective_world')}>Open Effective World</button>
          <button type="button" onClick={() => openFloat('interventions')}>
            Interventions · {Number(frame?.world_intervention_summary?.n || frame?.world_interventions?.length || 0)}
          </button>
          {pending && appliedConfig && (
            <button type="button" onClick={discardPendingExperiment}>Discard pending</button>
          )}
        </div>
      );
      if (tabId === 'vision') {
        const visBase = canonicalBaseline?.vision;
        const visOverridden = Boolean(visBase) && (
          visBase!.radius !== visionEffective.radius
          || visBase!.spatial_vision !== visionEffective.spatial_vision
          || visBase!.visual_surface_discrimination !== visionEffective.visual_surface_discrimination
          || visBase!.optical_mapping !== visionEffective.optical_mapping
          || Boolean(visBase!.enabled) !== Boolean(visionEffective.enabled)
        );
        return (
          <div className="device-form" data-testid="experiment-vision-config">
            <div className="pending-banner" data-testid="experiment-draft-hint">
              Changes saved to experiment draft — current run unchanged
            </div>
            <div className="subtle">Organism vision configuration (Class C). Draft only — no local Apply; receptor FPV is a separate observation destination.</div>
            <div className="metric" data-testid="vision-canonical-status">
              <span>Profile status</span>
              <strong>{visOverridden ? 'OVERRIDDEN' : 'CANONICAL / DEFAULT'}</strong>
            </div>
            <VisionExperimenterControl
              deferred
              visionEnabled={Boolean(visionEffective.enabled)}
              runtimeRadius={visionEffective.radius}
              configuredRadius={runtimeR}
              mismatch={visionMismatch}
              visionMechanismPresent={!!visionMech}
              onToggleVision={visionMech ? () => toggleExperimentMechanism(visionMech, !visionEffective.enabled) : undefined}
              onSetRadius={(r) => setVisionDraft({ ...visionEffective, radius: r })}
              onSetSurfaceDiscrimination={(mode) => setVisionDraft({ ...visionEffective, visual_surface_discrimination: mode })}
              surfaceDiscrimination={visionEffective.visual_surface_discrimination}
              onSetOpticalMapping={(mode) => setVisionDraft({ ...visionEffective, optical_mapping: mode })}
              opticalMapping={visionEffective.optical_mapping}
              onSetSpatialVision={(mode) => setVisionDraft({ ...visionEffective, spatial_vision: mode })}
              spatialVision={visionEffective.spatial_vision}
            />
            <div className="metric">
              <span>FOV</span>
              <strong>{physical?.near_field_exteroception?.fov_deg != null ? `${physical.near_field_exteroception.fov_deg}°` : '—'}</strong>
            </div>
            <div className="subtle">FOV is applied-runtime readout (not an independent editor).</div>
          </div>
        );
      }
      if (tabId === 'model') return (
        <div className="device-form" data-testid="experiment-model-config">
          <label className="setting-label-row">
            Public model
            <SettingInfoHelp
              label="Public model"
              brief="Exactly two public models: Tiktaalik Beta 3.1 and Acanthostega Beta 4.0."
              detail={
                <p>
                  Explicit selection loads the complete canonical model profile into the shared draft only
                  (does not overwrite later experimental edits until Restore model defaults).
                  Acanthostega Beta 4.0: PSC initial OFF with auto-enable tick 1000, Observed Composite motor
                  resolution, experimental physical signal OFF, oscillatory signaling ON, vision R3/RICH/INDEPENDENT/OCCLUSION.
                </p>
              }
              testId="info-public-model"
            />
            <select value={preset} onChange={e => { void loadCanonicalPresetIntoDraft(e.target.value); }} data-testid="experiment-model-preset">
              {PUBLIC_MODEL_PRESETS.map(option => <option key={option}>{option}</option>)}
            </select>
          </label>
          <div className="metric" data-testid="experiment-preset-identity">
            <span>Base preset</span>
            <strong>{presetModifiedStatusLabel(preset, draftPresetIsModified)}</strong>
          </div>
          <div className="metric" data-testid="experiment-preset-status">
            <span>Status</span>
            <strong>{preset === UI_PRESET_CUSTOM ? 'CUSTOM' : (draftPresetIsModified ? 'OVERRIDDEN' : 'CANONICAL')}</strong>
          </div>
          <label className="check setting-label-row">
            <span className="setting-label-row">
              Agent Count
              <SettingInfoHelp
                label="Agent Count"
                brief="One- or two-agent runtime for the next prepared run."
                detail={<p>Draft only until Review / Apply. Does not change the active tick by itself.</p>}
                testId="info-agent-count"
              />
            </span>
            <input type="checkbox" checked={twoAgentExperimental} onChange={e => { setTwoAgentExperimental(e.target.checked); }}/>
            Two-agent runtime
          </label>
          <label className="check">
            <input type="checkbox" checked={cognitionEnabled} onChange={e => setCognitionEnabled(e.target.checked)} data-testid="experiment-cognition-enabled"/>
            Cognition enabled
          </label>
          <button type="button" data-testid="restore-model-defaults" disabled={!canonicalBaseline} onClick={restoreModelDefaultsIntoDraft}>
            Restore model defaults
          </button>
          <details className="phenomenon-category" data-testid="model-included-mechanisms">
            <summary className="phenomenon-category-summary">
              <span className="phenomenon-category-title">Included mechanisms</span>
              <span className="phenomenon-category-line subtle">Collapsed · read-only summary</span>
            </summary>
            <div className="subtle phenomenon-category-body">
              {(experimentMechanisms || []).slice(0, 48).map((m: any) => (
                <div key={m.id} className="metric">
                  <span>{m.label || m.id}</span>
                  <strong>{m.enabled ? 'ON' : 'OFF'}</strong>
                </div>
              ))}
            </div>
          </details>
          <details className="phenomenon-category" data-testid="model-phase-notes">
            <summary className="phenomenon-category-summary">
              <span className="phenomenon-category-title">Advanced material / Phase notes</span>
              <span className="phenomenon-category-line subtle">Collapsed · researcher reference</span>
            </summary>
            <div className="subtle phenomenon-category-body">
              Acanthostega Phase A/B material, grasp, traction, and surface-optical notes are researcher-only.
              Not agent-accessible recipes. Lifecycle is not implemented. Full historical prose remains in docs.
            </div>
          </details>
          <div className="metric"><span>Active public_preset</span><strong>{String(header?.public_preset || experiment.runtime?.public_preset || '—')}</strong></div>
          <div className="metric"><span>Active model_line</span><strong>{String(header?.model_line || '—')}</strong></div>
          <div className="metric" data-testid="experiment-locomotion-profile">
            <span>Physics profile</span>
            <strong>{String((header as any)?.locomotion_profile || 'TIKTAALIK')}</strong>
          </div>
          <div className="metric" data-testid="experiment-gentle-locomotion">
            <span>gentle_terrain_locomotion</span>
            <strong>{(header as any)?.gentle_terrain_locomotion ? 'ON' : 'OFF'}</strong>
          </div>
          <div className="metric"><span>Runtime</span><strong>{experiment.runtime?.type || '—'} · agents {experiment.runtime?.agent_count ?? '—'}</strong></div>
        </div>
      );
      if (tabId === 'ecology') return (
        <div className="device-form" data-testid="experiment-ecology-config">
          <div className="subtle">Ecology preset is draft-only until APPLY EXPERIMENT. Live runtime shown below for comparison.</div>
          <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
            {[
              ['BASELINE_CLIMATE_DEFAULT', 'Baseline Climate'],
              ['CURRENT_LEGACY', 'Basic World (Current Legacy)'],
              ['GENTLE_FREE_MOVEMENT', 'Gentle'],
              ['STRUCTURED_TERRAIN_EXPERIMENTAL', 'Structured Terrain'],
              ['STRUCTURED_WORLD_EXPERIMENTAL', 'Structured World'],
              ['CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL', 'Calibrated World'],
            ].map(([id, lab]) => (
              <button key={id} type="button" className={ecologyPreset === id ? 'active' : ''}
                onClick={() => { setEcologyPreset(id); }}>{lab}</button>
            ))}
          </div>
          {(ecologyPreset.includes('STRUCTURED') || ecologyPreset.includes('CALIBRATED')) && (
            <label>Terrain seed override<input value={terrainSeedOverride} onChange={e => setTerrainSeedOverride(e.target.value)} placeholder="default"/>
              <span className="na"> included in APPLY EXPERIMENT</span>
            </label>
          )}
          <div className="metric"><span>Active runtime preset</span><strong>{experiment.ecology_preset || header.ecology_preset || '—'}</strong></div>
          {overrideCount > 0 && <div className="flag overrides">Overrides: {overrideCount}</div>}
          <div className="section-label">Climate dynamics</div>
          <div className="subtle">Temporal thermal / insolation ecology (T_eq, seasonal cycle). Does not erase R_A/R_B. Draft until APPLY EXPERIMENT.</div>
          {climateMechs.map((m: any) => (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span>{m.label || m.id}</span>
              <button type="button" disabled={!m.ablatable} title={!m.ablatable ? 'NOT INDEPENDENTLY ABLATABLE' : 'Draft'} onClick={() => toggleExperimentMechanism(m)}>
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
              <button type="button" onClick={() => toggleExperimentMechanism(m)}>{m.enabled ? 'ON' : 'OFF'}</button>
            </div>
          ))}
          <div className="section-label">R_B ecology</div>
          <div className="subtle">Environmental production, persistence and regeneration of R_B.</div>
          {resourceEcoMechs.filter((m: any) => String(m.id).includes('_B')).map((m: any) => (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span>{m.label || m.id}</span>
              <button type="button" onClick={() => toggleExperimentMechanism(m)}>{m.enabled ? 'ON' : 'OFF'}</button>
            </div>
          ))}
          {!resourceEcoMechs.length && <div className="na">Resource ecology mechanism rows not in registry</div>}
        </div>
      );
      if (tabId === 'body') return (
        <div className="device-form section-gt">
          <div className="subtle">Body parameters edit the shared experiment draft. Resource GT below is the active runtime.</div>
          <label>Body mass<input value={bodyMass} onChange={e => { setBodyMass(e.target.value); }}/></label>
          <label>Body v_max<input value={bodyVMax} onChange={e => { setBodyVMax(e.target.value); }}/></label>
          <div className="subtle">WORLD GT — R_A / R_B (anonymous environmental quantities). Ecology gated independently via Ecology tab.</div>
          <KV name="R_A mean" value={effWorld?.resources_now?.R_A?.mean ?? experiment.observer_ground_truth?.resources?.R_A_mean}/>
          <KV name="R_A max" value={effWorld?.resources_now?.R_A?.max}/>
          <KV name="R_B mean" value={effWorld?.resources_now?.R_B?.mean ?? experiment.observer_ground_truth?.resources?.R_B_mean}/>
          <KV name="R_B max" value={effWorld?.resources_now?.R_B?.max}/>
          <button type="button" onClick={() => openFloat('effective_world')}>Effective World</button>
        </div>
      );
      if (tabId === 'psc') {
        const pscMech = (experimentMechanisms || []).find((m: any) => m.id === 'prospective_scenario_competition');
        const pscOn = Boolean(pscMech?.enabled);
        const runtimeSched = (
          experiment?.runtime?.psc_schedule
          || frame?.experiment?.runtime?.psc_schedule
          || null
        ) as any;
        const live = currentRuntimePresentation(runtimeSched);
        const nextRunSched = nextRunScheduleLabel(pscOffTicksDraft);
        const frozenInitial = experiment?.applied_configuration?.requested?.mechanisms?.prospective_scenario_competition;
        const frozenSchedule = experiment?.applied_configuration?.requested?.psc_off_ticks
          ?? experiment?.scientific_meta?.psc_off_ticks;
        return (
          <div className="device-form" data-testid="experiment-psc-config">
            <div className="panel" data-testid="psc-authority-strip" style={{ marginBottom: 10 }}>
              <div className="metric" data-testid="psc-current-run-summary">
                <span>CURRENT RUNTIME</span>
                <strong>Current run: {live.summary}</strong>
              </div>
              <div className="metric" data-testid="psc-next-run-summary">
                <span>NEXT RUN</span>
                <strong>Next run: {nextRunSched}</strong>
              </div>
              <div className="subtle">
                Current runtime is live overlay. Next-run draft does not change this run until Apply.
              </div>
            </div>

            <div className="section-label">CURRENT RUNTIME</div>
            <div className="panel" data-testid="psc-runtime-panel">
              <div className="metric">
                <span>PSC</span>
                <strong data-testid="psc-current-psc">{live.pscLabel === 'ON' ? 'PSC ON' : (live.pscLabel === 'OFF' ? 'PSC OFF' : 'unavailable')}</strong>
              </div>
              {live.unavailable ? (
                <div className="metric"><span>Schedule</span><strong>unavailable</strong></div>
              ) : (
                <>
                  {live.enabledAt != null ? (
                    <>
                      <div className="metric"><span>Enabled at tick</span><strong>{live.enabledAt}</strong></div>
                      <div className="metric"><span>Transition count</span><strong>{live.transitionCount ?? 'unavailable'}</strong></div>
                    </>
                  ) : (
                    <div className="metric"><span>Scheduled at tick</span><strong>{live.scheduleLabel}</strong></div>
                  )}
                  <div className="metric"><span>Armed</span><strong>{live.armedLabel}</strong></div>
                  {live.withholdLabel ? (
                    <div className="metric"><span>Withhold gate</span><strong>{live.withholdLabel}</strong></div>
                  ) : null}
                </>
              )}
            </div>

            <div className="section-label" style={{ marginTop: 12 }}>NEXT RUN</div>
            <div className="subtle" data-testid="psc-draft-panel">
              Draft for the next Apply. Not the active runtime schedule until applied.
            </div>
            <div className="metric">
              <span>Initial state</span>
              <strong data-testid="psc-next-run-initial">{nextRunInitialLabel(pscOn)}</strong>
            </div>
            {pscMech ? (
              <div className="metric" style={{ alignItems: 'center' }}>
                <span>{String(pscMech.label || pscMech.id || 'Prospective Scenario Competition')}</span>
                <button type="button" disabled={!pscMech.ablatable} onClick={() => toggleExperimentMechanism(pscMech)}>
                  {pscMech.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
            ) : (
              <div className="na">PSC mechanism not in registry snapshot</div>
            )}
            <div className="section-label">Auto-enable schedule (draft)</div>
            <SettingInfoHelp
              label="PSC Auto-enable Tick (draft)"
              brief="Schedule survives Apply even when initial PSC state is OFF."
              detail={
                <p>
                  Canonical Acanthostega Beta 4.0 uses tick 1000. MANUAL clears the schedule.
                  This edits the experiment draft — not a live intervention.
                </p>
              }
              testId="info-psc-draft-schedule"
            />
            <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {[['MANUAL', null], ['0', 0], ['1000', 1000], ['5000', 5000]].map(([lab, val]) => (
                <button
                  key={String(lab)}
                  type="button"
                  className={(val === null ? pscOffTicksDraft == null : pscOffTicksDraft === val) ? 'active' : ''}
                  onClick={() => setPscOffTicksDraft(val as number | null)}
                >
                  {String(lab)}
                </button>
              ))}
            </div>
            <div className="metric">
              <span>Auto-enable</span>
              <strong data-testid="psc-next-run-schedule">{pscOffTicksDraft == null ? 'MANUAL' : `Auto-enable tick ${pscOffTicksDraft}`}</strong>
            </div>
            <div className="section-label">Motor resolution</div>
            <PscMotorResolutionControl
              deferred
              mode={(pscMotorDraft === 'OBSERVED_COMPOSITE' ? 'OBSERVED_COMPOSITE' : 'LOCO_FACTORIZED')}
              onModeChange={(mode) => setPscMotorDraft(mode)}
              pscEnabled={pscOn}
              refreshKey={`${header?.tick ?? ''}-${header?.run_id ?? ''}-${String(pscOn)}-${pscMotorDraft || ''}`}
            />
            <div className="metric">
              <span>Motor resolution</span>
              <strong data-testid="psc-next-run-motor">{pscMotorDraft === 'OBSERVED_COMPOSITE' ? 'OBSERVED_COMPOSITE' : String(pscMotorDraft || '—')}</strong>
            </div>
            {pending ? <div className="subtle" data-testid="psc-unapplied">Unapplied changes</div> : null}

            <div className="section-label" style={{ marginTop: 12 }}>EXPERIMENTAL STATUS</div>
            <div className="panel" data-testid="psc-experimental-status">
              <div className="subtle">
                OBSERVED_COMPOSITE is experimental motor competition. This label is not current PSC ON/OFF.
              </div>
            </div>

            <details className="phenomenon-category" data-testid="psc-applied-configuration">
              <summary className="phenomenon-category-summary">
                <span className="phenomenon-category-title">APPLIED CONFIGURATION · initial / frozen</span>
              </summary>
              <div className="subtle">
                Apply-time initial values only. They do not override CURRENT RUNTIME.
              </div>
              <div className="metric">
                <span>Initial PSC at Apply</span>
                <strong>
                  {frozenInitial === undefined || frozenInitial === null
                    ? 'unavailable'
                    : (frozenInitial ? 'ON (initial)' : 'OFF (initial)')}
                </strong>
              </div>
              <div className="metric">
                <span>Initial auto-enable</span>
                <strong>{frozenSchedule == null ? 'unavailable' : `Tick ${String(frozenSchedule)} (frozen)`}</strong>
              </div>
            </details>

            <details className="phenomenon-category">
              <summary className="phenomenon-category-summary">
                <span className="phenomenon-category-title">Live intervention · Active run only</span>
              </summary>
              <PscOffTicksControl />
            </details>
          </div>
        );
      }
      if (tabId === 'ablations') {
        const smcMech = (experimentMechanisms || []).find((m: any) => m.id === 'sensorimotor_consequence_model');
        const hssMech = (experimentMechanisms || []).find((m: any) => m.id === 'historical_sensorimotor_selection_bridge');
        const cpoMech = (experimentMechanisms || []).find((m: any) => m.id === 'contextual_predictive_organization');
        const cgpMech = (experimentMechanisms || []).find((m: any) => m.id === 'context_grounded_prospection');
        const ppcMech = (experimentMechanisms || []).find((m: any) => m.id === 'persistent_prospective_control');
        const renderMech = (m: any) => {
          if (!m) return null;
          const baseOn = canonicalBaseline?.mechanisms?.[m.id];
          const departed = baseOn !== undefined && Boolean(baseOn) !== Boolean(m.enabled);
          return (
            <div key={m.id} className="metric" style={{ alignItems: 'center' }}>
              <span title={(m.description || '') + (mechanismHelp(m) ? (' — ' + mechanismHelp(m)) : '')}>
                {m.label || m.id}{departed ? ' · OVERRIDE' : ''}
              </span>
              <button type="button" disabled={!m.ablatable} onClick={() => toggleExperimentMechanism(m)}>
                {m.enabled ? 'ON' : 'OFF'}
              </button>
            </div>
          );
        };
        return (
          <div className="device-form" data-testid="experiment-ablations-config">
            <div className="subtle">
              Effective canonical mechanism profile with explicit experimental overrides.
              Draft only — never mutates the active run before global Apply.
            </div>
            <div className="metric"><span>Profile status</span><strong>{draftPresetIsModified ? 'OVERRIDDEN' : 'CANONICAL'}</strong></div>
            <button type="button" data-testid="ablations-restore-model-defaults" disabled={!canonicalBaseline} onClick={restoreModelDefaultsIntoDraft}>
              Reset to model defaults
            </button>
            <div className="section-label">Signaling</div>
            {(['experimental_physical_signal', 'oscillatory_signaling'] as const).map((id) => {
              const m = (experimentMechanisms || []).find((x: any) => x.id === id);
              return m ? renderMech(m) : null;
            })}
            <div className="section-label">Illumination / optical (from Perception)</div>
            {visionMechs.filter((m: any) => m.id !== 'physical_near_field_vision').map((m: any) => renderMech(m))}
            <div className="section-label">Predictive stack (from Predictive)</div>
            {[cpoMech, cgpMech, ppcMech, smcMech, hssMech].map((m) => renderMech(m))}
            <div className="section-label">PE Cold History Eviction</div>
            <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <button type="button" className={peColdHistoryEviction ? 'active' : ''} onClick={() => setPeColdHistoryEviction(true)}>ON</button>
              <button type="button" className={!peColdHistoryEviction ? 'active' : ''} onClick={() => setPeColdHistoryEviction(false)}>OFF</button>
            </div>
            <div className="section-label">Other ablatable mechanisms</div>
            {otherAblatable.slice(0, 40).map((m: any) => renderMech(m))}
            <div className="section-label">Flow channel ablations</div>
            <div className="na">Direct / wave thermal-body coupling — NOT independently available in runtime. No fake switches.</div>
            <button type="button" onClick={() => openFloat('effective_world')}>Effective World truth</button>
            <button type="button" onClick={() => openFloat('mechanisms')}>All mechanisms</button>
          </div>
        );
      }
    }
    if (which === 'intervention') return (
      <div className="device-form">
        <div className="metric"><span>UNDERCOVER</span><strong>{undercoverIn ? 'IN WORLD' : 'OUT'}</strong></div>
        <InteractPanel live={frame.experimenter_interaction} globalPressed={expKb.pressed} onRefresh={() => undefined} />
      </div>
    );
    if (which === 'observe') return null;
    if (which === 'sensors') {
      return (
      <div className="device-form section-agent">
        <MechanismPreflightPanel integrity={integrity} />
        <div className="subtle">Vision configuration: Experiment → Vision. This panel is diagnostic readout.</div>
        <div className="section-label">Agent-accessible channels</div>
        <VisionBars
          observation={agentObservation}
          visionEnabled={visionAuthorityOn}
          agentLabel={String(selectedAgentId || 'agent_0').toUpperCase()}
          spatialVision={String(physical?.near_field_exteroception?.spatial_vision || 'LEGACY').toUpperCase()}
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
          <div className="subtle">Live mutations only — APPLY EXPERIMENT starts a new generation and clears this list.</div>
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
    // Public complete models must rebuild from the preset builder (not merge into prior Tiktaalik draft).
    const payload = buildCompleteApplyPayload({
      loadPreset: isPublicModelSelectorEntry(preset) || isNamedCanonicalUiPreset(preset),
    });
    const tickNow = Number(statusStore.get().simTick ?? statusStore.get().tick ?? header.tick ?? 0);
    const runId = String(header.run_id || header.runtime_id || header.session_id || '—');
    if (Number.isFinite(tickNow) && tickNow > 0 && pending) {
      const changed = [
        'world/model/vision/mechanism draft differs from active config',
        `current tick ${tickNow}`,
        `run ${runId}`,
        'applying starts a NEW run at tick 0 and replaces live progress',
      ].join('\n');
      const ok = window.confirm(
        `Apply configuration and start a new run at tick 0?\n\n${changed}\n\nCancel preserves the current run exactly.`,
      );
      if (!ok) return;
    }
    const keptDraft = currentExperimentDraft();
    setApplyingExperiment(true);
    setApplyExperimentFailed(false);
    try {
      const f = await applyExperiment(payload);
      if (f.control_receipt && f.control_receipt.accepted === false) {
        setApplyExperimentFailed(true);
        setControlMessage(f.control_receipt);
        return;
      }
      let adoptFrame = f;
      if (!canonicalSourceFromApplyResponse(f)) {
        const exp = await fetch('/api/experiment').then((r) => r.json()).catch(() => ({}));
        const active = exp?.active_experiment && typeof exp.active_experiment === 'object'
          ? exp.active_experiment
          : null;
        if (active) adoptFrame = { ...f, active_experiment: active, experiment: { ...(f.experiment || {}), ...exp, active_experiment: active } };
      }
      resetGeoEmpiricalCache();
      setControlMessage(f.control_receipt);
      if (Array.isArray(adoptFrame.mechanism_result?.mechanisms)) {
        setMechanisms(adoptFrame.mechanism_result.mechanisms);
      }
      mechanismCatalogGenRef.current = null;
      adoptRuntimeExperiment(adoptFrame, adoptFrame.mechanism_result?.mechanisms);
      const agent = desiredAgentIdRef.current || requestedAgentId(f);
      const projected = applyProjectionToFrame(mergeGeoTransportIntoFrame(f), agent);
      setLiveFrame(projected); setViewFrame(projected); setMode('LIVE');
      await refreshAux().catch(() => undefined);
    } catch (err: any) {
      setApplyExperimentFailed(true);
      setControlMessage({
        operation: 'APPLY_EXPERIMENT',
        accepted: false,
        reason: String(err?.message || err),
      });
      void keptDraft;
    } finally {
      setApplyingExperiment(false);
    }
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

  void applyLiveFromDevice;

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

  return <div className={`desktop app ${layoutShellClassName(layoutShell)}`} data-observer-shell data-workspace={lab.workspace} data-testid="observer-app-shell">
    <ClockDriver />
    <InterestDriver />
    <TabVisibilityDriver />
    <DerivedViewportSubscriptionDriver mode={volumeWorkspace} />
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

    <div className="desktop-body observer-shell-body s7b-shell-body">
      <LeftSidebar
        open={leftOpen}
        onToggleOpen={() => setLeftOpen(!leftOpen)}
        active={observationDest}
        onActiveChange={setObservationDest}
        onDeviceTool={(t) => setDeviceTool(t)}
        pending={pending}
        selectedAgentLabel={String(selectedAgentId || 'agent_0').toUpperCase()}
      />
      <TiktaalikEyeDock
        frame={frame}
        executionMode={String(header.execution_mode || statusStore.get().executionMode || 'LIVE')}
        paused={String(header.status || statusStore.get().status || '').toUpperCase() === 'PAUSED'}
        runtimeGeneration={header.runtime_generation != null ? Number(header.runtime_generation) : statusStore.get().runtimeGeneration}
        selectedCell={selectedCell}
        centralOwnsSensory={
          observationDest === 'FPV_VISION' ? 'VISION'
            : observationDest === 'HEARING' ? 'HEARING'
              : null
        }
        agentCount={Number(frame.experiment?.runtime?.agent_count || frame.agents_observer?.length || 1)}
        selectedAgentId={String(selectedAgentId || 'agent_0')}
        onSelectAgent={(i) => { void selectObserverAgent(i); }}
        onOpenDetailedFpv={(i) => {
          void selectObserverAgent(i);
          setObservationDest('FPV_VISION');
        }}
        onOpenDetailedHearing={() => {
          setObservationDest('HEARING');
          const ui = inspectorUiStore.get();
          inspectorUiStore.set({
            ...ui,
            leftSensoryMode: 'HEARING',
            eyeDockMode: 'CLOSED',
          });
        }}
        onEditVisionConfig={() => {
          setObservationDest('MODEL');
        }}
      />
      <div className="shell-center-column">
      <main className="sim-workspace" ref={simWorkspaceRef}>
        {lab.workspace === 'ANALYZE' ? (
          <AnalyzeWorkspace
            analysis={runAnalysis}
            analyzing={analyzing}
            analysisProgress={analysisProgress}
            analysisProgressDetail={analysisProgressDetail}
            analysisError={analysisError}
            analysisSource={analysisSource}
            onAnalysisSourceChange={handleAnalysisSourceChange}
            savedRuns={savedRunCatalog}
            selectedRunId={selectedSavedRunId}
            onSelectRunId={handleSelectSavedRunId}
            onRefreshRuns={refreshSavedRuns}
            onAnalyze={runExplicitAnalysis}
            onAnalyzeCurrent={runAnalyzeCurrent}
            onCancelAnalysis={() => { void cancelActiveAnalysis(); }}
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
            onCopyReport={() => { void copyAnalyzerReport(); }}
            onSaveMarkdown={() => { void saveAnalyzerMarkdown(); }}
            onSaveJson={() => { void saveAnalyzerJson(); }}
            onInspectTick={(t) => { inspect(t); }}
            overview={overviewPanel}
          />
        ) : lab.workspace === 'INSPECT' ? (
          <InspectWorkspace
            prefs={worldPrefs}
            volumeWorkspace={
              observationDest === 'FPV_VISION'
              || observationDest === 'HEARING'
              || observationDest === 'ORGANISM'
              || observationDest === 'EVENTS'
              || observationDest === 'SIMULATION_INFO'
              || observationDest === 'SCIENTIFIC_TOOLS'
                ? 'MAP'
                : volumeWorkspace
            }
            onVolumeWorkspaceChange={setVolumeWorkspace}
            rightPanelOpen={layoutShell.rightOpen}
            onToggleRightPanel={() => layoutShellStore.patch({ rightOpen: !layoutShell.rightOpen })}
            mechanisms={mechanisms}
            onToggleMechanism={(id, enabled) => {
              const m = (mechanisms || []).find((x: any) => x.id === id);
              if (!m) return;
              const prep = lab.inspector === 'EXPERIMENT' || lab.inspector === 'MECHANISMS' || lab.inspector === 'PREDICTIVE';
              if (prep) {
                toggleExperimentMechanism(m, enabled);
                return;
              }
              void toggleMechanism(m, enabled);
            }}
            onSetVisionRadius={setVisionRadius}
            onSetSurfaceDiscrimination={setSurfaceDiscrimination}
            onSetOpticalMapping={setOpticalMapping}
            onSetSpatialVision={setSpatialVision}
            onSelectCell={inspectCell}
            expPressed={expKb.pressed}
            mapKey={mapKey}
            experimentMechanismDraft={mechanismDraft}
            observationDest={observationDest}
            observationCentral={
              observationDest === 'FPV_VISION' ? (
                <FpvObservationWorkspace
                  selectedAgentId={String(selectedAgentId || 'agent_0')}
                  agentCount={Number(frame.experiment?.runtime?.agent_count || frame.agents_observer?.length || 1)}
                  onSelectAgent={(i) => { void selectObserverAgent(i); }}
                />
              ) : observationDest === 'HEARING' ? (
                <HearingObservationWorkspace
                  frame={frame}
                  executionMode={String(header.execution_mode || statusStore.get().executionMode || 'LIVE')}
                  paused={String(header.status || statusStore.get().status || '').toUpperCase() === 'PAUSED'}
                  runtimeGeneration={header.runtime_generation != null ? Number(header.runtime_generation) : statusStore.get().runtimeGeneration}
                  selectedCell={selectedCell}
                />
              ) : observationDest === 'ORGANISM' ? (
                <OrganismCentralWorkspace
                  frame={frame}
                  selectedAgentId={String(selectedAgentId || 'agent_0')}
                  agentCount={Number(frame.experiment?.runtime?.agent_count || frame.agents_observer?.length || 1)}
                  onSelectAgent={(i) => { void selectObserverAgent(i); }}
                />
              ) : observationDest === 'EVENTS' ? (
                <EventsCentralWorkspace
                  events={events}
                  selectedEvent={selectedEvent}
                  onSelectEvent={(e) => {
                    setSelectedEvent(e);
                    const t = Number(e?._tick_end ?? e?.tick);
                    if (Number.isFinite(t)) inspect(t);
                  }}
                  selectedAgentId={String(selectedAgentId || 'agent_0')}
                  tick={header.tick ?? '—'}
                  generation={header.runtime_generation ?? '—'}
                />
              ) : observationDest === 'SIMULATION_INFO' ? (
                <SimulationInfoWorkspace
                  frame={frame}
                  status={statusStore.get()}
                  pendingDraft={!!pending}
                  selectedCell={selectedCell}
                />
              ) : observationDest === 'SCIENTIFIC_TOOLS' ? (
                <ScientificToolsLanding
                  onOpenTool={(tool) => {
                    const { dest, nextWorkspace } = applyRailDestination(tool, workspaceStore.get());
                    setDeviceTool(dest.deviceTool);
                    workspaceStore.set(nextWorkspace);
                  }}
                />
              ) : null
            }
            experimentApplyBar={(
              <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  type="button"
                  className="active"
                  data-testid="apply-experiment"
                  onClick={() => void applyFromDevice()}
                  disabled={!!finalizing || applyingExperiment}
                  title="APPLY_AND_RESET_WORLD — rebuilds runtime at tick 0"
                >
                  Apply configuration and start a new run at tick 0
                </button>
                <span className="subtle" data-testid="experiment-apply-status">
                  {applyStatusLabel(experimentApplyStatus)}
                </span>
                {pending ? (
                  <span className="flag pending" data-testid="experiment-draft-hint">
                    Changes saved to experiment draft — current run unchanged
                  </span>
                ) : null}
                {applyExperimentFailed && (
                  <span className="na">Draft kept · active runtime unchanged</span>
                )}
              </div>
            )}
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
                    spatialVision={String(physical?.near_field_exteroception?.spatial_vision || 'LEGACY').toUpperCase()}
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
            volumeWorkspace={volumeWorkspace}
            onVolumeWorkspaceChange={setVolumeWorkspace}
          />
        )}
      </main>
      {layoutShell.bottomOpen ? (
        <BottomEvidencePanel observationDest={observationDest} />
      ) : (
        <BottomDrawerAffordance />
      )}
      </div>
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
