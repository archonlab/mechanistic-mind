/** External stores — HOT frame updates do not go through App useState. */

export type SlimStatus = {
  connection: string;
  tick: number | null;
  simTick: number | null;
  displayTick: number | null;
  displayFrozen: boolean;
  status: string;
  executionMode: string;
  evidenceMode: string;
  simulationSpeed: number | null;
  simTps: number | null;
  observerHz: number | null;
  observerFps: number | null;
  lastArrival: number;
  heartbeat: any;
  pendingApply: any;
  selectedAgentId: string | null;
  undercoverIn: boolean;
  runtimeGeneration: number | null;
  modelName: string | null;
  evidenceLabel: string | null;
};

export type WorkspaceId = 'RUN' | 'INSPECT' | 'ANALYZE';
export type InspectorId =
  | 'EXPERIMENT'
  | 'INTERVENTION'
  | 'OBSERVE'
  | 'SENSORS'
  | 'SIGNALS'
  | 'RUNS'
  | 'WORLD_STATUS'
  | 'BODY'
  | 'COGNITION'
  | 'PREDICTIVE'
  | 'MECHANISMS'
  | 'EXPERIMENTER'
  | 'WORLD';

export type WorkspaceState = {
  workspace: WorkspaceId;
  inspector: InspectorId;
  inspectorOpen: boolean;
};

export type CameraFollow = 'FREE' | 'YOU' | 'TARGET';

export type FovOverlayState = {
  show: boolean;
  showCandidates: boolean;
  /** Missing agent id defaults to visible. */
  agents: Record<string, boolean>;
};

export type InspectorUiState = {
  tabs: Partial<Record<InspectorId, string>>;
  accordions: Record<string, boolean>;
  cameraFollow: CameraFollow;
  fovOverlay: FovOverlayState;
};

function createStore<T>(initial: T) {
  let state = initial;
  const listeners = new Set<() => void>();
  return {
    get(): T {
      return state;
    },
    set(next: T) {
      if (Object.is(state, next)) return;
      state = next;
      listeners.forEach((l) => l());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

export const EMPTY_STATUS: SlimStatus = {
  connection: 'CONNECTING',
  tick: null,
  simTick: null,
  displayTick: null,
  displayFrozen: false,
  status: 'UNKNOWN',
  executionMode: 'LIVE',
  evidenceMode: 'FULL_SCIENTIFIC',
  simulationSpeed: 1,
  simTps: null,
  observerHz: null,
  observerFps: null,
  lastArrival: 0,
  heartbeat: null,
  pendingApply: null,
  selectedAgentId: null,
  undercoverIn: false,
  runtimeGeneration: null,
  modelName: 'Tiktaalik',
  evidenceLabel: null,
};

export function slimStatusFromFrame(frame: any, extras: Partial<SlimStatus> = {}): SlimStatus {
  const header = frame?.header || {};
  const exp = frame?.experimenter_interaction || {};
  return {
    ...EMPTY_STATUS,
    ...extras,
    tick: header.tick ?? extras.tick ?? null,
    simTick: header.sim_tick ?? header.live_runtime_tick ?? header.tick ?? null,
    displayTick: header.display_tick ?? header.frame_tick ?? header.tick ?? null,
    displayFrozen: Boolean(header.display_frozen),
    status: String(header.status || extras.status || 'UNKNOWN'),
    executionMode: String(header.execution_mode || extras.executionMode || 'LIVE'),
    evidenceMode: String(header.evidence_mode || extras.evidenceMode || 'FULL_SCIENTIFIC'),
    simulationSpeed: header.simulation_speed ?? extras.simulationSpeed ?? 1,
    simTps: header.sim_ticks_per_sec ?? null,
    observerHz: header.observer_hz ?? null,
    observerFps: header.observer_fps ?? null,
    selectedAgentId: frame?.observer?.selected_agent_id || header.selected_agent_id || extras.selectedAgentId || null,
    undercoverIn: String(exp.status || '').toUpperCase() === 'IN_WORLD' || Boolean(exp.active && exp.in_world),
    runtimeGeneration: header.runtime_generation ?? null,
    modelName: header.model_display_name || extras.modelName || 'Tiktaalik',
    evidenceLabel: header.evidence_label || null,
  };
}

function statusEqual(a: SlimStatus, b: SlimStatus): boolean {
  return (
    a.connection === b.connection
    && a.tick === b.tick
    && a.simTick === b.simTick
    && a.displayTick === b.displayTick
    && a.displayFrozen === b.displayFrozen
    && a.status === b.status
    && a.executionMode === b.executionMode
    && a.evidenceMode === b.evidenceMode
    && a.simulationSpeed === b.simulationSpeed
    && a.simTps === b.simTps
    && a.observerHz === b.observerHz
    && a.observerFps === b.observerFps
    && a.lastArrival === b.lastArrival
    && a.pendingApply === b.pendingApply
    && a.selectedAgentId === b.selectedAgentId
    && a.undercoverIn === b.undercoverIn
    && a.runtimeGeneration === b.runtimeGeneration
    && a.heartbeat === b.heartbeat
  );
}

export const frameStore = (() => {
  let live: any = null;
  let view: any = null;
  const listeners = new Set<() => void>();
  const notify = () => listeners.forEach((l) => l());
  return {
    getLive: () => live,
    getView: () => view,
    getVisible: () => view || live,
    setLive(next: any) {
      live = next;
      notify();
    },
    setView(next: any) {
      view = next;
      notify();
    },
    publish(projected: any, mode: string) {
      live = projected;
      if (mode === 'LIVE') view = projected;
      notify();
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
})();

export const statusStore = (() => {
  const inner = createStore<SlimStatus>(EMPTY_STATUS);
  return {
    get: inner.get,
    subscribe: inner.subscribe,
    patch(partial: Partial<SlimStatus>) {
      const next = { ...inner.get(), ...partial };
      if (statusEqual(inner.get(), next)) return;
      inner.set(next);
    },
    replace(next: SlimStatus) {
      if (statusEqual(inner.get(), next)) return;
      inner.set(next);
    },
  };
})();

export const clockStore = createStore(0);

export const workspaceStore = createStore<WorkspaceState>({
  workspace: 'RUN',
  inspector: 'SENSORS',
  inspectorOpen: true,
});

export const inspectorUiStore = createStore<InspectorUiState>({
  tabs: {},
  accordions: {},
  cameraFollow: 'FREE',
  fovOverlay: { show: true, showCandidates: true, agents: {} },
});

export const cameraFollowStore = {
  get: () => inspectorUiStore.get().cameraFollow,
  set(mode: CameraFollow) {
    inspectorUiStore.set({ ...inspectorUiStore.get(), cameraFollow: mode });
  },
  subscribe: inspectorUiStore.subscribe,
};

export const lifecycleStore = createStore<{
  controlMessage: any;
  saveBanner: any;
  finalizing: string | null;
}>({
  controlMessage: null,
  saveBanner: null,
  finalizing: null,
});

/** Probe counters for isolation tests (presentation only). */
export const renderCounts: Record<string, number> = {
  App: 0,
  WorldPane: 0,
  ObserverHeader: 0,
  InspectorDock: 0,
  AnalyzeWorkspace: 0,
  ExperimentConfig: 0,
  RuntimeClock: 0,
};

export function noteRender(name: string) {
  renderCounts[name] = (renderCounts[name] || 0) + 1;
}

export function resetRenderCounts() {
  Object.keys(renderCounts).forEach((k) => {
    renderCounts[k] = 0;
  });
}
