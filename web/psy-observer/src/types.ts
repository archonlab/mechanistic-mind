export type Status = 'RUNNING' | 'PAUSED' | 'STOPPED';
export type ViewMode = 'LIVE' | 'INSPECT' | 'REPLAY';

export type TrajectoryPoint = { tick: number; x: number; y: number };

export type ObserverFrame = {
  observation?: {
    observation_frame_id: string;
    runtime_generation: number;
    captured_at: string;
    captured_monotonic: number;
    stale_after_seconds: number;
    ticks: Record<string, number>;
    tick_consistent: boolean;
    selected_agent_id?: string;
  };
  header: Record<string, any>;
  observer?: {
    selected_agent_id?: string;
    selected_body_id?: string;
    inspected_tick?: number;
    runtime_generation?: number;
    identity_tuple?: {
      runtime_generation?: number;
      inspected_tick?: number;
      selected_agent_id?: string;
    };
    agent_body_mapping?: Array<Record<string, any>>;
    note?: string;
  };
  world: Record<string, any>;
  body: Record<string, any>;
  perception: Record<string, any>;
  internal_physical: Record<string, any>;
  mind: Record<string, any>;
  causal_chain: Record<string, any>;
  physical?: Record<string, any>;
  model_banner?: Record<string, any>;
  cognition_pipeline?: Record<string, any>;
  prospection_view?: Record<string, any>;
  experimenter_interaction?: Record<string, any>;
  agents_observer?: any[];
  agents_views?: Record<string, any>;
  signal_forensics?: Record<string, any>;
  structured_events?: any[];
  world_interventions?: any[];
  motor_control?: Record<string, any>;
  scientific_history?: Record<string, any>;
  signal_context_interpretation?: Record<string, any>;
  experiment?: Record<string, any>;
  trajectory?: { points: TrajectoryPoint[]; capacity: number; boundary: string };
  telemetry?: { series: any[]; capacity: number };
  honesty?: Record<string, any>;
  overview_facts?: Record<string, any>;
  control_receipt?: Record<string, any>;
  historical_compatibility?: Record<string, any>;
  error?: string;
  reason?: string;
};

