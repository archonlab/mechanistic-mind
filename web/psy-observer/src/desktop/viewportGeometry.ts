/** Pure geometry helpers for OBSERVER_SIMULATION_VIEWPORT_01. */

/** Fit a square world into a rectangular simulation workspace (uniform scale). */
export function mapDisplayMetrics(
  workspaceWidth: number,
  workspaceHeight: number,
  worldW: number,
  worldH: number,
  padding = 8,
): {
  availableWidth: number;
  availableHeight: number;
  mapDisplaySize: number;
  cell: number;
  originX: number;
  originY: number;
  scaleFinite: boolean;
  positive: boolean;
} {
  const availableWidth = Math.max(0, workspaceWidth - 2 * padding);
  const availableHeight = Math.max(0, workspaceHeight - 2 * padding);
  const mapDisplaySize = Math.min(availableWidth, availableHeight);
  const gw = Math.max(1, worldW);
  const gh = Math.max(1, worldH);
  const cell = mapDisplaySize > 0 ? Math.min(availableWidth / gw, availableHeight / gh) : 0;
  const drawnW = gw * cell;
  const drawnH = gh * cell;
  const originX = padding + (availableWidth - drawnW) / 2;
  const originY = padding + (availableHeight - drawnH) / 2;
  return {
    availableWidth,
    availableHeight,
    mapDisplaySize,
    cell,
    originX,
    originY,
    scaleFinite: Number.isFinite(cell) && cell > 0,
    positive: availableWidth > 0 && availableHeight > 0 && mapDisplaySize > 0,
  };
}

/** Diagnose the blank-map failure mode from measured sizes. */
export function diagnoseViewport(sizes: {
  workspaceW: number;
  workspaceH: number;
  canvasParentW: number;
  canvasParentH: number;
  canvasCssW: number;
  canvasCssH: number;
}): { blank: boolean; reason: string; gates: Record<string, boolean> } {
  const gates = {
    V3_WORKSPACE_WIDTH_POSITIVE: sizes.workspaceW > 1,
    V4_WORKSPACE_HEIGHT_POSITIVE: sizes.workspaceH > 1,
    V5_MAP_DISPLAY_SIZE_POSITIVE: Math.min(sizes.canvasParentW, sizes.canvasParentH) > 1,
    V6_MAP_SCALE_FINITE: sizes.canvasParentW > 1 && sizes.canvasParentH > 1,
    V7_MAP_VISIBLE: sizes.canvasCssW > 1 && sizes.canvasCssH > 1,
  };
  const blank = !gates.V5_MAP_DISPLAY_SIZE_POSITIVE || !gates.V7_MAP_VISIBLE;
  let reason = 'ok';
  if (sizes.workspaceH <= 1) reason = 'simulation_workspace_height_zero';
  else if (sizes.canvasParentH <= 1) reason = 'canvas_parent_height_zero_absolute_collapse';
  else if (sizes.canvasCssH <= 1) reason = 'canvas_css_height_zero';
  return { blank, reason, gates };
}

/** Map must sit strictly to the right of the left dock (no cover). */
export function mapNotCoveredByDock(
  dockRight: number,
  mapLeft: number,
): boolean {
  return mapLeft >= dockRight - 0.5;
}
