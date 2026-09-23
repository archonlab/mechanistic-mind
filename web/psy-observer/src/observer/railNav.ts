/** Map leftover ControlDevice rail icons onto the Inspector section model. */

import type { DeviceTool } from '../desktop/types';
import type { InspectorId, WorkspaceId, WorkspaceState } from './stores';

export type RailDestination = {
  workspace?: WorkspaceId;
  inspector?: InspectorId;
  inspectorOpen?: boolean;
  deviceTool: DeviceTool;
  deviceCollapsed: boolean;
};

const RAIL_INSPECTOR: Partial<Record<DeviceTool, InspectorId>> = {
  experiment: 'EXPERIMENT',
  intervention: 'INTERVENTION',
  observe: 'OBSERVE',
  sensors: 'SENSORS',
  signals: 'SIGNALS',
  runs: 'RUNS',
  world_status: 'WORLD_STATUS',
};

/** Every LEVEL-1 rail destination owns the full right Inspector (Analyze is its own workspace). */
export function railDestination(tool: DeviceTool): RailDestination {
  if (tool === 'analyze') {
    return { workspace: 'ANALYZE', deviceTool: tool, deviceCollapsed: true };
  }
  const inspector = RAIL_INSPECTOR[tool];
  if (inspector) {
    return {
      workspace: 'INSPECT',
      inspector,
      inspectorOpen: true,
      deviceTool: tool,
      deviceCollapsed: true,
    };
  }
  return { deviceTool: tool, deviceCollapsed: true };
}

export function applyRailDestination(
  tool: DeviceTool,
  current: WorkspaceState,
): { dest: RailDestination; nextWorkspace: WorkspaceState } {
  const dest = railDestination(tool);
  const nextWorkspace: WorkspaceState = {
    workspace: dest.workspace ?? current.workspace,
    inspector: dest.inspector ?? current.inspector,
    inspectorOpen: dest.inspectorOpen ?? (
      dest.workspace === 'INSPECT' ? true : current.inspectorOpen
    ),
  };
  return { dest, nextWorkspace };
}

const INSPECTOR_TO_RAIL: Partial<Record<InspectorId, DeviceTool>> = {
  EXPERIMENT: 'experiment',
  INTERVENTION: 'intervention',
  OBSERVE: 'observe',
  SENSORS: 'sensors',
  SIGNALS: 'signals',
  RUNS: 'runs',
  WORLD_STATUS: 'world_status',
  BODY: 'sensors',
  EXPERIMENTER: 'intervention',
  MECHANISMS: 'experiment',
  PREDICTIVE: 'experiment',
  COGNITION: 'observe',
  WORLD: 'world_status',
};

/** Truthful rail highlight: workspace/inspector win over leftover deviceTool. */
export function railSelectedTool(
  ws: WorkspaceState,
  deviceTool: DeviceTool,
  deviceCollapsed: boolean,
): DeviceTool | null {
  if (!deviceCollapsed && deviceTool !== 'home' && deviceTool !== 'analyze') return deviceTool;
  if (ws.workspace === 'ANALYZE') return 'analyze';
  if (ws.workspace === 'INSPECT') {
    return INSPECTOR_TO_RAIL[ws.inspector] || null;
  }
  return null;
}
