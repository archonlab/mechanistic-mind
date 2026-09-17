/** Shared types for Psy Observer post-run / live analysis (observer-only). */

export type EvidenceClass =
  | 'OBSERVED'
  | 'DERIVED'
  | 'CAUSALLY_LINKED'
  | 'TEMPORALLY_ASSOCIATED'
  | 'NOT_AVAILABLE';

export type AnalysisMode = 'LIVE' | 'FINAL';

export type AnalysisLifecyclePhase = 'INSUFFICIENT_DATA' | 'LIVE' | 'PAUSED' | 'COMPLETE';

export type CoverageLevel = 'INSUFFICIENT' | 'LIVE' | 'INCREMENTAL' | 'PARTIAL' | 'COMPLETE';

export type AnalysisLifecycle = {
  phase: AnalysisLifecyclePhase;
  /** e.g. ANALYSIS: LIVE */
  banner: string;
  analyzed_start: number | null;
  analyzed_end: number | null;
  live_runtime_tick: number | null;
  agents: number;
  events_observed: number;
  frames_sampled: number;
  coverage: CoverageLevel;
  coverage_reason: string;
  insufficient: boolean;
};

export type AgentId = string;

export type NaMetric<T = number> = T | 'NOT AVAILABLE';

export type RunIdentity = {
  runtime: string;
  seed: number | null;
  generation: number | null;
  map_width: number | null;
  map_height: number | null;
  boundary: string;
  start_tick: number;
  end_tick: number;
  duration_ticks: number;
  agent_count: number;
  agents: Array<{
    agent_id: string;
    body_id: string;
    seed: number | null;
  }>;
  cognition_enabled: boolean | 'NOT AVAILABLE';
  experimental_overrides: Record<string, any>;
  active_mechanisms: string[];
  status: string;
  analysis_mode: AnalysisMode;
};

export type AgentAnalysis = {
  agent_id: string;
  seed: NaMetric;
  body_id: string;
  ticks_observed: number;
  actions: {
    wait_count: NaMetric;
    wait_pct: NaMetric;
    move_count: NaMetric;
    move_pct: NaMetric;
    move_distribution: Record<string, number> | 'NOT AVAILABLE';
    action_transitions: Record<string, number> | 'NOT AVAILABLE';
    longest_wait_streak: NaMetric;
    longest_move_streak: NaMetric;
  };
  movement: {
    distance_travelled: NaMetric;
    net_displacement: NaMetric;
    mean_speed: NaMetric;
    max_speed: NaMetric;
    rotation_accumulated: NaMetric;
    unique_cells: NaMetric;
  };
  body: {
    deformation_events: NaMetric;
    work_requested: NaMetric;
    work_realized: NaMetric;
    work_limited_events: NaMetric;
  };
  resources: {
    resource_A: { start: NaMetric; end: NaMetric; min: NaMetric; max: NaMetric };
    resource_B: { start: NaMetric; end: NaMetric; min: NaMetric; max: NaMetric };
    work_reservoir: { start: NaMetric; end: NaMetric; min: NaMetric; max: NaMetric };
    limiting_events: NaMetric;
    conversion_events: NaMetric;
  };
  cognition: {
    prediction_count: NaMetric;
    prediction_error: NaMetric;
    prospective_compositions: NaMetric;
    novel_compositions: NaMetric;
    retrieval_events: NaMetric;
    scenario_competitions: NaMetric;
    scenario_selected: NaMetric;
    scenario_selected_wait: NaMetric;
    scenario_selected_move: NaMetric;
    cognitive_wait_selections: NaMetric;
    fallback_wait_selections: NaMetric;
    conflicts: NaMetric;
    revisions: NaMetric;
    selected_action_sources: Record<string, number> | 'NOT AVAILABLE';
  };
  signals: {
    emissions_A: number;
    emissions_B: number;
    receptions_A: number;
    receptions_B: number;
    contact_triggered_emissions: number;
    motion_triggered_emissions: number;
    reception_attribution: { mixed: number; not_unique: number; unknown: number };
  };
  interaction: {
    body_body_contacts: NaMetric;
    cross_agent_signal_contributions: number;
  };
};

export type ImportantEvent = {
  tick: number;
  category: 'FIRST' | 'EXTREMA' | 'TRANSITION' | 'ANOMALY';
  kind: string;
  title: string;
  reason: string;
  evidence_class: EvidenceClass;
  agent_ids?: string[];
  body_ids?: string[];
  event_ids?: string[];
  emission_ids?: string[];
  refs?: Record<string, any>;
};

export type InteractionSummary = {
  first_contact_tick: number | null;
  contact_ticks: number;
  contact_episodes: Array<{ start: number; end: number; ticks: number }>;
  contact_triggered_emissions: number;
  cross_agent_contributions: number;
  causal_snippets: Array<{
    tick: number;
    steps: string[];
    evidence_class: EvidenceClass;
  }>;
  notes: string[];
};

export type CausalChain = {
  id: string;
  tick: number;
  edges: Array<{
    from: string;
    to: string;
    link: 'DIRECT_CAUSAL_LINK' | 'TEMPORAL_ASSOCIATION' | 'NOT_ESTABLISHED';
    reason: string;
  }>;
  nodes: string[];
};

export type Phase = {
  start: number;
  end: number;
  name: string;
  reason: string;
};

export type OverviewCard = {
  id: string;
  kind: 'KEY' | 'EPISODE' | 'PHASE' | 'QUIET';
  tick_start: number;
  tick_end: number;
  title: string;
  body: string;
  category: string;
  agent_filter: string[];
  evidence_class: EvidenceClass;
  evidence: {
    tick: number;
    event_ids?: string[];
    agent_ids?: string[];
    body_ids?: string[];
    emission_ids?: string[];
    frame_tick?: number;
  };
  keyframe?: KeyFrameRef | null;
};

export type KeyFrameRef = {
  tick: number;
  reason: string;
  agents: Array<{ agent_id: string; x: number; y: number }>;
  contact: boolean;
  world_w: number | null;
  world_h: number | null;
};

export type DataCoverage = {
  world: string;
  body: string;
  cognition: string;
  signals: string;
  causal_provenance: string;
  timeline_samples: number;
  event_samples: number;
  telemetry_samples: number;
  level: CoverageLevel;
  reason: string;
};

export type RunAnalysis = {
  identity: RunIdentity;
  lifecycle: AnalysisLifecycle;
  agents: AgentAnalysis[];
  comparison: {
    rows: Array<{ metric: string; agent_0: any; agent_1: any }>;
    divergences: string[];
  } | null;
  interactions: InteractionSummary;
  important_events: ImportantEvent[];
  causal_chains: CausalChain[];
  phases: Phase[];
  overview: OverviewCard[];
  keyframes: KeyFrameRef[];
  coverage: DataCoverage;
  analysis_log: string;
  generated_at_tick: number;
};

/** Compact archived observer run (not scientific snapshot). */
export type ObserverRunRecord = {
  run_id: string;
  run_number: number;
  runtime_generation: number | null;
  runtime_type: string;
  base_seed: number | null;
  started_at: string;
  finished_at: string | null;
  initial_tick: number;
  final_tick: number;
  map: { width: number | null; height: number | null; boundary: string };
  agents: Array<{ agent_id: string; body_id: string; seed: number | null }>;
  config_fingerprint: string;
  experimental: boolean;
  status: 'RUNNING' | 'PAUSED' | 'COMPLETE' | 'STOPPED';
  summary: {
    first_contact_tick: number | null;
    signals_observed: number;
    cross_agent_contributions: number;
    important_events: number;
    anomalies: number;
    contact_ticks: number;
  };
  thumbnail: KeyFrameRef | null;
  analysis: RunAnalysis;
};
