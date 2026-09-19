/**
 * Ingest Observer telemetry into bounded AnalysisState and build RunAnalysis.
 */
import {
  BOUNDS,
  createAnalysisState,
  ensureAgent,
  ingestAction,
  ingestXy,
  claimTimelineAgentState,
  pushBounded,
  recordExtrema,
  recordFirst,
  updateResourceSeries,
  canonicalBody,
  SUSTAINED_WAIT_THRESHOLD,
  SUSTAINED_MOVE_THRESHOLD,
} from './aggregates.ts';
import type { AnalysisState, AgentAgg } from './aggregates.ts';
import { buildAgentAnalyses, buildComparison } from './agentAnalysis.ts';
import { buildInteractions } from './interactionAnalysis.ts';
import { buildImportantEvents, maybeAddKeyframe } from './importantEvents.ts';
import { detectPhases } from './phaseDetection.ts';
import { buildCausalChains } from './causalChains.ts';
import { buildOverview } from './overviewNarrative.ts';
import { formatAnalysisLog } from './analysisLog.ts';
import type { AnalysisMode, RunAnalysis, RunIdentity } from './types.ts';
import { buildCoverageBlock, buildLifecycle } from './lifecycle.ts';
import {
  episodesFromContactTicks,
  rememberKey,
  rememberNumber,
  sanitizeContactEpisode,
  structuredEventKey,
  liveSummaryKey,
  telemetryRowKey,
} from './dedup.ts';
import {
  buildConfigurationHistory,
  collectWorldInterventions,
} from './configurationHistory.ts';
import type { RegimeReport } from './configurationHistory.ts';
import {
  analyzeOpticalSeries,
  mergeAgentVision,
  opticalTickFromLiveFrame,
  opticalTicksFromScientificRows,
  visionImportantEvents,
} from './visionForensics.ts';
import type { OpticalTickTS, VisionForensicsReport } from './visionForensics.ts';

export type AnalysisInput = {
  frame?: any;
  timeline?: any[];
  events?: any[];
  telemetry?: any[];
  mechanisms?: any[];
  mode?: AnalysisMode;
  /** When true, prefer scientific evidence semantics (no cumulative→tick conflation). */
  scientificEvidence?: boolean;
  /** Skip folding runtime cumulative action_counts into tick aggregates. */
  skipLiveCumulativeActions?: boolean;
  /** Optional pre-collected WORLD_INTERVENTION events. */
  world_interventions?: any[];
  /** Scientific timeline rows with optional vision_optical compact. */
  scientific_rows?: any[];
  /** Pre-built optical tick series for vision forensics. */
  optical_ticks?: import('./visionForensics.ts').OpticalTickTS[];
};

/** Reset or create state; call when generation/seed/runtime identity changes. */
export function resetAnalysis(_prev?: AnalysisState | null): AnalysisState {
  return createAnalysisState();
}

export function shouldResetAnalysis(state: AnalysisState, frame: any): boolean {
  const gen = frame?.header?.runtime_generation ?? frame?.observation?.runtime_generation;
  const seed = frame?.header?.seed;
  if (state.generation != null && gen != null && Number(gen) !== Number(state.generation)) return true;
  if (state.seed != null && seed != null && Number(seed) !== Number(state.seed)) return true;
  return false;
}

export function ingestAnalysisInput(state: AnalysisState, input: AnalysisInput): AnalysisState {
  const frame = input.frame;
  if (frame && shouldResetAnalysis(state, frame)) {
    const next = createAnalysisState();
    Object.assign(state, next);
  }
  if (frame) ingestFrameMeta(state, frame, input.mechanisms);
  if (input.timeline?.length) ingestTimeline(state, input.timeline);
  if (input.events?.length) ingestEvents(state, input.events);
  if (input.telemetry?.length) ingestTelemetry(state, input.telemetry, frame);
  if (frame && !input.skipLiveCumulativeActions) ingestLiveSummaries(state, frame);
  else if (frame && input.scientificEvidence) ingestLiveSummariesScientific(state, frame);
  // Merge WORLD_INTERVENTION provenance (frame list + event stream).
  const collected = collectWorldInterventions({
    frame,
    events: [
      ...(input.events || []),
      ...(input.world_interventions || []),
    ],
  });
  if (collected.length) {
    const seen = new Set(
      state.world_interventions.map((e) => String(e.event_id || `${e.simulation_tick}-${JSON.stringify(e.changes)}`)),
    );
    for (const ev of collected) {
      const id = String(ev.event_id || `${ev.simulation_tick}-${JSON.stringify(ev.changes)}`);
      if (seen.has(id)) continue;
      seen.add(id);
      state.world_interventions.push(ev);
    }
    state.world_interventions.sort((a, b) =>
      Number(a.simulation_tick ?? a.tick ?? 0) - Number(b.simulation_tick ?? b.tick ?? 0),
    );
  }
  if (!state.initial_world_fingerprint && state.world_interventions[0]?.effective_world_fingerprint_before) {
    state.initial_world_fingerprint = state.world_interventions[0].effective_world_fingerprint_before;
  }
  if (!state.initial_world_fingerprint && frame?.experiment?.observer_ground_truth?.effective_world?.world_fingerprint) {
    state.initial_world_fingerprint = frame.experiment.observer_ground_truth.effective_world.world_fingerprint;
  }
  return state;
}

function ingestFrameMeta(state: AnalysisState, frame: any, mechanisms?: any[]) {
  const h = frame.header || {};
  const tick = Number(h.tick ?? 0);
  state.generation = h.runtime_generation ?? state.generation;
  state.seed = h.seed != null ? Number(h.seed) : state.seed;
  state.runtime = h.runtime_model || frame.experiment?.runtime?.type || state.runtime;
  state.map_w = frame.world?.width ?? h.world_size?.width ?? state.map_w;
  state.map_h = frame.world?.height ?? h.world_size?.height ?? state.map_h;
  state.boundary = h.boundary_topology || frame.world?.boundary || state.boundary;
  state.status = h.status || state.status;
  state.cognition_enabled =
    frame.experiment?.runtime?.cognition_enabled ?? h.cognition_enabled ?? state.cognition_enabled;
  state.experimental_overrides = h.experimental_overrides || frame.experiment?.experimental_overrides || {};
  state.agent_count = Number(h.agent_count || frame.experiment?.runtime?.agent_count || state.agent_count || 1);
  if (state.start_tick == null) state.start_tick = tick;
  state.end_tick = tick;
  if (Array.isArray(mechanisms)) {
    state.active_mechanisms = mechanisms.filter((m) => m.enabled).map((m) => m.id || m.label).slice(0, 40);
  } else if (frame.model_banner?.mechanisms?.enabled) {
    state.active_mechanisms = Object.entries(frame.model_banner.mechanisms.enabled)
      .filter(([, v]) => v)
      .map(([k]) => k)
      .slice(0, 40);
  }
  const mapping = h.agent_body_mapping || frame.observer?.agent_body_mapping || [];
  for (const row of mapping) {
    ensureAgent(state, row.agent_id, row.body_id, row.agent_seed != null ? Number(row.agent_seed) : null);
  }
  if (!mapping.length) {
    ensureAgent(state, 'agent_0', 'body-0', state.seed);
  }
}

function ingestTimeline(state: AnalysisState, timeline: any[]) {
  const sorted = [...timeline].sort((a, b) => Number(a.tick) - Number(b.tick));
  for (const ev of sorted) {
    const tick = Number(ev.tick);
    if (!Number.isFinite(tick)) continue;
    // Diagnostic: every Observer sample, including duplicates.
    state.timeline_samples += 1;
    rememberNumber(state.unique_simulation_ticks, tick);
    if (state.start_tick == null || tick < state.start_tick) state.start_tick = tick;
    if (state.end_tick == null || tick > state.end_tick) state.end_tick = tick;

    const bodies = Array.isArray(ev.bodies) && ev.bodies.length
      ? ev.bodies
      : [{ agent_id: ev.agent_id || 'agent_0', x: ev.body_xy?.x, y: ev.body_xy?.y, action: ev.action }];

    for (const b of bodies) {
      const aid = String(b.agent_id || 'agent_0');
      const agg = ensureAgent(state, aid, canonicalBody(aid));
      // Scientific action/position once per (tick, agent).
      if (!claimTimelineAgentState(state, tick, aid)) continue;
      const applied = b.action ? ingestAction(agg, String(b.action), tick) : false;
      if (applied && b.action_source) {
        const src = String(b.action_source);
        agg.selection_sources[src] = (agg.selection_sources[src] || 0) + 1;
      } else if (applied && ev.action_source && bodies.length === 1) {
        const src = String(ev.action_source);
        agg.selection_sources[src] = (agg.selection_sources[src] || 0) + 1;
      }
      if (b.x != null && b.y != null) {
        ingestXy(
          agg,
          Number(b.x),
          Number(b.y),
          b.speed != null ? Number(b.speed) : undefined,
          tick,
          state.map_w ?? undefined,
          state.map_h ?? undefined,
        );
      }
      if (b.work != null) updateResourceSeries(agg.work, Number(b.work));
      if (b.resource_A != null) updateResourceSeries(agg.resA, Number(b.resource_A));
      if (b.resource_B != null) updateResourceSeries(agg.resB, Number(b.resource_B));
      if (b.prediction_count != null) agg.prediction_count = Number(b.prediction_count);
      if (b.prospective_compositions != null) agg.prospective = Number(b.prospective_compositions);
      if (b.agent_seed != null && agg.seed == null) agg.seed = Number(b.agent_seed);
      if (applied && String(b.action || '').startsWith('MOVE')) {
        if (recordFirst(state, `first_move_${aid}`, tick, { action: b.action })) {
          pushImportant(state, {
            tick,
            category: 'FIRST',
            kind: 'FIRST_MOVE',
            title: `FIRST OBSERVED MOVE (${aid})`,
            reason: `First MOVE selection observed for ${aid} in retained timeline (not necessarily first ever if coverage incomplete).`,
            evidence_class: 'OBSERVED',
            agent_ids: [aid],
          });
          maybeAddKeyframe(state, tick, `first move ${aid}`, frameAgentsFromTimeline(ev), !!ev.contact, state.map_w, state.map_h);
        }
      }
      // Threshold events only when THIS agent's canonical action was applied this tick.
      if (applied) maybeEmitSustainedThreshold(state, agg, tick);
    }

    // Contact FSM advances once per unique simulation tick.
    if (rememberKey(state.contact_fsm_ticks, String(tick))) {
      if (ev.contact) {
        if (rememberNumber(state.contact_tick_set, tick)) {
          state.contact_ticks = state.contact_tick_set.size;
        }
        if (!state.contact_active) {
          state.contact_active = true;
          state.contact_episode_start = tick;
          if (state.first_contact_tick == null) {
            state.first_contact_tick = tick;
            recordFirst(state, 'first_body_body_contact', tick);
            pushImportant(state, {
              tick,
              category: 'FIRST',
              kind: 'FIRST_BODY_BODY_CONTACT',
              title: 'FIRST BODY-BODY CONTACT',
              reason: 'First BODY_BODY_CONTACT / timeline.contact=true in this run.',
              evidence_class: 'OBSERVED',
              body_ids: ['body-0', 'body-1'],
            });
            maybeAddKeyframe(state, tick, 'first contact', frameAgentsFromTimeline(ev), true, state.map_w, state.map_h);
          }
        }
      } else if (state.contact_active) {
        closeContactEpisode(state, tick - 1);
      }
    }

    state.last_processed_timeline_tick = Math.max(state.last_processed_timeline_tick, tick);
  }
}

/**
 * Emit at most one SUSTAINED_* threshold event per continuous canonical streak.
 * Primary tick = threshold-reaching simulation tick (not streak start).
 * Identity: (agent_id, kind, streak_start_tick).
 */
function maybeEmitSustainedThreshold(state: AnalysisState, agg: AgentAgg, reachTick: number) {
  const aid = agg.agent_id;
  const coverageStart = state.start_tick;

  if (
    agg.wait_streak === SUSTAINED_WAIT_THRESHOLD
    && !agg.sustained_wait_threshold_emitted
    && agg.wait_streak_start_tick != null
  ) {
    const streakStart = agg.wait_streak_start_tick;
    // Never fabricate pre-coverage / negative spans.
    if (streakStart >= 0 && (coverageStart == null || streakStart >= coverageStart)) {
      const id = `sustained_wait_${aid}_s${streakStart}`;
      if (recordFirst(state, id, reachTick)) {
        agg.sustained_wait_threshold_emitted = true;
        pushImportant(state, {
          tick: reachTick,
          category: 'TRANSITION',
          kind: 'SUSTAINED_WAIT',
          title: `SUSTAINED WAIT (${aid})`,
          reason:
            `${aid} reached ${SUSTAINED_WAIT_THRESHOLD} consecutive WAIT simulation ticks at t${reachTick} `
            + `(streak threshold span t${streakStart}–t${reachTick}).`,
          evidence_class: 'DERIVED',
          agent_ids: [aid],
          refs: { streak_start: streakStart, threshold_tick: reachTick, threshold: SUSTAINED_WAIT_THRESHOLD },
        });
      }
    } else {
      // Origin not establishable from available evidence — arm so we don't spam.
      agg.sustained_wait_threshold_emitted = true;
    }
  }

  if (
    agg.move_streak === SUSTAINED_MOVE_THRESHOLD
    && !agg.sustained_move_threshold_emitted
    && agg.move_streak_start_tick != null
  ) {
    const streakStart = agg.move_streak_start_tick;
    if (streakStart >= 0 && (coverageStart == null || streakStart >= coverageStart)) {
      // FIRST MOVE consistency: never emit MOVE streak before first canonical MOVE.
      if (agg.first_move_tick != null && streakStart < agg.first_move_tick) {
        agg.sustained_move_threshold_emitted = true;
        return;
      }
      const id = `sustained_move_${aid}_s${streakStart}`;
      if (recordFirst(state, id, reachTick)) {
        agg.sustained_move_threshold_emitted = true;
        pushImportant(state, {
          tick: reachTick,
          category: 'TRANSITION',
          kind: 'SUSTAINED_MOVE',
          title: `SUSTAINED MOVE (${aid})`,
          reason:
            `${aid} reached ${SUSTAINED_MOVE_THRESHOLD} consecutive MOVE simulation ticks at t${reachTick} `
            + `(streak threshold span t${streakStart}–t${reachTick}).`,
          evidence_class: 'DERIVED',
          agent_ids: [aid],
          refs: { streak_start: streakStart, threshold_tick: reachTick, threshold: SUSTAINED_MOVE_THRESHOLD },
        });
      }
    } else {
      agg.sustained_move_threshold_emitted = true;
    }
  }
}

function closeContactEpisode(state: AnalysisState, endTick: number) {
  if (!state.contact_active || state.contact_episode_start == null) return;
  const ep = sanitizeContactEpisode(state.contact_episode_start, endTick);
  if (ep) pushBounded(state.contact_episodes, ep, BOUNDS.contact_episodes);
  state.contact_active = false;
  state.contact_episode_start = null;
}

function frameAgentsFromTimeline(ev: any) {
  if (Array.isArray(ev.bodies)) {
    return ev.bodies.map((b: any) => ({
      agent_id: String(b.agent_id || 'agent_0'),
      x: Number(b.x || 0),
      y: Number(b.y || 0),
    }));
  }
  return [{
    agent_id: String(ev.agent_id || 'agent_0'),
    x: Number(ev.body_xy?.x || 0),
    y: Number(ev.body_xy?.y || 0),
  }];
}

function ingestEvents(state: AnalysisState, events: any[]) {
  for (const ev of events) {
    const tick = Number(ev.tick);
    const et = String(ev.type || ev.kind || '');
    const evidence = ev.evidence || {};
    const key = structuredEventKey(ev);
    if (!rememberKey(state.seen_event_keys, key)) continue;
    state.event_samples += 1;

    if (et.includes('SIGNAL_EMITTED')) {
      const aid = String(ev.emitter_agent_id || evidence.emitter_agent_id || 'UNKNOWN');
      if (aid.startsWith('agent_')) {
        const agg = ensureAgent(state, aid, evidence.emitter_body_id || canonicalBody(aid));
        const ch = String(evidence.channel || '').toUpperCase();
        if (ch === 'A') agg.emit_A += 1;
        if (ch === 'B') agg.emit_B += 1;
        if (evidence.trigger === 'body_contact') agg.emit_contact += 1;
        if (evidence.trigger === 'body_motion') agg.emit_motion += 1;
      }
      if (recordFirst(state, 'first_signal_emission', tick, { channel: evidence.channel })) {
        pushImportant(state, {
          tick,
          category: 'FIRST',
          kind: 'FIRST_SIGNAL_EMISSION',
          title: 'FIRST SIGNAL EMISSION',
          reason: `First PHYSICAL_SIGNAL_EMITTED (channel ${evidence.channel || '?'}).`,
          evidence_class: 'OBSERVED',
          emission_ids: evidence.emission_id ? [evidence.emission_id] : [],
          agent_ids: aid.startsWith('agent_') ? [aid] : [],
        });
      }
      if (evidence.trigger === 'body_contact' && recordFirst(state, 'first_contact_emission', tick)) {
        pushImportant(state, {
          tick,
          category: 'FIRST',
          kind: 'FIRST_CONTACT_TRIGGERED_EMISSION',
          title: 'FIRST CONTACT-TRIGGERED FIELD_B EMISSION',
          reason: 'First emission with trigger=body_contact.',
          evidence_class: 'CAUSALLY_LINKED',
          emission_ids: evidence.emission_id ? [evidence.emission_id] : [],
        });
      }
      const inten = Number(evidence.realized || evidence.intensity || 0);
      if (inten > 0 && recordExtrema(state, 'max_signal_intensity', tick, inten, 'max')) {
        /* extrema recorded */
      }
    }

    if (et.includes('SIGNAL_RECEIVED')) {
      const aid = String(ev.receiver_agent_id || evidence.receiver_agent_id || ev.agent_id || 'agent_0');
      const agg = ensureAgent(state, aid, evidence.receiver_body_id || canonicalBody(aid));
      if (Number(evidence['local.FIELD_A'] || 0) > 0) agg.recv_A += 1;
      if (Number(evidence['local.FIELD_B'] || 0) > 0) agg.recv_B += 1;
      const attr = String(evidence.source_attribution || '');
      if (attr === 'MIXED') agg.recv_mixed += 1;
      else if (attr.includes('NOT_UNIQUE')) agg.recv_not_unique += 1;
      else agg.recv_unknown += 1;
      if (recordFirst(state, 'first_signal_reception', tick)) {
        pushImportant(state, {
          tick,
          category: 'FIRST',
          kind: 'FIRST_SIGNAL_RECEPTION',
          title: 'FIRST SIGNAL RECEPTION',
          reason: 'First PHYSICAL_SIGNAL_RECEIVED in this run.',
          evidence_class: 'OBSERVED',
          agent_ids: [aid],
        });
      }
      const parents = evidence.contributing_emissions_this_tick || [];
      for (const p of parents) {
        const em = String(p.emitter_agent_id || '');
        if (em && em !== aid && em.startsWith('agent_')) {
          agg.cross_agent_contrib += 1;
          pushBounded(state.causal_pairs, {
            tick,
            parent: String(p.emission_id || em),
            child: `recv:${aid}`,
            meta: { emitter: em, receiver: aid, attribution: attr },
          }, 200);
          if (recordFirst(state, 'first_cross_agent_contribution', tick, { emitter: em, receiver: aid })) {
            pushImportant(state, {
              tick,
              category: 'FIRST',
              kind: 'FIRST_CROSS_AGENT_CONTRIBUTION',
              title: 'FIRST CROSS-AGENT PHYSICAL SIGNAL CONTRIBUTION',
              reason: `Same-tick emission from ${em} listed in ${aid} reception parents (${attr || 'attribution recorded'}). Not communication.`,
              evidence_class: 'CAUSALLY_LINKED',
              agent_ids: [em, aid],
              emission_ids: p.emission_id ? [p.emission_id] : [],
            });
            maybeAddKeyframe(state, tick, 'cross-agent contribution', [
              { agent_id: em, x: 0, y: 0 },
              { agent_id: aid, x: 0, y: 0 },
            ], false, state.map_w, state.map_h);
          }
        }
      }
    }

    if (et.includes('PREDICTION') || et === 'PREDICTION_MATCHED' || et === 'PREDICTION_VIOLATED') {
      if (recordFirst(state, 'first_prediction', tick)) {
        pushImportant(state, {
          tick,
          category: 'FIRST',
          kind: 'FIRST_PREDICTION',
          title: 'FIRST PREDICTION EVENT',
          reason: `First prediction-related structured event (${et}).`,
          evidence_class: 'OBSERVED',
        });
      }
    }
    if (et.includes('SCENARIO') || et.includes('OBSERVATION_ACQUIRED')) {
      if (recordFirst(state, 'first_prospective_or_scenario', tick)) {
        pushImportant(state, {
          tick,
          category: 'FIRST',
          kind: 'FIRST_PROSPECTIVE_OR_SCENARIO',
          title: 'FIRST PROSPECTIVE / SCENARIO EVENT',
          reason: `First scenario/prospective structured event (${et}).`,
          evidence_class: 'OBSERVED',
        });
      }
    }
    if (et === 'SCENARIO_SELECTED') {
      const aid = String(ev.actor_agent_id || ev.agent_id || evidence.actor_agent_id || 'agent_0');
      const agg = ensureAgent(state, aid, evidence.body_id || canonicalBody(aid));
      const act = String(evidence.selected_action || evidence.action || '');
      agg.scenario_selected += 1;
      if (act === 'WAIT') {
        agg.scenario_selected_wait += 1;
        agg.cognitive_wait_selections += 1;
      } else if (act.startsWith('MOVE')) {
        agg.scenario_selected_move += 1;
      }
    }
    if (et === 'DISCRETE_ACTION_SELECTED') {
      const aid = String(ev.actor_agent_id || ev.agent_id || evidence.actor_agent_id || 'agent_0');
      const agg = ensureAgent(state, aid, evidence.body_id || canonicalBody(aid));
      const act = String(evidence.selected_action || evidence.action || '');
      const src = String(evidence.selection_source || '');
      agg.discrete_action_selected += 1;
      if (src) {
        agg.selection_sources[src] = (agg.selection_sources[src] || 0) + 1;
      }
      // Fallback / non-scenario WAIT (not PROSPECTIVE_*).
      if (act === 'WAIT' && !src.startsWith('PROSPECTIVE_')) {
        agg.fallback_wait_selections += 1;
      }
    }
    if (et.includes('DEFORM')) {
      const aid = String(ev.agent_id || evidence.agent_id || 'agent_0');
      ensureAgent(state, aid).deform_events += 1;
    }
    if (et.includes('WORK_LIMIT') || et.includes('WORK_UNAVAILABLE') || et.includes('LIMITING')) {
      const aid = String(ev.agent_id || 'agent_0');
      const agg = ensureAgent(state, aid);
      agg.work_limited += 1;
      if (et.includes('LIMITING')) agg.limiting_events += 1;
    }
    if (et.includes('CONVERSION') || et.includes('RESOURCE_CONVERTED')) {
      ensureAgent(state, String(ev.agent_id || 'agent_0')).conversion_events += 1;
    }
    if (et === 'CONTACT' || (evidence.contact_entity_a_id && evidence.contact_entity_b_id && et.includes('SIGNAL'))) {
      /* contact also tracked via timeline */
    }
  }
}

function ingestTelemetry(state: AnalysisState, series: any[], frame?: any) {
  // Telemetry is typically selected-agent / shared series — attribute to agent_0 unless bodies present
  const primary = ensureAgent(state, 'agent_0', 'body-0', state.seed);
  for (const row of series) {
    state.telemetry_samples += 1;
    const tick = Number(row.tick);
    if (Number.isFinite(tick) && !rememberKey(state.seen_event_keys, telemetryRowKey(tick))) {
      // Already applied scientific telemetry for this tick — skip resource/speed double-count.
      continue;
    }
    updateResourceSeries(primary.resA, row.resource_A);
    updateResourceSeries(primary.resB, row.resource_B);
    updateResourceSeries(primary.work, row.work_reservoir);
    const speed = Number(row.speed);
    if (Number.isFinite(speed)) {
      primary.max_speed = Math.max(primary.max_speed, speed);
      primary.speed_sum += speed;
      primary.speed_n += 1;
      if (recordExtrema(state, 'max_velocity', tick, speed, 'max')) {
        /* */
      }
    }
    if (row.resource_A != null && recordExtrema(state, 'min_resource_A', tick, Number(row.resource_A), 'min')) {
      /* */
    }
  }
  // Two-agent: also fold agents_observer resource snapshots if present
  const observers = frame?.agents_observer || [];
  for (const o of observers) {
    const aid = String(o.observer_id || '');
    if (!aid) continue;
    const agg = ensureAgent(state, aid, canonicalBody(aid), o.agent_seed != null ? Number(o.agent_seed) : null);
    updateResourceSeries(agg.resA, o.body_A);
    updateResourceSeries(agg.resB, o.body_B);
    updateResourceSeries(agg.work, o.work);
  }
}

function ingestLiveSummaries(state: AnalysisState, frame: any) {
  const tick = Number(frame?.header?.tick);
  const observers = frame.agents_observer || [];
  const isNewLiveTick = Number.isFinite(tick)
    ? rememberKey(state.seen_event_keys, liveSummaryKey(tick))
    : true;
  if (Number.isFinite(tick)) state.last_live_summary_tick = tick;

  if (observers.length) {
    state.agent_count = Math.max(state.agent_count, observers.length);
    for (const o of observers) {
      const aid = String(o.observer_id);
      const agg = ensureAgent(state, aid, canonicalBody(aid), o.agent_seed != null ? Number(o.agent_seed) : null);
      if (o.distance_travelled != null) {
        // Runtime cumulative may be wrap-aware after LOCAL_PHYSICAL_COHERENCE_01;
        // never overwrite Analyzer unique-tick path — keep as separate ceiling hint only.
        (agg as any)._runtime_distance_travelled = Number(o.distance_travelled);
      }
      if (o.unique_cells_visited != null && Number(o.unique_cells_visited) > agg.unique_cells.size) {
        (agg as any)._unique_cells_runtime = Number(o.unique_cells_visited);
      }
      if (o.collision_count != null) agg.collision_ticks = Math.max(agg.collision_ticks, Number(o.collision_count));
      if (o.prediction_count != null) agg.prediction_count = Number(o.prediction_count);
      if (o.prospective_compositions != null) agg.prospective = Number(o.prospective_compositions);
      // CRITICAL: runtime cumulative action_counts are a separate evidence class.
      // Never Math.max them into tick-level occupancy (that produced WAIT+MOVE > ticks_observed).
      if (o.action_counts && typeof o.action_counts === 'object') {
        (agg as any)._cumulative_action_counts = { ...o.action_counts };
      }
      // selection_source for tick-level occupancy comes from scientific/timeline rows only.
      // Do not increment selection_sources here (would double-count vs timeline).
      // CRITICAL: never mutate agg.last_xy from LIVE summaries — that poisoned
      // the next unique-tick delta and inflated WRAP path/unwrapped by ~100×.
      // Also never seed start_xy from LIVE pose — that poisoned net_displacement.
      if (o.x != null && o.y != null) {
        agg.live_pose_xy = { x: Number(o.x), y: Number(o.y) };
      }
      const spd = Math.hypot(Number(o.vx || 0), Number(o.vy || 0));
      if (spd > agg.max_speed) agg.max_speed = spd;
      if (isNewLiveTick && o.theta != null) {
        if (agg.theta_start == null) agg.theta_start = Number(o.theta);
        if (agg.theta_last != null) {
          let d = Number(o.theta) - agg.theta_last;
          while (d > Math.PI) d -= 2 * Math.PI;
          while (d < -Math.PI) d += 2 * Math.PI;
          agg.rotation_accum += Math.abs(d);
        }
        agg.theta_last = Number(o.theta);
      } else if (o.theta != null) {
        if (agg.theta_start == null) agg.theta_start = Number(o.theta);
        agg.theta_last = Number(o.theta);
      }
    }
  } else {
    // single-agent fallback from mind/body — cognition metrics only, not tick occupancy
    const agg = ensureAgent(state, 'agent_0', frame.header?.selected_body_id || 'body-0', state.seed);
    const metrics = frame.mind?.metrics || {};
    if (metrics.action_counts && typeof metrics.action_counts === 'object') {
      (agg as any)._cumulative_action_counts = { ...metrics.action_counts };
    }
    if (metrics.prediction_count != null) agg.prediction_count = Number(metrics.prediction_count);
    if (metrics.prediction_error != null || metrics.last_prediction_error != null) {
      agg.prediction_error = Number(metrics.prediction_error ?? metrics.last_prediction_error);
    }
    if (metrics.prospective_compositions != null) agg.prospective = Number(metrics.prospective_compositions);
    if (metrics.novel_compositions != null) agg.novel = Number(metrics.novel_compositions);
    if (frame.body?.x != null) {
      ingestXy(
        agg,
        Number(frame.body.x),
        Number(frame.body.y),
        Math.hypot(Number(frame.body.vx || 0), Number(frame.body.vy || 0)),
        Number.isFinite(tick) ? tick : undefined,
        state.map_w ?? undefined,
        state.map_h ?? undefined,
      );
    }
  }
}

/**
 * Scientific re-analysis path: update cognition/pose hints from the frame
 * without folding cumulative action_counts into tick-level aggregates.
 */
function ingestLiveSummariesScientific(state: AnalysisState, frame: any) {
  const observers = frame.agents_observer || [];
  if (observers.length) {
    state.agent_count = Math.max(state.agent_count, observers.length);
    for (const o of observers) {
      const aid = String(o.observer_id);
      const agg = ensureAgent(state, aid, canonicalBody(aid), o.agent_seed != null ? Number(o.agent_seed) : null);
      if (o.prediction_count != null) agg.prediction_count = Number(o.prediction_count);
      if (o.prospective_compositions != null) agg.prospective = Number(o.prospective_compositions);
      // Store cumulative separately on agg for report exposure — never merge into action_counts.
      if (o.action_counts && typeof o.action_counts === 'object') {
        (agg as any)._cumulative_action_counts = { ...o.action_counts };
      }
    }
  }
}

function pushImportant(state: AnalysisState, ev: any) {
  pushBounded(state.important, ev, BOUNDS.important_events);
}

export function buildRunAnalysis(
  state: AnalysisState,
  mode: AnalysisMode = 'LIVE',
  opts?: { optical_ticks?: OpticalTickTS[]; scientific_rows?: any[]; frame?: any },
): RunAnalysis {
  // Prefer episodes rebuilt from unique contact simulation ticks (authoritative).
  let episodes = episodesFromContactTicks(state.contact_tick_set, BOUNDS.contact_episodes);
  if (!episodes.length && state.contact_episodes.length) {
    episodes = state.contact_episodes
      .map((e) => sanitizeContactEpisode(e.start, e.end))
      .filter((e): e is { start: number; end: number; ticks: number } => !!e);
  }
  if (state.contact_active && state.contact_episode_start != null && state.end_tick != null) {
    const open = sanitizeContactEpisode(state.contact_episode_start, state.end_tick);
    if (open) {
      const last = episodes[episodes.length - 1];
      if (!last || last.start !== open.start || last.end !== open.end) episodes.push(open);
    }
  }
  state.contact_ticks = state.contact_tick_set.size;

  const identity = buildIdentity(state, mode);
  const lifecycle = buildLifecycle(state, mode, state.end_tick);
  let agents = buildAgentAnalyses(state);

  // Vision forensics from scientific rows / explicit ticks / LIVE frame snapshot
  let opticalTicks: OpticalTickTS[] = opts?.optical_ticks || [];
  let opticalHistoryAuthority: import('./visionForensics.ts').OpticalHistoryAuthority = 'NONE';
  if (opticalTicks.length) {
    opticalHistoryAuthority = 'HISTORICAL';
  } else if (opts?.scientific_rows?.length) {
    opticalTicks = opticalTicksFromScientificRows(opts.scientific_rows);
    opticalHistoryAuthority = opticalTicks.length ? 'HISTORICAL' : 'NONE';
  }
  if (!opticalTicks.length && opts?.frame) {
    const live: OpticalTickTS[] = [];
    for (const aid of Object.keys(opts.frame.agents_views || { agent_0: true })) {
      const ot = opticalTickFromLiveFrame(opts.frame, aid);
      if (ot) live.push(ot);
    }
    opticalTicks = live;
    opticalHistoryAuthority = opticalTicks.length ? 'LIVE_FRAME_ONLY' : 'NONE';
  }
  const vision_forensics: VisionForensicsReport = analyzeOpticalSeries(opticalTicks, {
    first_contact_tick: state.first_contact_tick,
    optical_history_authority: opticalHistoryAuthority,
  });
  if (vision_forensics.summary.by_agent && Object.keys(vision_forensics.summary.by_agent).length) {
    agents = agents.map((a) => {
      const byId = vision_forensics.summary.by_agent?.[a.agent_id];
      const byBody = vision_forensics.summary.by_agent?.[`body-${a.agent_id.replace('agent_', '')}`];
      return mergeAgentVision(a, byId || byBody);
    });
  } else {
    agents = agents.map((a) => mergeAgentVision(a, undefined));
  }

  const comparison = buildComparison(agents);
  const interactions = buildInteractions(state, episodes);
  const important_events = [
    ...buildImportantEvents(state),
    ...visionImportantEvents(vision_forensics),
  ];
  const signal_chains = buildCausalChains(state);
  const causal_chains = [...signal_chains, ...vision_forensics.causal_chains].slice(
    0,
    BOUNDS.max_causal_chains,
  );
  const phases = detectPhases(state);
  const overview = buildOverview(state, important_events, phases, interactions);
  const coverage = buildCoverageBlock(state, mode);
  const configuration_history: RegimeReport = buildConfigurationHistory(
    state.world_interventions,
    {
      start_tick: state.start_tick ?? 0,
      end_tick: state.end_tick,
      initial_fingerprint: state.initial_world_fingerprint,
    },
  );
  const analysis: RunAnalysis = {
    identity,
    lifecycle,
    agents,
    comparison,
    interactions,
    important_events,
    causal_chains,
    phases,
    overview,
    keyframes: [...state.keyframes],
    coverage,
    configuration_history,
    vision_forensics,
    analysis_log: '',
    generated_at_tick: state.end_tick ?? 0,
  };
  analysis.analysis_log = formatAnalysisLog(analysis);
  return analysis;
}

function buildIdentity(state: AnalysisState, mode: AnalysisMode): RunIdentity {
  const agents = Object.values(state.agents).sort((a, b) => a.agent_id.localeCompare(b.agent_id));
  const start = state.start_tick ?? 0;
  const end = state.end_tick ?? start;
  return {
    runtime: state.runtime,
    seed: state.seed,
    generation: state.generation,
    map_width: state.map_w,
    map_height: state.map_h,
    boundary: state.boundary,
    start_tick: start,
    end_tick: end,
    duration_ticks: Math.max(0, end - start),
    agent_count: Math.max(state.agent_count, agents.length || 1),
    agents: agents.map((a) => ({
      agent_id: a.agent_id,
      body_id: a.body_id,
      seed: a.seed,
    })),
    cognition_enabled: state.cognition_enabled == null ? 'NOT AVAILABLE' : state.cognition_enabled,
    experimental_overrides: state.experimental_overrides || {},
    active_mechanisms: state.active_mechanisms,
    status: state.status || 'UNKNOWN',
    analysis_mode: mode,
  };
}

/** One-shot convenience: ingest + build. */
export function analyzeObserverData(input: AnalysisInput): RunAnalysis {
  const state = createAnalysisState();
  ingestAnalysisInput(state, input);
  return buildRunAnalysis(state, input.mode || 'LIVE', {
    optical_ticks: input.optical_ticks,
    scientific_rows: input.scientific_rows,
    frame: input.frame,
  });
}
