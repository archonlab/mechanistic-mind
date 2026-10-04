/** Researcher-local collapsible layout shell — never world/scientific state. */

export type LayoutShellState = {
  leftOpen: boolean;
  rightOpen: boolean;
  bottomOpen: boolean;
};

export const LAYOUT_SHELL_STORAGE_KEY = 'mm.observer.layoutShell.v1';
export const LAYOUT_SHELL_SCHEMA = 'OBSERVER_LAYOUT_SHELL_UI_V1';

export const DEFAULT_LAYOUT_SHELL: LayoutShellState = {
  leftOpen: true,
  rightOpen: true,
  bottomOpen: true,
};

type Listener = () => void;

function loadInitial(): LayoutShellState {
  if (typeof localStorage === 'undefined') return { ...DEFAULT_LAYOUT_SHELL };
  try {
    const raw = localStorage.getItem(LAYOUT_SHELL_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_LAYOUT_SHELL };
    const parsed = JSON.parse(raw);
    return {
      leftOpen: parsed.leftOpen !== false,
      rightOpen: parsed.rightOpen !== false,
      bottomOpen: parsed.bottomOpen !== false,
    };
  } catch {
    return { ...DEFAULT_LAYOUT_SHELL };
  }
}

let state: LayoutShellState = loadInitial();
const listeners = new Set<Listener>();

function persist(next: LayoutShellState) {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(
      LAYOUT_SHELL_STORAGE_KEY,
      JSON.stringify({ schema: LAYOUT_SHELL_SCHEMA, ...next }),
    );
  } catch {
    /* ignore quota */
  }
}

export const layoutShellStore = {
  get(): LayoutShellState {
    return state;
  },
  set(next: LayoutShellState) {
    if (
      state.leftOpen === next.leftOpen
      && state.rightOpen === next.rightOpen
      && state.bottomOpen === next.bottomOpen
    ) {
      return;
    }
    state = { ...next };
    persist(state);
    listeners.forEach((l) => l());
  },
  patch(partial: Partial<LayoutShellState>) {
    layoutShellStore.set({ ...state, ...partial });
  },
  subscribe(listener: Listener) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

/** Observation destinations — presentation labels over existing authorities. */
export type ObservationDestination =
  | 'WORLD'
  | 'MODEL'
  | 'ORGANISM'
  | 'FPV_VISION'
  | 'HEARING'
  | 'EVENTS'
  | 'SIMULATION_INFO'
  | 'SCIENTIFIC_TOOLS';

export const OBSERVATION_DESTINATIONS: { id: ObservationDestination; label: string }[] = [
  { id: 'WORLD', label: 'World' },
  { id: 'MODEL', label: 'Model' },
  { id: 'ORGANISM', label: 'Organism' },
  { id: 'FPV_VISION', label: 'FPV Vision' },
  { id: 'HEARING', label: 'Hearing' },
  { id: 'EVENTS', label: 'Events' },
  { id: 'SIMULATION_INFO', label: 'Simulation Info' },
  { id: 'SCIENTIFIC_TOOLS', label: 'Scientific Tools' },
];

export function layoutShellClassName(s: LayoutShellState): string {
  return [
    'observer-app-shell',
    s.leftOpen ? 'shell-left-open' : 'shell-left-closed',
    s.rightOpen ? 'shell-right-open' : 'shell-right-closed',
    s.bottomOpen ? 'shell-bottom-open' : 'shell-bottom-closed',
  ].join(' ');
}

export function allPanelCombinations(): LayoutShellState[] {
  const out: LayoutShellState[] = [];
  for (const leftOpen of [true, false]) {
    for (const rightOpen of [true, false]) {
      for (const bottomOpen of [true, false]) {
        out.push({ leftOpen, rightOpen, bottomOpen });
      }
    }
  }
  return out;
}
