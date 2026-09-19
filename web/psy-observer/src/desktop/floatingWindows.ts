/** Pure helpers for floating window geometry / z-order (testable). */
import type { FloatingWindowId, FloatingWindowState } from './types';

const DEFAULTS: Record<FloatingWindowId, { title: string; w: number; h: number }> = {
  analysis: { title: 'Analysis', w: 520, h: 440 },
  sensor_inspector: { title: 'Sensor Inspector', w: 400, h: 420 },
  signal_forensics: { title: 'Signal Forensics', w: 440, h: 400 },
  effective_world: { title: 'Effective World', w: 380, h: 420 },
  mechanisms: { title: 'Mechanisms', w: 420, h: 400 },
  geometry: { title: 'Geometry', w: 360, h: 360 },
  agent_details: { title: 'Agent Details', w: 420, h: 440 },
  run_details: { title: 'Run Details', w: 400, h: 360 },
  observe_overlays: { title: 'Overlays', w: 340, h: 480 },
  observe_inspector: { title: 'Cell / Body Inspector', w: 360, h: 480 },
  interventions: { title: 'Live Interventions', w: 400, h: 360 },
  raw: { title: 'Advanced / Raw', w: 480, h: 400 },
};

export function nextZ(windows: FloatingWindowState[]): number {
  if (!windows.length) return 1;
  return Math.max(...windows.map((w) => w.z)) + 1;
}

export function clampWindow(
  win: FloatingWindowState,
  bounds: { width: number; height: number },
): FloatingWindowState {
  const margin = 8;
  const minVisible = 48;
  const maxX = Math.max(margin, bounds.width - minVisible);
  const maxY = Math.max(margin, bounds.height - minVisible);
  const x = Math.min(Math.max(win.x, -win.w + minVisible), maxX);
  const y = Math.min(Math.max(win.y, 0), maxY);
  const w = Math.min(Math.max(win.w, 240), Math.max(240, bounds.width - margin));
  const h = Math.min(Math.max(win.h, 160), Math.max(160, bounds.height - margin));
  return { ...win, x, y, w, h };
}

export function openOrFocusWindow(
  windows: FloatingWindowState[],
  id: FloatingWindowId,
  bounds: { width: number; height: number },
  cascadeIndex = 0,
): FloatingWindowState[] {
  const existing = windows.find((w) => w.id === id);
  if (existing) {
    return windows.map((w) => (w.id === id ? { ...w, z: nextZ(windows) } : w));
  }
  const d = DEFAULTS[id];
  const offset = 24 * (cascadeIndex % 6);
  const draft: FloatingWindowState = {
    id,
    title: d.title,
    x: 24 + offset,
    y: 24 + offset,
    w: d.w,
    h: d.h,
    z: nextZ(windows),
  };
  return [...windows, clampWindow(draft, bounds)];
}

export function closeWindow(windows: FloatingWindowState[], id: FloatingWindowId): FloatingWindowState[] {
  return windows.filter((w) => w.id !== id);
}

export function focusWindow(windows: FloatingWindowState[], id: FloatingWindowId): FloatingWindowState[] {
  const z = nextZ(windows);
  return windows.map((w) => (w.id === id ? { ...w, z } : w));
}

export function moveWindow(
  windows: FloatingWindowState[],
  id: FloatingWindowId,
  x: number,
  y: number,
  bounds: { width: number; height: number },
): FloatingWindowState[] {
  return windows.map((w) => (w.id === id ? clampWindow({ ...w, x, y }, bounds) : w));
}

export function resizeWindow(
  windows: FloatingWindowState[],
  id: FloatingWindowId,
  w: number,
  h: number,
  bounds: { width: number; height: number },
): FloatingWindowState[] {
  return windows.map((win) => (win.id === id ? clampWindow({ ...win, w, h }, bounds) : win));
}

export function toggleMaximize(
  windows: FloatingWindowState[],
  id: FloatingWindowId,
  bounds: { width: number; height: number },
): FloatingWindowState[] {
  return windows.map((win) => {
    if (win.id !== id) return win;
    if (win.maximized) {
      const r = win.savedRect || { x: 24, y: 24, w: DEFAULTS[id].w, h: DEFAULTS[id].h };
      return clampWindow({ ...win, ...r, maximized: false, savedRect: undefined }, bounds);
    }
    return {
      ...win,
      maximized: true,
      savedRect: { x: win.x, y: win.y, w: win.w, h: win.h },
      x: 8,
      y: 8,
      w: Math.max(240, bounds.width - 16),
      h: Math.max(160, bounds.height - 16),
    };
  });
}

export function resetWindowPosition(
  windows: FloatingWindowState[],
  id: FloatingWindowId,
  bounds: { width: number; height: number },
): FloatingWindowState[] {
  const d = DEFAULTS[id];
  return windows.map((win) =>
    win.id === id
      ? clampWindow({ ...win, x: 24, y: 24, w: d.w, h: d.h, maximized: false, savedRect: undefined }, bounds)
      : win,
  );
}

/** Simulation workspace center X relative to application (for docs/tests). */
export function simulationCenterX(appWidth: number, leftWorkspaceWidth: number): number {
  const avail = Math.max(0, appWidth - leftWorkspaceWidth);
  return leftWorkspaceWidth + avail / 2;
}

export function configPending(edit: Record<string, string | boolean | number>, applied: Record<string, string | boolean | number> | null): boolean {
  if (!applied) return false;
  for (const k of Object.keys(edit)) {
    if (String(edit[k]) !== String(applied[k])) return true;
  }
  return false;
}
