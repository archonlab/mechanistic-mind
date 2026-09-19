/** OBSERVER_DESKTOP_01 — shared types for control device + floating windows. */
export type DeviceTool =
  | 'home'
  | 'experiment'
  | 'intervention'
  | 'observe'
  | 'sensors'
  | 'signals'
  | 'analyze'
  | 'runs'
  | 'world_status';

export type ExperimentScreen =
  | 'menu'
  | 'set_world'
  | 'set_model'
  | 'set_ecology'
  | 'set_resources'
  | 'experimental';

export type FloatingWindowId =
  | 'analysis'
  | 'sensor_inspector'
  | 'signal_forensics'
  | 'effective_world'
  | 'mechanisms'
  | 'geometry'
  | 'agent_details'
  | 'run_details'
  | 'observe_overlays'
  | 'observe_inspector'
  | 'interventions'
  | 'raw';

export type FloatingWindowState = {
  id: FloatingWindowId;
  title: string;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  maximized?: boolean;
  savedRect?: { x: number; y: number; w: number; h: number };
};

export const HOME_TOOLS: { id: DeviceTool; label: string }[] = [
  { id: 'experiment', label: 'Experiment' },
  { id: 'intervention', label: 'Intervention' },
  { id: 'observe', label: 'Observe' },
  { id: 'sensors', label: 'Sensors' },
  { id: 'signals', label: 'Signals' },
  { id: 'analyze', label: 'Analyze Results' },
  { id: 'runs', label: 'Runs' },
  { id: 'world_status', label: 'World Status' },
];

export const EXPERIMENT_MENU: { id: ExperimentScreen; label: string }[] = [
  { id: 'set_world', label: 'Set World' },
  { id: 'set_model', label: 'Set Model' },
  { id: 'set_ecology', label: 'Set Ecology' },
  { id: 'set_resources', label: 'Set Resources' },
  { id: 'experimental', label: 'Experimental' },
];
