import type { RunAnalysis } from './types.ts';
import { formatConfigurationHistoryLog } from './configurationHistory.ts';
import { formatVisualForensicsSection } from './visionForensics.ts';

function show(v: any): string {
  if (v == null) return 'NOT AVAILABLE';
  if (typeof v === 'number' && Number.isFinite(v)) {
    return Number.isInteger(v) ? String(v) : String(Math.round(v * 10000) / 10000);
  }
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

/** Clean plain-text analysis log for clipboard / download. */
export function formatAnalysisLog(analysis: RunAnalysis): string {
  const id = analysis.identity;
  const lines: string[] = [];
  lines.push('MECHANISTIC MIND — RUN ANALYSIS');
  lines.push('================================');
  lines.push('');
  const meta = analysis.evidence_meta;
  if (meta) {
    lines.push('EVIDENCE / ANALYSIS METADATA');
    lines.push(`Analyzer version: ${meta.analyzer_version}`);
    lines.push(`Analysis timestamp: ${meta.analysis_timestamp}`);
    lines.push(`Run id: ${show(meta.run_id)}`);
    lines.push(`Source: ${show(meta.source)}`);
    lines.push(`Runtime status: ${show(meta.runtime_status)}`);
    lines.push(`Analysis cutoff tick: ${show(meta.analysis_cutoff_tick)}`);
    lines.push(`Scientific tick range analyzed: ${meta.scientific_tick_range[0]}–${meta.scientific_tick_range[1]}`);
    lines.push(`Coverage: ${meta.coverage}`);
    lines.push(`Complete tick-level re-analysis: ${meta.complete_tick_level_reanalysis ? 'YES' : 'NO'}`);
    lines.push(`Evidence files: ${(meta.evidence_files || []).join(', ') || 'NONE'}`);
    lines.push(`Evidence counts: ${JSON.stringify(meta.evidence_counts || {})}`);
    lines.push(`Used cumulative runtime summaries: ${meta.used_cumulative_runtime_summaries ? 'YES' : 'NO'}`);
    if (meta.used_cumulative_runtime_summaries && meta.cumulative_runtime_summaries?.length) {
      lines.push('CUMULATIVE RUNTIME SUMMARY (NOT tick-level history):');
      for (const row of meta.cumulative_runtime_summaries) {
        lines.push(`  ${row.agent_id}: action_counts=${JSON.stringify(row.action_counts || {})}`);
      }
      lines.push('  Note: cumulative counters do NOT reconstruct transition timing, streaks, or phase boundaries.');
    }
    if (meta.note) lines.push(`Note: ${meta.note}`);
    lines.push('');
  }
  lines.push('RUN');
  lines.push(`Runtime: ${id.runtime}`);
  lines.push(`Seed: ${show(id.seed)}`);
  lines.push(`Generation: ${show(id.generation)}`);
  lines.push(`Map: ${show(id.map_width)}×${show(id.map_height)} ${id.boundary}`);
  lines.push(`Ticks: ${id.start_tick}–${id.end_tick} (duration ${id.duration_ticks})`);
  lines.push(`Simulation ticks analyzed (unique): ${analysis.coverage.unique_simulation_ticks}`);
  lines.push(`Observer timeline samples ingested: ${analysis.coverage.timeline_samples}`);
  lines.push(`Agent count: ${id.agent_count}`);
  lines.push(`Cognition enabled: ${show(id.cognition_enabled)}`);
  lines.push(`Status: ${id.status}`);
  lines.push(`Analysis mode: ${id.analysis_mode}`);
  lines.push(`Active mechanisms: ${id.active_mechanisms.join(', ') || 'NONE / NOT AVAILABLE'}`);
  lines.push(`Experimental overrides: ${JSON.stringify(id.experimental_overrides || {})}`);
  lines.push('');

  if (analysis.configuration_history) {
    lines.push(...formatConfigurationHistoryLog(analysis.configuration_history));
    lines.push('');
  }

  for (const a of analysis.agents) {
    lines.push(a.agent_id.toUpperCase());
    lines.push(`  Seed: ${show(a.seed)}  Body: ${a.body_id}  Ticks observed (canonical action ticks): ${a.ticks_observed}`);
    const cm = (analysis as any).composite_motor;
    if (cm?.authoritative) {
      const ag = cm.agents?.[a.agent_id];
      lines.push(`  COMPOSITE MOTOR FORENSICS (authoritative; schema=${cm.schema}):`);
      if (ag) {
        lines.push(`    locomotion ticks: ${ag.locomotion_ticks}  neck-control: ${ag.neck_control_ticks}  osc-control: ${ag.oscillator_control_ticks}`);
        lines.push(`    emission triggers: ${ag.emission_trigger_ticks}  emission active ticks: ${ag.control_vs_effector?.emission_active_ticks}`);
        lines.push(`    push ticks: ${ag.push_ticks}  WAIT/no-intervention: ${ag.wait_no_intervention_ticks}`);
        lines.push(`    combinations: ${JSON.stringify(ag.combinations)}`);
      }
      lines.push(`  LEGACY PROJECTION (canonical one-label occupancy — not authoritative under COMPOSITE_MOTOR_V1):`);
    }
    lines.push(`  TICK-LEVEL ACTION OCCUPANCY (one canonical action per simulation tick${cm?.authoritative ? ' — LEGACY PROJECTION' : ''}):`);
    lines.push(`    WAIT ticks: ${show(a.actions.wait_count)} (${show(a.actions.wait_pct)}%)  MOVE ticks: ${show(a.actions.move_count)} (${show(a.actions.move_pct)}%)`);
    lines.push(`    Occupancy total: ${a.actions.occupancy_total}  (must be ≤ ticks observed; OBSERVED-TICK STATISTIC)`);
    lines.push(`    MOVE distribution: ${show(a.actions.move_distribution)}`);
    const cov = (a.actions as any).sequence_coverage || (a.movement as any).sequence_coverage || '';
    lines.push(`    Longest observed contiguous WAIT streak: ${show(a.actions.longest_wait_streak)}  MOVE: ${show(a.actions.longest_move_streak)}`);
    lines.push(`    True longest WAIT streak: ${show((a.actions as any).true_longest_wait_streak)}  MOVE: ${show((a.actions as any).true_longest_move_streak)}${cov ? `  [${cov}]` : ''}`);
    lines.push(`    Transitions (ordered unique ticks): ${show(a.actions.action_transitions)}`);
    if (a.cumulative_runtime_action_counts !== 'NOT AVAILABLE') {
      lines.push(`  CUMULATIVE RUNTIME ACTION COUNTS (cognition metrics; not tick-level occupancy merge):`);
      lines.push(`    ${JSON.stringify(a.cumulative_runtime_action_counts)}`);
    }
    lines.push(`  STRUCTURED COGNITIVE EVENTS / LEGACY STRUCTURED EVENT COUNTS (compatibility; not authoritative under SCIENTIFIC_V3):`);
    lines.push(`    SCENARIO_SELECTED event rows: ${show(a.cognition.scenario_selected)} (WAIT ${show(a.cognition.scenario_selected_wait)} / MOVE ${show(a.cognition.scenario_selected_move)})`);
    {
      const v3 = (analysis as any).scientific_v3_core;
      const v3Dec = Number(v3?.decision_receipts || 0);
      if (v3 && v3.evidence_version === 'SCIENTIFIC_V3' && v3Dec > 0) {
        lines.push(`  SCIENTIFIC_V3 DECISION EVIDENCE (authoritative):`);
        lines.push(`    DecisionReceipts: ${v3Dec}`);
        lines.push(`    Coverage: ${show(v3.decision_coverage || 'COMPLETE')}`);
        lines.push(`    Note: SCENARIO_SELECTED=0 does NOT mean cognition/decision evidence is absent.`);
      }
    }
    lines.push(`    Cognitive WAIT selections: ${show(a.cognition.cognitive_wait_selections)}  Fallback WAIT: ${show(a.cognition.fallback_wait_selections)}`);
    lines.push(`    Action sources (tick-level when from timeline): ${show(a.cognition.selected_action_sources)}`);
    lines.push(`  MOVEMENT: distance(${show((a.movement as any).distance_metric)}) ${show(a.movement.distance_travelled)}  path_euclid ${show((a.movement as any).path_length_euclidean)}  net_wrap_observed ${show(a.movement.net_displacement)}  unwrapped_net ${show((a.movement as any).unwrapped_net_displacement)}  unwrappedΔ (${show((a.movement as any).unwrapped_dx)}, ${show((a.movement as any).unwrapped_dy)})  max_exc ${show((a.movement as any).max_excursion_from_start)}  mean_speed ${show(a.movement.mean_speed)}  max_speed ${show(a.movement.max_speed)}`);
    lines.push(`  TRAJECTORY: unique_pos_ticks ${show((a.movement as any).unique_position_ticks)}  dup_ignored ${show((a.movement as any).duplicate_observer_samples_ignored)}  gaps_skipped ${show((a.movement as any).trajectory_gaps_skipped)}  wraps x/y ${show((a.movement as any).boundary_crossings_x)}/${show((a.movement as any).boundary_crossings_y)}  cell_cross_com ${show((a.movement as any).cell_boundary_crossings)}  nbhd_repl ${show((a.movement as any).neighborhood_replacements)}`);
    lines.push(`  Physical during WAIT/MOVE: path ${show((a.movement as any).path_during_requested_WAIT)}/${show((a.movement as any).path_during_requested_MOVE)}  unwrapped_net ${show((a.movement as any).unwrapped_displacement_during_WAIT)}/${show((a.movement as any).unwrapped_displacement_during_MOVE)}`);
    const pvc = (a.movement as any).path_vs_velocity_consistency;
    if (pvc === 'INCONSISTENT' || pvc === 'FLAG') {
      lines.push(`  WARNING: trajectory metrics inconsistent with runtime speed (ratio ${show((a.movement as any).path_vs_velocity_ratio)})`);
    } else if (pvc === 'NOT_COMPARABLE_DUE_TO_COVERAGE') {
      lines.push(`  path_vs_velocity: NOT COMPARABLE DUE TO COVERAGE (sparse/partial LIVE sampling)`);
    } else {
      lines.push(`  path_vs_velocity: ${show(pvc)} ratio ${show((a.movement as any).path_vs_velocity_ratio)}`);
    }
    lines.push(`  Unique cells (observed trajectory): ${show(a.movement.unique_cells)}  current_cell ${show((a.movement as any).current_cell)}  Rotation accum: ${show(a.movement.rotation_accumulated)}`);
    lines.push(`  BODY: deform_events ${show(a.body.deformation_events)}  work_limited ${show(a.body.work_limited_events)}`);
    lines.push(`  RESOURCES A: ${show(a.resources.resource_A)}`);
    lines.push(`  RESOURCES B: ${show(a.resources.resource_B)}`);
    lines.push(`  WORK RESERVOIR: ${show(a.resources.work_reservoir)}`);
    lines.push(`  COGNITION AGGREGATES (runtime metrics; NOT inferred from structured events):`);
    lines.push(`    Prediction count: ${show(a.cognition.prediction_count)}  error ${show(a.cognition.prediction_error)}  prospective ${show(a.cognition.prospective_compositions)}  novel ${show(a.cognition.novel_compositions)}`);
    lines.push(`  SIGNALS: emit A/B ${a.signals.emissions_A}/${a.signals.emissions_B}  recv A/B ${a.signals.receptions_A}/${a.signals.receptions_B}`);
    lines.push(`  Contact emissions: ${a.signals.contact_triggered_emissions}  Motion emissions: ${a.signals.motion_triggered_emissions}`);
    lines.push(`  Reception attribution: mixed=${a.signals.reception_attribution.mixed} not_unique=${a.signals.reception_attribution.not_unique} unknown=${a.signals.reception_attribution.unknown}`);
    lines.push(`  INTERACTION: contacts ${show(a.interaction.body_body_contacts)}  cross-agent contributions ${a.interaction.cross_agent_signal_contributions}`);
    if (a.vision) {
      const v: any = a.vision;
      lines.push('  VISION:');
      lines.push(`    foreign-body exposure ticks: ${show(v.foreign_body_exposure_ticks)}`);
      lines.push(`    observed exposure episodes: ${show(v.observed_exposure_episodes)}`);
      lines.push(`    vision-only episodes: ${show(v.vision_only_episodes)}`);
      if (v.first_observed_exposure != null) {
        lines.push(`    first observed exposure: t${v.first_observed_exposure}`);
      }
      lines.push(`    peak body optical contribution: ${show(v.peak_body_optical_contribution)}`);
      const peaks = v.body_derived_exo_peaks || v.exo_body_derived_delta;
      if (peaks && typeof peaks === 'object') {
        lines.push('    body-derived exo:');
        lines.push(`      L peak: ${show(peaks.exo_0)}`);
        lines.push(`      F peak: ${show(peaks.exo_1)}`);
        lines.push(`      R peak: ${show(peaks.exo_2)}`);
      } else {
        lines.push(`    exo body-derived delta: ${show(v.exo_body_derived_delta)}`);
      }
      if (v.exposure_without_contact_episodes != null) {
        lines.push(`    exposure without contact episodes: ${show(v.exposure_without_contact_episodes)}`);
      }
      lines.push(`    next-action observations: ${show(v.next_action_observations)}`);
      lines.push(`    cognition linkage: ${v.cognition_linkage}`);
    }
    lines.push('');
  }

  if (analysis.comparison) {
    lines.push('AGENT COMPARISON');
    for (const row of analysis.comparison.rows) {
      lines.push(`  ${row.metric}: agent_0=${show(row.agent_0)} | agent_1=${show(row.agent_1)}`);
    }
    lines.push('Divergences:');
    if (!analysis.comparison.divergences.length) lines.push('  NONE');
    for (const d of analysis.comparison.divergences) lines.push(`  - ${d}`);
    lines.push('');
  }

  lines.push('INTERACTIONS');
  const ix = analysis.interactions;
  lines.push(`  First contact tick: ${show(ix.first_contact_tick)}`);
  lines.push(`  Contact timeline ticks: ${ix.contact_ticks}`);
  lines.push(`  Contact episodes: ${ix.contact_episodes.length}`);
  for (const ep of ix.contact_episodes.slice(0, 12)) {
    lines.push(`    episode t${ep.start}–t${ep.end} (${ep.ticks} ticks)`);
  }
  lines.push(`  Contact-triggered emissions: ${ix.contact_triggered_emissions}`);
  lines.push(`  Cross-agent contributions: ${ix.cross_agent_contributions}`);
  lines.push('  Causal snippets:');
  for (const sn of ix.causal_snippets.slice(0, 8)) {
    lines.push(`    tick ${sn.tick} [${sn.evidence_class}]`);
    for (const step of sn.steps) lines.push(`      → ${step}`);
  }
  for (const n of ix.notes) lines.push(`  NOTE: ${n}`);
  lines.push('');

  lines.push('IMPORTANT EVENTS');
  if (!analysis.important_events.length) lines.push('  NONE');
  for (const ev of analysis.important_events.slice(0, 60)) {
    lines.push(`  t${ev.tick} [${ev.category}] ${ev.title}`);
    lines.push(`    Reason: ${ev.reason}`);
    lines.push(`    Evidence class: ${ev.evidence_class}`);
  }
  lines.push('');

  lines.push('PHASES');
  for (const ph of analysis.phases) {
    lines.push(`  ${ph.start}–${ph.end}: ${ph.name}`);
    lines.push(`    ${ph.reason}`);
  }
  lines.push('');

  lines.push('CAUSAL CHAINS');
  if (!analysis.causal_chains.length) lines.push('  NONE / NOT ESTABLISHED');
  for (const ch of analysis.causal_chains.slice(0, 20)) {
    lines.push(`  ${ch.id} @ t${ch.tick}`);
    lines.push(`    nodes: ${ch.nodes.join(' → ')}`);
    for (const e of ch.edges) {
      lines.push(`    ${e.from} =[${e.link}]=> ${e.to} (${e.reason})`);
    }
  }
  lines.push('');

  const br = (analysis as any).behavioral_reconstruction;
  lines.push('BEHAVIORAL RECONSTRUCTION');
  if (br && typeof br.report_text === 'string' && br.report_text.trim()) {
    // report_text already starts with the section title — avoid duplicating header body
    const body = br.report_text.replace(/^BEHAVIORAL RECONSTRUCTION\s*=*\s*/i, '').trimEnd();
    lines.push(body);
  } else if (br && br.status === 'NOT_RECORDED') {
    lines.push('  status: NOT_RECORDED');
    lines.push('  note: SCIENTIFIC_V3 CORE absent — O→D→M→C links NOT_RECORDED (not zero). V2 analysis remains below.');
  } else {
    lines.push('  status: NOT_AVAILABLE');
    lines.push('  note: Behavioral Reconstruction payload not present in evidence package.');
  }
  lines.push('');
  if (br && typeof br.sensorimotor_report_text === 'string' && br.sensorimotor_report_text.trim()) {
    lines.push(br.sensorimotor_report_text.trimEnd());
    lines.push('');
  } else if (br && br.status === 'AVAILABLE') {
    lines.push('SENSORIMOTOR CONSEQUENCE ANALYSIS');
    lines.push('  status: NOT_AVAILABLE in this package (rebuild Analyzer Next / re-analyze).');
    lines.push('');
  }

  const acm = (br as any)?.action_conditioned_model_report_text
    || (analysis as any).behavioral_reconstruction?.action_conditioned_model_report_text
    || (analysis as any).action_conditioned_model_report_text;
  if (acm && typeof acm === 'string' && acm.trim()) {
    lines.push(acm.trimEnd());
    lines.push('');
  } else {
    lines.push('ACTION-CONDITIONED SENSORIMOTOR MODEL');
    lines.push('  status: NOT_RECORDED');
    lines.push('  note: No sensorimotor consequence model telemetry in this analysis package.');
    lines.push('');
  }

  lines.push('HISTORICAL SENSORIMOTOR SELECTION');
  lines.push('  status: NOT_RECORDED in ordinary run packages (see dedicated investigation report).');
  lines.push('');

  lines.push('SIGNAL FORENSICS');
  lines.push('  Physical signals ≠ messages. Emission ≠ intentional emission. Reception ≠ interpretation.');
  lines.push(`  Coverage: ${analysis.coverage.signals}`);
  lines.push(`  Causal provenance: ${analysis.coverage.causal_provenance}`);
  lines.push('');

  const vfLines = formatVisualForensicsSection(analysis.vision_forensics);
  lines.push(...vfLines);
  lines.push('');

  const v3 = (analysis as any).scientific_v3_core;
  lines.push('SCIENTIFIC_V3 CORE RECONSTRUCTION');
  if (!v3 || v3.status === 'NOT_RECORDED' || v3.evidence_version !== 'SCIENTIFIC_V3') {
    lines.push('  status: NOT_RECORDED');
    lines.push('  note: No SCIENTIFIC_V3 CORE package in this run directory (V2-only or pre-V3). Not fabricated from V2.');
  } else {
    lines.push(`  status: ${show(v3.status || 'AVAILABLE')}`);
    lines.push(`  schema_version: ${show(v3.schema_version)}`);
    lines.push(`  evidence_tier: ${show(v3.evidence_tier)}`);
    lines.push(`  identity_coverage: ${show(v3.identity_coverage)}`);
    lines.push(`  observation_coverage: ${show(v3.observation_coverage)}`);
    lines.push(`  decision_coverage: ${show(v3.decision_coverage)}`);
    lines.push(`  motor_coverage: ${show(v3.motor_coverage)}`);
    lines.push(`  consequence_coverage: ${show(v3.consequence_coverage)}`);
    lines.push(`  identity_bodies: ${show(v3.identity_bodies)}`);
    lines.push(`  ticks_expected (autonomous spines): ${show(v3.ticks_expected)}`);
    lines.push(`  observation_receipts: ${show(v3.observation_receipts)}`);
    lines.push(`  decision_receipts: ${show(v3.decision_receipts)}`);
    lines.push(`  motor_receipts: ${show(v3.motor_receipts)}`);
    lines.push(`  consequence_receipts: ${show(v3.consequence_receipts)}`);
    lines.push(`  complete O→D→M→C chains: ${show(v3.complete_odmc_chains)}`);
    lines.push(`  incomplete O→D→M→C chains: ${show(v3.incomplete_odmc_chains)}`);
    lines.push(`  chain completeness: ${show(v3.chain_completeness_pct)}%`);
    lines.push(`  tick range: ${show(v3.tick_range)}`);
    if (Array.isArray(v3.identity_mapping) && v3.identity_mapping.length) {
      lines.push('  identity mapping:');
      for (const b of v3.identity_mapping) {
        lines.push(`    body=${b.physical_body_id} cog=${show(b.cognitive_agent_id)} ctrl=${show(b.controller_type)} role=${show(b.role_label)}`);
      }
    }
    const broken = v3.broken_chains_by_reason || {};
    lines.push(`  broken chains by reason: ${JSON.stringify(broken)}`);
    if (v3.health) lines.push(`  writer health: ${JSON.stringify(v3.health)}`);
  }
  lines.push('');

  lines.push('SCIENTIFIC BOUNDARY');
  lines.push('  This report is Observer/analysis only. It does not modify runtime dynamics.');
  lines.push('  Statements are tagged OBSERVED / DERIVED / CAUSALLY_LINKED / TEMPORALLY_ASSOCIATED / NOT_AVAILABLE.');
  lines.push('');

  lines.push('DATA COVERAGE:');
  lines.push(`  level: ${analysis.coverage.level}`);
  lines.push(`  reason: ${analysis.coverage.reason}`);
  const covAny = analysis.coverage as any;
  if (covAny.runtime_span) lines.push(`  Runtime span: ${covAny.runtime_span}`);
  lines.push(`  Unique simulation ticks observed: ${analysis.coverage.unique_simulation_ticks}`);
  if (covAny.sequence_coverage) lines.push(`  Sequence coverage: ${covAny.sequence_coverage}`);
  if (covAny.gap_count_agents_max != null) lines.push(`  Max trajectory gaps skipped (per agent): ${covAny.gap_count_agents_max}`);
  if (covAny.action_occupancy_semantics) lines.push(`  Action occupancy: ${covAny.action_occupancy_semantics}`);
  if (covAny.continuous_streaks) lines.push(`  Continuous streaks: ${covAny.continuous_streaks}`);
  lines.push(`  world: ${analysis.coverage.world}`);
  lines.push(`  body trajectory: ${analysis.coverage.body}`);
  lines.push(`  cognition aggregates: ${analysis.coverage.cognition}`);
  if (covAny.structured_cognition_events) {
    lines.push(`  structured cognition events: ${covAny.structured_cognition_events}`);
  }
  lines.push(`  signals: ${analysis.coverage.signals}`);
  lines.push(`  causal provenance: ${analysis.coverage.causal_provenance}`);
  lines.push(`  timeline_samples (Observer): ${analysis.coverage.timeline_samples}`);
  lines.push(`  event_samples: ${analysis.coverage.event_samples}`);
  lines.push(`  telemetry_samples: ${analysis.coverage.telemetry_samples}`);
  lines.push('');
  if (analysis.lifecycle) {
    lines.push('ANALYSIS LIFECYCLE:');
    lines.push(`  ${analysis.lifecycle.banner}`);
    lines.push(`  Analyzed ticks: ${analysis.lifecycle.analyzed_start ?? '—'}–${analysis.lifecycle.analyzed_end ?? '—'}`);
    lines.push(`  Coverage: ${analysis.lifecycle.coverage}`);
    lines.push(`  ${analysis.lifecycle.coverage_reason}`);
    lines.push('');
  }
  return lines.join('\n');
}
