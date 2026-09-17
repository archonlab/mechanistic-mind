import type { RunAnalysis } from './types.ts';

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
  lines.push('RUN');
  lines.push(`Runtime: ${id.runtime}`);
  lines.push(`Seed: ${show(id.seed)}`);
  lines.push(`Generation: ${show(id.generation)}`);
  lines.push(`Map: ${show(id.map_width)}×${show(id.map_height)} ${id.boundary}`);
  lines.push(`Ticks: ${id.start_tick}–${id.end_tick} (duration ${id.duration_ticks})`);
  lines.push(`Agent count: ${id.agent_count}`);
  lines.push(`Cognition enabled: ${show(id.cognition_enabled)}`);
  lines.push(`Status: ${id.status}`);
  lines.push(`Analysis mode: ${id.analysis_mode}`);
  lines.push(`Active mechanisms: ${id.active_mechanisms.join(', ') || 'NONE / NOT AVAILABLE'}`);
  lines.push(`Experimental overrides: ${JSON.stringify(id.experimental_overrides || {})}`);
  lines.push('');

  for (const a of analysis.agents) {
    lines.push(a.agent_id.toUpperCase());
    lines.push(`  Seed: ${show(a.seed)}  Body: ${a.body_id}  Ticks observed: ${a.ticks_observed}`);
    lines.push(`  ACTIONS: WAIT ${show(a.actions.wait_count)} (${show(a.actions.wait_pct)}%)  MOVE ${show(a.actions.move_count)} (${show(a.actions.move_pct)}%)`);
    lines.push(`  MOVE distribution: ${show(a.actions.move_distribution)}`);
    lines.push(`  Longest WAIT streak: ${show(a.actions.longest_wait_streak)}  Longest MOVE streak: ${show(a.actions.longest_move_streak)}`);
    lines.push(`  Transitions: ${show(a.actions.action_transitions)}`);
    lines.push(`  MOVEMENT: distance ${show(a.movement.distance_travelled)}  net ${show(a.movement.net_displacement)}  mean_speed ${show(a.movement.mean_speed)}  max_speed ${show(a.movement.max_speed)}`);
    lines.push(`  Unique cells: ${show(a.movement.unique_cells)}  Rotation accum: ${show(a.movement.rotation_accumulated)}`);
    lines.push(`  BODY: deform_events ${show(a.body.deformation_events)}  work_limited ${show(a.body.work_limited_events)}`);
    lines.push(`  RESOURCES A: ${show(a.resources.resource_A)}`);
    lines.push(`  RESOURCES B: ${show(a.resources.resource_B)}`);
    lines.push(`  WORK RESERVOIR: ${show(a.resources.work_reservoir)}`);
    lines.push(`  COGNITION: predictions ${show(a.cognition.prediction_count)}  error ${show(a.cognition.prediction_error)}  prospective ${show(a.cognition.prospective_compositions)}  novel ${show(a.cognition.novel_compositions)}`);
    lines.push(`  SCENARIO_SELECTED: ${show(a.cognition.scenario_selected)} (WAIT ${show(a.cognition.scenario_selected_wait)} / MOVE ${show(a.cognition.scenario_selected_move)})`);
    lines.push(`  Cognitive WAIT selections: ${show(a.cognition.cognitive_wait_selections)}  Fallback WAIT: ${show(a.cognition.fallback_wait_selections)}`);
    lines.push(`  Action sources: ${show(a.cognition.selected_action_sources)}`);
    lines.push(`  SIGNALS: emit A/B ${a.signals.emissions_A}/${a.signals.emissions_B}  recv A/B ${a.signals.receptions_A}/${a.signals.receptions_B}`);
    lines.push(`  Contact emissions: ${a.signals.contact_triggered_emissions}  Motion emissions: ${a.signals.motion_triggered_emissions}`);
    lines.push(`  Reception attribution: mixed=${a.signals.reception_attribution.mixed} not_unique=${a.signals.reception_attribution.not_unique} unknown=${a.signals.reception_attribution.unknown}`);
    lines.push(`  INTERACTION: contacts ${show(a.interaction.body_body_contacts)}  cross-agent contributions ${a.interaction.cross_agent_signal_contributions}`);
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

  lines.push('SIGNAL FORENSICS');
  lines.push('  Physical signals ≠ messages. Emission ≠ intentional emission. Reception ≠ interpretation.');
  lines.push(`  Coverage: ${analysis.coverage.signals}`);
  lines.push(`  Causal provenance: ${analysis.coverage.causal_provenance}`);
  lines.push('');

  lines.push('SCIENTIFIC BOUNDARY');
  lines.push('  This report is Observer/analysis only. It does not modify runtime dynamics.');
  lines.push('  Statements are tagged OBSERVED / DERIVED / CAUSALLY_LINKED / TEMPORALLY_ASSOCIATED / NOT_AVAILABLE.');
  lines.push('');

  lines.push('DATA COVERAGE:');
  lines.push(`  level: ${analysis.coverage.level}`);
  lines.push(`  reason: ${analysis.coverage.reason}`);
  lines.push(`  world: ${analysis.coverage.world}`);
  lines.push(`  body: ${analysis.coverage.body}`);
  lines.push(`  cognition: ${analysis.coverage.cognition}`);
  lines.push(`  signals: ${analysis.coverage.signals}`);
  lines.push(`  causal provenance: ${analysis.coverage.causal_provenance}`);
  lines.push(`  timeline_samples: ${analysis.coverage.timeline_samples}`);
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
